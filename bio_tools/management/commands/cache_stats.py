"""
Cache istatistiklerini gösterir.

Kullanım:
    python manage.py cache_stats
"""
from django.core.management.base import BaseCommand
from django.core.cache import caches
from django.conf import settings


class Command(BaseCommand):
    help = 'Yapılandırılmış cache backendlerinin durumunu gösterir'

    def add_arguments(self, parser):
        parser.add_argument('--cache', type=str, help='Belirli bir cache adı')

    def handle(self, *args, **options):
        cache_name = options.get('cache')

        if cache_name:
            self._show_cache_stats(cache_name)
        else:
            for name in settings.CACHES.keys():
                self._show_cache_stats(name)
                self.stdout.write('')

    def _show_cache_stats(self, cache_name):
        try:
            cache_obj = caches[cache_name]
            cache_config = settings.CACHES[cache_name]
            backend = cache_config['BACKEND']

            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 50}"))
            self.stdout.write(self.style.SUCCESS(f"  {cache_name.upper()}"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 50}"))
            self.stdout.write(f"  Backend: {backend.split('.')[-1]}")
            self.stdout.write(f"  Location: {cache_config.get('LOCATION', 'N/A')}")
            self.stdout.write(f"  Timeout: {cache_config.get('TIMEOUT', 'N/A')}s")

            # Okuma/yazma testi
            test_key = "cache_stats_test_key"
            cache_obj.set(test_key, "ok", 10)
            if cache_obj.get(test_key) == "ok":
                self.stdout.write(self.style.SUCCESS("  ✓ Okuma/Yazma çalışıyor"))
                cache_obj.delete(test_key)
            else:
                self.stdout.write(self.style.WARNING("  ⚠️ Okuma/Yazma başarısız"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Hata: {str(e)}"))