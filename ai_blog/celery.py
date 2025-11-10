import os
from celery import Celery

# Django'nun 'settings' modülünü Celery için varsayılan olarak ayarla.
# 'ai_blog.settings' adının kendi projenizle uyumlu olduğundan emin olun.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_blog.settings')

# Celery uygulama örneğini (instance) oluştur.
# 'ai_blog' adı, bu yapılandırma dosyasının bulunduğu Django projesinin adıyla eşleşmelidir.
app = Celery('ai_blog')

# Yapılandırmayı Django'nun settings dosyasından oku.
# namespace='CELERY' demek, settings.py dosyasındaki tüm Celery ayarlarının
# 'CELERY_' ön eki ile başlaması gerektiği anlamına gelir (örn: CELERY_BROKER_URL).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django app'leri içindeki tüm görev modüllerini (tasks.py dosyalarını)
# otomatik olarak bul ve yükle.
app.autodiscover_tasks()

app.conf.imports = ('bio_tools.tasks',)

# Make sure you're not setting parser explicitly
app.conf.update(
    broker_connection_retry_on_startup=True,
    # Remove or don't set: broker_transport_options with parser_class
)