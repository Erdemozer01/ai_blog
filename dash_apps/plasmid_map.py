"""
Plazmit Harita Görselleştirici (Plotly interaktif dairesel harita).

Özellikler:
  - DNA dizisi yapıştırma ile dairesel plazmit haritası
  - Otomatik ORF (gen adayı) tespiti — 6 çerçevede start→stop
  - Restriksiyon kesim bölgeleri (tek-kesim yapanlar haritada)
  - İnteraktif Plotly dairesel harita (hover, zoom)
  - Örnek plazmit (pUC19 benzeri)
  - Opsiyonel AI yorumu (5 kredi)
"""
import re
import math
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, dash_table, Input, Output, State, no_update
import plotly.graph_objects as go
from billing.dash_helpers import build_confirm_modal

app = DjangoDash('PlasmidMapApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True)


# Örnek plazmit: pUC19 MCS + lacZ + birkaç tipik özellik içeren temsili dizi (~500 bp)
EXAMPLE_PLASMID = (
    "ATGACCATGATTACGCCAAGCTTGCATGCCTGCAGGTCGACTCTAGAGGATCCCCGGGTACCGAGCTCGAATTC"
    "ACTGGCCGTCGTTTTACAACGTCGTGACTGGGAAAACCCTGGCGTTACCCAACTTAATCGCCTTGCAGCACATC"
    "CCCCTTTCGCCAGCTGGCGTAATAGCGAAGAGGCCCGCACCGATCGCCCTTCCCAACAGTTGCGCAGCCTGAAT"
    "GGCGAATGGCGCCTGATGCGGTATTTTCTCCTTACGCATCTGTGCGGTATTTCACACCGCATATGGTGCACTCT"
    "CAGTACAATCTGCTCTGATGCCGCATAGTTAAGCCAGCCCCGACACCCGCCAACACCCGCTGACGCGCCCTGAC"
    "GGGCTTGTCTGCTCCCGGCATCCGCTTACAGACAAGCTGTGACCGTCTCCGGGAGCTGCATGTGTCAGAGGTTT"
    "TCACCGTCATCACCGAAACGCGCGA"
)


def clean_sequence(seq_text):
    """DNA dizisini temizler (sadece harf, büyük harf)."""
    if not seq_text:
        return ""
    lines = [ln for ln in seq_text.splitlines() if not ln.strip().startswith('>')]
    seq = ''.join(lines)
    return re.sub(r'[^A-Za-z]', '', seq).upper()


def find_orfs(sequence, min_len=60):
    """
    Dizide ORF (Açık Okuma Çerçevesi) bulur — ATG'den stop kodona.
    Her iki yön (ileri/geri), 3 çerçeve. min_len = minimum nükleotid uzunluğu.
    """
    from Bio.Seq import Seq

    seq = Seq(sequence)
    seq_len = len(sequence)
    orfs = []
    stop_codons = {'TAA', 'TAG', 'TGA'}

    for strand, nuc in [(1, seq), (-1, seq.reverse_complement())]:
        for frame in range(3):
            i = frame
            while i < seq_len - 2:
                codon = str(nuc[i:i + 3])
                if codon == 'ATG':
                    # stop ara
                    j = i
                    while j < seq_len - 2:
                        c = str(nuc[j:j + 3])
                        if c in stop_codons:
                            orf_len = j + 3 - i
                            if orf_len >= min_len:
                                if strand == 1:
                                    start, end = i, j + 3
                                else:
                                    start = seq_len - (j + 3)
                                    end = seq_len - i
                                orfs.append({
                                    'start': start,
                                    'end': end,
                                    'strand': strand,
                                    'length': orf_len,
                                    'aa': orf_len // 3 - 1,
                                })
                            i = j + 3
                            break
                        j += 3
                    else:
                        i += 3
                else:
                    i += 3

    # Uzunluğa göre sırala, en uzun ORF'ler önce
    orfs.sort(key=lambda x: -x['length'])
    return orfs[:10]  # en fazla 10 ORF


def find_single_cutters(sequence):
    """Tek kesim yapan restriksiyon enzimlerini bulur (haritada gösterilecek)."""
    from Bio.Seq import Seq
    from Bio.Restriction import Analysis, CommOnly

    try:
        seq = Seq(sequence)
        ana = Analysis(CommOnly, seq, linear=False)
        full = ana.full()
        single = []
        for enzyme, positions in full.items():
            if len(positions) == 1:
                single.append({'name': str(enzyme), 'pos': positions[0]})
        single.sort(key=lambda x: x['pos'])
        return single[:12]  # en fazla 12 (görsel netlik)
    except Exception:
        return []


def _pos_to_angle(pos, total):
    """Pozisyonu açıya çevir (saat 12'den, saat yönünde)."""
    return 90 - (pos / total) * 360


def _polar(angle_deg, radius):
    a = math.radians(angle_deg)
    return radius * math.cos(a), radius * math.sin(a)


def create_plasmid_figure(total_length, orfs, cutters, lang='en'):
    """İnteraktif dairesel plazmit haritası (Plotly)."""
    from dash_apps.i18n_helper import t

    fig = go.Figure()

    # Ana daire (plazmit omurgası)
    theta = [math.radians(a) for a in range(0, 361, 2)]
    fig.add_trace(go.Scatter(
        x=[math.cos(a) for a in theta],
        y=[math.sin(a) for a in theta],
        mode='lines', line=dict(color='#34495e', width=4),
        hoverinfo='skip', showlegend=False
    ))

    # ORF yayları (genler) — daha dış halkada
    orf_colors = ['#3498db', '#2ecc71', '#9b59b6', '#1abc9c', '#34495e',
                  '#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50']
    for i, orf in enumerate(orfs):
        color = orf_colors[i % len(orf_colors)]
        r = 1.12 if orf['strand'] == 1 else 1.20
        a_start = _pos_to_angle(orf['start'], total_length)
        a_end = _pos_to_angle(orf['end'], total_length)
        # Yay noktaları
        steps = max(int(abs(a_start - a_end) / 2), 2)
        angles = [a_start + (a_end - a_start) * k / steps for k in range(steps + 1)]
        xs = [_polar(a, r)[0] for a in angles]
        ys = [_polar(a, r)[1] for a in angles]
        label = f"ORF{i+1} ({orf['strand']:+d})"
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode='lines',
            line=dict(color=color, width=8),
            name=label,
            hoverinfo='text',
            hovertext=f"{label}<br>{orf['start']}-{orf['end']} bp<br>{orf['aa']} aa",
            showlegend=True
        ))

    # Restriksiyon kesim bölgeleri — radyal çizgiler + etiket
    for c in cutters:
        a = _pos_to_angle(c['pos'], total_length)
        x1, y1 = _polar(a, 0.95)
        x2, y2 = _polar(a, 1.05)
        xl, yl = _polar(a, 1.35)
        fig.add_trace(go.Scatter(
            x=[x1, x2], y=[y1, y2], mode='lines',
            line=dict(color='#e74c3c', width=2),
            hoverinfo='text', hovertext=f"{c['name']} @ {c['pos']} bp",
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=[xl], y=[yl], mode='text',
            text=[f"{c['name']}<br>{c['pos']}"],
            textfont=dict(size=9, color='#c0392b'),
            hoverinfo='skip', showlegend=False
        ))

    # Merkez etiketi (plazmit adı + boyut)
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode='text',
        text=[f"<b>{t('pm_plasmid', lang)}</b><br>{total_length} bp"],
        textfont=dict(size=16, color='#2c3e50'),
        hoverinfo='skip', showlegend=False
    ))

    fig.update_layout(
        title=t('pm_map_title', lang),
        template='plotly_white',
        height=600,
        xaxis=dict(visible=False, range=[-1.6, 1.6], scaleanchor='y'),
        yaxis=dict(visible=False, range=[-1.6, 1.6]),
        legend=dict(orientation='v', x=1.02, y=0.5),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


# ----------------------------- Layout -----------------------------

def create_plasmid_layout(lang='en'):
    from dash_apps.i18n_helper import t

    control_panel = dbc.Card([
        dbc.CardHeader(t('pm_input', lang)),
        dbc.CardBody([
            dbc.Label(t('pm_seq_label', lang), className="fw-bold"),
            dcc.Textarea(
                id='pm-sequence-input',
                placeholder=t('pm_seq_placeholder', lang),
                style={'width': '100%', 'height': 160, 'fontFamily': 'monospace'},
                className="mb-3"
            ),
            dbc.Button(
                [html.I(className="fas fa-flask me-2"), t('pm_load_example', lang)],
                id='pm-example-btn', color="secondary", outline=True, className="w-100 mb-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-circle-notch me-2"),
                 f"{t('pm_draw', lang)} {credit_label('bio_plasmid_map', lang)}"],
                id='pm-draw-btn', color="primary", className="w-100 mb-2"
            ),
            html.Small(t('pm_note', lang), className="text-muted"),
        ])
    ])

    result_panel = dbc.Card([
        dbc.CardHeader(t('pm_results', lang)),
        dbc.CardBody([
            dcc.Loading(html.Div(
                id='pm-results-area',
                children=html.P(t('pm_start_hint', lang), className="text-muted")
            )),
            html.Div(id='pm-ai-container', style={'display': 'none'}, children=[
                html.Hr(),
                dbc.Button(
                    [html.I(className="fas fa-robot me-2"),
                     f"{t('pm_ai_comment', lang)} {credit_label('bio_tool_ai', lang)}"],
                    id='pm-ai-btn', color="success", className="w-100"
                ),
                dcc.Loading(html.Div(id='pm-ai-output', className="mt-3"))
            ])
        ])
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('pm-draw-modal', lang=lang),
        build_confirm_modal('pm-ai-modal', lang=lang),
        dcc.Store(id='pm-lang-store', data=lang),
        dcc.Store(id='pm-results-store'),
        html.H2(t('pm_title', lang)),
        html.P(t('pm_subtitle', lang), className="text-muted"),
        html.Hr(),
        dbc.Row([
            dbc.Col(control_panel, width=12, lg=4),
            dbc.Col(result_panel, width=12, lg=8),
        ]),
    ])


