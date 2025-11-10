# -*- coding: utf-8 -*-
import re
from io import StringIO
import pandas as pd
import google.generativeai as genai

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

# Django Entegrasyonu
from django_plotly_dash import DjangoDash
from blog.models import APIKey
from django.shortcuts import reverse

# --- UYGULAMA BAŞLATMA ---
# external_scripts kısmına Mermaid.js'i ekleyerek şemaların render edilmesini sağlıyoruz.
app = DjangoDash(
    name='PipelineDesignerApp',
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    external_scripts=["https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"]
)

# ==============================================================================
# SABİTLER VE YAPILANDIRMA
# ==============================================================================
# Daha karmaşık görevler için Pro modeli önerilir.
PIPELINE_MODEL_NAME = 'gemini-2.5-pro'

# ==============================================================================
# MERKEZİ MODEL YÖNETİM FONKSİYONU
# ==============================================================================
def get_gemini_model(model_name: str):
    """
    Django veritabanından API anahtarını alır, yapılandırır ve belirtilen
    Gemini modelini başlatır.
    """
    try:
        api_key_object = APIKey.objects.filter(is_active=True, service_name='Google Gemini').first()
        if not api_key_object:
            return None, "Aktif 'Google Gemini' API anahtarı veritabanında bulunamadı."
        genai.configure(api_key=api_key_object.key)
        model = genai.GenerativeModel(model_name)
        return model, None
    except Exception as e:
        return None, f"API yapılandırması veya model başlatma sırasında bir hata oluştu: {e}"


# ==============================================================================
# YARDIMCI PROMPT VE PARSING FONKSİYONLARI
# ==============================================================================
def generate_pipeline_prompt(pipeline_goal):
    """Pipeline tasarımı için Gemini modeline gönderilecek prompt'u oluşturur."""
    return f"""
Sen, yazılım mühendisliği ve sistem tasarımı konusunda uzman bir yapay zeka asistanısın.

**Görev:** Aşağıdaki hedef için bir iş akışı (pipeline) taslağı oluştur:
**Hedef:** "{pipeline_goal}"

**Kurallar:**
Cevabında HİÇBİR AÇIKLAMA METNİ OLMADAN, doğrudan sadece 3 bölüm ver:

1.  **Pipeline Akışı (MermaidJS):** `graph TD` formatında bir MermaidJS akış şeması. Sadece şema kodunu ` ```mermaid ... ``` ` bloğu içine yaz.
2.  **Adımların Açıklaması (Markdown Tablosu):** Pipeline'daki her bir adımı açıklayan bir tablo. Sütunlar: `Adım No`, `Araç/Teknoloji`, `Açıklama`.
3.  **Kod Parçacıkları:** Her bir adım için uygulanabilir, kısa ve varsayımsal bir kod örneği (Bash veya Python). Her kod bloğundan önce `### Adım X: [Adımın Adı]` şeklinde bir başlık kullan.

**Örnek Çıktı Formatı:**

```mermaid
graph TD
    A["Veri Toplama"] --> B("Veri İşleme");
    B --> C{{"Analiz"}};
    C --> D["Raporlama"];
```

| Adım No | Araç/Teknoloji | Açıklama |
|---|---|---|
| 1 | Python (requests) | API'den ham verileri çeker. |
| 2 | Pandas | Verileri temizler ve yapılandırır. |
| 3 | Scikit-learn | İşlenmiş veri üzerinde model eğitir. |
| 4 | Matplotlib | Sonuçları görselleştirir. |

### Adım 1: Veri Toplama
```python
import requests
def get_data(api_url):
    response = requests.get(api_url)
    return response.json()
```

### Adım 2: Veri İşleme
```python
import pandas as pd
def process_data(raw_data):
    df = pd.DataFrame(raw_data)
    df.dropna(inplace=True)
    return df
```
"""

