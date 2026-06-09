"""
Cache'i temizler.

Kullanım:
    python manage.py clear_cache
    python manage.py clear_cache --cache fastq_analysis
    python manage.py clear_cache --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import caches
from django.conf import settings


class Command(BaseCommand):
    help = 'Cache temizler'

    def add_arguments(self, parser):
        parser.add_argument('--cache', type=str, help='Belirli bir cache temizle')
        parser.add_argument('--all', action='store_true', help="Tüm cache'leri temizle")

    def handle(self, *args, **options):
        cache_name = options.get('cache')
        clear_all = options.get('all')

        if clear_all:
            self._clear_all_caches()
        elif cache_name:
            self._clear_single_cache(cache_name)
        else:
            self._clear_single_cache('default')

    def _clear_all_caches(self):
        self.stdout.write(self.style.WARNING("⚠️  TÜM CACHE'LER TEMİZLENİYOR..."))
        count = 0
        for cache_name in settings.CACHES.keys():
            try:
                caches[cache_name].clear()
                self.stdout.write(self.style.SUCCESS(f"  ✓ {cache_name} temizlendi"))
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {cache_name} hata: {str(e)}"))
        self.stdout.write(self.style.SUCCESS(f"\n✓ {count} cache temizlendi"))

    def _clear_single_cache(self, cache_name):
        try:
            caches[cache_name].clear()
            self.stdout.write(self.style.SUCCESS(f"✓ {cache_name} cache temizlendi"))
        except Exception as e:
            raise CommandError(f"Cache temizleme hatası: {str(e)}")