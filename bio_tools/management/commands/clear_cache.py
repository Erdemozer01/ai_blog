"""
Cache'i temizler

Kullanım:
    python manage.py clear_cache
    python manage.py clear_cache --cache fastq_analysis
    python manage.py clear_cache --pattern "fastq:*"
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache, caches
from django.conf import settings


class Command(BaseCommand):
    help = 'Cache temizler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cache',
            type=str,
            help='Belirli bir cache temizle',
        )
        parser.add_argument(
            '--pattern',
            type=str,
            help='Pattern ile key sil (örn: "fastq:*")',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Tüm cache\'leri temizle',
        )

    def handle(self, *args, **options):
        cache_name = options.get('cache')
        pattern = options.get('pattern')
        clear_all = options.get('all')

        if clear_all:
            self._clear_all_caches()
        elif pattern:
            self._clear_by_pattern(cache_name or 'default', pattern)
        elif cache_name:
            self._clear_single_cache(cache_name)
        else:
            self._clear_single_cache('default')

    def _clear_all_caches(self):
        """Tüm cache'leri temizle"""
        self.stdout.write(
            self.style.WARNING("⚠️  TÜM CACHE'LER TEMİZLENİYOR...")
        )

        count = 0
        for cache_name in settings.CACHES.keys():
            try:
                caches[cache_name].clear()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ {cache_name} temizlendi")
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {cache_name} hata: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\n✓ {count} cache temizlendi")
        )

    def _clear_single_cache(self, cache_name):
        """Tek bir cache'i temizle"""
        try:
            cache_obj = caches[cache_name]
            cache_config = settings.CACHES[cache_name]

            # Key sayısını al (Redis ise)
            key_count = 0
            if 'RedisCache' in cache_config['BACKEND']:
                try:
                    from django_redis import get_redis_connection
                    r = get_redis_connection(cache_name)
                    key_count = r.dbsize()
                except:
                    pass

            # Temizle
            cache_obj.clear()

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {cache_name} cache temizlendi ({key_count} key silindi)"
                )
            )

        except Exception as e:
            raise CommandError(f"Cache temizleme hatası: {str(e)}")

    def _clear_by_pattern(self, cache_name, pattern):
        """Pattern ile key'leri sil - DÜZELTİLMİŞ"""
        try:
            cache_config = settings.CACHES[cache_name]

            if 'RedisCache' not in cache_config['BACKEND']:
                raise CommandError("Bu cache Redis değil, pattern desteklemiyor")

            from django_redis import get_redis_connection
            r = get_redis_connection(cache_name)

            # Pattern'e uyan key'leri bul
            prefix = cache_config.get('KEY_PREFIX', '')
            full_pattern = f"{prefix}:{pattern}" if prefix else pattern

            keys = list(r.scan_iter(match=full_pattern))

            if not keys:
                self.stdout.write(
                    self.style.WARNING(f"Pattern '{pattern}' ile eşleşen key yok")
                )
                return

            # Key'leri sil
            deleted = r.delete(*keys)

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {deleted} key silindi (pattern: {pattern})"
                )
            )

        except Exception as e:
            raise CommandError(f"Pattern silme hatası: {str(e)}")