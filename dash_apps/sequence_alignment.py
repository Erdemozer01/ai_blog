import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash
import json
import base64
import io

# Sadece Dash-Bio'yu kullanacağız
import dash_bio

# YENİ: Gemini API'sini kullanmak için importlar

from django.shortcuts import reverse
from billing.dash_helpers import build_confirm_modal

app = DjangoDash('SequenceAlignmentApp', external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])

# --- Sabitler ---
COLORSCALES_DICT = [
    {'value': 'buried', 'label': 'Buried'}, {'value': 'cinema', 'label': 'Cinema'},
    {'value': 'clustal2', 'label': 'Clustal2'}, {'value': 'clustal', 'label': 'Clustal'},
    {'value': 'helix', 'label': 'Helix'}, {'value': 'hydro', 'label': 'Hydrophobicity'},
    {'value': 'lesk', 'label': 'Lesk'}, {'value': 'mae', 'label': 'Mae'},
    {'value': 'nucleotide', 'label': 'Nucleotide'}, {'value': 'purine', 'label': 'Purine'},
    {'value': 'strand', 'label': 'Strand'}, {'value': 'taylor', 'label': 'Taylor'},
    {'value': 'turn', 'label': 'Turn'}, {'value': 'zappo', 'label': 'Zappo'},
]


# --- Yardımcı Fonksiyonlar ---
def parse_upload_content(contents):
    """dcc.Upload'dan gelen base64 içeriğini string'e çevirir."""
    if contents is None:
        return ""
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        return decoded.decode('utf-8')
    except Exception as e:
        return f"HATA: Dosya okunamadı - {e}"


def get_alignment_interpretation(fasta_data, lang='en'):
    """Hizalama verisini alıp Gemini'ye yorumlatır."""
    from dash_apps.i18n_helper import t, credit_label
    if not fasta_data:
        return t('sal_no_interaction', lang)

    try:
        from ai_engine.services import generate_with_pool

        if lang == 'tr':
            prompt = f"""
            Sen uzman bir biyoinformatikçi ve moleküler biyologsun. Aşağıda, önceden hizalanmış bir çoklu sekans hizalama (MSA) verisi FASTA formatında verilmiştir.

            --- HİZALAMA VERİSİ ---
            {fasta_data}

            --- GÖREVİN ---
            Bu hizalama verisini, bir biyoloji öğrencisinin anlayacağı dilde, basitçe yorumla. Yorumunda şu noktalara değin:
            1.  **Korunmuş Bölgeler (Conserved Regions):** Hangi bölgelerdeki amino asitler/nükleotidler tüm sekanslarda aynı veya çok benzer kalmış? Bu korunmuş bölgelerin biyolojik olarak önemi ne olabilir? (Örn: Bir proteinin aktif bölgesi, bir genin düzenleyici elemanı vb.)
            2.  **Değişken Bölgeler (Variable Regions):** Hangi bölgelerde daha fazla mutasyon veya farklılık (mismatch/gap) var? Bu değişkenliğin anlamı ne olabilir?
            3.  **Boşluklar (Gaps):** Görülen tire (-) işaretleri ne anlama geliyor? (Insertion/Deletion olayları) Bunların evrimsel veya fonksiyonel anlamı hakkında ne söylenebilir?
            4.  **Genel Biyolojik Çıkarım:** Bu sekansların genel benzerliğine bakarak ne gibi bir sonuca varabilirsin? (Örn: Bu proteinler aynı aileye mi ait? Evrimsel olarak yakınlar mı?)

            Cevabını Markdown formatında, başlıklar kullanarak düzenli bir şekilde ver.
            """
        else:
            prompt = f"""
            You are an expert bioinformatician and molecular biologist. Below is a pre-aligned multiple sequence alignment (MSA) in FASTA format.

            --- ALIGNMENT DATA ---
            {fasta_data}

            --- YOUR TASK ---
            Interpret this alignment data simply, in language a biology student would understand. Address the following points:
            1.  **Conserved Regions:** In which regions are amino acids/nucleotides identical or very similar across all sequences? What might be the biological importance of these conserved regions? (e.g., a protein's active site, a gene's regulatory element, etc.)
            2.  **Variable Regions:** Which regions show more mutations or differences (mismatch/gap)? What might this variability mean?
            3.  **Gaps:** What do the dash (-) marks mean? (Insertion/Deletion events) What can be said about their evolutionary or functional significance?
            4.  **General Biological Inference:** Based on the overall similarity of these sequences, what conclusion can you draw? (e.g., Do these proteins belong to the same family? Are they evolutionarily close?)

            Provide your answer in Markdown format, organized with headings.
            """

        text, _key = generate_with_pool(prompt, service_name='Google Gemini', model_name='gemini-3.5-flash')
        return text

    except Exception as e:
        return f"{t('sal_interaction_failed', lang)}: {e}"


