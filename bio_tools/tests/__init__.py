from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from ..models import FastqUpload, AnalysisJob
import os


class FastqUploadTestCase(TestCase):
    def setUp(self):
        self.session_key = 'test_session_123'

    def test_file_upload(self):
        """Dosya yükleme testi"""
        file_content = b"@read1\nACGT\n+\nIIII\n"
        uploaded_file = SimpleUploadedFile(
            "test.fastq", file_content, content_type="text/plain"
        )

        upload = FastqUpload.objects.create(
            session_key=self.session_key,
            file=uploaded_file
        )

        self.assertEqual(upload.status, 'uploaded')
        self.assertIsNotNone(upload.id)

    def test_analysis_job_creation(self):
        """Analiz işi oluşturma testi"""
        job = AnalysisJob.objects.create(
            job_id='test_job_123',
            file_name='test.fastq'
        )

        self.assertEqual(job.status, 'PENDING')
        self.assertEqual(job.progress, 0)

    def tearDown(self):
        # Test dosyalarını temizle
        FastqUpload.objects.all().delete()
        AnalysisJob.objects.all().delete()