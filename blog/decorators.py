# blog/decorators.py (YENİ DOSYA)

from django.contrib import messages
from django.shortcuts import redirect

def superuser_required(view_func):
    """
    Sadece süper kullanıcıların erişebileceği view'ler için bir decorator.
    Eğer kullanıcı süper kullanıcı değilse, ana sayfaya yönlendirir.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Bu sayfaya erişim yetkiniz bulunmamaktadır.")
            return redirect('blog:anasayfa')
        return view_func(request, *args, **kwargs)
    return _wrapped_view