app.layout = create_plasmid_layout()


# ----------------------------- Callbacks -----------------------------

@app.callback(
    Output('pm-sequence-input', 'value'),
    Input('pm-example-btn', 'n_clicks'),
    prevent_initial_call=True
)
def load_example(n_clicks):
    if not n_clicks:
        return no_update
    return EXAMPLE_PLASMID


@app.callback(
    [Output('pm-results-area', 'children'),
     Output('pm-results-store', 'data'),
     Output('pm-ai-container', 'style')],
    Input('pm-draw-modal-confirm', 'n_clicks'),
    [State('pm-sequence-input', 'value'),
     State('pm-lang-store', 'data')],
    prevent_initial_call=True
)
def draw_map(n_clicks, sequence, lang, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'

    if not n_clicks:
        return no_update, no_update, no_update

    # Kredi (5)
    from billing.dash_helpers import try_charge
    ok, msg, _user = try_charge(kwargs, 'bio_plasmid_map', cost=5, lang=lang,
                                description="Plazmit harita çizimi")
    if not ok:
        return msg, None, {'display': 'none'}

    seq_clean = clean_sequence(sequence)
    if not seq_clean:
        return dbc.Alert(t('pm_no_seq', lang), color="warning"), None, {'display': 'none'}
    if not re.fullmatch(r'[ATGCN]+', seq_clean):
        return dbc.Alert(t('pm_invalid_seq', lang), color="warning"), None, {'display': 'none'}
    if len(seq_clean) < 30:
        return dbc.Alert(t('pm_too_short', lang), color="warning"), None, {'display': 'none'}

    try:
        orfs = find_orfs(seq_clean)
        cutters = find_single_cutters(seq_clean)
    except ImportError:
        return dbc.Alert(t('pm_no_biopython', lang), color="danger"), None, {'display': 'none'}
    except Exception as e:
        return dbc.Alert(f"{t('pm_error', lang)} {e}", color="danger"), None, {'display': 'none'}

    total_length = len(seq_clean)
    fig = create_plasmid_figure(total_length, orfs, cutters, lang)

    # Özet kartları
    summary = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4(f"{total_length}", className="text-primary mb-0"),
            html.Small("bp")
        ])), md=4),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4(str(len(orfs)), className="text-success mb-0"),
            html.Small(t('pm_orf_count', lang))
        ])), md=4),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4(str(len(cutters)), className="text-danger mb-0"),
            html.Small(t('pm_cutter_count', lang))
        ])), md=4),
    ], className="mb-3")

    # ORF tablosu
    orf_table = None
    if orfs:
        orf_table = html.Div([
            html.H5([html.I(className="fas fa-dna me-2"), t('pm_orf_title', lang)],
                    className="mt-3 mb-2"),
            dash_table.DataTable(
                data=[{
                    '#': i + 1,
                    t('pm_col_start', lang): o['start'],
                    t('pm_col_end', lang): o['end'],
                    t('pm_col_strand', lang): '+' if o['strand'] == 1 else '−',
                    t('pm_col_length', lang): o['length'],
                    t('pm_col_aa', lang): o['aa'],
                } for i, o in enumerate(orfs)],
                columns=[{'name': c, 'id': c} for c in
                         ['#', t('pm_col_start', lang), t('pm_col_end', lang),
                          t('pm_col_strand', lang), t('pm_col_length', lang), t('pm_col_aa', lang)]],
                style_cell={'textAlign': 'left', 'fontFamily': 'monospace', 'fontSize': '13px'},
                style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                page_size=10,
            )
        ])

    results_area = html.Div([
        summary,
        dcc.Graph(figure=fig),
        orf_table if orf_table else html.Div(),
    ])

    store_data = {
        'total_length': total_length,
        'orf_count': len(orfs),
        'cutters': [c['name'] for c in cutters],
        'orfs': [{'start': o['start'], 'end': o['end'], 'strand': o['strand'], 'aa': o['aa']}
                 for o in orfs[:5]],
    }

    return results_area, store_data, {'display': 'block'}


