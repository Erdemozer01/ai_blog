import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update, dash_table
from django_plotly_dash import DjangoDash
from Bio import Entrez


# --- ÇEVİRİ FONKSİYONU ---
def translate_to_english(text_to_translate):
    """Verilen metni Google Gemini kullanarak İngilizce'ye çevirir."""
    if not text_to_translate or len(str(text_to_translate).strip()) < 2:
        return text_to_translate

    try:
        from ai_engine.services import generate_with_pool

        prompt = f"Translate the following Turkish medical phrase to English for a PubMed search. Return only the accurately translated English text and nothing else, no quotation marks:\n\n'{text_to_translate}'"
        text, _key = generate_with_pool(prompt, service_name='Google Gemini', model_name='gemini-2.5-flash')
        return text.strip()

    except Exception as e:
        print(f"Çeviri sırasında hata oluştu: {e}")
        return text_to_translate


# --- PUBMED ARAMA FONKSİYONU ---
def search_and_fetch_pubmed(query, max_results=10, email="your_email@example.com"):
    """PubMed üzerinden makaleleri çeker."""
    Entrez.email = email
    if not query:
        return []

    try:
        # Arama yap ve ID listesini al
        handle_search = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
        record_search = Entrez.read(handle_search)
        handle_search.close()
        id_list = record_search.get("IdList", [])

        if not id_list:
            return []

        # Detayları çek
        handle_fetch = Entrez.efetch(db="pubmed", id=id_list, rettype="medline", retmode="xml")
        records_fetch = Entrez.read(handle_fetch)
        handle_fetch.close()

        articles = []
        for paper in records_fetch.get('PubmedArticle', []):
            try:
                citation = paper.get('MedlineCitation', {})
                article_info = citation.get('Article', {})

                title = article_info.get('ArticleTitle', 'Başlık bulunamadı')

                # Yazarları güvenli şekilde çek
                authors_list = article_info.get('AuthorList', [])
                if authors_list:
                    authors = ', '.join(
                        [f"{a.get('LastName', '')} {a.get('Initials', '')}" for a in authors_list if 'LastName' in a])
                else:
                    authors = "Yazar bilgisi yok"

                journal = article_info.get('Journal', {}).get('Title', 'Dergi bilgisi yok')

                # Yayın yılını çek
                pub_date = article_info.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
                year = pub_date.get('Year', pub_date.get('MedlineDate', 'Tarih yok'))

                pmid = str(citation.get('PMID', ''))
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
                markdown_title = f"[{title}]({url})"

                articles.append({
                    "title": markdown_title,
                    "authors": authors.strip(),
                    "journal": journal,
                    "year": year,
                })
            except Exception as inner_e:
                print(f"Makale işleme hatası: {inner_e}")
                continue

        return articles

    except Exception as e:
        print(f"Entrez API hatası: {e}")
        return []


# --- DASH UYGULAMASI VE LAYOUT ---
app = DjangoDash('ArticleSearchApp', external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])


def create_article_search_layout():
    return html.Div([
    dbc.Container([
        dbc.Row([
            # Yan Panel (Arama Formu)
            dbc.Col([
                html.H4("Makale Arama", className="mb-4 mt-4 text-primary"),
                html.Hr(),
                html.P("PubMed veritabanında yapay zeka destekli arama yapın.", className="text-muted small"),
                dbc.Label("Arama Terimi:", className="fw-bold"),
                dbc.Input(id="search-query-input", placeholder="Örn: alzheimer tedavi", type="text", className="mb-3"),
                dbc.Label("Sonuç Sayısı:", className="fw-bold"),
                dbc.Input(id="max-results-input", value=10, type="number", min=1, max=100, step=1, className="mb-4"),
                dbc.Button("Ara", id="search-button", color="primary", className="w-100 mb-4"),
            ], md=3, className="bg-light border-end p-4 shadow-sm"),

            # İçerik Paneli (Sonuçlar)
            dbc.Col([
                html.H4("Arama Sonuçları", className="p-4 pb-0"),
                html.Div(id="translated-query-display", className="px-4 text-muted fst-italic small"),
                dcc.Loading(
                    id="loading-results",
                    type="circle",
                    children=html.Div(id="results-table-div", className="p-4",
                                      children=html.P("Arama yapmak için yan paneli kullanın."))
                ),
            ], md=9),
        ])
    ], fluid=True)
])
app.layout = create_article_search_layout()


# --- CALLBACKS ---
@app.callback(
    [Output("results-table-div", "children"),
     Output("translated-query-display", "children")],
    [Input("search-button", "n_clicks")],
    [State("search-query-input", "value"),
     State("max-results-input", "value")],
    prevent_initial_call=True
)
def update_search_results(n_clicks, query, max_results):
    if not query:
        return dbc.Alert("Lütfen bir arama terimi girin.", color="warning"), ""

    # 1. Çeviri
    translated_query = translate_to_english(query)
    display_text = f"Aranan terim (İngilizce): '{translated_query}'" if query.lower() != translated_query.lower() else ""

    # 2. PubMed Veri Çekme
    articles = search_and_fetch_pubmed(translated_query, max_results)

    if not articles:
        return dbc.Alert("Eşleşen makale bulunamadı.", color="info"), display_text

    # 3. Tablo Oluşturma
    table = dash_table.DataTable(
        id='article-datatable',
        data=articles,
        columns=[
            {'name': 'Makale Başlığı', 'id': 'title', 'presentation': 'markdown'},
            {'name': 'Yazarlar', 'id': 'authors'},
            {'name': 'Dergi', 'id': 'journal'},
            {'name': 'Yıl', 'id': 'year'},
        ],
        page_action='native',
        page_size=10,
        sort_action='native',
        markdown_options={"link_target": "_blank"},
        style_cell={'textAlign': 'left', 'padding': '12px', 'whiteSpace': 'normal', 'height': 'auto'},
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold', 'border': '1px solid #dee2e6'},
        style_table={'overflowX': 'auto'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}],
    )

    return table, display_text

@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n_clicks, is_open):
    return not is_open