def parse_pipeline_response(markdown_text):
    """Yapay zeka yanıtını ayrıştırarak şema, adımlar ve kodları çıkarır."""
    mermaid_graph = ""
    steps_df = None
    code_snippets = {}

    # 1. Mermaid Grafiğini Ayrıştır
    mermaid_match = re.search(r"```mermaid\n(.*?)\n```", markdown_text, re.DOTALL)
    if mermaid_match:
        # Sadece içeriği alıyoruz, ```mermaid``` kısımlarını değil.
        mermaid_graph = mermaid_match.group(1).strip()

    # 2. Markdown Tablosunu Ayrıştır
    table_match = re.search(r"\|.*Adım No.*\|\n\|.*-.*\|\n((?:\|.*\|\n?)*)", markdown_text, re.MULTILINE)
    if table_match:
        table_str = table_match.group(0)
        try:
            data = StringIO(table_str)
            # '|' karakterine göre ayır ve baştaki/sondaki boşlukları temizle.
            df = pd.read_csv(data, sep='|', header=0, skipinitialspace=True).dropna(axis=1, how='all').iloc[1:]
            # Sütun isimlerindeki boşlukları temizle
            df.columns = [col.strip() for col in df.columns]
            # İlk ve son sütunlar (boş) olabilir, onları at.
            df = df.iloc[:, 1:-1]
            steps_df = df
        except Exception as e:
            print(f"Pandas ile tablo ayrıştırma hatası: {e}")
            steps_df = None

    # 3. Kod Parçacıklarını Ayrıştır
    code_matches = re.finditer(r"###\s*(.*?)\s*```(\w*)\n(.*?)\n```", markdown_text, re.DOTALL)
    for match in code_matches:
        step_title = match.group(1).strip()
        language = match.group(2).strip() or "plaintext"
        code_content = match.group(3).strip()
        code_snippets[step_title] = {'language': language, 'code': code_content}

    return mermaid_graph, steps_df, code_snippets

# ==============================================================================
# LAYOUT
# ==============================================================================
def get_about_text():
    return dcc.Markdown("""
        **Pipeline Tasarım Asistanı'na Hoş Geldiniz!**

        Bu araç, Google Gemini yapay zeka modelini kullanarak çeşitli iş akışları (pipeline) tasarlamanıza yardımcı olmak için geliştirilmiştir.

        **Nasıl Çalışır?**
        1.  **Hedefinizi Belirtin:** Oluşturmak istediğiniz pipeline'ın amacını açıklayın. Örneğin, "Ham log dosyalarını işleyip günlük bir rapor oluşturan bir ETL hattı" veya "FASTQ dosyalarından başlayarak variant calling yapan bir biyoinformatik pipeline'ı".
        2.  **Tasarımı Oluşturun:** Yapay zeka, belirttiğiniz hedef doğrultusunda bir akış şeması, adımların detaylı bir tablosunu ve her adım için örnek kod parçacıkları üretecektir.
        3.  **İnceleyin ve Kullanın:** Oluşturulan tasarımı inceleyebilir ve kod parçacıklarını projelerinizde başlangıç noktası olarak kullanabilirsiniz.
    """)

def create_pipeline_layout():
    control_panel = dbc.Card(dbc.CardBody(dbc.Tabs(id="control-tabs", active_tab="tab-input", children=[
        dbc.Tab(label="Hakkında", tab_id="tab-about", children=html.Div(get_about_text(), className="p-3")),
        dbc.Tab(label="Tasarım Girişi", tab_id="tab-input", children=html.Div(className="p-3", children=[
            dbc.Label("Pipeline Amacı / Tanımı:", className="fw-bold mt-3"),
            dcc.Textarea(id='pipeline-goal-input',
                         placeholder="Örn: RNA-Seq verileri için diferansiyel gen ekspresyonu analizi yapacak bir pipeline oluştur.",
                         style={'width': '100%', 'height': 200}),
            html.Hr(),
            dbc.Button("Pipeline Tasarımını Oluştur", id="btn-generate-pipeline", color="primary", className="w-100"),
        ])),
    ])))

    result_panel = dbc.Card([
        dbc.CardHeader("Sonuçlar"),
        dbc.CardBody(dcc.Loading(id="loading-results-spinner",
                                 children=html.Div(id="pipeline-output", className="p-3", children=html.P(
                                     "Başlamak için hedeflerinizi girip butona tıklayın.",
                                     className="text-muted"
                                 ))))
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        html.H2("Pipeline Tasarım Asistanı"),
        html.Hr(),
        dbc.Row([
            dbc.Col(control_panel, width=12, lg=4),
            dbc.Col(result_panel, width=12, lg=8)
        ])
    ])