@app.callback(
    Output('pm-ai-output', 'children'),
    Input('pm-ai-modal-confirm', 'n_clicks'),
    [State('pm-results-store', 'data'),
     State('pm-lang-store', 'data')],
    prevent_initial_call=True
)
def ai_comment(n_clicks, store_data, lang, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'

    if not n_clicks or not store_data:
        return no_update

    from billing.dash_helpers import try_charge
    ok, msg, _user = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                                description="Plazmit harita AI yorumu")
    if not ok:
        return msg

    total = store_data.get('total_length', 0)
    orf_count = store_data.get('orf_count', 0)
    cutters = store_data.get('cutters', [])

    if lang == 'tr':
        prompt = (
            f"Bir plazmit haritası analiz edildi. Plazmit boyutu: {total} bp. "
            f"Tespit edilen ORF (gen adayı) sayısı: {orf_count}. "
            f"Tek kesim yapan restriksiyon enzimleri: {', '.join(cutters) if cutters else 'yok'}. "
            f"Bu plazmit hakkında kısa bir moleküler biyoloji değerlendirmesi yap: "
            f"klonlama için uygun enzimler, ORF'lerin olası işlevi, dikkat edilmesi gerekenler. "
            f"En fazla 3-4 paragraf, Türkçe, pratik öneriler."
        )
    else:
        prompt = (
            f"A plasmid map was analyzed. Plasmid size: {total} bp. "
            f"Number of detected ORFs (gene candidates): {orf_count}. "
            f"Single-cutter restriction enzymes: {', '.join(cutters) if cutters else 'none'}. "
            f"Provide a brief molecular biology evaluation of this plasmid: "
            f"suitable enzymes for cloning, possible function of ORFs, things to watch out for. "
            f"Max 3-4 paragraphs, in English, practical recommendations."
        )

    try:
        from ai_engine.services import generate_with_pool
        comment, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-3.5-flash'
        )
        if not comment:
            return dbc.Alert(t('pm_ai_error', lang), color="warning")
        return dbc.Card(dbc.CardBody([
            html.H5([html.I(className="fas fa-robot me-2"), t('pm_ai_title', lang)], className="mb-3"),
            dcc.Markdown(comment)
        ]))
    except Exception as e:
        return dbc.Alert(f"{t('pm_ai_error', lang)} {e}", color="danger")


@app.callback(Output("plasmid_map", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:plasmid_map')
    except Exception:
        return False


# --- Kredi onay modalı: pm-draw-btn ---
@app.callback(
    Output('pm-draw-modal', 'is_open'),
    Output('pm-draw-modal-body', 'children'),
    Output('pm-draw-modal-confirm', 'disabled'),
    Input('pm-draw-btn', 'n_clicks'),
    Input('pm-draw-modal-cancel', 'n_clicks'),
    Input('pm-draw-modal-confirm', 'n_clicks'),
    State('pm-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_pm_draw_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'pm-draw-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_plasmid_map', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: pm-ai-btn ---
@app.callback(
    Output('pm-ai-modal', 'is_open'),
    Output('pm-ai-modal-body', 'children'),
    Output('pm-ai-modal-confirm', 'disabled'),
    Input('pm-ai-btn', 'n_clicks'),
    Input('pm-ai-modal-cancel', 'n_clicks'),
    Input('pm-ai-modal-confirm', 'n_clicks'),
    State('pm-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_pm_ai_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'pm-ai-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
