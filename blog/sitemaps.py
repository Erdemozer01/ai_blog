# blog/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from blog.models import GeneratedArticle


class ArticleSitemap(Sitemap):
    changefreq = "hourly"   # Makalelerin ne sıklıkla değiştiği
    priority = 0.9          # Sitedeki diğer sayfalara göre önceliği

    def items(self):
        # Site haritasına eklenecek tüm tamamlanmış makaleler
        return GeneratedArticle.objects.filter(status='tamamlandi')

    def lastmod(self, obj):
        # Her makalenin son güncellenme tarihini döndür
        return obj.created_at


class StaticViewSitemap(Sitemap):
    """Statik/önemli sayfalar (anasayfa, iletişim)."""
    changefreq = "hourly"
    priority = 1.0

    def items(self):
        return ['blog:anasayfa', 'blog:blog_list', 'blog:contact']

    def location(self, item):
        return reverse(item)


class BioToolsSitemap(Sitemap):
    """13+ biyoinformatik aracının giriş sayfaları — aramalar için değerli landing page'ler."""
    changefreq = "hourly"
    priority = 0.8

    def items(self):
        return [
            'bio_tools:sequence_analyzer',
            'bio_tools:phylogenetic_tree',
            'bio_tools:sequence_alignment',
            'bio_tools:molecule_viewer',
            'bio_tools:mutation_predictor',
            'bio_tools:bacterial_designer',
            'bio_tools:pipline_designer_view',
            'bio_tools:primer_design',
            'bio_tools:restriction_analysis',
            'bio_tools:plasmid_map',
            'bio_tools:fastq_analyzer',
            'bio_tools:federated_learning',
            'bio_tools:pharmacogenomics',
            'bio_tools:variant_prioritization',
            'bio_tools:crispr_designer',
        ]

    def location(self, item):
        return reverse(item)