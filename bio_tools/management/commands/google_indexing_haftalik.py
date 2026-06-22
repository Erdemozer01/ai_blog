# blog/management/commands/google_indexing_haftalik.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from blog.models import GeneratedArticle, SearchQuery
from blog.utils import notify_google_indexing_api

class Command(BaseCommand):
    help = 'Son 1 haftada eklenen makale ve arama sorgularını Google Indexing API ye gönderir.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Google Indexing API haftalık gönderim işlemi başlatılıyor..."))

        # Site domain adresin (HTTPS ile)
        site_url = "https://aiblog.pythonanywhere.com"
        
        # Tam 7 gün öncesinin tarihini alıyoruz
        bir_hafta_once = timezone.now() - timedelta(days=7)

        # ---------------------------------------------------------
        # 1. BÖLÜM: SON 1 HAFTADA YAPILAN YENİ ARAMA SORGULARI
        # ---------------------------------------------------------
        yeni_sorgular = SearchQuery.objects.filter(olusturulma_tarihi__gte=bir_hafta_once)
        sorgu_sayisi = yeni_sorgular.count()
        self.stdout.write(f"Bulunan yeni arama sorgusu: {sorgu_sayisi}")

        for sorgu in yeni_sorgular:
            try:
                # get_absolute_url() üzerinden linki oluştur ve domain ile birleştir
                tam_url = site_url + sorgu.get_absolute_url()
                notify_google_indexing_api(tam_url)
                self.stdout.write(f"Başarıyla gönderildi: {tam_url}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Arama sorgusu gönderim hatası (Sorgu: {sorgu.sorgu_kelimesi}): {e}"))


        # ---------------------------------------------------------
        # 2. BÖLÜM: SON 1 HAFTADA ÜRETİLEN YENİ MAKALELER
        # ---------------------------------------------------------
        yeni_makaleler = GeneratedArticle.objects.filter(status='tamamlandi', created_at__gte=bir_hafta_once)
        makale_sayisi = yeni_makaleler.count()
        self.stdout.write(f"Bulunan yeni makale: {makale_sayisi}")

        for makale in yeni_makaleler:
            try:
                # Makale URL'sini urls.py yapısına göre (article_id ve slug) oluştur
                makale_path = reverse('blog:article_detail', kwargs={'article_id': makale.id, 'slug': makale.slug})
                tam_url = site_url + makale_path
                notify_google_indexing_api(tam_url)
                self.stdout.write(f"Başarıyla gönderildi: {tam_url}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Makale gönderim hatası (ID: {makale.id}): {e}"))

        self.stdout.write(self.style.SUCCESS("Haftalık Google Indexing API gönderimi tamamlandı."))
