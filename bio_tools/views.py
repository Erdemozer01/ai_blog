import os
import json
import uuid
import sys
import pathlib
from io import BytesIO
import logging

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views import View
from django.utils.decorators import method_decorator
from dash import html

# Werkzeug exception import for specific error handling
try:
    from werkzeug.exceptions import BadRequestKeyError
except ImportError:
    BadRequestKeyError = None

# Application imports
from .tasks import process_fastq_file
from .models import AnalysisJob
from blog.views import create_main_navbar
from dash_apps.sequence_analyzer import app as sequence_analyzer_app, create_sequence_analyzer_layout
from dash_apps.sequence_alignment import app as sequence_alignment_app, create_sequence_alignment_layout
from dash_apps.molecule_viewer import app as molecule_viewer_app, create_molecule_viewer_layout
from dash_apps.mutation_predictor import app as mutation_predictor_app, mutation_create_layout
from dash_apps.bacterial_designer import app as bacterial_designer_app, bacterial_create_layout
from dash_apps.pipeline_designer import app as pipeline_designer_app, create_pipeline_layout
from dash_apps.fastq_app import app as fastq_app

# --- Constants and Setup ---
logger = logging.getLogger(__name__)

DEFAULT_UPLOAD_DIR = os.path.join(getattr(settings, "MEDIA_ROOT", "media"), "fastq_uploads")
UPLOAD_ROOT = getattr(settings, "FASTQ_UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
os.makedirs(UPLOAD_ROOT, exist_ok=True)


# --- Helper Functions ---

def safe_join(base_dir: str, filename: str) -> str:
    """
    Güvenli dosya yolu birleştirme - Path traversal saldırılarını engeller
    pathlib kullanarak daha güvenli implementasyon
    """
    base_path = pathlib.Path(base_dir).resolve()

    # Filename'i temizle
    safe_filename = os.path.basename(filename)
    file_path = (base_path / safe_filename).resolve()

    # Relative_to kontrolü - path traversal'ı engelle
    try:
        file_path.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Path traversal detected: {filename}")

    return str(file_path)


def du_get_upload_path(root: str, upload_id: str) -> str:
    """
    dash-uploader yol yardımcısı
    """
    # Upload ID'yi de güvenli hale getir
    safe_upload_id = os.path.basename(upload_id)
    return os.path.join(root, safe_upload_id)


def validate_job_id(job_id: str) -> bool:
    """Job ID formatını doğrula (UUID formatı)"""
    try:
        uuid.UUID(job_id)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


# --- FASTQ DASH APP VIEW ---
@method_decorator(csrf_exempt, name='dispatch')
class FastqDashAppView(View):
    """
    Dash app proxy with proper stream handling
    """

    def dispatch(self, request, *args, **kwargs):
        """Request tracking"""
        request_id = str(uuid.uuid4())[:8]
        content_length = request.META.get('CONTENT_LENGTH', '0')
        logger.info(f"[{request_id}] {request.method} {request.path} - Size: {content_length} bytes")

        try:
            response = super().dispatch(request, *args, **kwargs)
            logger.info(f"[{request_id}] Response: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"[{request_id}] Error: {e}", exc_info=True)
            return HttpResponse("Internal Server Error", status=500)

    def get(self, request, *args, **kwargs):
        """Handle GET requests"""
        try:
            with fastq_app.server.test_request_context(
                    request.get_full_path(),
                    method='GET',
                    headers=dict(request.headers)
            ):
                flask_response = fastq_app.server.full_dispatch_request()

                django_response = HttpResponse(
                    content=flask_response.get_data(),
                    status=flask_response.status_code,
                    content_type=flask_response.content_type
                )

                for key, value in flask_response.headers:
                    if key.lower() not in ['content-type', 'content-length', 'date', 'server']:
                        django_response[key] = value

                return django_response

        except Exception as e:
            logger.error(f"GET error: {e}", exc_info=True)
            return HttpResponse("Internal Server Error", status=500)

    def post(self, request, *args, **kwargs):
        """
        Handle POST with seekable stream
        CRITICAL FIX: Reset stream position before WSGI call
        """
        environ = self._build_wsgi_environ(request)

        status_headers = {'status': None, 'headers': None}

        def start_response(status, headers, exc_info=None):
            if exc_info:
                try:
                    raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None
            elif status_headers['status'] is not None:
                raise AssertionError("start_response called twice")

            status_headers['status'] = status
            status_headers['headers'] = headers

        try:
            response_iter = fastq_app.server.wsgi_app(environ, start_response)
            response_body = b''.join(response_iter)

            if status_headers['status'] is None:
                raise RuntimeError("WSGI app did not call start_response")

            status_code = int(status_headers['status'].split(' ')[0])

            django_response = HttpResponse(
                content=response_body,
                status=status_code,
            )

            if status_headers['headers']:
                for key, value in status_headers['headers']:
                    if key.lower() not in ['content-length', 'date', 'server', 'connection']:
                        django_response[key] = value

            return django_response

        except Exception as e:
            logger.error(f"POST WSGI error: {e}", exc_info=True)

            if 'API/resumable' in request.path:
                return JsonResponse({
                    'error': f'Upload processing error: {type(e).__name__}',
                    'detail': str(e)
                }, status=500)

            return HttpResponse(
                f"Internal Server Error: {type(e).__name__}",
                status=500
            )

    def _build_wsgi_environ(self, request):
        """
        Build WSGI environment with seekable stream
        CRITICAL FIX: Create fresh BytesIO and seek to start
        """
        # Get content length
        content_length = request.META.get('CONTENT_LENGTH', '0')
        try:
            content_length = str(int(content_length))
        except (ValueError, TypeError):
            content_length = str(len(request.body))

        # Get full Content-Type with boundary
        content_type = request.content_type
        if content_type.startswith('multipart/'):
            full_content_type = request.META.get('CONTENT_TYPE', content_type)
        else:
            full_content_type = content_type

        # CRITICAL FIX: Create fresh, seekable stream
        body_stream = BytesIO(request.body)
        body_stream.seek(0)  # Ensure we're at the start

        # Build base environ
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': request.scheme,
            'wsgi.input': body_stream,  # Fresh, seekable stream
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': True,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'REQUEST_METHOD': request.method,
            'SCRIPT_NAME': '',
            'PATH_INFO': request.path_info,
            'QUERY_STRING': request.META.get('QUERY_STRING', ''),
            'CONTENT_TYPE': full_content_type,
            'CONTENT_LENGTH': content_length,
            'SERVER_NAME': request.META.get('SERVER_NAME', 'localhost'),
            'SERVER_PORT': request.META.get('SERVER_PORT', '8000'),
            'SERVER_PROTOCOL': request.META.get('SERVER_PROTOCOL', 'HTTP/1.1'),
            'REMOTE_ADDR': request.META.get('REMOTE_ADDR', '127.0.0.1'),
        }

        # Add HTTP headers
        for key, value in request.headers.items():
            key_upper = key.upper().replace('-', '_')
            env_key = f'HTTP_{key_upper}'

            if env_key not in ('HTTP_CONTENT_TYPE', 'HTTP_CONTENT_LENGTH'):
                environ[env_key] = value

        return environ


# --- OTHER DASH APP VIEWS ---

def sequence_analyzer_view(request):
    """Sekans Analiz Aracı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = create_sequence_analyzer_layout()
    sequence_analyzer_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/sequence_analyzer.html', {
        'meta_title': "Sekans Analiz Aracı - AI Blog"
    })


def sequence_alignment_view(request):
    """Sekans Hizalama Aracı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = create_sequence_alignment_layout()
    sequence_alignment_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/sequence_alignment.html', {
        'meta_title': "Sekans Hizalama Aracı - AI Blog"
    })


