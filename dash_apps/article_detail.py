import dash_bootstrap_components as dbc
import markdown
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update, html, dcc
import plotly.express as px
import re
from django.db import transaction
from django.db.models import F
from blog.models import GeneratedArticle, ArticleFeedback
import pandas as pd

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
app = DjangoDash('ArticleDetailApp', external_stylesheets=external_stylesheets)


def create_table_from_json(table_data):
    try:
        header = [html.Thead(html.Tr([html.Th(col) for col in table_data['columns']]))]
        body = [html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in table_data['data']])]
        card_header = dbc.CardHeader([
            html.H5(table_data.get('title', 'Tablo'), className="mb-1"),
            html.P(table_data.get('description', ''), className="mb-0 text-muted small")
        ])
        card_footer = None
        if table_data.get('source'):
            card_footer = dbc.CardFooter(html.Small(f"Kaynak: {table_data.get('source')}", className="text-muted"))
        return dbc.Card([
            card_header,
            dbc.CardBody(
                dbc.Table(header + body, bordered=True, striped=True, hover=True, responsive=True, className="m-0")),
            card_footer
        ], className="my-5 shadow-sm")
    except (KeyError, TypeError):
        return dbc.Alert("Tablo verisi hatalı formatta.", color="danger")


def create_graph_from_json(data_item):
    """
    Gelen JSON verisine göre dinamik olarak bir Plotly grafiği veya Dash tablosu oluşturur.
    Hem sözlük (dict) hem de liste (list) formatındaki veri yapılarını işleyebilir.
    """
    template = "plotly_white"

    # --- Tablo Oluşturma Mantığı (Değişiklik yok) ---
    if data_item.get('type') == 'table':
        table_data = data_item.get('data', {})
        header = [html.Th(col) for col in table_data.get('columns', [])]
        rows = [html.Tr([html.Td(item) for item in row]) for row in table_data.get('data', [])]

        return html.Div([
            html.H5(data_item.get('title', 'Tablo'), className="mt-4"),
            html.P(data_item.get('description', ''), className="text-muted small"),
            dbc.Table([html.Thead(html.Tr(header)), html.Tbody(rows)], bordered=True, striped=True, hover=True,
                      responsive=True),
            html.Em(f"Kaynak: {data_item.get('source', 'Belirtilmemiş')}", className="small")
        ], className="mb-5")

    # --- Grafik Oluşturma Mantığı (YENİ VE ESNEK YAPI) ---
    elif data_item.get('type') == 'chart':
        chart_type = data_item.get('chart_type', 'bar')
        chart_data = data_item.get('data', {})

        if not chart_data:
            return html.Div("Grafik için veri bulunamadı.", className="alert alert-warning")

        df = None
        try:
            # --- AKILLI VERİ İŞLEME ---
            # Gelen verinin formatını kontrol et
            if isinstance(chart_data, dict):
                # Format 1: {'x': [...], 'y1': [...]} ise doğrudan DataFrame yap
                df = pd.DataFrame(chart_data)
            elif isinstance(chart_data, list) and len(chart_data) > 1:
                # Format 2: [['header1', 'header2'], [val1, val2], ...] ise
                # İlk satırı başlık, geri kalanını veri olarak al
                df = pd.DataFrame(chart_data[1:], columns=chart_data[0])
            else:
                return html.Div("Desteklenmeyen veya geçersiz grafik verisi formatı.", className="alert alert-danger")

            # Sütun adlarını dinamik olarak al
            if df.empty or len(df.columns) < 2:
                return html.Div("Grafik için yetersiz sütun verisi (en az 2 sütun gerekli).",
                                className="alert alert-warning")

            x_col = df.columns[0]  # Her zaman ilk sütunu X ekseni olarak kabul et
            y_cols = df.columns[1:].tolist()  # Geri kalan tüm sütunları Y ekseni olarak kabul et

            # --- GRAFİK ÇİZDİRME ---
            fig = None
            if chart_type == 'line':
                fig = px.line(df, x=x_col, y=y_cols, template=template, markers=True, title=data_item.get('title', ''))
            elif chart_type == 'bar':
                fig = px.bar(df, x=x_col, y=y_cols, template=template, barmode='group',
                             title=data_item.get('title', ''))
            elif chart_type == 'pie':
                if len(y_cols) == 1:
                    fig = px.pie(df, names=x_col, values=y_cols[0], template=template, title=data_item.get('title', ''))
                else:
                    return html.Div("Pasta grafiği için bir isim ve bir değer sütunu gereklidir.",
                                    className="alert alert-warning")
            else:  # Desteklenmeyen veya belirtilmeyen türler için varsayılan
                fig = px.line(df, x=x_col, y=y_cols, template=template, markers=True, title=data_item.get('title', ''))

            fig.update_layout(
                margin=dict(l=40, r=20, t=60, b=40),
                legend_title_text='',
                title_x=0.5
            )

            return html.Div([
                # Başlığı ve açıklamayı doğrudan grafiğin içine taşıdığımız için buradan kaldırabiliriz
                # html.H5(data_item.get('title', 'Grafik'), className="mt-4"),
                html.P(data_item.get('description', ''), className="text-muted small"),
                dcc.Graph(figure=fig),
                html.Em(f"Kaynak: {data_item.get('source', 'Belirtilmemiş')}", className="small")
            ], className="mb-5")

        except Exception as e:
            # Hata ayıklamayı kolaylaştırmak için daha detaylı hata mesajı
            return html.Div(f"Grafik oluşturulurken beklenmedik bir hata oluştu: {e}", className="alert alert-danger")

    return None

