"""
Restriksiyon Enzim Analizi (Kesim Haritası) Aracı.

Özellikler:
  - DNA dizisi yapıştırma ile restriksiyon enzim analizi
  - Yaygın enzimleri (CommOnly) veya seçili enzimleri tarama
  - Her enzim için: tanıma dizisi, kesim pozisyonları, kesim sayısı
  - Doğrusal/dairesel (plazmit) DNA desteği
  - Kesim haritası görselleştirmesi (Plotly)
  - Opsiyonel AI yorumu (ai_engine havuzu, 5 kredi)
"""
import re
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, dash_table, Input, Output, State
import plotly.graph_objects as go
from billing.dash_helpers import build_confirm_modal

app = DjangoDash('RestrictionApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True)


# Örnek plazmit dizisi: pUC19 MCS (çoklu klonlama bölgesi) + lacZ flanking
# Klasik klonlama enzimlerini (EcoRI, BamHI, HindIII, SalI, PstI vb.) tek-kesim olarak içerir
EXAMPLE_PLASMID = (
    "TGTAAAACGACGGCCAGTGAATTCGAGCTCGGTACCCGGGGATCCTCTAGAGTCGACCTGCAGG"
    "CATGCAAGCTTGGCACTGGCCGTCGTTTTACAACGTCGTGACTGGGAAAACCCTGGCGTTACCC"
    "AACTTAATCGCCTTGCAGCACATCCCCCTTTCGCCAGCTGGCGTAATAGCGAAGAGGCCCGCAC"
    "CGATCGCCCTTCCCAACAGTTGCGCAGCCTGAATGGCGAATGG"
)


# ----------------------------- Çekirdek mantık -----------------------------

def clean_sequence(sequence):
    """Diziden ATGC dışındaki karakterleri temizler (FASTA başlığı, boşluk, sayı)."""
    lines = [ln for ln in sequence.splitlines() if not ln.strip().startswith('>')]
    joined = ''.join(lines)
    return re.sub(r'[^ATGCatgc]', '', joined).upper()


def analyze_restriction(sequence, is_linear=True, enzyme_names=None):
    """
    Restriksiyon analizi yapar.
    enzyme_names verilmezse yaygın (ticari) enzimler kullanılır.
    Dönüş: (results: list[dict], error: str|None)
    """
    seq_clean = clean_sequence(sequence)
    if len(seq_clean) < 10:
        return None, "Lütfen en az 10 bazlık geçerli bir DNA dizisi girin."

    try:
        from Bio.Seq import Seq
        from Bio.Restriction import Analysis, RestrictionBatch, CommOnly
        from Bio import Restriction
    except ImportError:
        return None, "Biopython kurulu değil (Bio.Restriction gerekli)."

    seq = Seq(seq_clean)

    # Enzim seti
    if enzyme_names:
        enzymes = []
        for name in enzyme_names:
            enz = getattr(Restriction, name, None)
            if enz is not None:
                enzymes.append(enz)
        if not enzymes:
            return None, "Geçerli enzim seçilmedi."
        rb = RestrictionBatch(enzymes)
    else:
        rb = CommOnly  # yaygın ticari enzimler

    try:
        analysis = Analysis(rb, seq, linear=is_linear)
        full = analysis.full()
    except Exception as e:
        return None, f"Analiz hatası: {e}"

    results = []
    for enzyme, sites in full.items():
        if sites:  # sadece kesen enzimleri göster
            results.append({
                'enzyme': str(enzyme),
                'site': str(enzyme.site),
                'cuts': len(sites),
                'positions': ', '.join(str(p) for p in sites),
                '_positions_list': sites,
            })

    # Kesim sayısına göre sırala (az kesenler önce — klonlama için makbul)
    results.sort(key=lambda x: x['cuts'])

    if not results:
        return [], None  # boş ama hatasız: hiçbir enzim kesmedi

    return results, None


def create_cut_map_figure(results, seq_length, lang='en'):
    """Kesim haritası grafiği (her enzimin kesim noktaları dizi üzerinde)."""
    from dash_apps.i18n_helper import t, credit_label

    # Sadece az kesen enzimleri haritada göster (kalabalık olmasın) — ilk 15
    show = [r for r in results if r['cuts'] <= 5][:15]
    if not show:
        show = results[:15]

    fig = go.Figure()

    # Dizi ekseni (yatay çizgi)
    fig.add_trace(go.Scatter(
        x=[0, seq_length], y=[0, 0],
        mode='lines', line=dict(color='#888', width=3),
        showlegend=False, hoverinfo='skip'
    ))

    colors = ['#e63946', '#457b9d', '#2a9d8f', '#e76f51', '#6a4c93',
              '#f4a261', '#1d3557', '#06d6a0', '#ef476f', '#118ab2',
              '#ff9f1c', '#8338ec', '#3a86ff', '#fb5607', '#06aed5']

    for i, r in enumerate(show):
        color = colors[i % len(colors)]
        for pos in r['_positions_list']:
            fig.add_trace(go.Scatter(
                x=[pos, pos], y=[-0.3, 0.3],
                mode='lines', line=dict(color=color, width=2),
                showlegend=False, hoverinfo='text',
                text=f"{r['enzyme']} @ {pos}"
            ))
        # Lejant için tek nokta
        fig.add_trace(go.Scatter(
            x=[show[0]['_positions_list'][0] if show[0]['_positions_list'] else 0],
            y=[None], mode='markers',
            marker=dict(color=color, size=10),
            name=f"{r['enzyme']} ({r['cuts']})"
        ))

    fig.update_layout(
        title=t('re_cut_map', lang),
        xaxis_title=t('re_position', lang),
        yaxis=dict(visible=False, range=[-1, 1]),
        template='plotly_white',
        height=400,
        legend=dict(title=t('re_enzymes', lang))
    )
    return fig


# ----------------------------- Layout -----------------------------

def create_restriction_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label

    control_panel = dbc.Card([
        dbc.CardHeader(t('re_input', lang)),
        dbc.CardBody([
            dbc.Label(t('re_seq_label', lang), className="fw-bold"),
            dcc.Textarea(
                id='re-sequence-input',
                placeholder=t('re_seq_placeholder', lang),
                style={'width': '100%', 'height': 160, 'fontFamily': 'monospace'},
                className="mb-3"
            ),
            dbc.Label(t('re_dna_type', lang), className="fw-bold"),
            dbc.RadioItems(
                id='re-dna-type',
                options=[
                    {'label': t('re_linear', lang), 'value': 'linear'},
                    {'label': t('re_circular', lang), 'value': 'circular'},
                ],
                value='linear',
                inline=True,
                className="mb-3"
            ),
            dbc.Button(
                [html.I(className="fas fa-flask me-2"), t('re_load_example', lang)],
                id='re-example-btn', color="secondary", outline=True, className="w-100 mb-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-cut me-2"),
                 f"{t('re_analyze', lang)} {credit_label('bio_restriction', lang)}"],
                id='re-analyze-btn', color="primary", className="w-100 mb-2"
            ),
            html.Small(t('re_note', lang), className="text-muted"),
        ])
    ])

    result_panel = dbc.Card([
        dbc.CardHeader(t('re_results', lang)),
        dbc.CardBody([
            dcc.Loading(html.Div(
                id='re-results-area',
                children=html.P(t('re_start_hint', lang), className="text-muted")
            )),
            html.Div(id='re-ai-container', style={'display': 'none'}, children=[
                html.Hr(),
                dbc.Button(
                    [html.I(className="fas fa-robot me-2"),
                     f"{t('re_ai_comment', lang)} {credit_label('bio_tool_ai', lang)}"],
                    id='re-ai-btn', color="success", className="w-100"
                ),
                dcc.Loading(html.Div(id='re-ai-output', className="mt-3"))
            ])
        ])
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('re-analyze-modal', lang=lang),
        build_confirm_modal('re-ai-modal', lang=lang),
        dcc.Store(id='re-lang-store', data=lang),
        dcc.Store(id='re-results-store'),
        html.H2(t('re_title', lang)),
        html.P(t('re_subtitle', lang), className="text-muted"),
        html.Hr(),
        dbc.Row([
            dbc.Col(control_panel, width=12, lg=4),
            dbc.Col(result_panel, width=12, lg=8),
        ])
    ])


