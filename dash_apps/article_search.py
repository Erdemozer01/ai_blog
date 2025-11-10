import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update, dash_table
from django_plotly_dash import DjangoDash

# PubMed API'si için
from Bio import Entrez
# YENİ: Çeviri için AI modelini ve API anahtarını kullanmak üzere importlar
import google.generativeai as genai
from blog.models import APIKey


# --- ÇEVİRİ FONKSİYONU (Yeniden GEMINI API VERSİYONU) ---
def translate_to_english(text_to_translate):
    """Verilen metni Google Gemini kullanarak İngilizce'ye çevirir."""
    if not text_to_translate or len(text_to_translate.strip()) < 2:
        return text_to_translate

    try:
        # Veritabanından aktif Gemini API anahtarını al
        api_key_object = APIKey.objects.filter(service_name='Google Gemini', is_active=True).first()
        genai.configure(api_key=api_key_object.key)

        prompt = f"Translate the following Turkish medical phrase to English for a PubMed search. Return only the accurately translated English text and nothing else, no quotation marks:\n\n'{text_to_translate}'"

        model = genai.GenerativeModel(model_name="gemini-2.5-flash")

        response = model.generate_content(prompt)
        translated_text = response.text.strip()

        return translated_text

    except APIKey.DoesNotExist:
        print("Çeviri için aktif bir Google Gemini API anahtarı bulunamadı.")
        return text_to_translate  # Anahtar yoksa, çevirmeden orijinal metni döndür
    except Exception as e:
        print(f"Çeviri sırasında hata: {e}")
        return text_to_translate  # Hata olursa, çevirmeden geri döndür


# --- Arka Plan Fonksiyonları ---

def search_and_fetch_pubmed(query, max_results=10, email="your_email@example.com"):
    """
    PubMed'de arama yapar ve bulunan tüm makalelerin detaylarını tek seferde çeker.
    """
    Entrez.email = email
    if not query:
        return []

    try:
        handle_search = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
        record_search = Entrez.read(handle_search)
        handle_search.close()
        id_list = record_search["IdList"]

        if not id_list:
            return []

        handle_fetch = Entrez.efetch(db="pubmed", id=id_list, rettype="medline", retmode="xml")
        records_fetch = Entrez.read(handle_fetch)
        handle_fetch.close()

        articles = []
        for paper in records_fetch['PubmedArticle']:
            article_info = paper['MedlineCitation']['Article']
            title = article_info.get('ArticleTitle', 'Başlık bulunamadı')
            authors_list = article_info.get('AuthorList', [])
            authors = ', '.join([f"{author.get('LastName', '')} {author.get('Initials', '')}" for author in
                                 authors_list]) if authors_list else "Yazar bulunamadı"
            journal = article_info.get('Journal', {}).get('Title', 'Dergi bilgisi yok')
            year = article_info.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {}).get('Year', 'Tarih yok')
            pmid = paper['MedlineCitation'].get('PMID', '')
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
            markdown_title = f"[{title}]({url})"

            articles.append({
                "title": markdown_title,
                "authors": authors.strip(),
                "journal": journal,
                "year": year,
            })
        return articles

    except Exception as e:
        print(f"Entrez API hatası: {e}")
        return []


# --- Ön Yüz: Dash Uygulaması ---
app = DjangoDash('ArticleSearchApp', external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])


def create_article_search_layout():
    """Makale arama sayfasının navbar'sız, sadece içerik bölümünü oluşturur."""
    sidebar = dbc.Col(
        [
            html.H4("Makale Arama", className="mb-4 mt-4"),
            html.Hr(),
            html.P("Aramak istediğiniz konuyu herhangi bir dilde yazabilirsiniz.", className="text-muted small"),
            dbc.Label("Makale Konusu veya Anahtar Kelime:", className="fw-bold"),
            dbc.Input(id="search-query-input", placeholder="Örn: kanser araştırmaları", type="text", className="mb-3"),
            dbc.Label("Makale Sayısı:", className="fw-bold"),
            dbc.Input(id="max-results-input", placeholder="10", type="number", value=10, min=10, max=500, step=5,
                      className="mb-4"),
            dbc.Button("Ara", id="search-button", color="primary", className="w-100 mb-4"),
        ],
        md=3,
        className="bg-light border-end p-5 shadow-lg",
        style={"margin-left": "auto", "margin-right": "auto"},
    )

    content = dbc.Col(
        [
            html.H4("Arama Sonuçları", className="p-4 pb-0"),
            html.Div(id="translated-query-display", className="px-4 text-muted fst-italic small"),
            dcc.Loading(
                id="loading-results", type="border",
                children=html.Div(id="results-table-div", className="p-2",
                                  style={"margin-left": "auto", "margin-right": "auto", "margin-bottom": "50%"},
                                  children=html.P("Makale Konusu veya Anahtar Kelime ile arama yapın."))
            ),
        ],
        md=8,
        style={"margin-left": "auto", "margin-right": "auto", "margin-bottom": "30%"},
    )

    return html.Div([
        dbc.Container([
            dbc.Row([
                sidebar,
                content,
            ])
        ], fluid=True, className="mt-4")
    ])


# --- CALLBACK (Arama için) ---
@app.callback(
    Output("results-table-div", "children"),
    Output("translated-query-display", "children"),
    Input("search-button", "n_clicks"),
    State("search-query-input", "value"),
    State("max-results-input", "value"),
    prevent_initial_call=True
)
def update_search_results(n_clicks, query, max_results):
    if not query:
        return dbc.Alert("Lütfen bir arama terimi girin.", color="warning"), ""

    translated_query = translate_to_english(query)
    display_text = ""
    if query.lower() != translated_query.lower():
        display_text = f"Arama yapılıyor: '{translated_query}' (Orijinal: '{query}')"

    articles = search_and_fetch_pubmed(translated_query, max_results)

    if not articles:
        return dbc.Alert("Aramanızla eşleşen sonuç bulunamadı.", color="info"), display_text

    return dash_table.DataTable(
        id='article-datatable',
        data=articles,
        columns=[
            {'name': 'Başlık', 'id': 'title', 'presentation': 'markdown'},
            {'name': 'Yazarlar', 'id': 'authors'},
            {'name': 'Dergi', 'id': 'journal'},
            {'name': 'Yıl', 'id': 'year'},
        ],
        page_action='native',
        page_size=10,
        sort_action='native',
        markdown_options={"link_target": "_blank"},
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': 'sans-serif', 'whiteSpace': 'normal',
                    'height': 'auto'},
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold', 'border': '1px solid #dee2e6'},
        style_data={'border': '1px solid #dee2e6'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f2f2f2'}],
        style_table={'overflowX': 'auto'},
    ), display_text


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
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open