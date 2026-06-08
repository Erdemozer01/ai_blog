import base64
import io
import warnings

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash

warnings.filterwarnings("ignore")

app = DjangoDash(
    "VariantPrioritizationApp",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
)

# ClinVar/CIViC benzeri bilgi tabanı (örnek varyantlar)
KNOWLEDGE_BASE = {
    "BRCA1": {"disease": "Meme/Yumurtalık Kanseri", "actionable": True,
              "drugs": ["Olaparib", "Talazoparib"], "evidence": "PharmGKB 1A"},
    "BRCA2": {"disease": "Meme/Pankreas Kanseri", "actionable": True,
              "drugs": ["Olaparib"], "evidence": "CIViC A"},
    "KRAS": {"disease": "Akciğer/Kolorektal Kanser", "actionable": True,
             "drugs": ["Sotorasib (G12C)"], "evidence": "CIViC A"},
    "TP53": {"disease": "Çok sayıda kanser tipi", "actionable": False,
             "drugs": [], "evidence": "ClinVar Pathogenic"},
    "EGFR": {"disease": "Akciğer Kanseri", "actionable": True,
             "drugs": ["Erlotinib", "Gefitinib", "Osimertinib"], "evidence": "CIViC A"},
    "ALK": {"disease": "Akciğer Kanseri", "actionable": True,
            "drugs": ["Krizotinib", "Alektinib"], "evidence": "CIViC A"},
    "BRAF": {"disease": "Melanom/Kolorektal", "actionable": True,
             "drugs": ["Vemurafenib", "Dabrafenib"], "evidence": "CIViC A"},
    "PIK3CA": {"disease": "Meme Kanseri", "actionable": True,
               "drugs": ["Alpelisib"], "evidence": "CIViC B"},
    "PTEN": {"disease": "Çok sayıda kanser", "actionable": False,
             "drugs": [], "evidence": "ClinVar Pathogenic"},
    "RET": {"disease": "Tiroid/Akciğer Kanseri", "actionable": True,
            "drugs": ["Selpercatinib"], "evidence": "CIViC A"},
    "CFTR": {"disease": "Kistik Fibrozis", "actionable": True,
             "drugs": ["İvakaftor", "Lumakaftor"], "evidence": "PharmGKB 1A"},
    "CYP2C9": {"disease": "Warfarin Toksisitesi", "actionable": True,
               "drugs": ["Warfarin (doz ayarı)"], "evidence": "PharmGKB 1A"},
    "DPYD": {"disease": "5-FU Toksisitesi", "actionable": True,
             "drugs": ["Kapesitabin (doz azalt)"], "evidence": "PharmGKB 1A"},
    "TPMT": {"disease": "Tiopürin Toksisitesi", "actionable": True,
             "drugs": ["Azatioprin (doz ayarı)"], "evidence": "PharmGKB 1A"},
    "HLA-B": {"disease": "İlaç Aşırı Duyarlılığı", "actionable": True,
              "drugs": ["Abakavir", "Karbamazepin"], "evidence": "PharmGKB 1A"},
}

CONSEQUENCE_SCORES = {
    "stop_gained": 10, "frameshift": 9, "splice_site": 8,
    "missense": 5, "inframe_indel": 4, "synonymous": 1,
    "5_prime_utr": 2, "3_prime_utr": 1, "intron": 0,
}

CLINVAR_SCORES = {
    "Pathogenic": 10, "Likely pathogenic": 7,
    "Uncertain significance": 3, "Likely benign": 1, "Benign": 0,
}


def _card(title, icon, children):
    return dbc.Card([
        dbc.CardHeader(html.H5([html.I(className=f"fas {icon} me-2"), title],
                               className="mb-0 text-white"),
                       style={"background": "linear-gradient(135deg,#1e3a5f,#1e40af)"}),
        dbc.CardBody(children),
    ], className="mb-4 shadow")


