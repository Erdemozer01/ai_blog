"""
CRISPR sgRNA Tasarımcısı — Dash Uygulaması.

Hesaplama mantığı dash_apps/crispr_engine.py içindedir (Django'dan bağımsız).
Bu dosya yalnızca arayüz, etkileşim, görselleştirme, kredi ve AI yorumu içerir.
İki dillidir (lang-store deseni). Diğer bio-tool'larla aynı yapıyı izler.
"""
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, dash_table, Input, Output, State, no_update
import plotly.graph_objects as go

from billing.dash_helpers import build_confirm_modal
from dash_apps.crispr_engine import (
    find_guides, summarize, clean_sequence, ENZYMES, EXAMPLE_SEQUENCE,
)
from dash_apps.ensembl_fetch import SPECIES, BLAST_ORGANISM, fetch_gene_sequence

app = DjangoDash('CrisprApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True)


# ----------------------------- Görselleştirme -----------------------------

def create_pam_map_figure(guides, seq_len, lang='en'):
    """Aday gRNA'ların dizi üzerindeki konumlarını iplik ve skora göre çizer."""
    from dash_apps.i18n_helper import t

    fig = go.Figure()

    # Dizi ekseni (referans çizgi)
    fig.add_trace(go.Scatter(
        x=[1, seq_len], y=[0, 0], mode='lines',
        line=dict(color='#adb5bd', width=3), showlegend=False, hoverinfo='skip',
    ))

    for strand, yval, color in [('+', 0.5, '#2563eb'), ('-', -0.5, '#dc2626')]:
        gs = [g for g in guides if g['strand'] == strand]
        if not gs:
            continue
        xs = [(g['start'] + g['end']) / 2 for g in gs]
        ys = [yval for _ in gs]
        sizes = [6 + (g['score'] / 100.0) * 12 for g in gs]
        texts = [
            f"{g['guide']}<br>PAM: {g['pam']} | {t('crispr_col_score', lang)}: {g['score']} "
            f"| GC: {g['gc']}%<br>{t('crispr_col_pos', lang)}: {g['start']}-{g['end']}"
            for g in gs
        ]
        label = t('crispr_strand_fwd', lang) if strand == '+' else t('crispr_strand_rev', lang)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode='markers',
            marker=dict(size=sizes, color=color, opacity=0.75,
                        line=dict(width=0.5, color='white')),
            name=label, hoverinfo='text', text=texts,
        ))

    fig.update_layout(
        title=t('crispr_map_title', lang),
        xaxis_title=t('crispr_map_xaxis', lang),
        yaxis=dict(visible=False, range=[-1.3, 1.3]),
        template='plotly_white', height=320,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=20, r=20, t=60, b=40),
    )
    return fig


# ----------------------------- Layout -----------------------------

