from django.db import models
from django.contrib.auth.models import User


class APIKey(models.Model):
    SERVICE_CHOICES = (('Google Gemini', 'Google Gemini'),)
    service_name = models.CharField(max_length=100, choices=SERVICE_CHOICES, unique=True, verbose_name="Servis Adı")
    key = models.CharField(max_length=255, verbose_name="API Anahtarı")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.service_name

    class Meta: verbose_name = "API Anahtarı"; verbose_name_plural = "API Anahtarları"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Kategori Adı")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name

    class Meta: verbose_name = "Kategori"; verbose_name_plural = "Kategoriler"; ordering = ['name']


class GeneratedArticle(models.Model):
    STATUS_CHOICES = (('beklemede', 'Beklemede'), ('tamamlandi', 'Tamamlandı'), ('hata', 'Hata'))
    user_request = models.TextField(verbose_name="Kullanıcı İsteği")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='beklemede', verbose_name="Durum")
    title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Üretilen Başlık")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kategori")
    keywords = models.CharField(max_length=255, blank=True, null=True, verbose_name="Anahtar Kelimeler")
    english_abstract = models.TextField(blank=True, null=True, verbose_name="İngilizce Özet (Abstract)")
    turkish_abstract = models.TextField(blank=True, null=True, verbose_name="Türkçe Özet")
    full_content = models.TextField(blank=True, null=True, verbose_name="Üretilen Tam İçerik")
    bibliography = models.TextField(blank=True, null=True, verbose_name="Üretilen Kaynakça")

    structured_data = models.JSONField(blank=True, null=True, verbose_name="Grafik/Tablo Verileri")

    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Sahibi")
    view_count = models.PositiveIntegerField(default=0, verbose_name="Okunma Sayısı")

    created_at = models.DateTimeField(auto_now_add=True)

    likes = models.PositiveIntegerField(default=0, verbose_name="Faydalı Oy Sayısı")
    dislikes = models.PositiveIntegerField(default=0, verbose_name="Faydasız Oy Sayısı")

    def __str__(self): return self.title or f"'{self.user_request[:20]}...' için istek"

    class Meta: ordering = ['-created_at']; verbose_name = "AI Makalesi"; verbose_name_plural = "AI Makaleleri"


class ContactMessage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Gönderenin Adı")
    email = models.EmailField(verbose_name="Gönderenin E-postası")
    subject = models.CharField(max_length=200, verbose_name="Konu")
    message = models.TextField(verbose_name="Mesaj")
    is_read = models.BooleanField(default=False, verbose_name="Okundu olarak işaretle")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Gönderilme Tarihi")

    def __str__(self):
        return f"'{self.subject}' - {self.name}"

    class Meta:
        verbose_name = "İletişim Mesajı"
        verbose_name_plural = "İletişim Mesajları"
        ordering = ['-created_at']


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Kullanıcı")
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True,
                                        verbose_name="Profil Resmi")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Ad")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Soyad")
    title = models.CharField(max_length=100, verbose_name="Ünvan")
    summary = models.TextField(verbose_name="Özet")
    email = models.EmailField(verbose_name="E-posta")
    linkedin_url = models.URLField(blank=True, null=True, verbose_name="LinkedIn URL")
    github_url = models.URLField(blank=True, null=True, verbose_name="GitHub URL")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profiller"


class WorkExperience(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="experience")
    job_title = models.CharField(max_length=100, verbose_name="İş Ünvanı")
    company = models.CharField(max_length=100, verbose_name="Şirket")
    start_date = models.DateField(verbose_name="Başlangıç Tarihi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Bitiş Tarihi")
    description = models.TextField(verbose_name="Açıklama")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıralama")

    def __str__(self):
        return f"{self.job_title} @ {self.company}"

    class Meta:
        ordering = ['-start_date']
        verbose_name = "İş Deneyimi"
        verbose_name_plural = "İş Deneyimleri"


class Education(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="education")
    degree = models.CharField(max_length=100, verbose_name="Bölüm/Derece")
    institution = models.CharField(max_length=100, verbose_name="Okul/Kurum")
    graduation_year = models.PositiveIntegerField(verbose_name="Mezuniyet Yılı")

    def __str__(self):
        return f"{self.degree} - {self.institution}"

    class Meta:
        ordering = ['-graduation_year']
        verbose_name = "Eğitim"
        verbose_name_plural = "Eğitim Bilgileri"


class Skill(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=50, verbose_name="Yetenek Adı")
    level = models.PositiveIntegerField(default=80, verbose_name="Seviye (1-100)")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-level']
        verbose_name = "Yetenek"
        verbose_name_plural = "Yetenekler"
