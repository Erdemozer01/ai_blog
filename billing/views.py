from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from dash import html

from blog.views import create_main_navbar
from dash_apps.credits import app as credits_app, create_credits_layout

from .models import CreditTransaction, ServicePrice
from .services import get_balance


@login_required
def credits_view(request):
    """Kullanıcının kredi bakiyesi, işlem geçmişi ve fiyat listesi (Dash)."""
    balance = get_balance(request.user)
    is_superuser = request.user.is_superuser

    # İşlem geçmişi -> sade sözlük listesi (Dash layout'a verilebilir)
    transactions = [
        {
            'created_at': t.created_at.strftime('%d.%m.%Y %H:%M'),
            'description': t.description or '',
            'amount': t.amount,
        }
        for t in CreditTransaction.objects.filter(
            user=request.user).order_by('-created_at')[:50]
    ]

    # Fiyatlar -> sade sözlük listesi
    prices = [
        {'label': p.label, 'cost': p.cost}
        for p in ServicePrice.objects.filter(is_active=True).order_by('label')
    ]

    # Navbar + içerik birleştir (diğer Dash sayfaları gibi)
    main_navbar = create_main_navbar(request)
    content = create_credits_layout(balance, transactions, prices, is_superuser)
    full_layout = html.Div([main_navbar, content])

    def serve_layout():
        return full_layout

    credits_app.layout = serve_layout

    return render(request, 'billing/credits.html')