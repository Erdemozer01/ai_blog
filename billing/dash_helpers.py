"""
Dash callback'lerinde kredi kontrolü/düşürme yardımcısı.

Kullanım (callback içinde, **kwargs ile request alarak):

    from billing.dash_helpers import try_charge

    def my_callback(n_clicks, ..., **kwargs):
        ok, msg, user = try_charge(kwargs, 'bio_sequence_analyzer', cost=5)
        if not ok:
            return dbc.Alert(msg, color="warning")   # kredi yetersiz / giriş yok
        # ... işlemi yap (kredi düşüldü) ...

Mantık:
  - Giriş yapılmamışsa  -> (False, "giriş yapın", None)
  - superuser           -> (True, "", user)  [kredi düşmez]
  - kredi yetersiz      -> (False, "yetersiz kredi", user)
  - yeterli             -> kredi DÜŞÜLÜR -> (True, "", user)
"""


def get_request_user(kwargs):
    """django_plotly_dash callback kwargs'ından Django user'ı çıkarır."""
    request = kwargs.get('request') if kwargs else None
    if request is None:
        return None
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return user


def insufficient_alert(balance, cost, lang='tr'):
    """Yetersiz kredi durumunda gösterilecek zengin uyarı (bakiye + Kredi Yükle butonu)."""
    import dash_bootstrap_components as dbc
    from dash import html
    try:
        from django.urls import reverse
        credits_url = reverse('billing:credits')
    except Exception:
        credits_url = '/billing/credits/'

    if lang == 'tr':
        title = "Yetersiz Kredi"
        body = f"Bu işlem {cost} kredi gerektiriyor. Mevcut krediniz: {balance}."
        btn = "Kredi Yükle"
    else:
        title = "Insufficient Credits"
        body = f"This operation requires {cost} credits. Your balance: {balance}."
        btn = "Top Up Credits"

    return dbc.Alert([
        html.H5([html.I(className="fas fa-coins me-2"), title], className="alert-heading"),
        html.P(body, className="mb-2"),
        dbc.Button(btn, href=credits_url, color="warning", external_link=True, size="sm")
    ], color="warning", className="mt-3")


def try_charge(kwargs, service_key, cost=5, description=None, lang=None):
    """
    Kredi kontrol + düşürme. (ok: bool, mesaj_veya_alert, user) döner.
    İşlem başarılıysa kredi düşülmüştür.
    Yetersiz kredide mesaj yerine zengin bir uyarı bileşeni (Kredi Yükle butonlu) döner.

    lang verilmezse, request cookie'sinden (site_lang) otomatik belirlenir.
    """
    # Dil: parametre > request cookie > 'en'
    if lang is None:
        lang = 'en'
        request = kwargs.get('request') if kwargs else None
        if request is not None:
            try:
                from dash_apps.i18n_helper import get_lang
                lang = get_lang(request)
            except Exception:
                lang = (getattr(request, 'COOKIES', {}) or {}).get('site_lang', 'en')

    user = get_request_user(kwargs)

    if user is None:
        import dash_bootstrap_components as dbc
        msg_login = ("Bu işlem için lütfen giriş yapın." if lang == 'tr'
                     else "Please log in to use this feature.")
        return False, dbc.Alert(msg_login, color="warning", className="mt-3"), None

    # superuser sınırsız
    if getattr(user, 'is_superuser', False):
        return True, "", user

    try:
        from billing.services import can_use, charge, get_balance
        ok, why = can_use(user, service_key, default_cost=cost)
        if not ok:
            balance = get_balance(user)
            return False, insufficient_alert(balance, cost, lang=lang), user
        charge(user, service_key, default_cost=cost, description=description)
        return True, "", user
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Kredi düşme hatası (%s): %s", service_key, e)
        return True, "", user