def create_crispr_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label

    def L(tr, en):
        return tr if lang == 'tr' else en

    enzyme_options = [
        {'label': ENZYMES[k]['label_tr'] if lang == 'tr' else ENZYMES[k]['label_en'],
         'value': k}
        for k in ENZYMES
    ]

    species_options = [
        {'label': (row[2] if lang == 'tr' else row[3]), 'value': row[0]}
        for row in SPECIES
    ]

    # --- Ensembl'den gen adıyla dizi getirme bloğu ---
    gene_fetch_block = html.Div([
        dbc.Label(L("Gen adından dizi getir (Ensembl)",
                    "Fetch sequence from gene name (Ensembl)"), className="fw-bold"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(
                id='crispr-species', options=species_options,
                value='homo_sapiens', clearable=False,
            ), width=5),
            dbc.Col(dbc.Input(
                id='crispr-gene-input', type='text',
                placeholder=L("ör. TP53", "e.g. TP53"),
            ), width=7),
        ], className="g-2 mb-2"),
        dbc.Button(
            [html.I(className="fas fa-cloud-download-alt me-2"),
             L("Ensembl'den çek", "Fetch from Ensembl")],
            id='crispr-gene-btn', color="info", outline=True, className="w-100 mb-1",
        ),
        dcc.Loading(html.Div(id='crispr-gene-status', className="small")),
        html.Small(
            L("Not: Genomik dizi (intronlar dahil) getirilir; çok uzunsa kırpılır. "
              "Gen çekmek off-target'ı çözmez.",
              "Note: fetches the genomic sequence (introns included); long genes are "
              "truncated. Fetching a gene does not solve off-target."),
            className="text-muted"),
        html.Hr(),
    ])

    control_panel = dbc.Card([
        dbc.CardHeader(t('crispr_input', lang)),
        dbc.CardBody([
            gene_fetch_block,
            dbc.Label(t('crispr_seq_label', lang), className="fw-bold"),
            dcc.Textarea(
                id='crispr-sequence-input',
                placeholder=t('crispr_seq_placeholder', lang),
                style={'width': '100%', 'height': 160, 'fontFamily': 'monospace'},
                className="mb-3",
            ),
            dbc.Label(t('crispr_enzyme_label', lang), className="fw-bold"),
            dcc.Dropdown(
                id='crispr-enzyme', options=enzyme_options,
                value='SpCas9', clearable=False, className="mb-3",
            ),
            dbc.Button(
                [html.I(className="fas fa-flask me-2"), t('crispr_load_example', lang)],
                id='crispr-example-btn', color="secondary", outline=True,
                className="w-100 mb-2",
            ),
            dbc.Button(
                [html.I(className="fas fa-scissors me-2"),
                 f"{t('crispr_analyze', lang)} {credit_label('bio_crispr', lang)}"],
                id='crispr-analyze-btn', color="primary", className="w-100 mb-2",
            ),
            html.Small(t('crispr_note', lang), className="text-muted"),
        ])
    ])

    result_panel = dbc.Card([
        dbc.CardHeader(t('crispr_results', lang)),
        dbc.CardBody([
            dcc.Loading(html.Div(
                id='crispr-results-area',
                children=html.P(t('crispr_start_hint', lang), className="text-muted"),
            )),
            html.Div(id='crispr-ai-container', style={'display': 'none'}, children=[
                html.Hr(),
                dbc.Button(
                    [html.I(className="fas fa-robot me-2"),
                     f"{t('crispr_ai_comment', lang)} {credit_label('bio_tool_ai', lang)}"],
                    id='crispr-ai-btn', color="success", className="w-100",
                ),
                dcc.Loading(html.Div(id='crispr-ai-output', className="mt-3")),

                # --- Off-target (yaklaşık, NCBI BLAST) — dış Loading'in DIŞINDA ---
                html.Hr(),
                html.H6([html.I(className="fas fa-crosshairs me-2"),
                         L("Off-target taraması", "Off-target scan")]),
                dbc.Button(
                    [html.I(className="fas fa-crosshairs me-2"),
                     L("En iyi 3 guide için off-target tara",
                       "Scan off-targets for top 3 guides")],
                    id='crispr-offtarget-btn', color="warning", outline=True,
                    className="w-100",
                ),
                html.Small(
                    L("NCBI'nin genomik kayıtlarına BLAST hizalaması; guide başına ~30-90 sn "
                      "sürebilir. MM0/MM1/MM2/MM3 = 0/1/2/3 uyumsuzlukla eşleşen genomik bölge "
                      "sayısı. MM0 hedefin kendisini de içerir (beklenen ≥1). Tarama sürerken "
                      "üstteki tablo ve grafik yerinde kalır.",
                      "BLAST alignment to NCBI genomic records; may take ~30-90 s per guide. "
                      "MM0/MM1/MM2/MM3 = number of genomic sites matching with 0/1/2/3 mismatches. "
                      "MM0 includes the intended target itself (≥1 expected). The table and chart "
                      "above stay in place while scanning."),
                    className="text-muted d-block mt-1"),
                dcc.Loading(html.Div(id='crispr-offtarget-output', className="mt-2")),
            ]),
        ])
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('crispr-analyze-modal', lang=lang),
        build_confirm_modal('crispr-ai-modal', lang=lang),
        dcc.Store(id='crispr-lang-store', data=lang),
        dcc.Store(id='crispr-results-store'),
        html.H2([html.I(className="fas fa-dna me-2 text-primary"),
                 t('crispr_title', lang)]),
        html.P(t('crispr_subtitle', lang), className="text-muted"),
        html.Hr(),
        dbc.Row([
            dbc.Col(control_panel, width=12, lg=4),
            dbc.Col(result_panel, width=12, lg=8),
        ])
    ])


app.layout = create_crispr_layout()


# ----------------------------- Callbacks -----------------------------

