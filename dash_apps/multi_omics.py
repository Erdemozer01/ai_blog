import base64
import io
import warnings

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State
from django_plotly_dash import DjangoDash
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

app = DjangoDash(
    "MultiOmicsApp",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
)

OMICS_LAYERS = ["Genomik", "Transkriptomik", "Proteomik", "Metabolomik"]
OMICS_COLORS = {"Genomik": "#ef4444", "Transkriptomik": "#3b82f6",
                "Proteomik": "#10b981", "Metabolomik": "#f59e0b"}


def _card(title, icon, children, color="#1a1a2e"):
    return dbc.Card([
        dbc.CardHeader(
            html.H5([html.I(className=f"fas {icon} me-2"), title], className="mb-0 text-white"),
            style={"background": f"linear-gradient(135deg,{color},#16213e)"},
        ),
        dbc.CardBody(children),
    ], className="mb-4 shadow")


def create_multiomics_layout():
    return dbc.Container([
        html.H2([html.I(className="fas fa-layer-group me-2 text-warning"),
                 "Multi-Omik Veri Entegrasyonu"],
                className="my-4 fw-bold"),
        html.P(
            "Genomik, transkriptomik, proteomik ve metabolomik katmanlarını tek bir analiz "
            "boru hattında birleştirin. CSV yükleyin veya demo veri ile başlayın.",
            className="text-muted mb-4",
        ),

        # Veri Yükleme — 4 katman
        _card("Omik Katman Yükleme", "fa-database", [
            dbc.Row([
                dbc.Col([
                    html.Strong("Genomik", className="text-danger"),
                    dcc.Upload(id="omics-upload-genomik",
                               children=html.Div(["📂 CSV yükle"], className="text-center py-2"),
                               style={"border": "2px dashed #ef4444", "borderRadius": "8px", "cursor": "pointer"},
                               multiple=False),
                    html.Div(id="omics-status-genomik", className="small mt-1"),
                ], width=3),
                dbc.Col([
                    html.Strong("Transkriptomik", className="text-primary"),
                    dcc.Upload(id="omics-upload-transkriptomik",
                               children=html.Div(["📂 CSV yükle"], className="text-center py-2"),
                               style={"border": "2px dashed #3b82f6", "borderRadius": "8px", "cursor": "pointer"},
                               multiple=False),
                    html.Div(id="omics-status-transkriptomik", className="small mt-1"),
                ], width=3),
                dbc.Col([
                    html.Strong("Proteomik", className="text-success"),
                    dcc.Upload(id="omics-upload-proteomik",
                               children=html.Div(["📂 CSV yükle"], className="text-center py-2"),
                               style={"border": "2px dashed #10b981", "borderRadius": "8px", "cursor": "pointer"},
                               multiple=False),
                    html.Div(id="omics-status-proteomik", className="small mt-1"),
                ], width=3),
                dbc.Col([
                    html.Strong("Metabolomik", className="text-warning"),
                    dcc.Upload(id="omics-upload-metabolomik",
                               children=html.Div(["📂 CSV yükle"], className="text-center py-2"),
                               style={"border": "2px dashed #f59e0b", "borderRadius": "8px", "cursor": "pointer"},
                               multiple=False),
                    html.Div(id="omics-status-metabolomik", className="small mt-1"),
                ], width=3),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Button([html.I(className="fas fa-flask me-2"), "Demo Veri Yükle (4 Katman)"],
                               id="omics-demo-btn", color="outline-warning", size="sm", className="mt-3"),
                ])
            ]),
        ], color="#7c3aed"),

        # Entegrasyon Parametreleri
        _card("Entegrasyon Yöntemi", "fa-cogs", [
            dbc.Row([
                dbc.Col([
                    dbc.Label("Entegrasyon Yöntemi"),
                    dcc.Dropdown(
                        id="omics-method",
                        options=[
                            {"label": "Erken Füzyon (Concatenation)", "value": "early"},
                            {"label": "PCA Tabanlı Entegrasyon", "value": "pca"},
                            {"label": "Korelasyon Analizi", "value": "corr"},
                        ],
                        value="pca",
                    ),
                ], width=4),
                dbc.Col([
                    dbc.Label("Normalize Et"),
                    dcc.Dropdown(
                        id="omics-normalize",
                        options=[{"label": "Z-Score", "value": "zscore"},
                                 {"label": "Min-Max", "value": "minmax"},
                                 {"label": "Yok", "value": "none"}],
                        value="zscore",
                    ),
                ], width=3),
                dbc.Col([
                    dbc.Label("PCA Bileşen Sayısı"),
                    dbc.Input(id="omics-n-pca", type="number", value=10, min=2, max=50),
                ], width=2),
                dbc.Col([
                    dbc.Button([html.I(className="fas fa-play me-2"), "Entegre Et"],
                               id="omics-run-btn", color="warning", className="mt-4"),
                ], width=3),
            ]),
        ], color="#7c3aed"),

        dcc.Loading(type="circle", children=[
            html.Div(id="omics-results", style={"display": "none"}, children=[

                # Katman Özet Kartları
                html.Div(id="omics-summary-cards", className="mb-4"),

                # PCA Scatter
                _card("Entegre PCA Skoru", "fa-chart-scatter", [
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="omics-pca-scatter"), width=6),
                        dbc.Col(dcc.Graph(id="omics-variance-bar"), width=6),
                    ])
                ], color="#0f3460"),

                # Katmanlar arası korelasyon ısı haritası
                _card("Katmanlar Arası Korelasyon (Özellik Bazında)", "fa-th", [
                    dcc.Graph(id="omics-corr-heatmap"),
                ], color="#0f3460"),

                # Veri istatistikleri
                _card("Katman İstatistikleri", "fa-table", [
                    html.Div(id="omics-stats-table"),
                ], color="#0f3460"),
            ]),
        ]),

        dcc.Store(id="omics-data-store"),
    ], fluid=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_csv(contents):
    _, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    return pd.read_csv(io.StringIO(decoded.decode("utf-8")), index_col=0)