app.layout = create_restriction_layout()


# ----------------------------- Callbacks -----------------------------

@app.callback(
    [
        Output('re-sequence-input', 'value'),
        Output('re-dna-type', 'value'),
    ],
    Input('re-example-btn', 'n_clicks'),
    prevent_initial_call=True
)
def load_example(n_clicks):
    """Örnek pUC19 plazmit dizisini yükler ve dairesel (circular) seçer."""
    from dash import no_update
    if not n_clicks:
        return no_update, no_update
    return EXAMPLE_PLASMID, 'circular'


@app.callback(
    [
        Output('re-results-area', 'children'),
        Output('re-results-store', 'data'),
        Output('re-ai-container', 'style'),
    ],
    Input('re-analyze-modal-confirm', 'n_clicks'),
    [
        State('re-sequence-input', 'value'),
        State('re-dna-type', 'value'),
        State('re-lang-store', 'data'),
    ],
    prevent_initial_call=True
)
def run_analysis(n_clicks, sequence, dna_type, lang, **kwargs):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'

    if not sequence:
        return dbc.Alert(t('re_no_seq', lang), color="warning"), None, {'display': 'none'}

    # Kredi düş (her analiz 5 kredi)
    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_restriction', cost=5, lang=lang,
                             description="Restriksiyon analizi")
    if not ok:
        return msg, None, {'display': 'none'}

    is_linear = (dna_type == 'linear')
    results, error = analyze_restriction(sequence, is_linear=is_linear)

    if error:
        return dbc.Alert(error, color="danger"), None, {'display': 'none'}

    seq_len = len(clean_sequence(sequence))

    if not results:
        return (dbc.Alert(t('re_no_cuts', lang), color="info"),
                None, {'display': 'none'})

    # Tablo
    table_rows = [{
        t('re_col_enzyme', lang): r['enzyme'],
        t('re_col_site', lang): r['site'],
        t('re_col_cuts', lang): r['cuts'],
        t('re_col_positions', lang): r['positions'],
    } for r in results]

    table = dash_table.DataTable(
        data=table_rows,
        columns=[{'name': c, 'id': c} for c in table_rows[0].keys()],
        style_cell={'textAlign': 'left', 'fontFamily': 'monospace', 'fontSize': '13px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f1f3f5'},
        page_size=15,
        sort_action='native',
        style_table={'overflowX': 'auto'},
    )

    # Kesim haritası
    fig = create_cut_map_figure(results, seq_len, lang)

    # Özet
    single_cutters = [r['enzyme'] for r in results if r['cuts'] == 1]
    summary = dbc.Alert([
        html.Strong(t('re_summary', lang) + ": "),
        f"{seq_len} bp, {len(results)} {t('re_enzymes_cut', lang)}. ",
        (f"{t('re_single_cutters', lang)}: {', '.join(single_cutters[:10])}"
         if single_cutters else t('re_no_single', lang)),
    ], color="info")

    content = html.Div([
        summary,
        dcc.Graph(figure=fig),
        html.H5(t('re_detail_table', lang), className="mt-3"),
        table,
    ])

    # AI için sonuçları sakla
    store_data = {
        'seq_len': seq_len,
        'results': [{'enzyme': r['enzyme'], 'site': r['site'],
                     'cuts': r['cuts'], 'positions': r['positions']}
                    for r in results[:30]],
    }

    return content, store_data, {'display': 'block'}