app.layout = create_pipeline_layout()


# ==============================================================================
# ANA CALLBACK
# ==============================================================================
@app.callback(
    Output('pipeline-output', 'children'),
    Input('btn-generate-pipeline', 'n_clicks'),
    State('pipeline-goal-input', 'value'),
    prevent_initial_call=True
)
def handle_pipeline_generation(n_clicks, pipeline_goal):
    if not pipeline_goal:
        return dbc.Alert("Lütfen pipeline amacını açıklayan bir metin girin.", color="warning")

    model, error_msg = get_gemini_model(PIPELINE_MODEL_NAME)
    if error_msg:
        return dbc.Alert(error_msg, color="danger")

    try:
        prompt = generate_pipeline_prompt(pipeline_goal)
        response = model.generate_content(prompt)
        mermaid_graph, steps_df, code_snippets = parse_pipeline_response(response.text)
    except Exception as e:
        return dbc.Alert(f"Pipeline tasarımı oluşturulurken bir hata oluştu: {e}", color="danger")

    output_components = []

    # Mermaid Şeması
    if mermaid_graph:
        output_components.extend([
            html.H4("Pipeline Akış Şeması"),
            # Mermaid component'i, şema kodunu doğrudan render eder.
            html.Div(className="mermaid", children=mermaid_graph, style={'textAlign': 'center'}),
            html.Hr()
        ])
    else:
        output_components.append(dbc.Alert("Pipeline akış şeması oluşturulamadı.", color="warning"))

    # Adımlar Tablosu
    if steps_df is not None and not steps_df.empty:
        output_components.extend([
            html.H4("Adımların Açıklaması"),
            dbc.Table.from_dataframe(steps_df, striped=True, bordered=True, hover=True, responsive=True),
            html.Hr()
        ])
    else:
        output_components.append(dbc.Alert("Pipeline adımları tablosu oluşturulamadı.", color="warning"))

    # Kod Parçacıkları
    if code_snippets:
        output_components.append(html.H4("Kod Parçacıkları"))
        for i, (title, snippet) in enumerate(code_snippets.items()):
            code_content = snippet['code']
            language = snippet['language']

            code_card = dbc.Card(
                dbc.CardBody([
                    html.H6(title, className="card-title"),
                    html.Div(
                        className="position-relative",
                        children=[
                            dcc.Markdown(
                                f"```{language}\n{code_content}\n```",
                                className="p-2 bg-light rounded border"
                            ),
                            dcc.Clipboard(
                                content=code_content,
                                className="position-absolute top-0 end-0 mt-1 me-1 p-1",
                                title="Kodu Kopyala",
                            )
                        ]
                    )
                ]),
                className="mb-3"
            )
            output_components.append(code_card)

    if not any([mermaid_graph, isinstance(steps_df, pd.DataFrame), code_snippets]):
        return dbc.Alert(
            "Yapay zeka modelinden geçerli bir yanıt alınamadı. Lütfen girdinizi kontrol edip tekrar deneyin veya daha spesifik bir hedef belirtin.",
            color="danger"
        )

    return output_components


# ==============================================================================
# NAVBAR CALLBACK'LERİ (Değişiklik yok)
# ==============================================================================
@app.callback(Output("navbar-collapse", "is_open"), [Input("navbar-toggler", "n_clicks")],
              [State("navbar-collapse", "is_open")])
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

@app.callback(Output("pipeline_designer", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    # Bu kısmı kendi Django URL yapınıza göre düzenlemeniz gerekir.
    # Örneğin: 'bio_tools' uygulamanızın adı ve 'pipeline_designer' URL name'iniz ise:
    # return pathname == reverse('bio_tools:pipeline_designer')
    try:
        # Kendi projenizdeki app_name ve url name ile değiştirin
        return pathname == reverse('your_app_name:pipeline_designer_url_name')
    except:
        return False
