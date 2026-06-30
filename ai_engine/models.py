from django.db import models


class Provider(models.Model):
    """
    Yapay zeka sağlayıcısı (Google Gemini, OpenAI, Anthropic).
    Bir sağlayıcının birden çok modeli ve birden çok API anahtarı olabilir.
    API anahtarları model'den bağımsızdır (bir Google anahtarı tüm Gemini
    modellerini kullanabilir).
    """
    SERVICE_CHOICES = (
        ('Google Gemini', 'Google Gemini'),
        ('OpenAI', 'OpenAI'),
        ('Anthropic', 'Anthropic'),
    )
    service_name = models.CharField(max_length=100, choices=SERVICE_CHOICES,
                                    unique=True, verbose_name="Sağlayıcı")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.service_name

    @property
    def active_key_count(self):
        return self.api_keys.filter(is_active=True).count()

    @property
    def active_model_count(self):
        return self.ai_models.filter(is_active=True).count()

    def get_active_key(self):
        """Bu sağlayıcının en az kullanılan aktif anahtarını döndürür."""
        return self.api_keys.filter(is_active=True).order_by('usage_count', 'id').first()

    class Meta:
        verbose_name = "Sağlayıcı"
        verbose_name_plural = "Sağlayıcılar"
        ordering = ['service_name']


class AIModel(models.Model):
    """
    Bir sağlayıcıya ait yapay zeka modeli (örn. gemini-3.5-flash).
    Aynı sağlayıcı altında birden fazla model tanımlanabilir.
    """
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE,
                                 related_name='ai_models', verbose_name="Sağlayıcı")
    model_name = models.CharField(max_length=100, verbose_name="Model Adı",
                                  help_text="Örn: gemini-3.5-flash, gpt-4o, claude-sonnet-4")
    label = models.CharField(max_length=100, blank=True, verbose_name="Görünen Ad",
                             help_text="İsteğe bağlı (örn: 'Gemini 2.5 Flash')")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider.service_name} — {self.model_name}"

    class Meta:
        verbose_name = "Model"
        verbose_name_plural = "Modeller"
        unique_together = ('provider', 'model_name')
        ordering = ['provider__service_name', 'model_name']


class APIKey(models.Model):
    """
    Bir sağlayıcıya ait API anahtarı (havuz). Model'den bağımsızdır.
    Aynı sağlayıcı altında birden fazla anahtar olabilir — havuz mantığıyla
    biri dolduğunda (429/kota) diğerine geçilir.
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
