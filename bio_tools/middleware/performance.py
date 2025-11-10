import time
import logging

logger = logging.getLogger('bio_tools.performance')


class PerformanceMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time

        # 1 saniyeden uzun istekleri logla
        if duration > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.path} "
                f"took {duration:.2f}s"
            )

        # Response header ekle
        response['X-Request-Duration'] = f"{duration:.4f}"
        return response