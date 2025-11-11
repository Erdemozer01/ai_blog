# Celery app'imizin her Django başlangıcında yüklendiğinden emin ol.
from . import app as celery_app

__all__ = ('celery_app',)

