"""
Django settings for ai_blog project.

Canlı (Production) ve Geliştirme (Development) ortamları için ayrılmış ayarlar.
"""
import locale
import os
import platform  # Bu hala veritabanı ayrımı için kullanılabilir, ancak ENV daha iyidir
from pathlib import Path
from dotenv import load_dotenv
import logging
import redis  # Geliştirme ortamında Redis'i test etmek için

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# .env dosyasını yükle (Geliştirme ortamı için)
dotenv_path = BASE_DIR / '.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# Log klasörünü oluştur
LOG_DIR = BASE_DIR / 'logs'
os.makedirs(LOG_DIR, exist_ok=True)

# Logger'ı erken başlat
logger = logging.getLogger(__name__)

# ==============================================================================
# ORTAM AYARI (ENVIRONMENT)
# Canlı ortam (PythonAnywhere) için "Web" sekmesinde
# DJANGO_ENV = 'production' değişkenini ekleyin.
# Yerel makinenizde (.env) DJANGO_ENV = 'development' ekleyin veya boş bırakın.
# ==============================================================================
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development')

# Türkçe locale ayarları
try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except locale.Error:
    # ... (locale hata ayıklaması sizinkisiyle aynı) ...
    print("Uyarı: Türkçe locale ayarlanamadı.")

# ==============================================================================
# PAYLAŞILAN AYARLAR (Her iki ortam için de geçerli)
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'blog.apps.BlogConfig',
    'bio_tools.apps.BioToolsConfig',

    'django_plotly_dash',
    'django_bootstrap5',
    'dash_uploader',
    'dash_apps',
    'channels',
    'channels_redis',
    'autoslug',
    'rest_framework',
    'django_redis',  # Redis cache ve session'lar için gerekli
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Whitenoise (Prod & Dev)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_plotly_dash.middleware.BaseMiddleware',
    'django_plotly_dash.middleware.ExternalRedirectionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'bio_tools.middleware.performance.PerformanceMonitoringMiddleware',
]

ROOT_URLCONF = 'ai_blog.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ai_blog.wsgi.application'
ASGI_APPLICATION = "ai_blog.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# Statik ve Medya dosyaları (Her iki ortam için de aynı)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / 'media'
FASTQ_UPLOAD_DIR = MEDIA_ROOT / 'fastq_uploads'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Plotly Dash Ayarları
PLOTLY_DASH = {
    "ws_route": "dpd/ws/channel",
    "http_route": "dpd/views",
    "http_poke_enabled": True,
    "insert_demo_migrations": False,
    "cache_timeout_initial_arguments": 60,
    "view_decorator": None,
    "cache_arguments": True,
    "serve_locally": False,
}

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django_plotly_dash.finders.DashAssetFinder',
    'django_plotly_dash.finders.DashComponentFinder',
    'django_plotly_dash.finders.DashAppDirectoryFinder',
]

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Celery Ortak Ayarları
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Istanbul'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 3600}

NOTO_FONT_PATH = BASE_DIR / "static/fonts/NotoSans-Regular.ttf"

# Yükleme Limitleri
DATA_UPLOAD_MAX_MEMORY_SIZE = 5000 * 1024 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5000 * 1024 * 1024 * 1024

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ]
}

# Logging (Her iki ortam için de aynı, logları LOG_DIR'e yazar)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'django.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'celery.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': True},
        'celery': {'handlers': ['celery_file', 'console'], 'level': 'INFO'},
        'bio_tools.performance': {'handlers': ['file', 'console'], 'level': 'WARNING'},
    },
}

