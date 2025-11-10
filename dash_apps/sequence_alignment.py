import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash
import json
import base64
import io

# Sadece Dash-Bio'yu kullanacağız
import dash_bio

# YENİ: Gemini API'sini kullanmak için importlar
import google.generativeai as genai
from blog.models import APIKey

from django.shortcuts import reverse

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


def get_alignment_interpretation(fasta_data):
    """Hizalama verisini alıp Gemini'ye yorumlatır."""
    if not fasta_data:
        return "Yorumlanacak hizalama verisi bulunamadı."

    try:
        api_key_object = APIKey.objects.filter(service_name='Google Gemini', is_active=True).first()
        if not api_key_object:
            return "Yorumlama için aktif bir Google Gemini API anahtarı bulunamadı."

        genai.configure(api_key=api_key_object.key)
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")

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

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Yorumlama sırasında bir hata oluştu: {e}"


# --- Ön Yüz: Dash Layout Fonksiyonu ---
def create_sequence_alignment_layout():
    """Gelişmiş Sekans Hizalama Görüntüleyicisi'nin layout'unu oluşturur."""

    sidebar = dbc.Col([
        dcc.Tabs(id='alignment-control-tabs', value='data-tab', children=[
            dcc.Tab(label='Veri Girişi', value='data-tab', children=html.Div(className='control-tab p-3', children=[
                html.H5("Veri Yükleme", className="mt-3"),
                html.P("Lütfen önceden hizalanmış bir FASTA veya Clustal dosyası yükleyin.",
                       className="text-muted small"),
                dcc.Upload(id='upload-alignment-data',
                           children=html.Div(['Dosyayı Sürükle-Bırak veya ', html.A('Dosya Seç')]),
                           style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                                  'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center',
                                  'margin': '10px 0'}),
                dcc.Textarea(id="alignment-data-textarea", placeholder="...veya hizalanmış veriyi buraya yapıştırın.",
                             style={'width': '100%', 'height': 300}, className="form-control mb-3 font-monospace"),
            ])),
            dcc.Tab(label='Grafik Ayarları', value='graph-tab',
                    children=html.Div(className='control-tab p-3', style={'maxHeight': '65vh', 'overflowY': 'auto'},
                                      children=[
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Renk Skalası", className="fw-bold"),
                                              dcc.Dropdown(id='alignment-colorscale-dropdown', options=COLORSCALES_DICT,
                                                           value='clustal2'),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Önizleme Tipi", className="fw-bold"),
                                              dcc.Dropdown(id='alignment-overview-dropdown',
                                                           options=[{'label': 'Heatmap', 'value': 'heatmap'},
                                                                    {'label': 'Slider', 'value': 'slider'},
                                                                    {'label': 'Yok', 'value': 'none'}],
                                                           value='heatmap'),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Metin Boyutu", className="fw-bold"),
                                              dcc.Slider(id='alignment-textsize-slider', value=10, min=8, max=14,
                                                         step=1, marks={str(i): str(i) for i in range(8, 15)}),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Konsensüs Sekansı", className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showconsensus-radio',
                                                             options=[{'label': 'Göster', 'value': True},
                                                                      {'label': 'Gizle', 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Korunma Grafiği", className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showconservation-radio',
                                                             options=[{'label': 'Göster', 'value': True},
                                                                      {'label': 'Gizle', 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                          html.Div(className="mb-3", children=[
                                              dbc.Label("Boşluk (Gap) Grafiği", className="fw-bold"),
                                              dbc.RadioItems(id='alignment-showgap-radio',
                                                             options=[{'label': 'Göster', 'value': True},
                                                                      {'label': 'Gizle', 'value': False}], value=True,
                                                             inline=True),
                                          ]),
                                      ])),
            dcc.Tab(label='Etkileşim Verisi', value='interaction-tab',
                    children=html.Div(className='control-tab p-3', children=[
                        html.P("Grafikteki bir karaktere tıklayarak veya üzerine gelerek verisini burada görün.",
                               className="mt-3 text-muted"),
                        html.Pre(id='alignment-events', style={'maxHeight': '50vh', 'overflowY': 'auto'})
                    ])),
        ])
    ], md=4, className="bg-light p-4 border-end")

    content = dbc.Col([
        html.H4("Hizalama Sonucu", className="mt-4"),
        html.Hr(),
        dcc.Loading(id="loading-alignment-result", children=html.Div(id="alignment-result-container", children=[
            html.P("Görüntülemek için soldaki panele hizalanmış bir sekans verisi girin veya yükleyin.",
                   className="text-muted mt-4")
        ])),
        dcc.Loading(id="loading-alignment-interpretation",
                    children=html.Div(id="alignment-ai-interpretation-container", className="mt-4"))
    ], md=8, className="p-4")

    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        html.H2("Çoklu Sekans Görüntüleme ve Yorumlama", className="mt-4"),
        html.P("Önceden hizalanmış sekansları yükleyin, görüntüleyin ve otomatik olarak yorumlayın.",
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
    prevent_initial_call=True
)
def render_alignment_chart(data, colorscale, overview, textsize, showconsensus, showconservation, showgap):
    """Veri girildiğinde veya grafik ayarları değiştiğinde hizalama grafiğini oluşturur."""
    if not data:
        return html.P("Görüntülemek için veri girin.", className="text-muted")

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
        return dbc.Alert(f"Grafik oluşturulurken hata: {e}. Lütfen verinin doğru formatta olduğundan emin olun.",
                         color="danger")


@app.callback(
    Output("alignment-ai-interpretation-container", "children"),
    Input("alignment-data-textarea", "value"),
    prevent_initial_call=True
)
def update_alignment_ai_interpretation(alignment_data):
    """Veri girildiğinde hizalamayı otomatik olarak yorumlar."""
    if not alignment_data:
        return None  # Veri yoksa yorum alanını temizle

    interpretation = get_alignment_interpretation(alignment_data)
    ai_card = dbc.Card([
        dbc.CardHeader(html.H5("Yorum")),
        dbc.CardBody(dcc.Markdown(interpretation, dangerously_allow_html=True))
    ], color="success", outline=True, className="mt-4")
    return ai_card


@app.callback(
    Output("alignment-events", "children"),
    Input("alignment-chart", "eventDatum"),
    prevent_initial_call=True
)
def event_data_select(data):
    if data is None:
        return "Etkileşim verisi yok."
    try:
        data_dict = json.loads(data)
        if not data_dict:
            return "Etkileşim verisi yok."
        return [html.Div(f"- {key}: {data_dict[key]}") for key in data_dict.keys()]
    except:
        return "Etkileşim verisi alınamadı."


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