def create_variant_layout():
    return dbc.Container([
        html.H2([html.I(className="fas fa-dna me-2 text-primary"),
                 "Varyant Önceliklendirme (Variant Prioritization)"],
                className="my-4 fw-bold"),
        html.P(
            "WGS/WES çıktısından gelen varyantları ClinVar, CIViC ve PharmGKB bilgi "
            "tabanlarıyla karşılaştırarak klinik öneme göre sıralayın.",
            className="text-muted mb-4",
        ),

        _card("Varyant Girişi", "fa-upload", [
            dbc.Tabs([
                dbc.Tab(label="Manuel Giriş", tab_id="manual", children=[
                    dbc.Textarea(
                        id="variant-manual-input",
                        placeholder="Her satıra bir varyant:\nGEN\tKROMAZOM\tPOZİSYON\tREF\tALT\tCONSEQUENCE\tCLINVAR\n"
                                    "BRCA1\tchr17\t43094464\tG\tA\tmissense\tPathogenic\n"
                                    "TP53\tchr17\t7674220\tC\tT\tstop_gained\tPathogenic",
                        rows=6, className="font-monospace small",
                    ),
                    dbc.Button([html.I(className="fas fa-play me-2"), "Analiz Et"],
                               id="variant-manual-btn", color="primary", className="mt-2"),
                ]),
                dbc.Tab(label="VCF / TSV Yükle", tab_id="upload", children=[
                    dcc.Upload(
                        id="variant-upload",
                        children=html.Div(["📂 TSV/CSV VCF yükle"],
                                          className="text-center py-3"),
                        style={"border": "2px dashed #3b82f6", "borderRadius": "8px",
                               "cursor": "pointer", "background": "#eff6ff"},
                        multiple=False,
                    ),
                    html.Div(id="variant-upload-status", className="mt-2"),
                ]),
                dbc.Tab(label="Demo Veri", tab_id="demo", children=[
                    dbc.Button([html.I(className="fas fa-flask me-2"),
                                "Demo Varyantlar Yükle (20 varyant)"],
                               id="variant-demo-btn", color="outline-primary", className="mt-2"),
                ]),
            ], id="variant-input-tabs", active_tab="manual"),
        ]),

        dcc.Loading(type="circle", children=[
            html.Div(id="variant-results", style={"display": "none"}, children=[

                # Özet Metrikler
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("Toplam Varyant", className="text-muted small mb-1"),
                        html.H4(id="vm-total", className="fw-bold text-primary mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("Patolojik / Olası Patolojik", className="text-muted small mb-1"),
                        html.H4(id="vm-pathogenic", className="fw-bold text-danger mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("Klinik Eyleme Geçilebilir", className="text-muted small mb-1"),
                        html.H4(id="vm-actionable", className="fw-bold text-success mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P("İlaç Eşleşmesi", className="text-muted small mb-1"),
                        html.H4(id="vm-druggable", className="fw-bold text-warning mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                ], className="mb-4"),

                _card("Öncelik Skoru Dağılımı", "fa-chart-bar", [
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="variant-score-dist"), width=6),
                        dbc.Col(dcc.Graph(id="variant-consequence-pie"), width=6),
                    ]),
                ]),

                _card("Önceliklendirilmiş Varyant Tablosu", "fa-table", [
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Filtrele"),
                            dcc.Dropdown(
                                id="variant-filter",
                                options=[
                                    {"label": "Tümü", "value": "all"},
                                    {"label": "Yalnızca Patolojik", "value": "pathogenic"},
                                    {"label": "Eyleme Geçilebilir", "value": "actionable"},
                                    {"label": "İlaç Hedefi Var", "value": "druggable"},
                                ],
                                value="all", clearable=False,
                            ),
                        ], width=4),
                    ]),
                    html.Div(id="variant-table", className="mt-3"),
                ]),

                _card("Klinik Karar Özeti", "fa-stethoscope", [
                    html.Div(id="variant-clinical-summary"),
                ]),
            ]),
        ]),

        dcc.Store(id="variant-data-store"),
        dcc.Store(id="click-memory-store"),
    ], fluid=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _priority_score(row):
    conseq_score = CONSEQUENCE_SCORES.get(str(row.get("consequence", "")).lower(), 0)
    clinvar_score = CLINVAR_SCORES.get(str(row.get("clinvar", "")), 0)
    kb = KNOWLEDGE_BASE.get(str(row.get("gene", "")), {})
    actionable_bonus = 10 if kb.get("actionable") else 0
    drug_bonus = 5 if kb.get("drugs") else 0
    return conseq_score + clinvar_score + actionable_bonus + drug_bonus


