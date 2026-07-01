# -*- coding: utf-8 -*-
import re
from io import StringIO
import pandas as pd

from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

# Django Entegrasyonu
from django_plotly_dash import DjangoDash
from billing.dash_helpers import build_confirm_modal

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
PIPELINE_MODEL_NAME = 'gemini-3.5-flash'

# ==============================================================================
# MERKEZİ MODEL YÖNETİM FONKSİYONU
# ==============================================================================
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

def create_pipeline_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label
    control_panel = dbc.Card(dbc.CardBody(dbc.Tabs(id="control-tabs", active_tab="tab-input", children=[
        dbc.Tab(label=t('pd_about', lang), tab_id="tab-about", children=html.Div(get_about_text(), className="p-3")),
        dbc.Tab(label=t('pd_design_input', lang), tab_id="tab-input", children=html.Div(className="p-3", children=[
            dbc.Label(t('pd_goal_label', lang), className="fw-bold mt-3"),
            dcc.Textarea(id='pipeline-goal-input',
                         placeholder=t('pd_goal_placeholder', lang),
                         style={'width': '100%', 'height': 200}),
            html.Hr(),
            dbc.Button(f"{t('pd_generate', lang)} {credit_label('bio_pipeline_designer', lang)}", id="btn-generate-pipeline", color="primary", className="w-100"),
        ])),
    ])))

    result_panel = dbc.Card([
        dbc.CardHeader(t('pd_results', lang)),
        dbc.CardBody(dcc.Loading(id="loading-results-spinner",
                                 children=html.Div(id="pipeline-output", className="p-3", children=html.P(
                                     t('pd_start_hint', lang),
                                     className="text-muted"
                                 ))))
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('pd-modal', lang=lang),
        dcc.Store(id='pd-lang-store', data=lang),
        html.H2(t('pd_title', lang)),
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
    Input('pd-modal-confirm', 'n_clicks'),
    State('pipeline-goal-input', 'value'),
    State('pd-lang-store', 'data'),
    prevent_initial_call=True
)
def handle_pipeline_generation(n_clicks, pipeline_goal, lang=None, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'
    if not pipeline_goal:
        return dbc.Alert(t('pd_enter_goal', lang), color="warning")

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_pipeline_designer', cost=5, lang=lang,
                             description="Pipeline tasarımı")
    if not ok:
        return msg

    try:
        from ai_engine.services import generate_with_fallback as generate_with_pool
        prompt = generate_pipeline_prompt(pipeline_goal)
        response_text, _key = generate_with_pool(prompt, service_name='Google Gemini', model_name='gemini-3.5-flash')
        mermaid_graph, steps_df, code_snippets = parse_pipeline_response(response_text)
    except Exception as e:
        return dbc.Alert(f"{t('pd_error', lang)}: {e}", color="danger")

    output_components = []

    # Mermaid Şeması
    if mermaid_graph:
        output_components.extend([
            html.H4(t('pd_flow_chart', lang)),
            html.Div(className="mermaid", children=mermaid_graph, style={'textAlign': 'center'}),
            html.Hr()
        ])
    else:
        output_components.append(dbc.Alert(t('pd_no_flow', lang), color="warning"))

    # Adımlar Tablosu
    if steps_df is not None and not steps_df.empty:
        output_components.extend([
            html.H4(t('pd_steps_desc', lang)),
            dbc.Table.from_dataframe(steps_df, striped=True, bordered=True, hover=True, responsive=True),
            html.Hr()
        ])
    else:
        output_components.append(dbc.Alert(t('pd_no_steps', lang), color="warning"))

    # Kod Parçacıkları
    if code_snippets:
        output_components.append(html.H4(t('pd_code_snippets', lang)))
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
                                title=t('pd_copy_code', lang),
                            )
                        ]
                    )
                ]),
                className="mb-3"
            )
            output_components.append(code_card)

    if not any([mermaid_graph, isinstance(steps_df, pd.DataFrame), code_snippets]):
        return dbc.Alert(
            t('pd_no_valid_response', lang),
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

@app.callback(Output("pipline_designer_view", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:pipline_designer_view')
    except Exception:
        return False


# --- Kredi onay modalı: btn-generate-pipeline tıklanınca onay sor ---
@app.callback(
    Output('pd-modal', 'is_open'),
    Output('pd-modal-body', 'children'),
    Output('pd-modal-confirm', 'disabled'),
    Input('btn-generate-pipeline', 'n_clicks'),
    Input('pd-modal-cancel', 'n_clicks'),
    Input('pd-modal-confirm', 'n_clicks'),
    State('pd-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_pd_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'btn-generate-pipeline' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_pipeline_designer', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
