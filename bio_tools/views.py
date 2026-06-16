import os
import json
import uuid
import sys
import pathlib
from io import BytesIO
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpRequest, HttpResponse
from billing.decorators import require_credits
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
from dash_apps.primer_design import app as primer_design_app, create_primer_layout
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
@login_required
def fastq_analyzer_view(request):
    """FASTQ Analiz Aracı (DjangoDash — diğer araçlarla aynı yapı)."""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.fastq_app import build_fastq_content
    from dash_apps.i18n_helper import get_lang
    content = build_fastq_content(get_lang(request))
    _layout = html.Div([main_navbar, content])
    fastq_app.layout = lambda: _layout

    return render(request, 'bio_tools/fastq_analyzer.html', {
        'meta_title': "FASTQ Analiz Aracı - AI Blog"
    })


# --- OTHER DASH APP VIEWS ---

@login_required
def sequence_analyzer_view(request):
    """Sekans Analiz Aracı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    lang = get_lang(request)
    content = create_sequence_analyzer_layout(lang)
    _layout = html.Div([main_navbar, content])
    sequence_analyzer_app.layout = lambda: _layout

    return render(request, 'bio_tools/sequence_analyzer.html', {
        'meta_title': "Sekans Analiz Aracı - AI Blog"
    })


@login_required
def sequence_alignment_view(request):
    """Sekans Hizalama Aracı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    content = create_sequence_alignment_layout(get_lang(request))
    _layout = html.Div([main_navbar, content])
    sequence_alignment_app.layout = lambda: _layout

    return render(request, 'bio_tools/sequence_alignment.html', {
        'meta_title': "Sekans Hizalama Aracı - AI Blog"
    })


@login_required
def molecule_viewer_view(request):
    """3D Molekül Görüntüleyici"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    content = create_molecule_viewer_layout(get_lang(request))
    _layout = html.Div([main_navbar, content])
    molecule_viewer_app.layout = lambda: _layout

    return render(request, 'bio_tools/molecule_viewer.html', {
        'meta_title': "3D Molekül Görüntüleyici - AI Blog"
    })


@login_required
def mutation_predictor_view(request):
    """Mutasyon Etki Tahmincisi"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    content = mutation_create_layout(get_lang(request))
    _layout = html.Div([main_navbar, content])
    mutation_predictor_app.layout = lambda: _layout

    return render(request, 'bio_tools/mutation_predictor.html', {
        'meta_title': "Mutasyon Etki Tahmincisi - AI Blog"
    })


@login_required
def bacterial_designer_view(request):
    """Sentetik Biyoloji Bakteri Tasarımcısı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    content = bacterial_create_layout(get_lang(request))
    _layout = html.Div([main_navbar, content])
    bacterial_designer_app.layout = lambda: _layout

    return render(request, 'bio_tools/bacterial_designer.html', {
        'meta_title': "Bakteri Tasarımcısı - AI Blog"
    })


@login_required
def pipline_designer_view(request):
    """Biyoinformatik Pipeline Tasarımcısı"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    content = create_pipeline_layout(get_lang(request))
    _layout = html.Div([main_navbar, content])
    pipeline_designer_app.layout = lambda: _layout

    return render(request, 'bio_tools/pipline_designer.html', {
        'meta_title': "Pipeline Tasarımcısı - AI Blog"
    })


@login_required
def primer_design_view(request):
    """Primer Tasarım Aracı (Primer3)"""
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")

    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    lang = get_lang(request)
    content = create_primer_layout(lang)
    _layout = html.Div([main_navbar, content])
    primer_design_app.layout = lambda: _layout

    return render(request, 'bio_tools/primer_design.html', {
        'meta_title': "Primer Tasarım Aracı - AI Blog"
    })


# --- FASTQ ANALİZ API VIEWS ---

@csrf_exempt
def start_analysis_view(request: HttpRequest):
    """
    FASTQ analiz işini başlatır (arka plan thread)
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

        # Dosya boyutu limiti kontrolü (sunucu tarafı)
        max_size_mb = getattr(settings, 'FASTQ_MAX_FILE_SIZE_MB', 100)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            logger.warning(f"File too large for job {job_id}: {file_size_mb:.1f} MB")
            return JsonResponse(
                {'error': f'Dosya çok büyük: {file_size_mb:.1f} MB. '
                          f'İzin verilen maksimum: {max_size_mb} MB.'},
                status=413
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

        # Analizi arka plan thread'inde başlat (Celery yerine)
        try:
            import threading
            from bio_tools.tasks import process_fastq_file
            thread = threading.Thread(
                target=process_fastq_file,
                kwargs={'job_id': job_id, 'file_path': file_path},
                daemon=True,
            )
            thread.start()
        except Exception as e:
            logger.error(f"Thread error for job {job_id}: {e}", exc_info=True)
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

        # Celery kaldırıldı — thread'i zorla durduramayız,
        # job durumunu CANCELLED yap. Task bir sonraki progress
        # güncellemesinde bu durumu kontrol edip sonlanabilir.

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

# ============================================================
# YENİ ARAÇLAR — Makale Entegrasyonu
# ============================================================

from dash_apps.federated_learning import app as federated_app
from dash_apps.pharmacogenomics import app as pgx_app
from dash_apps.variant_prioritization import app as variant_app

from dash_apps.federated_learning import create_federated_layout
from dash_apps.pharmacogenomics import create_pharmacogenomics_layout
from dash_apps.variant_prioritization import create_variant_layout


@login_required
def federated_view(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")
    main_navbar = create_main_navbar(request)
    _layout = html.Div([main_navbar, create_federated_layout()])
    federated_app.layout = lambda: _layout
    return render(request, 'bio_tools/federated_learning.html', {'meta_title': "Federated Learning - AI Blog"})


@login_required
def pharmacogenomics_view(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")
    main_navbar = create_main_navbar(request)
    _layout = html.Div([main_navbar, create_pharmacogenomics_layout()])
    pgx_app.layout = lambda: _layout
    return render(request, 'bio_tools/pharmacogenomics.html', {'meta_title': "Farmakogenomik Analiz - AI Blog"})


@login_required
def variant_view(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Lütfen giriş yapınız.')
        return redirect("admin:login")
    main_navbar = create_main_navbar(request)
    _layout = html.Div([main_navbar, create_variant_layout()])
    variant_app.layout = lambda: _layout
    return render(request, 'bio_tools/variant_prioritization.html', {'meta_title': "Varyant Önceliklendirme - AI Blog"})