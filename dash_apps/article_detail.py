import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update, html, dcc, ctx
import plotly.express as px
import re

from blog.models import GeneratedArticle

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('ArticleDetailApp', external_stylesheets=external_stylesheets)


def create_table_from_json(table_data):
    """Gelen JSON verisinden bir Bootstrap Tablosu oluşturur."""
    try:
        header = [html.Thead(html.Tr([html.Th(col) for col in table_data['columns']]))]
        body = [html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in table_data['data']])]
        return html.Div([
            html.H5(table_data.get('title', 'Tablo'), className="mt-4 mb-3 text-center"),
            dbc.Table(header + body, bordered=True, striped=True, hover=True, responsive=True, className="shadow-sm")
        ], className="my-5")
    except (KeyError, TypeError):
        return dbc.Alert("Tablo verisi hatalı formatta.", color="danger")


def create_graph_from_json(chart_data):
    """
    AI'dan gelen tek bir görsel verisini (chart_data) alır ve bunu bir Dash bileşenine
    (Grafik veya Tablo) dönüştürür. Hatalara karşı dayanıklıdır.
    """
    # 1. Gelen verinin formatını kontrol et
    if not isinstance(chart_data, dict) or 'type' not in chart_data or 'data' not in chart_data:
        return dbc.Alert("Grafik verisi hatalı veya eksik formatta.", color="danger", className="my-4")

    chart_type = chart_data.get("type", "bar").lower()
    data = chart_data.get("data", [])
    chart_title = chart_data.get("title", "Başlıksız Grafik")

    if not data or not isinstance(data, list) or not all(isinstance(i, dict) for i in data):
        return dbc.Alert("Grafik için geçerli veri bulunamadı.", color="warning", className="my-4")

    # 2. Veriyi işlemeye çalış
    try:
        df = pd.DataFrame(data)

        if len(df.columns) < 2:
            return dbc.Alert("Grafik verisi en az iki sütun içermelidir.", color="warning", className="my-4")

        # Sütun isimlerini dinamik olarak al
        x_col, y_col = df.columns[0], df.columns[1]

        fig = None
        if chart_type == 'bar':
            fig = px.bar(df, x=x_col, y=y_col, title=chart_title, labels={x_col: x_col.title(), y_col: y_col.title()})
        elif chart_type == 'line':
            fig = px.line(df, x=x_col, y=y_col, title=chart_title, labels={x_col: x_col.title(), y_col: y_col.title()})
        elif chart_type == 'pie':
            fig = px.pie(df, names=x_col, values=y_col, title=chart_title)

        # 3. Sonucu oluştur
        if fig:
            # Temaya uyum sağlaması için arkaplanı şeffaf yap
            fig.update_layout(
                margin=dict(l=40, r=20, t=50, b=40),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="inherit")  # Yazı rengini ana temadan al
            )
            return dcc.Graph(figure=fig, className="my-4 shadow-sm border rounded")
        else:
            # Desteklenmeyen bir türse, veriyi şık bir tablo olarak göster
            return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, responsive=True,
                                            className="mt-4")

    except Exception as e:
        # Herhangi bir başka beklenmedik hata olursa
        return dbc.Alert(f"Grafik oluşturulurken bir hata oluştu: {e}", color="danger", className="my-4")


# === ANA İÇERİK OLUŞTURMA CALLBACK'İ ===
@app.callback(
    Output('dynamic-article-content', 'children'),
    Input('article-data-store', 'data')
)
def render_article_content(article_data):
    """
    Metin içeriğini ve yapısal veriyi alıp, aralarına tablo/grafik yerleştirerek
    nihai makale gövdesini oluşturur.
    """
    if not article_data:
        return dbc.Alert("Makale içeriği yüklenemedi.", color="danger")

    full_content = article_data.get('full_content', '')
    structured_data = article_data.get('structured_data', {})

    if not full_content:
        return html.P("Bu makale için içerik bulunamadı.")

    # Metni placeholder'lardan bölüyoruz. '(\d+)' placeholder'daki sayıyı yakalar.
    # Örn: _||_STRUCTURED_DATA_1_||_ -> '1' yakalanır.
    pattern = r'(_\|\|_STRUCTURED_DATA_(\d+)_\|\|_)'
    content_parts = re.split(pattern, full_content)

    final_layout = []
    # content_parts listesi şöyle görünür: ['metin kısmı', '_||_..._||_', '1', 'diğer metin kısmı', ...]
    # Bu yüzden 3'erli adımlarla ilerliyoruz.
    i = 0
    while i < len(content_parts):
        # Metin kısmını ekle
        text_segment = content_parts[i]
        if text_segment.strip():
            final_layout.append(dcc.Markdown(text_segment, className="academic-text-format"))

        # Eğer bir sonraki bölüm bir placeholder ise
        if i + 2 < len(content_parts):
            placeholder_num = content_parts[i + 2]
            data_item = structured_data.get(placeholder_num)

            if data_item:
                item_type = data_item.get('type')
                if item_type == 'table':
                    final_layout.append(create_table_from_json(data_item))
                elif item_type == 'chart':
                    final_layout.append(create_graph_from_json(data_item))
        i += 3

    return final_layout


@app.callback(
    Output('like-count', 'children'),
    Output('dislike-count', 'children'),
    Output('like-button', 'disabled'),
    Output('dislike-button', 'disabled'),
    Output('like-toast-container', 'children'),
    Output('feedback-button-store', 'data'),  # Store'u güncellemek için yeni Output

    Input('like-button', 'n_clicks'),
    Input('dislike-button', 'n_clicks'),

    State('article-data-store', 'data'),
    State('feedback-button-store', 'data'),  # Önceki tıklama sayılarını okumak için yeni State
    prevent_initial_call=True
)
def update_feedback(like_clicks, dislike_clicks, article_data, stored_clicks):
    # Hafızadaki tıklama sayılarını al, eğer yoksa sıfırdan başlat
    stored_clicks = stored_clicks or {'like': 0, 'dislike': 0}

    # Hangi butonun tıklanma sayısının arttığını kontrol et
    button_id = None
    if like_clicks > stored_clicks['like']:
        button_id = 'like-button'
    elif dislike_clicks > stored_clicks['dislike']:
        button_id = 'dislike-button'

    # Eğer bir butona basıldıysa devam et
    if not button_id:
        return no_update

    try:
        article = GeneratedArticle.objects.get(id=article_data['article_id'])

        if button_id == 'like-button':
            article.likes += 1
            article.save(update_fields=['likes'])
        elif button_id == 'dislike-button':
            article.dislikes += 1
            article.save(update_fields=['dislikes'])

        # Hafızadaki tıklama sayılarını güncelle
        new_stored_clicks = {'like': like_clicks, 'dislike': dislike_clicks}

        toast = dbc.Toast(
            "Geri bildiriminiz için teşekkür ederiz!", id="feedback-toast",
            header="İşlem Başarılı", icon="success", duration=3000, is_open=True
        )

        return f"({article.likes})", f"({article.dislikes})", True, True, toast, new_stored_clicks

    except GeneratedArticle.DoesNotExist:
        return "(0)", "(0)", True, True, dbc.Alert("Makale bulunamadı!", color="danger"), stored_clicks


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open
