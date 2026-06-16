import warnings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash

warnings.filterwarnings("ignore")

app = DjangoDash(
    "FederatedLearningApp",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
)


def _card(title, icon, children):
    return dbc.Card([
        dbc.CardHeader(html.H5([html.I(className=f"fas {icon} me-2"), title],
                                className="mb-0 text-white"),
                       style={"background": "linear-gradient(135deg,#064e3b,#065f46)"}),
        dbc.CardBody(children),
    ], className="mb-4 shadow")


def create_federated_layout():
    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        html.H2([html.I(className="fas fa-network-wired me-2 text-success"),
                 "Birleşik Öğrenme (Federated Learning) Simülatörü"],
                className="my-4 fw-bold"),
        html.P(
            "Farklı hastanelerdeki hasta verilerini merkeze göndermeden, yalnızca model "
            "ağırlıklarını paylaşarak ortak bir AI modeli nasıl eğitilir? Bu simülatör "
            "ile federated öğrenme sürecini interaktif olarak keşfedin.",
            className="text-muted mb-4",
        ),

        # Mimari Diyagramı (Responsive Entegrasyonu)
        _card("FL Mimarisi", "fa-sitemap", [
            dbc.Row([
                # Sol Kısım: Hastaneler
                dbc.Col([
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-hospital fa-2x text-primary"),
                                html.Br(), html.Strong("Hastane A", className="mt-2 d-inline-block"),
                                html.Br(), html.Small("Lokal model eğit", className="text-muted"),
                            ],
                                className="text-center p-3 border rounded h-100 d-flex flex-column justify-content-center",
                                style={"background": "#eff6ff"}),
                        ], xs=12, md=4, className="mb-3 mb-md-0"),

                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-hospital fa-2x text-danger"),
                                html.Br(), html.Strong("Hastane B", className="mt-2 d-inline-block"),
                                html.Br(), html.Small("Lokal model eğit", className="text-muted"),
                            ],
                                className="text-center p-3 border rounded h-100 d-flex flex-column justify-content-center",
                                style={"background": "#fef2f2"}),
                        ], xs=12, md=4, className="mb-3 mb-md-0"),

                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-hospital fa-2x text-warning"),
                                html.Br(), html.Strong("Hastane C", className="mt-2 d-inline-block"),
                                html.Br(), html.Small("Lokal model eğit", className="text-muted"),
                            ],
                                className="text-center p-3 border rounded h-100 d-flex flex-column justify-content-center",
                                style={"background": "#fffbeb"}),
                        ], xs=12, md=4),
                    ])
                ], xs=12, lg=6),

                # Orta Kısım: İletişim Okları
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-arrows-alt-h fa-2x text-secondary mb-2 d-none d-lg-block"),
                        html.I(className="fas fa-arrows-alt-v fa-2x text-secondary mb-2 d-block d-lg-none"),
                        html.Small("Yalnızca ağırlıklar →", className="text-muted d-block"),
                        html.Small("← Hiç ham veri yok!", className="text-success fw-bold d-block mt-1"),
                    ], className="text-center p-3 h-100 d-flex flex-column justify-content-center"),
                ], xs=12, lg=3, className="my-3 my-lg-0"),

                # Sağ Kısım: Merkezi Sunucu
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-server fa-2x text-success"),
                        html.Br(), html.Strong("Merkezi Sunucu", className="mt-2 d-inline-block"),
                        html.Br(), html.Small("FedAvg Agregasyonu", className="text-muted"),
                    ],
                        className="text-center p-3 border rounded bg-light h-100 d-flex flex-column justify-content-center border-2 border-success"),
                ], xs=12, lg=3),
            ], className="align-items-stretch"),
        ]),

        # Simülasyon Parametreleri (Responsive Form Elemanları)
        _card("Simülasyon Parametreleri", "fa-sliders-h", [
            dbc.Row([
                dbc.Col([
                    dbc.Label("Hastane Sayısı (İstemci)"),
                    dcc.Slider(id="fl-n-clients", min=2, max=10, step=1, value=5,
                               marks={i: str(i) for i in range(2, 11)},
                               tooltip={"placement": "bottom"}),
                ], xs=12, lg=4, className="mb-4 mb-lg-0"),
                dbc.Col([
                    dbc.Label("Global Tur Sayısı"),
                    dcc.Slider(id="fl-n-rounds", min=5, max=50, step=5, value=20,
                               marks={i: str(i) for i in [5, 10, 20, 30, 50]},
                               tooltip={"placement": "bottom"}),
                ], xs=12, lg=4, className="mb-4 mb-lg-0"),
                dbc.Col([
                    dbc.Label("Veri Heterojenliği (Non-IID)"),
                    dcc.Slider(id="fl-heterogeneity", min=0.0, max=1.0, step=0.1, value=0.3,
                               marks={0: "IID", 0.5: "Orta", 1.0: "Yüksek"},
                               tooltip={"placement": "bottom"}),
                ], xs=12, lg=4),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Öğrenme Oranı"),
                    dbc.Input(id="fl-lr", type="number", value=0.01, min=0.001, max=0.5, step=0.001),
                ], xs=12, md=6, lg=3, className="mb-3 mb-lg-0 mt-lg-3"),
                dbc.Col([
                    dbc.Label("Lokal Epoch Sayısı"),
                    dbc.Input(id="fl-local-epochs", type="number", value=5, min=1, max=20),
                ], xs=12, md=6, lg=3, className="mb-3 mb-lg-0 mt-lg-3"),
                dbc.Col([
                    dbc.Label("Merkezi Eğitim ile Karşılaştır"),
                    dbc.Checklist(id="fl-compare", options=[{"label": " Evet", "value": "yes"}],
                                  value=["yes"], switch=True),
                ], xs=12, md=6, lg=3, className="mb-3 mb-lg-0 mt-lg-3"),
                dbc.Col([
                    dbc.Button([html.I(className="fas fa-play me-2"), "Simülasyonu Başlat (5 Kredi)"],
                               id="fl-run-btn", color="success", className="w-100 h-100"),
                ], xs=12, md=6, lg=3, className="mt-lg-3 d-flex align-items-end"),
            ], className="mt-0 mt-lg-3"),
        ]),

        dcc.Loading(type="circle", children=[
            html.Div(id="fl-results", style={"display": "none"}, children=[

                # Metrikler (Responsive Kartlar)
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("FL Son Doğruluk", className="text-muted small mb-1"),
                        html.H4(id="fl-metric-acc", className="text-success fw-bold mb-0"),
                    ]), className="text-center shadow-sm h-100 d-flex flex-column justify-content-center"),
                        xs=12, sm=6, xl=3, className="mb-3"),

                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("Merkezi Model Doğruluk", className="text-muted small mb-1"),
                        html.H4(id="fl-metric-central", className="text-primary fw-bold mb-0"),
                    ]), className="text-center shadow-sm h-100 d-flex flex-column justify-content-center"),
                        xs=12, sm=6, xl=3, className="mb-3"),

                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("İletişim Turu", className="text-muted small mb-1"),
                        html.H4(id="fl-metric-rounds", className="text-warning fw-bold mb-0"),
                    ]), className="text-center shadow-sm h-100 d-flex flex-column justify-content-center"),
                        xs=12, sm=6, xl=3, className="mb-3"),

                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("Gizlilik Koruması", className="text-muted small mb-1"),
                        html.H4("✓ Tam", className="text-success fw-bold mb-0"),
                    ]), className="text-center shadow-sm h-100 d-flex flex-column justify-content-center"),
                        xs=12, sm=6, xl=3, className="mb-3"),
                ], className="mb-2 align-items-stretch"),

                # Grafikler
                _card("Öğrenme Eğrisi — FL vs Merkezi Eğitim", "fa-chart-line", [
                    dcc.Graph(id="fl-learning-curve"),
                ]),

                dbc.Row([
                    dbc.Col(_card("İstemci Doğruluk Dağılımı", "fa-chart-bar", [
                        dcc.Graph(id="fl-client-acc-bar"),
                    ]), xs=12, lg=6, className="mb-3 mb-lg-0"),

                    dbc.Col(_card("İletişim Maliyeti vs Doğruluk", "fa-exchange-alt", [
                        dcc.Graph(id="fl-comm-cost"),
                    ]), xs=12, lg=6),
                ]),
            ]),
        ]),

        dcc.Store(id="fl-sim-store"),
    ], fluid=True)