def _parse_variants_text(text):
    lines = [l.strip() for l in text.strip().split("\n") if l.strip() and not l.startswith("#")]
    if not lines:
        return None

    # Başlık (header) kontrolü
    if lines[0].split("\t")[0].upper() in ["GEN", "GENE"]:
        lines = lines[1:]

    cols = ["gene", "chrom", "pos", "ref", "alt", "consequence", "clinvar"]
    records = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            row = dict(zip(cols, parts + [""] * max(0, len(cols) - len(parts))))
            records.append(row)
    return pd.DataFrame(records) if records else None


def _generate_demo():
    np.random.seed(7)
    genes = list(KNOWLEDGE_BASE.keys())
    consequences = list(CONSEQUENCE_SCORES.keys())
    clinvars = list(CLINVAR_SCORES.keys())
    n = 20
    df = pd.DataFrame({
        "gene": np.random.choice(genes, n),
        "chrom": [f"chr{np.random.randint(1, 22)}" for _ in range(n)],
        "pos": np.random.randint(1_000_000, 200_000_000, n),
        "ref": np.random.choice(list("ACGT"), n),
        "alt": np.random.choice(list("ACGT"), n),
        "consequence": np.random.choice(consequences, n, p=[0.05, 0.05, 0.05, 0.3,
                                                            0.1, 0.2, 0.1, 0.1, 0.05]),
        "clinvar": np.random.choice(clinvars, n, p=[0.15, 0.15, 0.4, 0.15, 0.15]),
    })
    return df


def _enrich(df):
    df = df.copy()
    df["priority_score"] = df.apply(_priority_score, axis=1)
    df["actionable"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("actionable", False))
    df["drugs"] = df["gene"].apply(lambda g: ", ".join(KNOWLEDGE_BASE.get(g, {}).get("drugs", [])))
    df["disease"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("disease", ""))
    df["evidence"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("evidence", ""))
    df["risk_class"] = df["clinvar"].apply(
        lambda c: "danger" if c in ("Pathogenic", "Likely pathogenic")
        else ("warning" if c == "Uncertain significance" else "success")
    )
    return df.sort_values("priority_score", ascending=False).reset_index(drop=True)


