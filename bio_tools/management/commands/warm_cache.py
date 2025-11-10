"""
Cache'i ön-ısıtır (popüler verileri önceden yükler)

Kullanım:
    python manage.py warm_cache
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from bio_tools.models import FastqUpload
from django.db.models import Count


class Command(BaseCommand):
    help = 'Popüler verileri cache\'e yükler'

    def handle(self, *args, **options):
        self.stdout.write("🔥 Cache ısıtılıyor...")

        # Örnek: Son 100 dosyanın istatistiklerini cache'le
        recent_files = FastqUpload.objects.all()[:100]

        for file_obj in recent_files:
            cache_key = f'file_stats_{file_obj.id}'
            stats = {
                'total_reads': file_obj.total_reads,
                'status': file_obj.status,
                'created_at': file_obj.created_at.isoformat(),
            }
            cache.set(cache_key, stats, timeout=3600)

        self.stdout.write(
            self.style.SUCCESS(f"✓ {len(recent_files)} dosya cache'lendi")
        )