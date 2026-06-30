"""
Primer Tasarım Aracı (Primer3 tabanlı, lab standardı).

Özellikler:
  - DNA dizisi yapıştırma ile primer tasarımı
  - Gen adı/accession ile EBI ENA'dan dizi çekme (yedek)
  - Forward/Reverse primer çiftleri: dizi, Tm, GC%, ürün boyu
  - Opsiyonel AI yorumu (ai_engine havuzu, 5 kredi)
"""
import re
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, dash_table, Input, Output, State
from billing.dash_helpers import build_confirm_modal

app = DjangoDash('PrimerDesignApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True)


# ----------------------------- Çekirdek mantık -----------------------------

def clean_sequence(sequence):
    """Diziden ATGC dışındaki karakterleri temizler (FASTA başlığı, boşluk, sayı)."""
    lines = [ln for ln in sequence.splitlines() if not ln.strip().startswith('>')]
    joined = ''.join(lines)
    return re.sub(r'[^ATGCatgc]', '', joined).upper()


def design_primers_core(sequence, product_min=100, product_max=300,
                        len_min=18, len_max=25, num_return=5, lang='en'):
    """Primer3 ile primer çiftleri tasarlar. Hata durumunda {'error': ...} döner."""
    from dash_apps.i18n_helper import t, credit_label
    try:
        import primer3
    except ImportError:
        return {'error': t('primer_not_installed', lang)}
    seq = clean_sequence(sequence)
    if len(seq) < 50:
        return {'error': t('primer_too_short', lang)}
    if len(seq) > 10000:
        return {'error': t('primer_too_long', lang)}
    opt_size = max(len_min, min(len_max, round((len_min + len_max) / 2)))
    try:
        res = primer3.design_primers(
            {'SEQUENCE_ID': 'user_seq', 'SEQUENCE_TEMPLATE': seq},
            {
                'PRIMER_NUM_RETURN': num_return,
                'PRIMER_OPT_SIZE': opt_size,
                'PRIMER_MIN_SIZE': len_min, 'PRIMER_MAX_SIZE': len_max,
                'PRIMER_OPT_TM': 60.0, 'PRIMER_MIN_TM': 57.0, 'PRIMER_MAX_TM': 63.0,
                'PRIMER_MIN_GC': 40.0, 'PRIMER_MAX_GC': 60.0,
                'PRIMER_PRODUCT_SIZE_RANGE': [[product_min, product_max]],
            }
        )
    except Exception as e:
        return {'error': f'Primer tasarım hatası: {e}'}

    n = res.get('PRIMER_PAIR_NUM_RETURNED', 0)
    if n == 0:
        return {'error': t('primer_not_found', lang)}

    pairs = []
    for i in range(n):
        f_seq = res[f'PRIMER_LEFT_{i}_SEQUENCE']
        r_seq = res[f'PRIMER_RIGHT_{i}_SEQUENCE']
        pairs.append({
            'No': i + 1,
            'Forward (5→3)': f_seq,
            'Forward Uzunluk': len(f_seq),
            'Forward Tm': round(res[f'PRIMER_LEFT_{i}_TM'], 1),
            'Forward GC%': round(res[f'PRIMER_LEFT_{i}_GC_PERCENT'], 1),
            'Reverse (5→3)': r_seq,
            'Reverse Uzunluk': len(r_seq),
            'Reverse Tm': round(res[f'PRIMER_RIGHT_{i}_TM'], 1),
            'Reverse GC%': round(res[f'PRIMER_RIGHT_{i}_GC_PERCENT'], 1),
            'Ürün (bp)': res[f'PRIMER_PAIR_{i}_PRODUCT_SIZE'],
        })
    return {'pairs': pairs, 'seq_length': len(seq)}


def fetch_sequence_from_ebi(accession):
    """
    EBI ENA'dan accession/gen ID ile nükleotid dizisi çeker (FASTA).
    PythonAnywhere whitelist'inde .ebi.ac.uk var. Başarısızsa None döner.
    """
    import urllib.request
    acc = accession.strip()
    if not acc:
        return None, "Accession boş."
    url = f"https://www.ebi.ac.uk/ena/browser/api/fasta/{acc}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AIBlog-PrimerTool'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read().decode('utf-8', errors='ignore')
        seq = clean_sequence(data)
        if len(seq) < 50:
            return None, f"'{acc}' için yeterli dizi bulunamadı."
        return seq, None
    except Exception as e:
        return None, f"Dizi çekilemedi ({acc}): {e}. Lütfen diziyi elle yapıştırın."


# ----------------------------- Layout -----------------------------

def create_primer_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label
    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('primer-design-modal', lang=lang),
        build_confirm_modal('primer-ai-modal', lang=lang),
        # Dil bilgisini callback'lerin görmesi için store'da tut
        dcc.Store(id="primer-lang-store", data=lang),
        html.H2([html.I(className="fas fa-dna me-2"), t('primer_title', lang)],
                className="my-4"),
        html.P(t('primer_subtitle', lang), className="text-muted"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(t('input', lang)),
                    dbc.CardBody([
                        dbc.Label(t('primer_seq_label', lang)),
                        dbc.Textarea(id="primer-seq-input", rows=6,
                                     placeholder=t('primer_seq_placeholder', lang),
                                     className="mb-2", style={'fontFamily': 'monospace'}),

                        html.Div(t('primer_or', lang), className="text-center text-muted my-2"),

                        dbc.Label(t('primer_acc_label', lang)),
                        dbc.InputGroup([
                            dbc.Input(id="primer-acc-input",
                                      placeholder="örn: BC003596, NM_000546"),
                            dbc.Button(t('primer_fetch_btn', lang), id="primer-fetch-btn",
                                       color="secondary", n_clicks=0),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label(t('primer_prod_min', lang)),
                                dbc.Input(id="primer-prod-min", type="number",
                                          value=100, min=50, max=2000),
                            ], width=6),
                            dbc.Col([
                                dbc.Label(t('primer_prod_max', lang)),
                                dbc.Input(id="primer-prod-max", type="number",
                                          value=300, min=60, max=3000),
                            ], width=6),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label(t('primer_len_min', lang)),
                                dbc.Input(id="primer-len-min", type="number",
                                          value=18, min=15, max=35),
                            ], width=6),
                            dbc.Col([
                                dbc.Label(t('primer_len_max', lang)),
                                dbc.Input(id="primer-len-max", type="number",
                                          value=25, min=16, max=36),
                            ], width=6),
                        ], className="mb-3"),

                        dbc.Button([html.I(className="fas fa-cogs me-2"),
                                    f"{t('primer_design_btn', lang)} {credit_label('bio_primer_design', lang)}"],
                                   id="primer-design-btn", color="primary",
                                   className="w-100", n_clicks=0),
                    ]),
                ], className="shadow-sm mb-3"),
            ], md=4),

            dbc.Col([
                html.Div(id="primer-fetch-status", className="mb-2"),
                dcc.Loading(
                    html.Div(id="primer-results"),
                    type="default",
                ),
                html.Div(id="primer-ai-section", className="mt-3"),
                dcc.Loading(
                    html.Div(id="primer-ai-result", className="mt-3"),
                    type="default",
                ),
                dcc.Store(id="primer-seq-store"),
                dcc.Store(id="primer-results-store"),
            ], md=8),
        ]),
    ], fluid=True, className="pb-5")