# --- Ön Yüz: Dash Layout Fonksiyonu ---
def create_sequence_alignment_layout(lang='en'):
    """Gelişmiş Sekans Hizalama Görüntüleyicisi'nin layout'unu oluşturur."""
    from dash_apps.i18n_helper import t, credit_label

    sidebar = dbc.Col([
        dcc.Tabs(id='alignment-control-tabs', value='data-tab', children=[
            dcc.Tab(label=t('sal_data_input', lang), value='data-tab', children=html.Div(className='control-tab p-3', children=[
                html.H5(t('sal_data_upload', lang), className="mt-3"),
                html.P(t('sal_upload_hint', lang),
                       className="text-muted small"),
                dcc.Upload(id='upload-alignment-data',
                           children=html.Div([t('sal_drag_drop', lang), html.A(t('sal_select_file', lang))]),
                           style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                                  'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center',
                                  'margin': '10px 0'}),
                dcc.Textarea(id="alignment-data-textarea", placeholder=t('sal_paste_placeholder', lang),
                             style={'width': '100%', 'height': 300}, className="form-control mb-3 font-monospace"),
            ])),
            dcc.Tab(label=t('sal_graph_settings', lang), value='graph-tab',
                    children=html.Div(className='control-tab p-3', style={'maxHeight': '65vh', 'overflowY': 'auto'},
                                      children=[
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_color_scale', lang), className="fw-bold"),
                                              dcc.Dropdown(id='alignment-colorscale-dropdown', options=COLORSCALES_DICT,
                                                           value='clustal2'),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_preview_type', lang), className="fw-bold"),
                                              dcc.Dropdown(id='alignment-overview-dropdown',
                                                           options=[{'label': 'Heatmap', 'value': 'heatmap'},
                                                                    {'label': 'Slider', 'value': 'slider'},
                                                                    {'label': t('sal_none', lang), 'value': 'none'}],
                                                           value='heatmap'),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_text_size', lang), className="fw-bold"),
                                              dcc.Slider(id='alignment-textsize-slider', value=10, min=8, max=14,
                                                         step=1, marks={str(i): str(i) for i in range(8, 15)}),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_consensus', lang), className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showconsensus-radio',
                                                             options=[{'label': t('sal_show', lang), 'value': True},
                                                                      {'label': t('sal_hide', lang), 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_conservation', lang), className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showconservation-radio',
                                                             options=[{'label': t('sal_show', lang), 'value': True},
                                                                      {'label': t('sal_hide', lang), 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label(t('sal_gap', lang), className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showgap-radio',
                                                             options=[{'label': t('sal_show', lang), 'value': True},
                                                                      {'label': t('sal_hide', lang), 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                      ])),
            dcc.Tab(label=t('sal_interaction', lang), value='interaction-tab',
                    children=html.Div(className='control-tab p-3', children=[
                        html.P(t('sal_interaction_hint', lang),
                               className="mt-3 text-muted"),
                        html.Pre(id='alignment-events', style={'maxHeight': '50vh', 'overflowY': 'auto'})
                    ])),
        ])
    ], md=4, className="bg-light p-4 border-end")

    content = dbc.Col([
        html.H4(t('sal_result', lang), className="mt-4"),
        html.Hr(),
        dcc.Loading(id="loading-alignment-result", children=html.Div(id="alignment-result-container", children=[
            html.P(t('sal_result_placeholder', lang),
                   className="text-muted mt-4")
        ])),
        html.Div([
            dbc.Button([html.I(className="fas fa-robot me-2"),
                        f"{t('sal_ai_btn', lang)} {credit_label('bio_tool_ai', lang)}"],
                       id="alignment-ai-btn", color="info", outline=True, className="mt-3"),
            dbc.FormText(t('sal_ai_prompt_hint', lang), className="d-block text-muted mt-1"),
        ]),
        dcc.Loading(id="loading-alignment-interpretation",
                    children=html.Div(id="alignment-ai-interpretation-container", className="mt-4"))
    ], md=8, className="p-4")

    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('sal-modal', lang=lang),
        dcc.Store(id='sal-lang-store', data=lang),
        html.H2(t('sal_title', lang), className="mt-4"),
        html.P(t('sal_subtitle', lang),
               className="text-muted"),
        html.Hr(),
        dbc.Row([sidebar, content])
    ], fluid=True)


# --- Callback'ler ---

@app.callback(
    Output("alignment-data-textarea", "value"),
    Input("upload-alignment-data", "contents")
)
def update_textarea_from_upload(contents):
    if contents:
        return parse_upload_content(contents)
    return no_update


@app.callback(
    Output("alignment-result-container", "children"),
    Input("alignment-data-textarea", "value"),
    Input('alignment-colorscale-dropdown', 'value'),
    Input('alignment-overview-dropdown', 'value'),
    Input('alignment-textsize-slider', 'value'),
    Input('alignment-showconsensus-radio', 'value'),
    Input('alignment-showconservation-radio', 'value'),
    Input('alignment-showgap-radio', 'value'),
    State('sal-lang-store', 'data'),
    prevent_initial_call=True
)
def render_alignment_chart(data, colorscale, overview, textsize, showconsensus, showconservation, showgap, lang):
    """Veri girildiğinde veya grafik ayarları değiştiğinde hizalama grafiğini oluşturur."""
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not data:
        return html.P(t('sal_enter_data', lang), className="text-muted")

    try:
        alignment_chart = dash_bio.AlignmentChart(
            id='alignment-chart',
            data=data,
            colorscale=colorscale,
            overview=overview,
            textsize=textsize,
            showconsensus=showconsensus,
            showconservation=showconservation,
            showgap=showgap,
            height=800,
        )
        return alignment_chart

    except Exception as e:
        return dbc.Alert(f"{t('sal_graph_error', lang)}: {e}. {t('sal_format_hint', lang)}",
                         color="danger")


@app.callback(
    Output("alignment-ai-interpretation-container", "children"),
    Input('sal-modal-confirm', 'n_clicks'),
    State("alignment-data-textarea", "value"),
    State('sal-lang-store', 'data'),
    prevent_initial_call=True
)
def update_alignment_ai_interpretation(n_clicks, alignment_data, lang, **kwargs):
    """AI butonuna basıldığında hizalamayı yorumlar."""
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not n_clicks or not alignment_data:
        return None

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                             description="Hizalama AI yorumu")
    if not ok:
        return msg

    interpretation = get_alignment_interpretation(alignment_data, lang=lang)
    ai_card = dbc.Card([
        dbc.CardHeader(html.H5(t('sal_comment', lang))),
        dbc.CardBody(dcc.Markdown(interpretation, dangerously_allow_html=True))
    ], color="success", outline=True, className="mt-4")
    return ai_card


@app.callback(
    Output("alignment-events", "children"),
    Input("alignment-chart", "eventDatum"),
    State('sal-lang-store', 'data'),
    prevent_initial_call=True
)
def event_data_select(data, lang):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if data is None:
        return t('sal_no_interaction', lang)
    try:
        data_dict = json.loads(data)
        if not data_dict:
            return t('sal_no_interaction', lang)
        return [html.Div(f"- {key}: {data_dict[key]}") for key in data_dict.keys()]
    except Exception:
        return t('sal_interaction_failed', lang)


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


@app.callback(
    Output("sequence_alignment", "active"),
    Input("url", "pathname")
)
def toggle_sequence_alignment(pathname):
    return pathname == reverse('bio_tools:sequence_alignment')


# --- Kredi onay modalı: alignment-ai-btn tıklanınca onay sor ---
@app.callback(
    Output('sal-modal', 'is_open'),
    Output('sal-modal-body', 'children'),
    Output('sal-modal-confirm', 'disabled'),
    Input('alignment-ai-btn', 'n_clicks'),
    Input('sal-modal-cancel', 'n_clicks'),
    Input('sal-modal-confirm', 'n_clicks'),
    State('sal-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_sal_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'alignment-ai-btn' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
