import logging
import os
import uuid

from django.db import models
from django.utils import timezone


class AnalysisJob(models.Model):
    # Bu ID, Dash'in upload_id'si ile aynı olacak ve iş takibi için kullanılacak
    job_id = models.CharField(max_length=100, unique=True, db_index=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)

    # İşin durumunu takip etmek için: pending, running, done, error
    STATUS_CHOICES = [
        ('PENDING', 'Beklemede'),
        ('RUNNING', 'Çalışıyor'),
        ('DONE', 'Tamamlandı'),
        ('ERROR', 'Hata'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    progress = models.IntegerField(default=0)
    reads_processed = models.BigIntegerField(default=0)
    total_duration = models.FloatField(default=0.0)  # İşin toplam süresi (saniye)
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Ham verileri JSON olarak saklayacağız
    # Not: Büyük veriler için PostgreSQL'in JSONB alanı daha performanslıdır.
    # SQLite ile başlangıç için JSONField yeterlidir.
    quality_scores_json = models.JSONField(null=True, blank=True)
    gc_histogram_data_json = models.JSONField(null=True, blank=True)
    base_composition_json = models.JSONField(null=True, blank=True)
    overrepresented_seqs_json = models.JSONField(null=True, blank=True)

    def set_done(self, duration):
        self.status = 'DONE'
        self.progress = 100
        self.total_duration = duration
        self.completed_at = timezone.now()
        self.save()

    def set_error(self, message, duration):
        self.status = 'ERROR'
        self.error_message = message
        self.total_duration = duration
        self.completed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.file_name or 'N/A'} ({self.job_id}) - {self.status}"


def fastq_file_upload_path(instance, filename):
    """
    Dosyayı MEDIA_ROOT/fastq_uploads/<instance.session_key>/<filename>
    yoluna kaydedecek yolu oluşturur.

    'instance.session_key'nin dolu gelmesi için 'view' tarafında
    nesneye atanmış olması gerekir.
    """

    # <--- DEĞİŞİKLİK YOK: 'session_key' kullanmaya devam ---
    if not instance.session_key:
        # Bu durumun 'view' tarafında engellenmesi gerekir
        # ama bir güvenlik önlemi olarak buraya da ekleyelim.
        raise ValueError("Dosya kaydı için Session Key (oturum anahtarı) zorunludur.")

    return f'fastq_uploads/{instance.session_key}/{filename}'
    # <--- DEĞİŞİKLİK BİTTİ ---


class FastqUpload(models.Model):
    """
    Yüklenen her FASTQ dosyasının kaydını tutan model.
    """

    # Dosyanın BİRİNCİL (PK) anahtarı olarak UUID'yi tutuyoruz.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # <--- YENİ: Oturum (Session) Anahtarı Alanı ---
    # Bu, dosyayı yükleyen kullanıcının oturumunu (session) saklar.
    # Güvenlik kontrolü bununla yapılacak.
    session_key = models.CharField(max_length=40, db_index=True, null=True, blank=True)
    # <--- YENİ BİTTİ ---

    # Dosya, fastq_file_upload_path fonksiyonunun belirlediği
    # (artık session_key'e bağlı) yola kaydedilecek.
    file = models.FileField(upload_to=fastq_file_upload_path, max_length=500)

    # <--- YENİ ALAN: Mutlak Dosya Yolunu Sakla ---
    # Dash uygulamasının settings.MEDIA_ROOT'a güvenmemesi için
    # dosyanın mutlak yolunu (absolute path) burada saklayacağız.
    absolute_file_path = models.CharField(max_length=1024, blank=True, null=True)
    # <--- YENİ ALAN BİTTİ ---

    STATUS_CHOICES = [
        ('uploaded', 'Yüklendi'),
        ('counting', 'Sayılıyor'),
        ('counted', 'Sayım Bitti'),
        ('running', 'Analiz Ediliyor'),
        ('done', 'Tamamlandı'),
        ('count_error', 'Sayım Hatası'),
        ('error', 'Analiz Hatası'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')

    total_reads = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return os.path.basename(self.file.name) if self.file else str(self.id)

    def get_absolute_path(self):
        """
        Dosyanın C:\... gibi tam (mutlak) sistem yolunu döndürür.

        DEĞİŞİKLİK: Artık self.file.path'e GÜVENMİYORUZ, çünkü bu, Dash'in
        settings'ine bağlı olarak yanlış yolu oluşturabilir.
        Bunun yerine, view tarafında kaydedilen 'absolute_file_path' alanını döndürüyoruz.
        """
        return self.absolute_file_path

    def delete(self, *args, **kwargs):
        """
        Model silinirken ilişkili dosyayı da diskten sil.
        """
        # Önce dosya yolunu al (absolute_file_path veya self.file.path)
        file_path = self.absolute_file_path
        if not file_path and self.file:
            try:
                file_path = self.file.path
            except Exception:
                file_path = None

        # Veritabanı kaydını sil
        super().delete(*args, **kwargs)

        # Dosyayı diskten sil
        if file_path:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.error(f"Dosya diskten silinemedi (ID: {self.id}, Yol: {file_path}): {e}")