# Örnek dizi yükleme + Ensembl'den gen çekme TEK callback'te birleştirildi
# (aynı 'value' çıktısına iki ayrı callback yazınca DjangoDash'te duplicate
# çıktı sessizce düşüyordu; tek çıktı sahibiyle bu sorun ortadan kalkar).
@app.callback(
    Output('crispr-sequence-input', 'value'),
    Output('crispr-gene-status', 'children'),
    Input('crispr-example-btn', 'n_clicks'),
    Input('crispr-gene-btn', 'n_clicks'),
    State('crispr-gene-input', 'value'),
    State('crispr-species', 'value'),
    State('crispr-lang-store', 'data'),
    prevent_initial_call=True,
)
def fill_sequence(ex_clicks, gene_clicks, gene, species, lang):
    import dash
    lang = lang or 'en'

    def L(tr, en):
        return tr if lang == 'tr' else en

    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''

    # 1) Örnek diziyi yükle
    if trig_id == 'crispr-example-btn':
        return EXAMPLE_SEQUENCE, no_update

    # 2) Ensembl'den gen adıyla dizi getir
    if trig_id == 'crispr-gene-btn':
        gene = (gene or '').strip()
        if not gene:
            return no_update, dbc.Alert(L("Gen adı girin.", "Enter a gene name."),
                                        color="warning", className="py-1 my-1 small")

        seq, meta, err = fetch_gene_sequence(gene, species or 'homo_sapiens')
        if err or not seq:
            msgs = {
                'not_found': L("Gen bulunamadı. Adı/türü kontrol edin.",
                               "Gene not found. Check the name/species."),
                'network': L("Ensembl'e ulaşılamadı. Biraz sonra tekrar deneyin.",
                             "Could not reach Ensembl. Please try again shortly."),
                'no_seq': L("Bu gen için dizi bulunamadı.",
                            "No sequence found for this gene."),
            }
            return no_update, dbc.Alert(
                msgs.get(err, L("Dizi getirilemedi.", "Could not fetch the sequence.")),
                color="danger", className="py-1 my-1 small")

        note = L(
            f"{meta['symbol']} ({meta['id']}) — kromozom {meta['chr']}, "
            f"{meta['length']} bp getirildi" + (" (kırpıldı)" if meta['truncated'] else "") + ".",
            f"{meta['symbol']} ({meta['id']}) — chr {meta['chr']}, "
            f"fetched {meta['length']} bp" + (" (truncated)" if meta['truncated'] else "") + ".",
        )
        return seq, dbc.Alert(note, color="success", className="py-1 my-1 small")

    return no_update, no_update


@app.callback(
    Output('crispr-offtarget-output', 'children'),
    Input('crispr-offtarget-btn', 'n_clicks'),
    State('crispr-results-store', 'data'),
    State('crispr-lang-store', 'data'),
    prevent_initial_call=True,
)
def run_offtarget(n_clicks, store_data, lang):
    lang = lang or 'en'

    def L(tr, en):
        return tr if lang == 'tr' else en

    if not n_clicks or not store_data:
        return no_update

    from dash_apps.offtarget import blast_offtarget, risk_label
    species = store_data.get('species', 'homo_sapiens')
    organism = BLAST_ORGANISM.get(species, 'Homo sapiens')
    guides = (store_data.get('guides') or [])[:3]
    if not guides:
        return dbc.Alert(L("Taranacak guide yok.", "No guides to scan."), color="info")

    rows = []
    any_ok = False
    for g in guides:
        res = blast_offtarget(g['guide'], organism=organism)
        if res.get('ok'):
            any_ok = True
            mm = res['mm']
            label, _c = risk_label(mm, lang)
            rows.append({
                '#': g['rank'], 'Guide': g['guide'],
                'MM0': mm.get(0, 0), 'MM1': mm.get(1, 0),
                'MM2': mm.get(2, 0), 'MM3': mm.get(3, 0),
                L('Risk', 'Risk'): label,
            })
        else:
            rows.append({
                '#': g['rank'], 'Guide': g['guide'],
                'MM0': '-', 'MM1': '-', 'MM2': '-', 'MM3': '-',
                L('Risk', 'Risk'): L('doğrulanamadı', 'unverified'),
            })

    table = dash_table.DataTable(
        data=rows, columns=[{'name': c, 'id': c} for c in rows[0].keys()],
        style_cell={'textAlign': 'left', 'fontFamily': 'monospace', 'fontSize': '13px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f3f5'},
        style_table={'overflowX': 'auto'},
    )
    if not any_ok:
        return dbc.Alert(
            L("Off-target servisi şu an yanıt vermedi. Biraz sonra tekrar deneyin.",
              "Off-target service did not respond. Please try again shortly."),
            color="danger", className="small")
    return html.Div([table])