@app.callback(
    Output('re-ai-output', 'children'),
    Input('re-ai-modal-confirm', 'n_clicks'),
    [
        State('re-results-store', 'data'),
        State('re-lang-store', 'data'),
    ],
    prevent_initial_call=True
)
def ai_comment(n_clicks, store_data, lang, **kwargs):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'

    if not n_clicks or not store_data:
        return ""

    # AI yorumu ayrı işlem — 5 kredi
    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                             description="Restriksiyon AI yorumu")
    if not ok:
        return msg

    # Özet metin oluştur
    lines = []
    for r in store_data['results'][:20]:
        lines.append(f"{r['enzyme']} ({r['site']}): {r['cuts']} kesim @ {r['positions']}")
    summary_text = '\n'.join(lines)

    if lang == 'tr':
        prompt = (
            f"Bir {store_data['seq_len']} bp DNA dizisi için restriksiyon enzim analizi sonuçları "
            f"aşağıdadır. Klonlama açısından yorumla: hangi enzimler tek kesim yapıyor (klonlama için "
            f"ideal), hangi enzim çiftleri yönlü klonlama için uygun, dikkat edilmesi gereken noktalar. "
            f"Kısa ve pratik ol.\n\n{summary_text}"
        )
    else:
        prompt = (
            f"Below are restriction enzyme analysis results for a {store_data['seq_len']} bp DNA "
            f"sequence. Comment from a cloning perspective: which enzymes cut once (ideal for cloning), "
            f"which enzyme pairs are suitable for directional cloning, and points to watch out for. "
            f"Be concise and practical.\n\n{summary_text}"
        )

    try:
        from ai_engine.services import generate_with_pool
        comment, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-3.5-flash'
        )
        return dcc.Markdown(comment)
    except Exception as e:
        return dbc.Alert(f"{t('re_ai_error', lang)}: {e}", color="danger")


@app.callback(Output("restriction_analysis", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:restriction_analysis')
    except Exception:
        return False


# --- Kredi onay modalı: re-analyze-btn ---
@app.callback(
    Output('re-analyze-modal', 'is_open'),
    Output('re-analyze-modal-body', 'children'),
    Output('re-analyze-modal-confirm', 'disabled'),
    Input('re-analyze-btn', 'n_clicks'),
    Input('re-analyze-modal-cancel', 'n_clicks'),
    Input('re-analyze-modal-confirm', 'n_clicks'),
    State('re-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_re_analyze_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 're-analyze-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_restriction', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: re-ai-btn ---
@app.callback(
    Output('re-ai-modal', 'is_open'),
    Output('re-ai-modal-body', 'children'),
    Output('re-ai-modal-confirm', 'disabled'),
    Input('re-ai-btn', 'n_clicks'),
    Input('re-ai-modal-cancel', 'n_clicks'),
    Input('re-ai-modal-confirm', 'n_clicks'),
    State('re-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_re_ai_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 're-ai-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