def molecule_viewer_view(request):
    """3D Molekül Görüntüleyici"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = create_molecule_viewer_layout()
    molecule_viewer_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/molecule_viewer.html', {
        'meta_title': "3D Molekül Görüntüleyici - AI Blog"
    })


def mutation_predictor_view(request):
    """Mutasyon Etki Tahmincisi"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = mutation_create_layout()
    mutation_predictor_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/mutation_predictor.html', {
        'meta_title': "Mutasyon Etki Tahmincisi - AI Blog"
    })


def bacterial_designer_view(request):
    """Sentetik Biyoloji Bakteri Tasarımcısı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = bacterial_create_layout()
    bacterial_designer_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/bacterial_designer.html', {
        'meta_title': "Bakteri Tasarımcısı - AI Blog"
    })


def pipline_designer_view(request):
    """Biyoinformatik Pipeline Tasarımcısı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    content = create_pipeline_layout()
    pipeline_designer_app.layout = html.Div([main_navbar, content])

    return render(request, 'bio_tools/pipline_designer.html', {
        'meta_title': "Pipeline Tasarımcısı - AI Blog"
    })


# --- API VIEWS FOR CELERY ---

@csrf_exempt
def start_analysis_view(request: HttpRequest):
    """
    FASTQ analiz işini başlatır (Celery task)
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Only POST method is allowed'},
            status=405
        )

    try:
        # Request body'yi parse et
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request: {e}")
            return JsonResponse(
                {'error': 'Invalid JSON in request body'},
                status=400
            )

        # Gerekli parametreleri al
        job_id = data.get('job_id')
        upload_id = data.get('upload_id')
        file_names = data.get('fileNames')
        upload_root_from_request = data.get('upload_root', UPLOAD_ROOT)

        # Parametre validasyonu
        if not job_id:
            return JsonResponse(
                {'error': 'Missing required parameter: job_id'},
                status=400
            )

        if not upload_id:
            return JsonResponse(
                {'error': 'Missing required parameter: upload_id'},
                status=400
            )

        if not file_names or not isinstance(file_names, list) or len(file_names) == 0:
            return JsonResponse(
                {'error': 'Missing or invalid parameter: fileNames'},
                status=400
            )

        # Güvenli dosya yolu oluştur
        try:
            folder = du_get_upload_path(upload_root_from_request, upload_id)
            file_path = safe_join(folder, file_names[0])
        except ValueError as e:
            logger.error(f"Invalid file path for job {job_id}: {e}")
            return JsonResponse(
                {'error': f'Invalid file path: {str(e)}'},
                status=400
            )

        # Dosya varlığını kontrol et
        if not os.path.exists(file_path):
            logger.warning(f"File not found for job {job_id}: {file_path}")
            return JsonResponse(
                {'error': f'File not found on server: {file_names[0]}'},
                status=404
            )

        # Dosya erişim izinlerini kontrol et
        if not os.access(file_path, os.R_OK):
            logger.error(f"Permission denied for job {job_id}: {file_path}")
            return JsonResponse(
                {'error': 'Permission denied: Cannot read file'},
                status=403
            )

        logger.info(f"Starting analysis job {job_id} for file: {file_path}")

        # Veritabanında işi oluştur veya güncelle
        try:
            job, created = AnalysisJob.objects.update_or_create(
                job_id=job_id,
                defaults={
                    'file_name': file_names[0],
                    'status': 'PENDING',
                    'progress': 0,
                    'reads_processed': 0,
                    'error_message': None
                }
            )
        except Exception as e:
            logger.error(f"Database error creating job {job_id}: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Database error: Could not create job'},
                status=500
            )

        # Celery görevini başlat
        try:
            process_fastq_file.delay(job_id=job_id, file_path=file_path)
        except Exception as e:
            logger.error(f"Celery error for job {job_id}: {e}", exc_info=True)

            # Job durumunu güncelle
            job.status = 'FAILED'
            job.error_message = f'Failed to start analysis task: {str(e)}'
            job.save()

            return JsonResponse(
                {'error': f'Failed to start analysis task: {str(e)}'},
                status=500
            )

        return JsonResponse({
            'status': 'Analysis job started successfully',
            'job_id': job.job_id,
            'created': created
        })

    except Exception as e:
        logger.error(f"Unexpected error in start_analysis_view: {e}", exc_info=True)
        return JsonResponse(
            {'error': f'Internal server error: {str(e)}'},
            status=500
        )


def get_job_status_view(request: HttpRequest, job_id: str):
    """
    İş durumunu ve sonuçlarını döndürür
    """
    try:
        # Job ID validasyonu
        if not job_id or len(job_id) > 100:
            return JsonResponse(
                {'error': 'Invalid job_id'},
                status=400
            )

        # Job'u veritabanından al
        try:
            job = get_object_or_404(AnalysisJob, job_id=job_id)
        except AnalysisJob.DoesNotExist:
            return JsonResponse(
                {'error': f'Job with ID {job_id} not found'},
                status=404
            )

        # JSON alanlarını güvenli şekilde parse et
        def safe_json_parse(json_str, default=None):
            if not json_str:
                return default
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse JSON for job {job_id}: {e}")
                return default

        # Response data hazırla
        data = {
            'job_id': job.job_id,
            'status': job.status,
            'progress': job.progress or 0,
            'reads_processed': job.reads_processed or 0,
            'error_message': job.error_message,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
            'results': {
                'quality_scores': safe_json_parse(
                    job.quality_scores_json,
                    default=None
                ),
                'gc_histogram': safe_json_parse(
                    job.gc_histogram_data_json,
                    default=None
                ),
                'base_composition': safe_json_parse(
                    job.base_composition_json,
                    default=None
                ),
                'overrepresented_sequences': safe_json_parse(
                    job.overrepresented_seqs_json,
                    default=None
                ),
            }
        }

        return JsonResponse(data)

    except Exception as e:
        logger.error(
            f"Unexpected error retrieving status for job {job_id}: {e}",
            exc_info=True
        )
        return JsonResponse(
            {'error': 'Internal server error'},
            status=500
        )


@csrf_exempt
def cancel_job_view(request: HttpRequest, job_id: str):
    """
    Çalışan bir işi iptal eder
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Only POST method is allowed'},
            status=405
        )

    try:
        # Job'u al
        job = get_object_or_404(AnalysisJob, job_id=job_id)

        # Sadece çalışan işler iptal edilebilir
        if job.status not in ['PENDING', 'RUNNING']:
            return JsonResponse({
                'error': f'Cannot cancel job with status: {job.status}',
                'status': job.status
            }, status=400)

        # Celery task'ı iptal et
        from celery.result import AsyncResult
        result = AsyncResult(job_id)
        result.revoke(terminate=True)

        # Job durumunu güncelle
        job.status = 'CANCELLED'
        job.error_message = 'Job cancelled by user'
        job.save()

        logger.info(f"Job {job_id} cancelled successfully")

        return JsonResponse({
            'status': 'Job cancelled successfully',
            'job_id': job_id
        })

    except AnalysisJob.DoesNotExist:
        return JsonResponse(
            {'error': f'Job with ID {job_id} not found'},
            status=404
        )
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        return JsonResponse(
            {'error': f'Failed to cancel job: {str(e)}'},
            status=500
        )