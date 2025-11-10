"""
Cache istatistiklerini gösterir

Kullanım:
    python manage.py cache_stats
"""
from django.core.management.base import BaseCommand
from django.core.cache import caches
from django.conf import settings


class Command(BaseCommand):
    help = 'Redis cache istatistiklerini gösterir'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cache',
            type=str,
            help='Belirli bir cache adı',
        )

    def handle(self, *args, **options):
        cache_name = options.get('cache')

        # Redis durumunu göster
        redis_status = getattr(settings, 'REDIS_AVAILABLE', False)
        if redis_status:
            self.stdout.write(self.style.SUCCESS("✓ Redis aktif\n"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Redis yok - LocMem cache kullanılıyor\n"))

        if cache_name:
            self._show_cache_stats(cache_name)
        else:
            for name in settings.CACHES.keys():
                self._show_cache_stats(name)
                self.stdout.write('')

    def _show_cache_stats(self, cache_name):
        """Cache istatistiklerini göster"""
        try:
            cache_obj = caches[cache_name]
            cache_config = settings.CACHES[cache_name]
            backend = cache_config['BACKEND']

            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 50}"))
            self.stdout.write(self.style.SUCCESS(f"  {cache_name.upper()}"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 50}"))
            self.stdout.write(f"  Backend: {backend.split('.')[-1]}")
            self.stdout.write(f"  Location: {cache_config.get('LOCATION', 'N/A')}")

            # Redis ise detaylı stats
            if 'RedisCache' in backend:
                self._show_redis_stats_fixed(cache_obj, cache_name, cache_config)

            # LocMem ise basit stats
            elif 'LocMemCache' in backend:
                self._show_locmem_stats(cache_config)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Hata: {str(e)}"))

    def _show_redis_stats_fixed(self, cache_obj, cache_name, cache_config):
        """Redis cache istatistikleri - DÜZELTİLMİŞ"""
        try:
            # YENİ YÖNTEM: django-redis'in client metodunu kullan
            from django_redis import get_redis_connection

            # Redis bağlantısını al
            r = get_redis_connection(cache_name)

            # Key sayısı
            key_count = r.dbsize()
            self.stdout.write(f"  Toplam Key: {key_count}")

            # Stats
            info = r.info('stats')
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)

            self.stdout.write(f"  Cache Hit: {hits:,}")
            self.stdout.write(f"  Cache Miss: {misses:,}")

            # Hit ratio
            total = hits + misses
            if total > 0:
                hit_ratio = (hits / total) * 100
                color = self.style.SUCCESS if hit_ratio > 50 else self.style.WARNING
                self.stdout.write(color(f"  Hit Oranı: {hit_ratio:.2f}%"))

            # Memory
            memory_info = r.info('memory')
            used_memory = memory_info.get('used_memory_human', 'N/A')
            peak_memory = memory_info.get('used_memory_peak_human', 'N/A')
            self.stdout.write(f"  Kullanılan Bellek: {used_memory}")
            self.stdout.write(f"  Peak Bellek: {peak_memory}")

            # Örnek key'ler
            prefix = cache_config.get('KEY_PREFIX', '')
            pattern = f"{prefix}:*" if prefix else "*"
            keys = list(r.scan_iter(match=pattern, count=5))[:5]

            if keys:
                self.stdout.write("\n  Örnek Key'ler:")
                for key in keys:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    ttl = r.ttl(key)
                    if ttl == -1:
                        ttl_str = "sonsuz"
                    elif ttl == -2:
                        ttl_str = "yok"
                    else:
                        ttl_str = f"{ttl}s"
                    self.stdout.write(f"    - {key_str} (TTL: {ttl_str})")

            # Test yapabilirlik
            self.stdout.write("\n  Test:")
            test_key = f"{prefix}:test_key"
            r.set(test_key, "test_value", ex=10)
            test_val = r.get(test_key)
            if test_val:
                self.stdout.write(self.style.SUCCESS(f"    ✓ Okuma/Yazma çalışıyor"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Redis hatası: {str(e)}"))
            import traceback
            self.stdout.write(f"  Detay: {traceback.format_exc()}")

    def _show_locmem_stats(self, cache_config):
        """LocMem cache istatistikleri"""
        max_entries = cache_config.get('OPTIONS', {}).get('MAX_ENTRIES', 'N/A')
        timeout = cache_config.get('TIMEOUT', 'N/A')
        self.stdout.write(f"  Max Entries: {max_entries}")
        self.stdout.write(f"  Timeout: {timeout}s")
        self.stdout.write(self.style.WARNING("  ⚠️ Detaylı stats için Redis gerekli"))