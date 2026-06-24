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

    enzyme_options = [
        {'label': ENZYMES[k]['label_tr'] if lang == 'tr' else ENZYMES[k]['label_en'],
         'value': k}
        for k in ENZYMES
    ]

    control_panel = dbc.Card([
        dbc.CardHeader(t('crispr_input', lang)),
        dbc.CardBody([
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

@app.callback(
    Output('crispr-sequence-input', 'value'),
    Input('crispr-example-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def load_example(n_clicks):
    if not n_clicks:
        return no_update
    return EXAMPLE_SEQUENCE


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
        State('crispr-lang-store', 'data'),
    ],
    prevent_initial_call=True,
)
def run_design(n_clicks, sequence, enzyme, lang, **kwargs):
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
        from ai_engine.services import generate_with_pool
        comment, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-2.5-flash')
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