def _build_outputs(df):
    df = _enrich(df)
    n_total = len(df)
    n_path = len(df[df["clinvar"].isin(["Pathogenic", "Likely pathogenic"])])
    n_actionable = df["actionable"].sum()
    n_druggable = (df["drugs"] != "").sum()

    # Skor dağılımı
    fig_dist = px.histogram(df, x="priority_score", nbins=15,
                            title="Öncelik Skoru Dağılımı",
                            color_discrete_sequence=["#3b82f6"])

    # Consequence pasta
    fig_pie = px.pie(df, names="consequence", title="Varyant Sonuç Dağılımı",
                     color_discrete_sequence=px.colors.qualitative.Set3)

    return df, n_total, n_path, n_actionable, n_druggable, fig_dist, fig_pie


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("variant-data-store", "data"),
    Output("variant-results", "style"),
    Output("vm-total", "children"),
    Output("vm-pathogenic", "children"),
    Output("vm-actionable", "children"),
    Output("vm-druggable", "children"),
    Output("variant-score-dist", "figure"),
    Output("variant-consequence-pie", "figure"),
    Output("click-memory-store", "data"),
    Input("variant-manual-btn", "n_clicks"),
    Input("variant-demo-btn", "n_clicks"),
    Input("variant-upload", "contents"),
    State("variant-manual-input", "value"),
    State("click-memory-store", "data"),
    prevent_initial_call=True,
)
def analyze_variants(manual_clicks, demo_clicks, upload_contents, manual_text, click_memory):
    # Initialize state store if empty
    click_memory = click_memory or {"manual": None, "demo": None, "upload": None}

    triggered = None
    # Use string mapping representing file size and header to efficiently track file changes
    upload_sig = f"{len(upload_contents)}_{upload_contents[:50]}" if upload_contents else None

    # Determine which input triggered the callback safely bypassing dash.ctx
    if manual_clicks != click_memory.get("manual"):
        triggered = "manual"
        click_memory["manual"] = manual_clicks
    elif demo_clicks != click_memory.get("demo"):
        triggered = "demo"
        click_memory["demo"] = demo_clicks
    elif upload_sig != click_memory.get("upload"):
        triggered = "upload"
        click_memory["upload"] = upload_sig

    # Execution logic based on deduced trigger
    if triggered == "demo":
        df = _generate_demo()
    elif triggered == "manual" and manual_text:
        df = _parse_variants_text(manual_text)
        if df is None:
            return (None, {"display": "none"}, "—", "—", "—", "—", {}, {}, click_memory)
    elif triggered == "upload" and upload_contents:
        content_type, content_string = upload_contents.split(',')
        decoded = base64.b64decode(content_string).decode('utf-8')
        df = _parse_variants_text(decoded)
        if df is None:
            return (None, {"display": "none"}, "—", "—", "—", "—", {}, {}, click_memory)
    else:
        return (None, {"display": "none"}, "—", "—", "—", "—", {}, {}, click_memory)

    df_enriched, n_total, n_path, n_action, n_drug, fig_dist, fig_pie = _build_outputs(df)

    return (
        df_enriched.to_dict("records"), {"display": "block"},
        str(n_total), str(n_path), str(n_action), str(n_drug),
        fig_dist, fig_pie, click_memory
    )


@app.callback(
    Output("variant-table", "children"),
    Output("variant-clinical-summary", "children"),
    Input("variant-filter", "value"),
    State("variant-data-store", "data"),
    prevent_initial_call=True,
)
def update_table(filter_val, data):
    if not data:
        return no_update, no_update

    df = pd.DataFrame(data)

    if filter_val == "pathogenic":
        df = df[df["clinvar"].isin(["Pathogenic", "Likely pathogenic"])]
    elif filter_val == "actionable":
        df = df[df["actionable"] == True]
    elif filter_val == "druggable":
        df = df[df["drugs"] != ""]

    display_cols = ["gene", "chrom", "pos", "consequence", "clinvar",
                    "priority_score", "disease", "drugs", "evidence"]
    display_df = df[[c for c in display_cols if c in df.columns]].head(30)
    display_df.columns = ["Gen", "Krom", "Pozisyon", "Sonuç",
                          "ClinVar", "Öncelik", "Hastalık", "İlaçlar", "Kanıt"][:len(display_df.columns)]

    table = dbc.Table.from_dataframe(
        display_df, striped=True, bordered=True, hover=True,
        responsive=True, size="sm",
    )

    # Klinik özet
    top5 = df.head(5)
    clinical_items = []
    for _, row in top5.iterrows():
        risk_color = {"danger": "#ef4444", "warning": "#f59e0b", "success": "#10b981"}.get(
            row.get("risk_class", "success"), "#6b7280"
        )
        clinical_items.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        html.Strong(row.get("gene", ""), style={"color": risk_color}),
                        dbc.Badge(row.get("clinvar", ""), color=row.get("risk_class", "secondary"),
                                  className="ms-2"),
                    ], width=4),
                    dbc.Col(html.Small(row.get("disease", "—"), className="text-muted"), width=3),
                    dbc.Col(html.Small(f"💊 {row.get('drugs', '—') or '—'}",
                                       className="text-success"), width=3),
                    dbc.Col(html.Small(f"Skor: {row.get('priority_score', 0):.0f}",
                                       className="fw-bold"), width=2),
                ])
            ])
        )

    clinical = html.Div([
        html.H6("En Yüksek Öncelikli 5 Varyant:", className="text-muted mb-2"),
        dbc.ListGroup(clinical_items),
    ])

    return table, clinical


@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n_clicks, is_open):
    return not is_open