def _normalize(df, method):
    if method == "zscore":
        return pd.DataFrame(StandardScaler().fit_transform(df), index=df.index, columns=df.columns)
    elif method == "minmax":
        mn, mx = df.min(), df.max()
        return (df - mn) / (mx - mn + 1e-9)
    return df


def _generate_demo():
    """4 katman sentetik veri — 80 örnek."""
    np.random.seed(0)
    n = 80
    samples = [f"Sample_{i}" for i in range(n)]
    groups = np.array(["A"] * 40 + ["B"] * 40)

    layers = {}
    for layer, n_feat in [("Genomik", 200), ("Transkriptomik", 500),
                           ("Proteomik", 150), ("Metabolomik", 100)]:
        X = np.random.randn(n, n_feat)
        # Grup farkı ekle
        X[groups == "B", :n_feat // 5] += 2
        cols = [f"{layer[:3]}_{i}" for i in range(n_feat)]
        layers[layer] = pd.DataFrame(X, index=samples, columns=cols)
    return layers, groups


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _upload_callback(layer_name):
    @app.callback(
        Output(f"omics-status-{layer_name}", "children"),
        Input(f"omics-upload-{layer_name}", "contents"),
        State(f"omics-upload-{layer_name}", "filename"),
        prevent_initial_call=True,
    )
    def _cb(contents, filename):
        if not contents:
            return ""
        try:
            df = _parse_csv(contents)
            return html.Span(f"✓ {filename} ({df.shape[0]}×{df.shape[1]})", className="text-success")
        except Exception as e:
            return html.Span(f"✗ {e}", className="text-danger")
    return _cb


for _layer in OMICS_LAYERS:
    _upload_callback(_layer)


@app.callback(
    Output("omics-data-store", "data"),
    Output("omics-results", "style"),
    Output("omics-pca-scatter", "figure"),
    Output("omics-variance-bar", "figure"),
    Output("omics-corr-heatmap", "figure"),
    Output("omics-stats-table", "children"),
    Output("omics-summary-cards", "children"),
    Input("omics-run-btn", "n_clicks"),
    Input("omics-demo-btn", "n_clicks"),
    State("omics-upload-genomik", "contents"),
    State("omics-upload-transkriptomik", "contents"),
    State("omics-upload-proteomik", "contents"),
    State("omics-upload-metabolomik", "contents"),
    State("omics-method", "value"),
    State("omics-normalize", "value"),
    State("omics-n-pca", "value"),
    prevent_initial_call=True,
)
def run_integration(run_clicks, demo_clicks, g_cont, t_cont, p_cont, m_cont,
                    method, normalize, n_pca):
    from dash import ctx
    triggered = ctx.triggered_id

    try:
        if triggered == "omics-demo-btn":
            layers_dict, groups = _generate_demo()
        else:
            raw = {"Genomik": g_cont, "Transkriptomik": t_cont,
                   "Proteomik": p_cont, "Metabolomik": m_cont}
            available = {k: _parse_csv(v) for k, v in raw.items() if v}
            if len(available) < 2:
                return None, {"display": "none"}, {}, {}, {}, "En az 2 katman gerekli.", []
            # Ortak örnekler
            common_idx = list(set.intersection(*[set(df.index) for df in available.values()]))
            layers_dict = {k: df.loc[common_idx] for k, df in available.items()}
            groups = None

        # Normalizasyon
        norm_layers = {k: _normalize(df, normalize) for k, df in layers_dict.items()}

        # Entegrasyon
        combined = pd.concat(list(norm_layers.values()), axis=1)
        n_components = min(int(n_pca or 10), combined.shape[0] - 1, combined.shape[1])
        pca = PCA(n_components=n_components)
        scores = pca.fit_transform(combined.fillna(0))
        explained = pca.explained_variance_ratio_

        pca_df = pd.DataFrame(scores[:, :2], columns=["PC1", "PC2"], index=combined.index)
        pca_df["Grup"] = groups if groups is not None else "Bilinmiyor"

        # PCA scatter
        fig_pca = px.scatter(
            pca_df, x="PC1", y="PC2", color="Grup",
            title=f"Entegre PCA ({method.upper()}) — PC1 vs PC2",
            color_discrete_sequence=["#6366f1", "#f59e0b"],
        )

        # Varyans bar
        var_df = pd.DataFrame({
            "Bileşen": [f"PC{i+1}" for i in range(len(explained))],
            "Açıklanan Varyans (%)": explained * 100,
        })
        fig_var = px.bar(var_df, x="Bileşen", y="Açıklanan Varyans (%)",
                         title="PCA Açıklanan Varyans",
                         color="Açıklanan Varyans (%)", color_continuous_scale="Blues")

        # Korelasyon ısı haritası (katman ortalamaları)
        layer_means = pd.DataFrame({k: df.mean(axis=1) for k, df in norm_layers.items()})
        corr_matrix = layer_means.corr()
        fig_corr = go.Figure(go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns.tolist(),
            y=corr_matrix.index.tolist(),
            colorscale="RdBu",
            zmin=-1, zmax=1,
            text=np.round(corr_matrix.values, 3),
            texttemplate="%{text}",
        ))
        fig_corr.update_layout(title="Katmanlar Arası Korelasyon Matrisi")

        # İstatistik tablosu
        stats_rows = []
        for layer, df in layers_dict.items():
            stats_rows.append({
                "Katman": layer,
                "Örnek Sayısı": df.shape[0],
                "Özellik Sayısı": df.shape[1],
                "Ortalama İfade": f"{df.mean().mean():.3f}",
                "Std": f"{df.std().mean():.3f}",
                "Eksik Değer (%)": f"{df.isna().mean().mean() * 100:.1f}%",
            })
        stats_df = pd.DataFrame(stats_rows)
        table = dbc.Table.from_dataframe(stats_df, striped=True, bordered=True,
                                         hover=True, responsive=True, size="sm")

        # Özet kartları
        summary_cards = dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P(layer, className="text-muted small mb-1"),
                    html.H5(f"{df.shape[0]} × {df.shape[1]}", className="fw-bold mb-0",
                            style={"color": OMICS_COLORS.get(layer, "#666")}),
                    html.Small("örnek × özellik"),
                ])
            ], className="text-center shadow-sm"), width=3)
            for layer, df in layers_dict.items()
        ])

        return (combined.to_dict(), {"display": "block"},
                fig_pca, fig_var, fig_corr, table, summary_cards)

    except Exception as e:
        return None, {"display": "none"}, {}, {}, {}, str(e), []

@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n_clicks, is_open):
    return not is_open