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


def build_confirm_modal(modal_id, title=None, lang='tr'):
    """
    Yeniden kullanılabilir kredi onay modalı (kapalı başlar).
    Araç layout'una bir kez eklenir; tüm kredili işlemler bunu paylaşabilir
    veya her işlem kendi modal_id'siyle ayrı bir tane kullanabilir.

    İçindeki bileşen id'leri:
      f"{modal_id}"          -> dbc.Modal (is_open kontrol edilir)
      f"{modal_id}-body"     -> mesaj gövdesi (krediniz/işlem maliyeti)
      f"{modal_id}-confirm"  -> Onayla butonu
      f"{modal_id}-cancel"   -> İptal butonu
    """
    import dash_bootstrap_components as dbc
    from dash import html
    if title is None:
        title = "İşlem Onayı" if lang == 'tr' else "Confirm Action"
    confirm_txt = "Onaylıyorum" if lang == 'tr' else "Confirm"
    cancel_txt = "İptal" if lang == 'tr' else "Cancel"
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-coins me-2 text-warning"), title])),
        dbc.ModalBody(id=f"{modal_id}-body"),
        dbc.ModalFooter([
            dbc.Button(cancel_txt, id=f"{modal_id}-cancel", color="secondary",
                       outline=True, className="me-2"),
            dbc.Button(confirm_txt, id=f"{modal_id}-confirm", color="primary"),
        ]),
    ], id=modal_id, is_open=False, centered=True)


def confirm_modal_body(kwargs, service_key, cost=5, lang='tr'):
    """
    Modal gövdesi metnini üretir: 'Krediniz: X. Bu işlem Y kredi düşecek. Onaylıyor musunuz?'
    Ayrıca yeterli kredi yoksa uygun uyarı döndürür.

    Döner: (body_children, can_proceed: bool)
      can_proceed False ise işlem yapılmamalı (giriş yok / yetersiz kredi).
    """
    import dash_bootstrap_components as dbc
    from dash import html

    user = get_request_user(kwargs)
    if user is None:
        msg = ("Bu işlem için lütfen giriş yapın." if lang == 'tr'
               else "Please log in to use this feature.")
        return dbc.Alert(msg, color="warning", className="mb-0"), False

    # superuser: kredi düşmez, bilgilendir
    if getattr(user, 'is_superuser', False):
        msg = ("Yönetici hesabı: bu işlem ücretsizdir." if lang == 'tr'
               else "Admin account: this operation is free.")
        return dbc.Alert(msg, color="info", className="mb-0"), True

    try:
        from billing.services import get_balance, get_cost
        balance = get_balance(user)
        real_cost = get_cost(service_key, default=cost)
    except Exception:
        balance, real_cost = None, cost

    if balance is not None and balance < real_cost:
        # yetersiz kredi
        if lang == 'tr':
            body = [
                html.P([html.Strong("Krediniz: "), f"{balance}"], className="mb-1"),
                html.P([html.Strong("Bu işlem: "), f"{real_cost} kredi"], className="mb-2"),
                dbc.Alert("Yeterli krediniz yok. Lütfen kredi yükleyin.",
                          color="danger", className="mb-0 py-2"),
            ]
        else:
            body = [
                html.P([html.Strong("Your balance: "), f"{balance}"], className="mb-1"),
                html.P([html.Strong("This operation: "), f"{real_cost} credits"], className="mb-2"),
                dbc.Alert("Insufficient credits. Please top up.",
                          color="danger", className="mb-0 py-2"),
            ]
        return html.Div(body), False

    # yeterli kredi → onay metni
    if lang == 'tr':
        body = [
            html.P([html.Strong("Mevcut krediniz: "),
                    f"{balance if balance is not None else '—'}"], className="mb-1"),
            html.P([html.Strong("Bu işlem için düşülecek: "),
                    html.Span(f"{real_cost} kredi", className="text-danger fw-bold")],
                   className="mb-2"),
            html.P("Onaylıyor musunuz?", className="mb-0"),
        ]
    else:
        body = [
            html.P([html.Strong("Your balance: "),
                    f"{balance if balance is not None else '—'}"], className="mb-1"),
            html.P([html.Strong("This will deduct: "),
                    html.Span(f"{real_cost} credits", className="text-danger fw-bold")],
                   className="mb-2"),
            html.P("Do you confirm?", className="mb-0"),
        ]
    return html.Div(body), True


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
        from billing.services import can_use, charge, get_balance, get_cost
        # Gerçek fiyatı veritabanından al (admin'den ayarlanan); yoksa parametre 'cost' yedek
        real_cost = get_cost(service_key, default=cost)
        ok, why = can_use(user, service_key, default_cost=cost)
        if not ok:
            balance = get_balance(user)
            return False, insufficient_alert(balance, real_cost, lang=lang), user
        charge(user, service_key, default_cost=cost, description=description)
        return True, "", user
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Kredi düşme hatası (%s): %s", service_key, e)
        return True, "", user
