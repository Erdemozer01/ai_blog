import dash_bootstrap_components as dbc
import markdown
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update, html, dcc
import plotly.express as px
import re
from blog.models import GeneratedArticle

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


def create_graph_from_json(chart_data):

    try:
        chart_type = chart_data.get('chart_type', 'bar').lower()
        fig = None
        template = "plotly_white"
        if chart_type == 'bar':
            fig = px.bar(chart_data['data'], x='x', y='y', labels={'x': '', 'y': ''}, text_auto=True, template=template,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(hovertemplate='<b>%{x}</b><br>Değer: %{y}<extra></extra>')
        elif chart_type == 'line':
            fig = px.line(chart_data['data'], x='x', y='y', labels={'x': '', 'y': ''}, markers=True, template=template)
            fig.update_traces(hovertemplate='<b>%{x}</b><br>Değer: %{y}<extra></extra>')
        elif chart_type == 'pie':
            fig = px.pie(chart_data['data'], names='x', values='y', template=template,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(hovertemplate='<b>%{label}</b><br>Oran: %{percent}<extra></extra>')
        elif chart_type == 'scatter':
            fig = px.scatter(chart_data['data'], x='x', y='y', labels={'x': '', 'y': ''}, template=template)
            fig.update_traces(hovertemplate='<b>X:</b> %{x}<br><b>Y:</b> %{y}<extra></extra>')

        if fig:
            fig.update_layout(
                margin=dict(l=40, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(
                    family="system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif")
            )
            card_header = dbc.CardHeader([
                html.H5(chart_data.get('title', 'Grafik'), className="mb-1"),
                html.P(chart_data.get('description', ''), className="mb-0 text-muted small")
            ])
            card_footer = None
            if chart_data.get('source'):
                card_footer = dbc.CardFooter(html.Small(f"Kaynak: {chart_data.get('source')}", className="text-muted"))
            return dbc.Card([
                card_header,
                dbc.CardBody(dcc.Graph(figure=fig, config={'displayModeBar': True, 'displaylogo': False})),
                card_footer
            ], className="my-5 shadow-sm")
        else:
            return dbc.Alert(f"Desteklenmeyen grafik türü: {chart_type}", color="warning")
    except (KeyError, TypeError):
        return dbc.Alert("Grafik verisi hatalı formatta.", color="danger")


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
def update_feedback(like_clicks, dislike_clicks, article_data, stored_clicks):
    # ... (Bu fonksiyon aynı, değişiklik yok)
    stored_clicks = stored_clicks or {'like': 0, 'dislike': 0}
    button_id = None
    if like_clicks and like_clicks > stored_clicks.get('like', 0):
        button_id = 'like-button'
    elif dislike_clicks and dislike_clicks > stored_clicks.get('dislike', 0):
        button_id = 'dislike-button'
    if not button_id or not article_data:
        return no_update, no_update, no_update, no_update, no_update, stored_clicks
    try:
        article = GeneratedArticle.objects.get(id=article_data['article_id'])
        if button_id == 'like-button':
            article.likes += 1
            article.save(update_fields=['likes'])
        elif button_id == 'dislike-button':
            article.dislikes += 1
            article.save(update_fields=['dislikes'])

        new_stored_clicks = {'like': like_clicks or 0, 'dislike': dislike_clicks or 0}
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
    # ... (Bu fonksiyon aynı, değişiklik yok)
    if n_clicks:
        return not is_open
    return is_open