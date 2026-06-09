from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from ..models import FastqUpload, AnalysisJob
from .serializers import FastqUploadSerializer, AnalysisJobSerializer
from ..tasks import analyze_single_file, parallel_fastq_analysis  # Düzeltildi


class FastqUploadViewSet(viewsets.ModelViewSet):
    serializer_class = FastqUploadSerializer
    permission_classes = [AllowAny]  # Geliştirme için, production'da IsAuthenticated kullanın

    def get_queryset(self):
        # Session bazlı filtreleme
        session_key = self.request.session.session_key
        if session_key:
            return FastqUpload.objects.filter(session_key=session_key)
        return FastqUpload.objects.none()

    @action(detail=True, methods=['post'])
    def reanalyze(self, request, pk=None):
        """Analizi yeniden başlat"""
        upload = self.get_object()
        import threading, uuid
        task_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=analyze_single_file, args=(str(upload.id),), daemon=True)
        thread.start()
        return Response({
            'task_id': task_id,
            'status': 'started',
            'message': 'Analiz başlatıldı'
        })

    @action(detail=False, methods=['post'])
    def batch_analyze(self, request):
        """Birden fazla dosyayı paralel analiz et"""
        file_ids = request.data.get('file_ids', [])

        if not file_ids:
            return Response(
                {'error': 'file_ids gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(file_ids) > 10:
            return Response(
                {'error': 'Maksimum 10 dosya analiz edilebilir'},
                status=status.HTTP_400_BAD_REQUEST
            )

        import threading, uuid
        task_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=parallel_fastq_analysis, args=(file_ids,), daemon=True)
        thread.start()
        return Response({
            'task_id': task_id,
            'status': 'started',
            'message': f'{len(file_ids)} dosya için analiz başlatıldı'
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Genel istatistikler"""
        queryset = self.get_queryset()
        stats = {
            'total_files': queryset.count(),
            'uploaded': queryset.filter(status='uploaded').count(),
            'completed': queryset.filter(status='done').count(),
            'failed': queryset.filter(status__in=['error', 'count_error']).count(),
            'total_reads': sum(f.total_reads or 0 for f in queryset)
        }
        return Response(stats)


class AnalysisJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AnalysisJob.objects.all()
    serializer_class = AnalysisJobSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """İş ilerlemesini getir"""
        job = self.get_object()
        return Response({
            'job_id': job.job_id,
            'status': job.status,
            'progress': job.progress,
            'reads_processed': job.reads_processed,
            'error_message': job.error_message
        })