# ---------------------------------------------------------------------------
# Simülasyon motoru (FedAvg benzeri)
# ---------------------------------------------------------------------------

def _simulate_fl(n_clients, n_rounds, heterogeneity, lr, local_epochs, compare):
    np.random.seed(42)

    # Her istemcinin veri büyüklüğü (non-IID: bazıları az, bazıları çok)
    client_sizes = np.random.dirichlet(np.ones(n_clients) * (1 - heterogeneity + 0.1) * 10) * 1000 + 50
    client_sizes = client_sizes.astype(int)

    # Başlangıç global ağırlık (skalar simülasyon)
    global_weight = 0.0
    fl_accs = []
    central_accs = []

    # Gerçek doğruluğun üst sınırı (heterojenilik arttıkça düşer)
    max_acc = 0.95 - heterogeneity * 0.15

    for rnd in range(n_rounds):
        # Lokal güncellemeler (FedAvg)
        client_weights = []
        for c in range(n_clients):
            noise = np.random.normal(0, heterogeneity * 0.1)
            local_update = global_weight + lr * local_epochs * (max_acc - global_weight + noise)
            client_weights.append((local_update, client_sizes[c]))

        # Ağırlıklı ortalama
        total = sum(s for _, s in client_weights)
        global_weight = sum(w * s / total for w, s in client_weights)
        global_weight = np.clip(global_weight, 0, 1)

        # Doğruluğa çevir (sigmoid benzeri)
        acc = max_acc * (1 - np.exp(-3 * global_weight))
        fl_accs.append(float(np.clip(acc + np.random.normal(0, 0.005), 0, 1)))

        # Merkezi eğitim (tüm veri bir arada, daha hızlı yakınsama)
        central_acc = max_acc * (1 - np.exp(-4 * (rnd + 1) / n_rounds))
        central_accs.append(float(np.clip(central_acc + np.random.normal(0, 0.003), 0, 1)))

    # Son tur istemci doğrulukları
    client_final_accs = [
        fl_accs[-1] + np.random.normal(0, heterogeneity * 0.05)
        for _ in range(n_clients)
    ]

    return {
        "fl_accs": fl_accs,
        "central_accs": central_accs,
        "client_final_accs": client_final_accs,
        "client_sizes": client_sizes.tolist(),
        "n_rounds": n_rounds,
        "n_clients": n_clients,
    }


