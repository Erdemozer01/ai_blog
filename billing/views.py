from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import UserCredit, CreditTransaction, ServicePrice
from .services import get_balance


@login_required
def credits_view(request):
    """Kullanıcının kredi bakiyesi, işlem geçmişi ve fiyat listesi."""
    balance = get_balance(request.user)
    transactions = CreditTransaction.objects.filter(
        user=request.user).order_by('-created_at')[:50]
    prices = ServicePrice.objects.filter(is_active=True).order_by('label')

    context = {
        'balance': balance,
        'transactions': transactions,
        'prices': prices,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'billing/credits.html', context)