@app.callback(
    [
        Output('crispr-results-area', 'children'),
        Output('crispr-results-store', 'data'),
        Output('crispr-ai-container', 'style'),
    ],
    Input('crispr-analyze-modal-confirm', 'n_clicks'),
    [
        State('crispr-sequence-input', 'value'),
        State('crispr-enzyme', 'value'),
        State('crispr-species', 'value'),
        State('crispr-lang-store', 'data'),
    ],
    prevent_initial_call=True,
)
def run_design(n_clicks, sequence, enzyme, species, lang, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'

    if not sequence or not clean_sequence(sequence):
        return dbc.Alert(t('crispr_no_seq', lang), color="warning"), None, {'display': 'none'}

    # Kredi düş (tasarım 5 kredi; bio_crispr DB'de yoksa default 5)
    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_crispr', cost=5, lang=lang,
                             description=t('crispr_charge_desc', lang))
    if not ok:
        return msg, None, {'display': 'none'}

    guides, error = find_guides(sequence, enzyme)

    if error:
        code = error.get('code')
        if code == 'too_short':
            txt = t('crispr_too_short', lang).format(min=error['min'], got=error['got'])
        elif code == 'unknown_enzyme':
            txt = t('crispr_unknown_enzyme', lang)
        else:
            txt = str(error)
        return dbc.Alert(txt, color="danger"), None, {'display': 'none'}

    if not guides:
        return dbc.Alert(t('crispr_no_guides', lang), color="info"), None, {'display': 'none'}

    seq_len = len(clean_sequence(sequence))
    s = summarize(guides)

    # Özet
    summary = dbc.Alert([
        html.Strong(t('crispr_summary', lang) + ": "),
        t('crispr_summary_text', lang).format(
            total=s['total'], plus=s['plus'], minus=s['minus'], high=s['high']),
    ], color="info")

    # Harita
    fig = create_pam_map_figure(guides, seq_len, lang)

    # Tablo (en iyi 50)
    strand_fwd = t('crispr_strand_fwd', lang)
    strand_rev = t('crispr_strand_rev', lang)
    st_doench = t('crispr_st_doench', lang)
    st_heur = t('crispr_st_heuristic', lang)
    table_rows = [{
        t('crispr_col_rank', lang): g['rank'],
        t('crispr_col_guide', lang): g['guide'],
        t('crispr_col_pam', lang): g['pam'],
        t('crispr_col_strand', lang): strand_fwd if g['strand'] == '+' else strand_rev,
        t('crispr_col_pos', lang): f"{g['start']}-{g['end']}",
        t('crispr_col_gc', lang): g['gc'],
        t('crispr_col_score', lang): g['score'],
        t('crispr_col_source', lang): st_doench if g.get('score_type') == 'doench' else st_heur,
        t('crispr_col_uniq', lang): g['uniqueness'],
    } for g in guides[:50]]

    score_col = t('crispr_col_score', lang)
    table = dash_table.DataTable(
        data=table_rows,
        columns=[{'name': c, 'id': c} for c in table_rows[0].keys()],
        style_cell={'textAlign': 'left', 'fontFamily': 'monospace', 'fontSize': '13px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f3f5'},
        page_size=15, sort_action='native', filter_action='native',
        style_table={'overflowX': 'auto'},
        style_data_conditional=[
            {'if': {'filter_query': f'{{{score_col}}} >= 70'},
             'backgroundColor': '#e7f5e9'},
            {'if': {'filter_query': f'{{{score_col}}} < 40'},
             'backgroundColor': '#fdecea'},
        ],
    )

    disclaimer = dbc.Alert([
        html.I(className="fas fa-exclamation-circle me-2"),
        t('crispr_disclaimer', lang),
    ], color="warning", className="small mt-3")

    # Not: Off-target butonu/çıktısı, dış Loading'in DIŞINDA (ai-container içinde)
    # durur; böylece BLAST sürerken üstteki tablo/grafik kaybolmaz.
    content = html.Div([
        summary,
        dcc.Graph(figure=fig),
        html.H5(t('crispr_detail_table', lang), className="mt-3"),
        table,
        disclaimer,
    ])

    # AI için sakla (en iyi 8 aday)
    store_data = {
        'seq_len': seq_len, 'enzyme': enzyme,
        'species': species or 'homo_sapiens',
        'guides': [{'rank': g['rank'], 'guide': g['guide'], 'pam': g['pam'],
                    'strand': g['strand'], 'gc': g['gc'], 'score': g['score'],
                    'score_type': g.get('score_type', 'heuristic'),
                    'uniqueness': g['uniqueness']} for g in guides[:8]],
    }
    return content, store_data, {'display': 'block'}


