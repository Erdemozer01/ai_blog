# blog/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from blog.models import GeneratedArticle

class ArticleSitemap(Sitemap):
    changefreq = "weekly"  # Makalelerin ne sıklıkla değiştiği
    priority = 0.9         # Sitedeki diğer sayfalara göre önceliği

    def items(self):
        # Site haritasına eklenecek tüm nesneleri döndür
        return GeneratedArticle.objects.filter(status='tamamlandi')

    def lastmod(self, obj):
        # Her makalenin son güncellenme tarihini döndür
        return obj.created_at