# ----------------------------- Callbacks -----------------------------

@app.callback(
    [Output("primer-seq-input", "value"),
     Output("primer-fetch-status", "children")],
    Input("primer-fetch-btn", "n_clicks"),
    [State("primer-acc-input", "value"),
     State("primer-lang-store", "data")],
    prevent_initial_call=True,
)
def fetch_sequence(n_clicks, accession, lang):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not accession:
        return "", dbc.Alert(t('primer_acc_empty', lang), color="warning")
    seq, err = fetch_sequence_from_ebi(accession)
    if err:
        return "", dbc.Alert(err, color="danger")
    return seq, dbc.Alert(f"✓ {t('primer_fetched', lang)} ({len(seq)} {t('primer_fetch_then', lang)}",
                          color="success")


@app.callback(
    [Output("primer-results", "children"),
     Output("primer-results-store", "data"),
     Output("primer-seq-store", "data"),
     Output("primer-ai-section", "children")],
    Input('primer-design-modal-confirm', 'n_clicks'),
    [State("primer-seq-input", "value"),
     State("primer-prod-min", "value"),
     State("primer-prod-max", "value"),
     State("primer-len-min", "value"),
     State("primer-len-max", "value"),
     State("primer-lang-store", "data")],
    prevent_initial_call=True,
)
def run_design(n_clicks, sequence, pmin, pmax, lmin, lmax, lang, **kwargs):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not sequence:
        return dbc.Alert(t('primer_no_seq', lang), color="warning"), None, None, ""

    # Kredi kontrol + düşür (her tasarım işlemi 5 kredi)
    from billing.dash_helpers import try_charge
    ok, msg, _user = try_charge(kwargs, 'bio_primer_design', cost=5, lang=lang,
                                description="Primer tasarımı")
    if not ok:
        return msg, None, None, ""

    result = design_primers_core(sequence, product_min=int(pmin or 100),
                                 product_max=int(pmax or 300),
                                 len_min=int(lmin or 18), len_max=int(lmax or 25),
                                 lang=lang)
    if 'error' in result:
        return dbc.Alert(result['error'], color="danger"), None, None, ""

    pairs = result['pairs']
    # DataTable için: id'ler basit (ASCII), name'ler çeviriden
    col_defs = [
        {'name': t('primer_no', lang), 'id': 'no'},
        {'name': t('primer_fwd', lang), 'id': 'fwd'},
        {'name': t('primer_fwd_len', lang), 'id': 'fwd_len'},
        {'name': t('primer_fwd_tm', lang), 'id': 'fwd_tm'},
        {'name': t('primer_fwd_gc', lang), 'id': 'fwd_gc'},
        {'name': t('primer_rev', lang), 'id': 'rev'},
        {'name': t('primer_rev_len', lang), 'id': 'rev_len'},
        {'name': t('primer_rev_tm', lang), 'id': 'rev_tm'},
        {'name': t('primer_rev_gc', lang), 'id': 'rev_gc'},
        {'name': t('primer_product', lang), 'id': 'product'},
    ]
    table_data = [
        {
            'no': p['No'],
            'fwd': p['Forward (5→3)'],
            'fwd_len': p['Forward Uzunluk'],
            'fwd_tm': p['Forward Tm'],
            'fwd_gc': p['Forward GC%'],
            'rev': p['Reverse (5→3)'],
            'rev_len': p['Reverse Uzunluk'],
            'rev_tm': p['Reverse Tm'],
            'rev_gc': p['Reverse GC%'],
            'product': p['Ürün (bp)'],
        }
        for p in pairs
    ]
    table = dash_table.DataTable(
        data=table_data,
        columns=col_defs,
        style_cell={'fontFamily': 'monospace', 'fontSize': '13px',
                    'textAlign': 'center', 'padding': '6px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
        style_table={'overflowX': 'auto'},
    )

    results_card = dbc.Card([
        dbc.CardHeader([html.I(className="fas fa-check-circle text-success me-2"),
                        f"{len(pairs)} {t('primer_found', lang)} "
                        f"({t('primer_seq_len', lang)}: {result['seq_length']} "
                        f"{'baz' if lang == 'tr' else 'bases'})"]),
        dbc.CardBody(table),
    ], className="shadow-sm")

    credits_word = t('credits_required', lang)
    ai_button = dbc.Card(dbc.CardBody([
        html.P(t('primer_ai_prompt', lang), className="mb-2 text-muted"),
        dbc.Button([html.I(className="fas fa-robot me-2"),
                    f"{t('primer_ai_btn', lang)} {credit_label('bio_tool_ai', lang)}"],
                   id="primer-ai-btn", color="info", outline=True, n_clicks=0),
    ]), className="shadow-sm")

    return results_card, pairs, clean_sequence(sequence), ai_button


@app.callback(
    Output("primer-ai-result", "children"),
    Input('primer-ai-modal-confirm', 'n_clicks'),
    [State("primer-results-store", "data"),
     State("primer-seq-store", "data"),
     State("primer-lang-store", "data")],
    prevent_initial_call=True,
)
def ai_comment(n_clicks, pairs, seq, lang, **kwargs):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not n_clicks or not pairs:
        return ""

    # AI yorumu ayrı işlem — 5 kredi
    from billing.dash_helpers import try_charge
    ok, msg, _user = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                                description="Primer AI yorumu")
    if not ok:
        return msg

    summary_lines = []
    for p in pairs:
        summary_lines.append(
            f"Pair {p['No']}: F={p['Forward (5→3)']} (Tm {p['Forward Tm']}, "
            f"GC {p['Forward GC%']}%), R={p['Reverse (5→3)']} "
            f"(Tm {p['Reverse Tm']}, GC {p['Reverse GC%']}%), product {p['Ürün (bp)']} bp")
    summary = "\n".join(summary_lines)

    if lang == 'tr':
        prompt = (
            "Aşağıda PCR primer tasarım sonuçları var. Deneyimli bir moleküler biyolog "
            "gözüyle KAPSAMLI bir değerlendirme yap (Türkçe). Şu başlıkları ayrı ayrı ele al:\n\n"
            "1. **Genel Değerlendirme:** Primerlerin kalitesi hakkında genel görüş.\n"
            "2. **Tm Analizi:** Forward/Reverse Tm değerlerinin uyumu, çift içi ve çiftler "
            "arası farklar, PCR için uygunluğu.\n"
            "3. **GC İçeriği:** GC% değerlerinin değerlendirmesi, 3' uç stabilitesi.\n"
            "4. **Primer-Dimer / Hairpin Riski:** Olası ikincil yapı riskleri.\n"
            "5. **Spesifiklik:** Primerlerin hedefe özgüllüğü hakkında genel uyarılar.\n"
            "6. **Öneriler:** Hangi primer çiftini önerirsin ve neden? Laboratuvarda "
            "dikkat edilmesi gerekenler (annealing sıcaklığı önerisi dahil).\n\n"
            "Her başlığı 2-4 cümleyle, somut ve pratik biçimde açıkla. "
            "Markdown başlıkları ve maddeler kullan.\n\n"
            f"Primer çiftleri:\n{summary}\n\n"
            f"Hedef dizi uzunluğu: {len(seq)} baz."
        )
    else:
        prompt = (
            "Below are PCR primer design results. Provide a COMPREHENSIVE assessment "
            "from the perspective of an experienced molecular biologist (in English). "
            "Address each of the following sections separately:\n\n"
            "1. **General Assessment:** Overall view on primer quality.\n"
            "2. **Tm Analysis:** Compatibility of Forward/Reverse Tm values, within-pair "
            "and between-pair differences, suitability for PCR.\n"
            "3. **GC Content:** Evaluation of GC% values, 3' end stability.\n"
            "4. **Primer-Dimer / Hairpin Risk:** Possible secondary structure risks.\n"
            "5. **Specificity:** General warnings about target specificity.\n"
            "6. **Recommendations:** Which primer pair do you recommend and why? "
            "Practical lab considerations (including annealing temperature suggestion).\n\n"
            "Explain each section in 2-4 sentences, concrete and practical. "
            "Use Markdown headings and bullet points.\n\n"
            f"Primer pairs:\n{summary}\n\n"
            f"Target sequence length: {len(seq)} bases."
        )

    try:
        from ai_engine.services import generate_with_pool
        text, _key = generate_with_pool(
            prompt, service_name="Google Gemini", model_name="gemini-3.5-flash",
            max_tokens=2500, temperature=0.5)
    except Exception as e:
        return dbc.Alert(f"{t('primer_ai_failed', lang)}: {e}", color="warning")

    return dbc.Card([
        dbc.CardHeader([html.I(className="fas fa-robot me-2"), t('primer_ai_title', lang)]),
        dbc.CardBody(dcc.Markdown(text)),
    ], className="shadow-sm")


@app.callback(Output("primer_design", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:primer_design')
    except Exception:
        return False


app.layout = html.Div()


# --- Kredi onay modalı: primer-design-btn ---
@app.callback(
    Output('primer-design-modal', 'is_open'),
    Output('primer-design-modal-body', 'children'),
    Output('primer-design-modal-confirm', 'disabled'),
    Input('primer-design-btn', 'n_clicks'),
    Input('primer-design-modal-cancel', 'n_clicks'),
    Input('primer-design-modal-confirm', 'n_clicks'),
    State('primer-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_primer_design_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'primer-design-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_primer_design', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: primer-ai-btn ---
@app.callback(
    Output('primer-ai-modal', 'is_open'),
    Output('primer-ai-modal-body', 'children'),
    Output('primer-ai-modal-confirm', 'disabled'),
    Input('primer-ai-btn', 'n_clicks'),
    Input('primer-ai-modal-cancel', 'n_clicks'),
    Input('primer-ai-modal-confirm', 'n_clicks'),
    State('primer-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_primer_ai_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'primer-ai-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
