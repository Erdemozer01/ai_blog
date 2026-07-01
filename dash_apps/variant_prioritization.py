import base64
import warnings

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash
from dash_apps.i18n_helper import t
from billing.dash_helpers import build_confirm_modal

warnings.filterwarnings("ignore")

app = DjangoDash(
    "VariantPrioritizationApp",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
)

# ClinVar/CIViC benzeri bilgi tabanı (örnek varyantlar)
KNOWLEDGE_BASE = {
    "BRCA1": {"disease": {"tr": "Meme/Yumurtalık Kanseri", "en": "Breast/Ovarian Cancer"}, "actionable": True,
              "drugs": {"tr": ["Olaparib", "Talazoparib"], "en": ["Olaparib", "Talazoparib"]}, "evidence": "PharmGKB 1A"},
    "BRCA2": {"disease": {"tr": "Meme/Pankreas Kanseri", "en": "Breast/Pancreatic Cancer"}, "actionable": True,
              "drugs": {"tr": ["Olaparib"], "en": ["Olaparib"]}, "evidence": "CIViC A"},
    "KRAS": {"disease": {"tr": "Akciğer/Kolorektal Kanser", "en": "Lung/Colorectal Cancer"}, "actionable": True,
             "drugs": {"tr": ["Sotorasib (G12C)"], "en": ["Sotorasib (G12C)"]}, "evidence": "CIViC A"},
    "TP53": {"disease": {"tr": "Çok sayıda kanser tipi", "en": "Multiple cancer types"}, "actionable": False,
             "drugs": {"tr": [], "en": []}, "evidence": "ClinVar Pathogenic"},
    "EGFR": {"disease": {"tr": "Akciğer Kanseri", "en": "Lung Cancer"}, "actionable": True,
             "drugs": {"tr": ["Erlotinib", "Gefitinib", "Osimertinib"], "en": ["Erlotinib", "Gefitinib", "Osimertinib"]}, "evidence": "CIViC A"},
    "ALK": {"disease": {"tr": "Akciğer Kanseri", "en": "Lung Cancer"}, "actionable": True,
            "drugs": {"tr": ["Krizotinib", "Alektinib"], "en": ["Crizotinib", "Alectinib"]}, "evidence": "CIViC A"},
    "BRAF": {"disease": {"tr": "Melanom/Kolorektal", "en": "Melanoma/Colorectal"}, "actionable": True,
             "drugs": {"tr": ["Vemurafenib", "Dabrafenib"], "en": ["Vemurafenib", "Dabrafenib"]}, "evidence": "CIViC A"},
    "PIK3CA": {"disease": {"tr": "Meme Kanseri", "en": "Breast Cancer"}, "actionable": True,
               "drugs": {"tr": ["Alpelisib"], "en": ["Alpelisib"]}, "evidence": "CIViC B"},
    "PTEN": {"disease": {"tr": "Çok sayıda kanser", "en": "Multiple cancers"}, "actionable": False,
             "drugs": {"tr": [], "en": []}, "evidence": "ClinVar Pathogenic"},
    "RET": {"disease": {"tr": "Tiroid/Akciğer Kanseri", "en": "Thyroid/Lung Cancer"}, "actionable": True,
            "drugs": {"tr": ["Selpercatinib"], "en": ["Selpercatinib"]}, "evidence": "CIViC A"},
    "CFTR": {"disease": {"tr": "Kistik Fibrozis", "en": "Cystic Fibrosis"}, "actionable": True,
             "drugs": {"tr": ["İvakaftor", "Lumakaftor"], "en": ["Ivacaftor", "Lumacaftor"]}, "evidence": "PharmGKB 1A"},
    "CYP2C9": {"disease": {"tr": "Warfarin Toksisitesi", "en": "Warfarin Toxicity"}, "actionable": True,
               "drugs": {"tr": ["Warfarin (doz ayarı)"], "en": ["Warfarin (dose adj.)"]}, "evidence": "PharmGKB 1A"},
    "DPYD": {"disease": {"tr": "5-FU Toksisitesi", "en": "5-FU Toxicity"}, "actionable": True,
             "drugs": {"tr": ["Kapesitabin (doz azalt)"], "en": ["Capecitabine (dose reduction)"]}, "evidence": "PharmGKB 1A"},
    "TPMT": {"disease": {"tr": "Tiopürin Toksisitesi", "en": "Thiopurine Toxicity"}, "actionable": True,
             "drugs": {"tr": ["Azatioprin (doz ayarı)"], "en": ["Azathioprine (dose adj.)"]}, "evidence": "PharmGKB 1A"},
    "HLA-B": {"disease": {"tr": "İlaç Aşırı Duyarlılığı", "en": "Drug Hypersensitivity"}, "actionable": True,
              "drugs": {"tr": ["Abakavir", "Karbamazepin"], "en": ["Abacavir", "Carbamazepine"]}, "evidence": "PharmGKB 1A"},
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


def create_variant_layout(lang='en'):
    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='variant-lang-store', data=lang),
        build_confirm_modal('variant-manual-modal', lang=lang),
        build_confirm_modal('variant-demo-modal', lang=lang),
        html.H2([html.I(className="fas fa-dna me-2 text-primary"),
                 t('vp_title', lang)],
                className="my-4 fw-bold"),
        html.P(
            t('vp_desc', lang),
            className="text-muted mb-4",
        ),

        _card(t('vp_input_card', lang), "fa-upload", [
            dbc.Tabs([
                dbc.Tab(label=t('vp_tab_manual', lang), tab_id="manual", children=[
                    dbc.Textarea(
                        id="variant-manual-input",
                        placeholder=t('vp_manual_placeholder', lang),
                        rows=6, className="font-monospace small",
                    ),
                    dbc.Button([html.I(className="fas fa-play me-2"), t('vp_analyze_btn', lang)],
                               id="variant-manual-btn", color="primary", className="mt-2"),
                ]),
                dbc.Tab(label=t('vp_tab_upload', lang), tab_id="upload", children=[
                    dcc.Upload(
                        id="variant-upload",
                        children=html.Div([t('vp_upload_text', lang)],
                                          className="text-center py-3"),
                        style={"border": "2px dashed #3b82f6", "borderRadius": "8px",
                               "cursor": "pointer", "background": "#eff6ff"},
                        multiple=False,
                    ),
                    html.Div(id="variant-upload-status", className="mt-2"),
                ]),
                dbc.Tab(label=t('vp_tab_demo', lang), tab_id="demo", children=[
                    dbc.Button([html.I(className="fas fa-flask me-2"),
                                t('vp_demo_btn', lang)],
                               id="variant-demo-btn", color="outline-primary", className="mt-2"),
                ]),
            ], id="variant-input-tabs", active_tab="manual"),
        ]),

        dcc.Loading(type="circle", children=[
            html.Div(id="variant-results", style={"display": "none"}, children=[

                # Özet Metrikler
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P(t('vp_m_total', lang), className="text-muted small mb-1"),
                        html.H4(id="vm-total", className="fw-bold text-primary mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P(t('vp_m_pathogenic', lang), className="text-muted small mb-1"),
                        html.H4(id="vm-pathogenic", className="fw-bold text-danger mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P(t('vp_m_actionable', lang), className="text-muted small mb-1"),
                        html.H4(id="vm-actionable", className="fw-bold text-success mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.P(t('vp_m_druggable', lang), className="text-muted small mb-1"),
                        html.H4(id="vm-druggable", className="fw-bold text-warning mb-0"),
                    ]), className="text-center shadow-sm"), width=3),
                ], className="mb-4"),

                _card(t('vp_score_dist', lang), "fa-chart-bar", [
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="variant-score-dist"), width=6),
                        dbc.Col(dcc.Graph(id="variant-consequence-pie"), width=6),
                    ]),
                ]),

                _card(t('vp_table_card', lang), "fa-table", [
                    dbc.Row([
                        dbc.Col([
                            dbc.Label(t('vp_filter', lang)),
                            dcc.Dropdown(
                                id="variant-filter",
                                options=[
                                    {"label": t('vp_f_all', lang), "value": "all"},
                                    {"label": t('vp_f_path', lang), "value": "pathogenic"},
                                    {"label": t('vp_f_action', lang), "value": "actionable"},
                                    {"label": t('vp_f_drug', lang), "value": "druggable"},
                                ],
                                value="all", clearable=False,
                            ),
                        ], width=4),
                    ]),
                    html.Div(id="variant-table", className="mt-3"),
                ]),

                _card(t('vp_clinical_card', lang), "fa-stethoscope", [
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
    drug_bonus = 5 if kb.get("drugs", {}).get("en") else 0
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


def _enrich(df, lang='en'):
    df = df.copy()
    df["priority_score"] = df.apply(_priority_score, axis=1)
    df["actionable"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("actionable", False))
    df["drugs"] = df["gene"].apply(lambda g: ", ".join(KNOWLEDGE_BASE.get(g, {}).get("drugs", {}).get(lang, [])))
    df["disease"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("disease", {}).get(lang, ""))
    df["evidence"] = df["gene"].apply(lambda g: KNOWLEDGE_BASE.get(g, {}).get("evidence", ""))
    df["risk_class"] = df["clinvar"].apply(
        lambda c: "danger" if c in ("Pathogenic", "Likely pathogenic")
        else ("warning" if c == "Uncertain significance" else "success")
    )
    return df.sort_values("priority_score", ascending=False).reset_index(drop=True)


def _build_outputs(df, lang='en'):
    df = _enrich(df, lang)
    n_total = len(df)
    n_path = len(df[df["clinvar"].isin(["Pathogenic", "Likely pathogenic"])])
    n_actionable = df["actionable"].sum()
    n_druggable = (df["drugs"] != "").sum()

    # Skor dağılımı
    fig_dist = px.histogram(df, x="priority_score", nbins=15,
                            title=t('vp_score_dist', lang),
                            color_discrete_sequence=["#3b82f6"])

    # Consequence pasta
    fig_pie = px.pie(df, names="consequence", title=t('vp_pie_title', lang),
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
    Input("variant-manual-modal-confirm", "n_clicks"),
    Input("variant-demo-modal-confirm", "n_clicks"),
    Input("variant-upload", "contents"),
    State("variant-manual-input", "value"),
    State("click-memory-store", "data"),
    State("variant-lang-store", "data"),
    prevent_initial_call=True,
)
def analyze_variants(manual_clicks, demo_clicks, upload_contents, manual_text, click_memory, lang, **kwargs):
    lang = lang or 'en'
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

    # Geçerli veri var, analiz başlayacak — kredi düş
    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_variant', cost=5,
                             description=t('vp_charge_desc', lang))
    if not ok:
        return (msg, {"display": "none"}, "—", "—", "—", "—", {}, {}, click_memory)

    df_enriched, n_total, n_path, n_action, n_drug, fig_dist, fig_pie = _build_outputs(df, lang)

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
    State("variant-lang-store", "data"),
    prevent_initial_call=True,
)
def update_table(filter_val, data, lang):
    lang = lang or 'en'
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
    display_df.columns = [t('vp_col_gene', lang), t('vp_col_chrom', lang), t('vp_col_pos', lang),
                          t('vp_col_conseq', lang), t('vp_col_clinvar', lang), t('vp_col_priority', lang),
                          t('vp_col_disease', lang), t('vp_col_drugs', lang), t('vp_col_evidence', lang)][:len(display_df.columns)]

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
                    dbc.Col(html.Small(f"{t('vp_score_label', lang)}: {row.get('priority_score', 0):.0f}",
                                       className="fw-bold"), width=2),
                ])
            ])
        )

    clinical = html.Div([
        html.H6(t('vp_top5', lang), className="text-muted mb-2"),
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


@app.callback(Output("variant_prioritization", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:variant_prioritization')
    except Exception:
        return False


# --- Kredi onay modalı: variant-manual-btn ---
@app.callback(
    Output('variant-manual-modal', 'is_open'),
    Output('variant-manual-modal-body', 'children'),
    Output('variant-manual-modal-confirm', 'disabled'),
    Input('variant-manual-btn', 'n_clicks'),
    Input('variant-manual-modal-cancel', 'n_clicks'),
    Input('variant-manual-modal-confirm', 'n_clicks'),
    State('variant-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_variant_manual(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'variant-manual-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_variant', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: variant-demo-btn ---
@app.callback(
    Output('variant-demo-modal', 'is_open'),
    Output('variant-demo-modal-body', 'children'),
    Output('variant-demo-modal-confirm', 'disabled'),
    Input('variant-demo-btn', 'n_clicks'),
    Input('variant-demo-modal-cancel', 'n_clicks'),
    Input('variant-demo-modal-confirm', 'n_clicks'),
    State('variant-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_variant_demo(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'variant-demo-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_variant', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
