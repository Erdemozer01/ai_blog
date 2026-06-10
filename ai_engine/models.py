from django.db import models


class Provider(models.Model):
    """
    Yapay zeka sağlayıcısı (Google Gemini, OpenAI, Anthropic).
    Hangi modelin kullanılacağını burada tanımlarız; altındaki tüm
    API anahtarları bu modeli kullanır.
    """
    SERVICE_CHOICES = (
        ('Google Gemini', 'Google Gemini'),
        ('OpenAI', 'OpenAI'),
        ('Anthropic', 'Anthropic'),
    )
    service_name = models.CharField(max_length=100, choices=SERVICE_CHOICES,
                                    verbose_name="Sağlayıcı")
    model_name = models.CharField(max_length=100, verbose_name="Model Adı",
                                  help_text="Örn: gemini-2.5-flash, gpt-4o, claude-sonnet-4")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service_name} — {self.model_name}"

    @property
    def active_key_count(self):
        return self.api_keys.filter(is_active=True).count()

    class Meta:
        verbose_name = "Sağlayıcı / Model"
        verbose_name_plural = "Sağlayıcılar / Modeller"
        ordering = ['service_name', 'model_name']


class APIKey(models.Model):
    """
    Bir sağlayıcıya ait API anahtarı. Aynı sağlayıcı (model) altında
    birden fazla anahtar olabilir — havuz mantığıyla biri dolduğunda
    diğerine geçilir.
    """
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE,
                                 related_name='api_keys', verbose_name="Sağlayıcı")
    label = models.CharField(max_length=100, blank=True, verbose_name="Etiket",
                             help_text="İsteğe bağlı isim (örn: 'Ana hesap', 'Yedek 2')")
    key = models.CharField(max_length=255, verbose_name="API Anahtarı")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    usage_count = models.PositiveIntegerField(default=0, verbose_name="Kullanım Sayısı",
                                              help_text="Bu anahtarla kaç kez başarılı üretim yapıldığı")
    last_used = models.DateTimeField(null=True, blank=True, verbose_name="Son Kullanım")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = self.label or f"Anahtar #{self.id}"
        return f"{self.provider.service_name} — {name}"

    class Meta:
        verbose_name = "API Anahtarı"
        verbose_name_plural = "API Anahtarları"
        ordering = ['usage_count']  # en az kullanılan önce

    @classmethod
    def get_active_key(cls, service_name="Google Gemini"):
        """
        Belirtilen servisin aktif bir API anahtarını döndürür
        (en az kullanılan önce). Bulamazsa None döner.
        """
        return cls.objects.filter(
            provider__service_name=service_name,
            provider__is_active=True,
            is_active=True,
        ).select_related('provider').order_by('usage_count', 'id').first()