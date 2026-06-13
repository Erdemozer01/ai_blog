import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html

# Kredi sayfası Dash uygulaması (diğer sayfalarla aynı tarz)
app = DjangoDash('CreditsApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP,
                                       'https://use.fontawesome.com/releases/v5.8.1/css/all.css'])


def create_credits_layout(balance, transactions, prices, is_superuser):
    """
    Kredi bakiyesi, fiyat listesi ve işlem geçmişini gösteren Dash layout'u.
    Veriler view'dan hazır olarak (liste/sözlük) gelir.
    """

    # --- Bakiye kartı ---
    if is_superuser:
        balance_body = html.Div([
            html.H5("Kredi Bakiyeniz", className="text-muted mb-1"),
            html.H1("∞ Sınırsız", className="display-4 text-success mb-0"),
            html.P("Superuser hesabı — kredi düşmez.", className="text-muted small mt-2"),
        ], className="text-center")
    else:
        balance_body = html.Div([
            html.H5("Kredi Bakiyeniz", className="text-muted mb-1"),
            html.H1(f"{balance}", className="display-3 fw-bold mb-0"),
            html.P("kredi", className="text-muted"),
            dbc.Button("Kredi Yükle (yakında)", color="primary", className="mt-2", disabled=True),
            html.P("Ödeme sistemi yakında eklenecek.", className="text-muted small mt-2"),
        ], className="text-center")

    balance_card = dbc.Card(dbc.CardBody(balance_body, className="p-4"),
                            className="shadow-sm mb-4")

    # --- Fiyat listesi ---
    if prices:
        price_rows = [html.Tr([html.Td(p['label']),
                               html.Td(f"{p['cost']} kredi", className="text-end")])
                      for p in prices]
    else:
        price_rows = [html.Tr(html.Td("Henüz fiyat tanımlanmamış.",
                                      colSpan=2, className="text-muted text-center"))]

    price_card = dbc.Card([
        dbc.CardHeader(html.Strong("İşlem Fiyatları")),
        dbc.CardBody(
            dbc.Table([
                html.Thead(html.Tr([html.Th("İşlem"), html.Th("Maliyet", className="text-end")])),
                html.Tbody(price_rows),
            ], className="mb-0"),
            className="p-0"),
    ], className="shadow-sm mb-4")

    # --- İşlem geçmişi ---
    if transactions:
        tx_rows = []
        for t in transactions:
            color = "text-success" if t['amount'] >= 0 else "text-danger"
            sign = "+" if t['amount'] >= 0 else ""
            tx_rows.append(html.Tr([
                html.Td(t['created_at'], className="text-muted small"),
                html.Td(t['description']),
                html.Td(f"{sign}{t['amount']}", className=f"text-end {color}"),
            ]))
    else:
        tx_rows = [html.Tr(html.Td("Henüz işlem yok.",
                                   colSpan=3, className="text-muted text-center"))]

    tx_card = dbc.Card([
        dbc.CardHeader(html.Strong("İşlem Geçmişi")),
        dbc.CardBody(
            dbc.Table([
                html.Thead(html.Tr([html.Th("Tarih"), html.Th("Açıklama"),
                                    html.Th("Miktar", className="text-end")])),
                html.Tbody(tx_rows),
            ], className="table-sm mb-0"),
            className="p-0"),
    ], className="shadow-sm")

    return dbc.Container(
        dbc.Row(
            dbc.Col([balance_card, price_card, tx_card], lg=8),
            justify="center"),
        className="my-5")


# Başlangıç boş layout (view her istekte günceller)
app.layout = html.Div()