# ==============================================================================
# CANLI ORTAM AYARLARI (PRODUCTION)
# ==============================================================================
if ENVIRONMENT == 'production':
    logger.info("Running in PRODUCTION mode")

    # GÜVENLİK: DEBUG=False
    DEBUG = False

    # SECRET_KEY PythonAnywhere ortam değişkeninden gelmeli
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY ortam değişkeni production için ayarlanmamış!")

    ALLOWED_HOSTS = ["aiblog.pythonanywhere.com"]

    # HTTPS için (Önemli)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 yıl
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # VERİTABANI (PythonAnywhere MySQL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'aiblog$default',
            'USER': 'aiblog',
            'PASSWORD': os.environ.get('MYSQL_PASSWORD'),
            'HOST': 'aiblog.mysql.pythonanywhere-services.com',
            'PORT': '3306',
            'OPTIONS': {
                'ssl': {'ssl-ca': '/etc/ssl/certs/ca-certificates.crt'},
                'sql_mode': 'STRICT_TRANS_TABLES',
            },
        }
    }

    # REDIS / CELERY / CACHE (Harici Redis)
    REDIS_URL = os.environ.get('REDIS_URL')
    if not REDIS_URL:
        raise ValueError("REDIS_URL ortam değişkeni production için ayarlanmamış!")

    logger.info("✓ Production: REDIS_URL bulundu. Redis cache ve session'lar kullanılacak.")

    CELERY_BROKER_URL = REDIS_URL + '/0'
    CELERY_RESULT_BACKEND = REDIS_URL + '/0'

    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL + '/1', 'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
            'KEY_PREFIX': 'ai_blog', 'TIMEOUT': 300,
        },
        'fastq_analysis': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL + '/2', 'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
            'KEY_PREFIX': 'fastq', 'TIMEOUT': 3600,
        },
        'session': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL + '/3', 'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
            'KEY_PREFIX': 'session', 'TIMEOUT': 86400,
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'session'

    # EMAIL (Gerçek SMTP)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'artificalintelligentblog@gmail.com'
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')


# ==============================================================================
# GELİŞTİRME ORTAMI AYARLARI (DEVELOPMENT)
# ==============================================================================
else:
    logger.info("Running in DEVELOPMENT mode")

    # GÜVENLİK: DEBUG=True
    DEBUG = True

    # SECRET_KEY .env dosyasından gelir (veya güvensiz bir varsayılan)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-development-key-fallback')

    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

    # VERİTABANI (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

    # REDIS / CELERY / CACHE (Localhost Testi)
    # Orijinal dosyanızdaki 'localhost' ping mantığı geliştirme için mükemmeldir.
    REDIS_AVAILABLE = False
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
        r.ping()
        REDIS_AVAILABLE = True
        logger.info("✓ Development: Yerel Redis (localhost:6379) bağlantısı başarılı.")
    except Exception as e:
        logger.warning(f"⚠️ Development: Yerel Redis (localhost:6379) bağlanamıyor: {e}. Fallback cache kullanılacak.")

    if REDIS_AVAILABLE:
        CELERY_BROKER_URL = 'redis://localhost:6379/0'
        CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

        CACHES = {
            'default': {'BACKEND': 'django_redis.cache.RedisCache', 'LOCATION': 'redis://127.0.0.1:6379/1', 'KEY_PREFIX': 'ai_blog', 'TIMEOUT': 300},
            'fastq_analysis': {'BACKEND': 'django_redis.cache.RedisCache', 'LOCATION': 'redis://127.0.0.1:6379/2', 'KEY_PREFIX': 'fastq', 'TIMEOUT': 3600},
            'session': {'BACKEND': 'django_redis.cache.RedisCache', 'LOCATION': 'redis://127.0.0.1:6379/3', 'KEY_PREFIX': 'session', 'TIMEOUT': 86400}
        }
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        SESSION_CACHE_ALIAS = 'session'

    else:
        logger.warning("Development: Celery (Redis) çalışmayacak. LocMem cache ve DB session kullanılacak.")
        CELERY_BROKER_URL = None  # Redis yoksa Celery'yi devre dışı bırak
        CELERY_RESULT_BACKEND = None

        CACHES = {
            'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-cache'},
            'fastq_analysis': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'fastq-cache'},
            'session': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'session-cache'}
        }
        SESSION_ENGINE = 'django.contrib.sessions.backends.db' # Veritabanı session'ları

    # EMAIL (Konsola Yazdır)
    # Geliştirme sırasında gerçek e-posta göndermez, terminale basar.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_HOST_USER = 'development@example.com'