@app.callback(
    Output("fl-results", "style"),
    Output("fl-metric-acc", "children"),
    Output("fl-metric-central", "children"),
    Output("fl-metric-rounds", "children"),
    Output("fl-learning-curve", "figure"),
    Output("fl-client-acc-bar", "figure"),
    Output("fl-comm-cost", "figure"),
    Output("fl-sim-store", "data"),
    Input("fl-run-btn", "n_clicks"),
    State("fl-n-clients", "value"),
    State("fl-n-rounds", "value"),
    State("fl-heterogeneity", "value"),
    State("fl-lr", "value"),
    State("fl-local-epochs", "value"),
    State("fl-compare", "value"),
    prevent_initial_call=True,
)
def run_simulation(n_clicks, n_clients, n_rounds, heterogeneity, lr, local_epochs, compare, **kwargs):
    from billing.dash_helpers import try_charge, get_request_user
    user = get_request_user(kwargs)
    # Önce kredi yeterli mi bak (düşürmeden)
    if user is not None and not getattr(user, 'is_superuser', False):
        try:
            from billing.services import can_use
            _ok, _ = can_use(user, 'bio_federated', default_cost=5)
        except Exception:
            _ok = True
        if not _ok:
            # Yetersiz kredi: simülasyonu çalıştırma, uyarıyı göster
            import plotly.graph_objects as _go
            from billing.dash_helpers import insufficient_alert
            from billing.services import get_balance
            _empty = _go.Figure()
            _alert_fig = _go.Figure()
            _alert_fig.add_annotation(text="Yetersiz kredi", showarrow=False,
                                      font=dict(size=20, color="orange"))
            _alert_fig.update_layout(xaxis={'visible': False}, yaxis={'visible': False})
            return ({"display": "block"}, "—", "—", "—", _alert_fig, _empty, _empty, {})

    # Krediyi düş
    ok, msg, _u = try_charge(kwargs, 'bio_federated', cost=5,
                             description="Federated learning simülasyonu")
    if not ok:
        import plotly.graph_objects as _go
        _empty = _go.Figure()
        return ({"display": "none"}, "—", "—", "—", _empty, _empty, _empty, {})

    results = _simulate_fl(
        int(n_clients or 5), int(n_rounds or 20),
        float(heterogeneity or 0.3), float(lr or 0.01),
        int(local_epochs or 5), compare,
    )

    fl_final = results["fl_accs"][-1]
    central_final = results["central_accs"][-1]

    # Öğrenme eğrisi
    rounds = list(range(1, results["n_rounds"] + 1))
    curve_df = pd.DataFrame({
        "Tur": rounds * 2,
        "Doğruluk": results["fl_accs"] + results["central_accs"],
        "Yöntem": ["Federated Learning"] * len(rounds) + ["Merkezi Eğitim"] * len(rounds),
    })
    fig_curve = px.line(
        curve_df, x="Tur", y="Doğruluk", color="Yöntem",
        title="FL vs Merkezi Eğitim — Öğrenme Eğrisi",
        color_discrete_map={"Federated Learning": "#10b981", "Merkezi Eğitim": "#6366f1"},
    )
    fig_curve.add_hline(y=0.9, line_dash="dot", line_color="gray",
                        annotation_text="Hedef: %90")

    # İstemci doğruluk bar
    client_df = pd.DataFrame({
        "İstemci": [f"Hastane {chr(65+i)}" for i in range(n_clients)],
        "Doğruluk": [np.clip(a, 0, 1) for a in results["client_final_accs"]],
        "Veri Boyutu": results["client_sizes"],
    })
    fig_client = px.bar(
        client_df, x="İstemci", y="Doğruluk", color="Doğruluk",
        title="İstemci Başına Son Doğruluk",
        color_continuous_scale="Greens",
        text=client_df["Doğruluk"].apply(lambda x: f"{x:.2%}"),
    )

    # İletişim maliyeti vs doğruluk
    comm_df = pd.DataFrame({
        "İletişim Turu": rounds,
        "Kümülatif İletişim (MB)": [r * n_clients * 0.5 for r in rounds],
        "FL Doğruluk": results["fl_accs"],
        "Merkezi Doğruluk": results["central_accs"],
    })
    fig_comm = px.scatter(
        comm_df, x="Kümülatif İletişim (MB)", y="FL Doğruluk",
        title="İletişim Maliyeti vs FL Doğruluğu",
        color="İletişim Turu", color_continuous_scale="Viridis",
        size=[5] * len(rounds),
    )

    return (
        {"display": "block"},
        f"{fl_final:.2%}", f"{central_final:.2%}", str(results["n_rounds"]),
        fig_curve, fig_client, fig_comm, results,
    )

@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n_clicks, is_open):
    return not is_open


@app.callback(Output("federated_learning", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:federated_learning')
    except Exception:
        return False