@app.callback(
    Output('dynamic-article-content', 'children'),
    Input('article-data-store', 'data')
)
def render_article_content(article_data):
    if not article_data:
        return dbc.Alert("Makale içeriği yüklenemedi.", color="danger")

    full_content = article_data.get('full_content', '')
    structured_data = article_data.get('structured_data', {})

    if not full_content:
        return html.P("Bu makale için içerik bulunamadı.")

    # Manuel (CKEditor) makaleler HTML içerir ve placeholder kullanmaz.
    # Bunları markdown'dan geçirmeden doğrudan HTML olarak göster.
    has_placeholder = '_||_STRUCTURED_DATA_' in full_content
    looks_like_html = bool(re.search(r'<(p|h[1-6]|div|figure|img|ul|ol|table|blockquote)\b', full_content, re.IGNORECASE))

    if looks_like_html and not has_placeholder:
        return html.Div(
            dcc.Markdown(full_content, dangerously_allow_html=True,
                         className="academic-text-format"),
            className="academic-text-format"
        )

    md_extensions = ['extra', 'attr_list']
    md = markdown.Markdown(extensions=md_extensions)
    pattern = r'(_\|\|_STRUCTURED_DATA_(\d+)_\|\|_)'
    content_parts = re.split(pattern, full_content)

    final_layout = []

    i = 0
    while i < len(content_parts):
        # Mevcut parça her zaman metindir.
        text_part = content_parts[i]
        if text_part.strip():
            html_content = md.convert(text_part)
            final_layout.append(
                dcc.Markdown(html_content, dangerously_allow_html=True, className="academic-text-format")
            )

        # Eğer listenin sonuna gelmediysek, sonraki iki parça yer tutucu ve numarasıdır.
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
    Output('feedback-button-store', 'data'),
    Input('like-button', 'n_clicks'),
    Input('dislike-button', 'n_clicks'),
    State('article-data-store', 'data'),
    State('feedback-button-store', 'data'),
    prevent_initial_call=True
)
def update_feedback(like_clicks, dislike_clicks, article_data, stored_clicks, user=None):
    # Giriş yapmamış kullanıcılar oy kullanamaz
    if not user or not user.is_authenticated:
        toast = dbc.Toast(
            "Oy kullanmak için giriş yapmanız gerekmektedir.",
            id="feedback-toast", header="Giriş Gerekli",
            icon="warning", duration=4000, is_open=True
        )
        return no_update, no_update, no_update, no_update, toast, stored_clicks

    stored_clicks = stored_clicks or {'like': 0, 'dislike': 0}
    button_id = None
    if like_clicks and like_clicks > stored_clicks.get('like', 0):
        button_id = 'like-button'
    elif dislike_clicks and dislike_clicks > stored_clicks.get('dislike', 0):
        button_id = 'dislike-button'

    if not button_id or not article_data:
        return no_update, no_update, no_update, no_update, no_update, stored_clicks

    try:
        article_id = article_data['article_id']
        vote_value = 'like' if button_id == 'like-button' else 'dislike'

        with transaction.atomic():
            # Kullanıcı daha önce oy kullandı mı?
            existing = ArticleFeedback.objects.filter(
                article_id=article_id, user=user
            ).first()

            if existing:
                # Aynı oy → iptal et
                if existing.vote == vote_value:
                    existing.delete()
                    if vote_value == 'like':
                        GeneratedArticle.objects.filter(pk=article_id).update(likes=F('likes') - 1)
                    else:
                        GeneratedArticle.objects.filter(pk=article_id).update(dislikes=F('dislikes') - 1)
                    toast_msg = "Oyunuz geri alındı."
                    toast_icon = "secondary"
                # Farklı oy → değiştir
                else:
                    old_vote = existing.vote
                    existing.vote = vote_value
                    existing.save()
                    if vote_value == 'like':
                        GeneratedArticle.objects.filter(pk=article_id).update(
                            likes=F('likes') + 1, dislikes=F('dislikes') - 1
                        )
                    else:
                        GeneratedArticle.objects.filter(pk=article_id).update(
                            likes=F('likes') - 1, dislikes=F('dislikes') + 1
                        )
                    toast_msg = "Oyunuz güncellendi."
                    toast_icon = "info"
            else:
                # İlk oy
                ArticleFeedback.objects.create(
                    article_id=article_id, user=user, vote=vote_value
                )
                if vote_value == 'like':
                    GeneratedArticle.objects.filter(pk=article_id).update(likes=F('likes') + 1)
                else:
                    GeneratedArticle.objects.filter(pk=article_id).update(dislikes=F('dislikes') + 1)
                toast_msg = "Geri bildiriminiz için teşekkür ederiz!"
                toast_icon = "success"

            article = GeneratedArticle.objects.only('likes', 'dislikes').get(pk=article_id)

        new_stored_clicks = {'like': like_clicks or 0, 'dislike': dislike_clicks or 0}
        toast = dbc.Toast(
            toast_msg, id="feedback-toast",
            header="İşlem Başarılı", icon=toast_icon, duration=3000, is_open=True
        )
        return f"({article.likes})", f"({article.dislikes})", False, False, toast, new_stored_clicks

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