@app.callback(
    Output('crispr-ai-output', 'children'),
    Input('crispr-ai-modal-confirm', 'n_clicks'),
    [
        State('crispr-results-store', 'data'),
        State('crispr-lang-store', 'data'),
    ],
    prevent_initial_call=True,
)
def ai_comment(n_clicks, store_data, lang, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'
    if not n_clicks or not store_data:
        return ""

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                             description=t('crispr_ai_charge_desc', lang))
    if not ok:
        return msg

    lines = [
        f"#{g['rank']} {g['guide']} (PAM {g['pam']}, {g['strand']}, "
        f"GC {g['gc']}%, score {g['score']} [{g.get('score_type','heuristic')}], "
        f"uniqueness {g['uniqueness']})"
        for g in store_data['guides']
    ]
    summary_text = '\n'.join(lines)

    if lang == 'tr':
        prompt = (
            f"{store_data['enzyme']} enzimi ile {store_data['seq_len']} bp'lik bir DNA dizisinde "
            f"tasarlanan en iyi aday sgRNA'lar aşağıdadır. Skor tipi 'doench' ise Doench 2014 "
            f"(Rule Set 1) eğitilmiş modelinden gelir (0-100, ~60+ iyi sayılır); 'heuristic' ise "
            f"sezgiseldir. En iyi 2-3 adayı seç ve NEDEN iyi olduklarını açıkla (skor, GC dengesi, "
            f"benzersizlik). Kaçınılması gerekenleri belirt. Off-target için genom çapında doğrulama "
            f"gerektiğini hatırlat. Kısa, pratik ve Türkçe ol. Skorları UYDURMA; verilenleri yorumla.\n\n{summary_text}"
        )
    else:
        prompt = (
            f"Below are the top candidate sgRNAs designed for a {store_data['seq_len']} bp DNA "
            f"sequence using {store_data['enzyme']}. If score type is 'doench' the score comes from "
            f"the trained Doench 2014 (Rule Set 1) model (0-100, ~60+ is good); 'heuristic' is a "
            f"rule-based estimate. Pick the best 2-3 candidates and explain WHY they are good (score, "
            f"GC balance, uniqueness). Flag any to avoid. Remind that genome-wide off-target "
            f"validation is required. Be concise, practical, and in English. Do NOT invent scores; "
            f"interpret the given ones.\n\n{summary_text}"
        )

    try:
        from ai_engine.services import generate_with_fallback as generate_with_pool
        comment, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-3.5-flash')
        return dcc.Markdown(comment)
    except Exception as e:
        return dbc.Alert(f"{t('crispr_ai_error', lang)}: {e}", color="danger")


@app.callback(Output("crispr_designer", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:crispr_designer')
    except Exception:
        return False


# --- Navbar menü (mobil "Menü" aç/kapa) — diğer araçlarla aynı ---
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


# --- Kredi onay modalı: tasarım ---
@app.callback(
    Output('crispr-analyze-modal', 'is_open'),
    Output('crispr-analyze-modal-body', 'children'),
    Output('crispr-analyze-modal-confirm', 'disabled'),
    Input('crispr-analyze-btn', 'n_clicks'),
    Input('crispr-analyze-modal-cancel', 'n_clicks'),
    Input('crispr-analyze-modal-confirm', 'n_clicks'),
    State('crispr-lang-store', 'data'),
    prevent_initial_call=True,
)
def toggle_crispr_analyze_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'crispr-analyze-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_crispr', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: AI ---
@app.callback(
    Output('crispr-ai-modal', 'is_open'),
    Output('crispr-ai-modal-body', 'children'),
    Output('crispr-ai-modal-confirm', 'disabled'),
    Input('crispr-ai-btn', 'n_clicks'),
    Input('crispr-ai-modal-cancel', 'n_clicks'),
    Input('crispr-ai-modal-confirm', 'n_clicks'),
    State('crispr-lang-store', 'data'),
    prevent_initial_call=True,
)
def toggle_crispr_ai_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'crispr-ai-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update