import json
import re
import warnings

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update, ALL
from django_plotly_dash import DjangoDash
from dash_apps.i18n_helper import t


from billing.dash_helpers import build_confirm_modal
warnings.filterwarnings("ignore")

app = DjangoDash(
    "PharmacoGenomicsApp",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
)

# Örnek araştırma konuları (kullanıcıya fikir vermek için)
EXAMPLE_QUERIES = ["CYP450", "CYP2D6", "CYP2C19", "TPMT", "DPYD",
                   "HLA-B*57:01", "Warfarin", "Klopidogrel"]

RISK_META = {
    "risk": ("danger", "#ef4444", "fa-times-circle text-danger"),
    "caution": ("warning", "#f59e0b", "fa-exclamation-triangle text-warning"),
    "normal": ("success", "#10b981", "fa-check-circle text-success"),
}


def _card(title, icon, children):
    return dbc.Card([
        dbc.CardHeader(html.H5([html.I(className=f"fas {icon} me-2"), title],
                                className="mb-0 text-white"),
                       style={"background": "linear-gradient(135deg,#4c1d95,#5b21b6)"}),
        dbc.CardBody(children),
    ], className="mb-4 shadow")


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def create_pharmacogenomics_layout(lang='en'):
    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='pgx-lang-store', data=lang),
        build_confirm_modal('pgx-modal', lang=lang),
        html.H2([html.I(className="fas fa-pills me-2"), t('pgx_title', lang)],
                style={"color": "#7c3aed"}, className="my-4 fw-bold"),
        html.P(
            t('pgx_desc', lang),
            className="text-muted mb-4",
        ),

        _card(t('pgx_card_research', lang), "fa-search", [
            dbc.InputGroup([
                dbc.Input(
                    id="pgx-query-input",
                    placeholder=t('pgx_placeholder', lang),
                    type="text", debounce=True,
                ),
                dbc.Button([html.I(className="fas fa-dna me-2"), t('pgx_search_btn', lang)],
                           id="pgx-search-btn", color="primary",
                           style={"background": "#7c3aed", "border": "none"}),
            ]),
            html.Div([
                html.Small(t('pgx_examples_label', lang), className="text-muted me-1"),
                *[dbc.Badge(q, id={"type": "pgx-example", "index": i},
                            color="light", text_color="primary",
                            className="me-1 mb-1",
                            style={"cursor": "pointer", "border": "1px solid #7c3aed"})
                  for i, q in enumerate(EXAMPLE_QUERIES)],
            ], className="mt-2"),
        ]),

        dcc.Loading(id="pgx-loading", type="circle", children=[
            html.Div(id="pgx-results"),
        ]),

        dcc.Store(id="pgx-store"),
    ], fluid=True)


# ---------------------------------------------------------------------------
# Gemini araştırma fonksiyonu
# ---------------------------------------------------------------------------

def _build_prompt(query, lang='en'):
    if lang == 'tr':
        L_summary_fam = "Ailenin genel açıklaması (Türkçe, 3-4 cümle). İlaç metabolizmasındaki rolü."
        L_role = "Bu enzimin kısa açıklaması ve metabolize ettiği ilaç sınıfları"
        L_notes_fam = "Aile geneli klinik öneriler (Türkçe)"
        L_summary_single = "2-3 cümlelik açıklama (Türkçe)"
        L_notes_single = "Klinik öneriler (Türkçe, 2-4 cümle)"
        L_alltext = "Tüm metinler Türkçe"
    else:
        L_summary_fam = "General description of the family (English, 3-4 sentences). Its role in drug metabolism."
        L_role = "Short description of this enzyme and the drug classes it metabolizes"
        L_notes_fam = "Family-wide clinical recommendations (English)"
        L_summary_single = "2-3 sentence description (English)"
        L_notes_single = "Clinical recommendations (English, 2-4 sentences)"
        L_alltext = "All text in English"
    return f"""You are an expert pharmacogenomics assistant.
The term given to you may be one of three categories:

1. SUPERFAMILY / GENE FAMILY (e.g. "CYP450", "CYP", "UGT", "SLCO") →
   In this case use mode="family" and list the important sub-enzymes of the family.
2. SINGLE ENZYME/GENE (e.g. "CYP2D6", "TPMT", "DPYD") →
   use mode="single", detail the variants and affected drugs.
3. DRUG or ALLELE (e.g. "Warfarin", "HLA-B*57:01") →
   use mode="single".

Term: "{query}"

Synthesize PharmGKB, CPIC and ClinVar information.

Return your answer ONLY as valid JSON. Do NOT add Markdown, ``` marks, or explanations.

IF mode="family" use this format:
{{
  "term": "{query}",
  "mode": "family",
  "type": "superfamily",
  "summary": "{L_summary_fam}",
  "members": [
    {{
      "enzyme": "CYP2D6",
      "role": "{L_role}",
      "key_variants": [
        {{"variant": "*1", "phenotype": "Normal Metabolizer", "risk": "normal"}},
        {{"variant": "*4", "phenotype": "Poor Metabolizer", "risk": "risk"}}
      ],
      "key_drugs": ["Codeine", "Tramadol", "Tamoxifen"]
    }}
  ],
  "clinical_notes": "{L_notes_fam}"
}}

IF mode="single" use this format:
{{
  "term": "{query}",
  "mode": "single",
  "type": "enzyme | drug | allele",
  "summary": "{L_summary_single}",
  "phenotypes": [
    {{"variant": "*1", "phenotype": "Normal Metabolizer", "risk": "normal"}},
    {{"variant": "*4", "phenotype": "Poor Metabolizer", "risk": "risk"}}
  ],
  "drugs": [
    {{"name": "Codeine", "effect": "Risk of ineffective analgesia", "risk": "risk"}}
  ],
  "clinical_notes": "{L_notes_single}"
}}

RULES:
- "risk" field only: "normal", "caution", "risk"
- In family mode list at least 4-6 important sub-enzymes, give each 2-4 variants
- {L_alltext}
- Be scientifically accurate, do not fabricate information"""


