"""
billing.decorators — View'lara kredi kontrolü ekleyen decorator.

Kullanım:
    from billing.decorators import require_credits

    @require_credits('makale_uretim')
    def generate_article_view(request):
        ...

Davranış:
  - Giriş yapılmamışsa login'e yönlendirir.
  - superuser ise serbest (kredi düşmez).
  - Yeterli kredi varsa: krediyi düşer, sayfaya girer.
  - Yetersizse: kredi yükleme sayfasına yönlendirir + uyarı.
"""
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

from .services import can_use, charge


def require_credits(service_key, default_cost=1):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user

            # superuser sınırsız — kredi düşmeden geç
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            ok, msg = can_use(user, service_key, default_cost=default_cost)
            if not ok:
                messages.error(request, msg)
                # Kredi yükleme sayfasına yönlendir
                return redirect('billing:credits')

            # Krediyi düş ve sayfaya gir
            try:
                charge(user, service_key, default_cost=default_cost)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('billing:credits')

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