def _parse_json(text):
    """Gemini cevabından JSON çıkar — olası ``` işaretlerini temizler."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # İlk { ve son } arasını al
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def _research(query, lang='en'):
    from ai_engine.services import generate_with_pool

    safety = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    text, _key = generate_with_pool(
        _build_prompt(query, lang), service_name="Google Gemini", model_name="gemini-3.5-flash",
        safety_settings=safety)
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sonuç render
# ---------------------------------------------------------------------------

def _render_family(data, lang='en'):
    """Süper aile modu — alt enzimleri listeler."""
    term = data.get("term", "—")
    summary = data.get("summary", "")
    members = data.get("members", [])
    notes = data.get("clinical_notes", "")

    summary_card = _card(f"{term} {t('pgx_superfamily_suffix', lang)}", "fa-sitemap", [
        dbc.Badge(t('pgx_superfamily_badge', lang), color="secondary", className="mb-2"),
        html.P(summary, className="mb-0"),
        html.Hr(),
        html.Small(t('pgx_members_found', lang).format(n=len(members)),
                   className="text-muted"),
    ])

    member_cards = []
    for m in members:
        enzyme = m.get("enzyme", "—")
        role = m.get("role", "")
        variants = m.get("key_variants", [])
        drugs = m.get("key_drugs", [])

        # Varyant rozetleri
        variant_badges = []
        for v in variants:
            risk = v.get("risk", "normal")
            badge_color, _, _ = RISK_META.get(risk, RISK_META["normal"])
            variant_badges.append(
                dbc.Badge(f"{v.get('variant', '')} · {v.get('phenotype', '')}",
                          color=badge_color, className="me-1 mb-1")
            )

        member_cards.append(
            dbc.Col(dbc.Card([
                dbc.CardHeader(html.Strong(enzyme, style={"color": "#7c3aed"})),
                dbc.CardBody([
                    html.P(role, className="small text-muted"),
                    html.Div([
                        html.Strong(t('pgx_variants_label', lang), className="small"),
                        *variant_badges,
                    ], className="mb-2") if variant_badges else None,
                    html.Div([
                        html.Strong(t('pgx_drugs_label', lang), className="small"),
                        html.Span(", ".join(drugs), className="small text-secondary"),
                    ]) if drugs else None,
                ]),
            ], className="h-100 shadow-sm"), width=6, className="mb-3")
        )

    members_section = _card(t('pgx_subenzymes', lang), "fa-dna", [dbc.Row(member_cards)])

    notes_card = _card(t('pgx_clinical', lang), "fa-stethoscope", [
        html.P(notes or t('pgx_no_notes', lang), className="mb-0"),
    ]) if notes else None

    disclaimer = dbc.Alert([
        html.I(className="fas fa-exclamation-circle me-2"),
        t('pgx_disclaimer', lang),
    ], color="warning", className="small")

    return html.Div([c for c in [summary_card, members_section, notes_card,
                                  disclaimer] if c is not None])


def _render_results(data, lang='en'):
    # Mod ayrımı — aile mi tekil mi?
    if data.get("mode") == "family":
        return _render_family(data, lang)

    term = data.get("term", "—")
    term_type = data.get("type", "")
    summary = data.get("summary", "")
    phenotypes = data.get("phenotypes", [])
    drugs = data.get("drugs", [])
    notes = data.get("clinical_notes", "")

    # Özet
    summary_card = _card(f"{term}", "fa-dna", [
        dbc.Badge(term_type.upper(), color="secondary", className="mb-2"),
        html.P(summary, className="mb-0"),
    ])

    # Fenotipler / varyantlar
    if phenotypes:
        pheno_items = []
        for p in phenotypes:
            risk = p.get("risk", "normal")
            badge_color, color, _ = RISK_META.get(risk, RISK_META["normal"])
            pheno_items.append(
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6(p.get("variant", "—"), style={"color": color},
                            className="mb-1 fw-bold"),
                    dbc.Badge(p.get("phenotype", ""), color=badge_color),
                ]), className="text-center shadow-sm h-100"), width=3, className="mb-2")
            )
        pheno_card = _card(t('pgx_pheno_card', lang), "fa-code-branch",
                           [dbc.Row(pheno_items)])
    else:
        pheno_card = None

    # İlaçlar
    if drugs:
        drug_items = []
        for d in drugs:
            risk = d.get("risk", "normal")
            badge_color, color, icon = RISK_META.get(risk, RISK_META["normal"])
            drug_items.append(
                dbc.Col(dbc.Card(dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.I(className=f"fas {icon} fa-2x"), width=2),
                        dbc.Col([
                            html.Strong(d.get("name", "")),
                            html.P(d.get("effect", ""), className="small mb-0 text-muted"),
                        ], width=10),
                    ], align="center"),
                ]), className="mb-2 shadow-sm"), width=6)
            )
        drug_card = _card(t('pgx_drugs_card', lang), "fa-prescription-bottle-alt",
                          [dbc.Row(drug_items)])
    else:
        drug_card = None

    # Klinik notlar
    notes_card = _card(t('pgx_clinical', lang), "fa-stethoscope", [
        html.P(notes or t('pgx_no_notes', lang), className="mb-0"),
    ]) if notes else None

    # Uyarı
    disclaimer = dbc.Alert([
        html.I(className="fas fa-exclamation-circle me-2"),
        t('pgx_disclaimer', lang),
    ], color="warning", className="small")

    return html.Div([c for c in [summary_card, pheno_card, drug_card,
                                  notes_card, disclaimer] if c is not None])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("pgx-query-input", "value"),
    Input({"type": "pgx-example", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def fill_example(n_clicks):
    if not n_clicks or not any(n_clicks):
        return no_update
    # django_plotly_dash ctx.triggered_id desteklemez —
    # tıklanan rozeti n_clicks listesinden bul
    import dash
    triggered = dash.callback_context.triggered
    if not triggered or not triggered[0]["value"]:
        return no_update
    # prop_id formatı: '{"index":2,"type":"pgx-example"}.n_clicks'
    prop_id = triggered[0]["prop_id"]
    try:
        json_part = prop_id.rsplit(".", 1)[0]
        idx = json.loads(json_part)["index"]
        return EXAMPLE_QUERIES[idx]
    except Exception:
        return no_update


@app.callback(
    Output("pgx-results", "children"),
    Output("pgx-store", "data"),
    Input("pgx-modal-confirm", "n_clicks"),
    State("pgx-query-input", "value"),
    State("pgx-lang-store", "data"),
    prevent_initial_call=True,
)
def do_research(confirm_clicks, query, lang, **kwargs):
    lang = lang or 'en'
    if not query or not query.strip():
        return dbc.Alert(t('pgx_empty_query', lang),
                         color="warning"), no_update

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_pharmacogenomics', cost=5,
                             description=t('pgx_charge_desc', lang))
    if not ok:
        return msg, no_update

    try:
        data = _research(query.strip(), lang)
        return _render_results(data, lang), data
    except json.JSONDecodeError:
        return dbc.Alert(
            t('pgx_parse_error', lang), color="danger"), no_update
    except Exception as e:
        return dbc.Alert(f"{t('pgx_error_prefix', lang)}: {e}", color="danger"), no_update


@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n, is_open):
    return not is_open


@app.callback(Output("pharmacogenomics", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:pharmacogenomics')
    except Exception:
        return False


# --- Kredi onay modalı: arama butonu veya Enter modalı açar ---
@app.callback(
    Output('pgx-modal', 'is_open'),
    Output('pgx-modal-body', 'children'),
    Output('pgx-modal-confirm', 'disabled'),
    Input('pgx-search-btn', 'n_clicks'),
    Input('pgx-query-input', 'n_submit'),
    Input('pgx-modal-cancel', 'n_clicks'),
    Input('pgx-modal-confirm', 'n_clicks'),
    State('pgx-query-input', 'value'),
    State('pgx-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_pgx_modal(search_click, submit_n, cancel_click, confirm_click, query, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id in ('pgx-search-btn', 'pgx-query-input'):
        if not query or not query.strip():
            return True, dbc.Alert(t('pgx_empty_query', lang),
                                   color="warning", className="mb-0"), True
        body, can_proceed = confirm_modal_body(kwargs, 'bio_pharmacogenomics', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, no_update, no_update
