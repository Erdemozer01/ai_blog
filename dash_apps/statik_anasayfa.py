# dash_apps/statik_anasayfa.py

import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State
from django.db.models import Q
from django.core.paginator import Paginator
from blog.models import GeneratedArticle, Category


external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('Anasayfa', external_stylesheets=external_stylesheets)


def create_post_cards(article_queryset):

    if not article_queryset:
        return [dbc.Alert("Filtre kriterlerinize uygun makale bulunamadı.", color="info", className="mt-4")]

    cards = []
    for article in article_queryset:
        detail_url = f"/article/{article.id}/"
        card = dbc.Card(
            dbc.CardBody([

                dbc.Badge(
                    article.category.name if article.category else "Kategorisiz",
                    color="primary",
                    pill=True,
                    className="mb-2"
                ),

                html.H2(html.A(article.title, href=detail_url, className="text-decoration-none")),
                html.P(
                    [
                        f"{article.created_at.strftime('%d %B %Y')} tarihinde oluşturuldu.",
                        html.Span(f" • {article.view_count} okunma", className="ms-2")
                    ],
                    className="text-muted"
                ),
                html.P(article.turkish_abstract or "Özet mevcut değil."),
                dbc.Button("Devamını Oku →", color="primary", outline=True, href=detail_url, external_link=True),
            ]),
            className="mb-4 shadow-sm"
        )
        cards.append(card)
    return cards


def get_sidebar():

    all_categories = Category.objects.all()
    category_options = [{'label': cat.name, 'value': str(cat.id)} for cat in all_categories]
    search_card = dbc.Card([
        dbc.CardHeader("Arama"),
        dbc.CardBody(dbc.Input(id='search-input', placeholder="Makalelerde ara...", type="search"))
    ], className="mb-4")
    sort_card = dbc.Card([
        dbc.CardHeader("Sırala"),
        dbc.CardBody(dcc.Dropdown(
            id='sort-by-dropdown',
            options=[
                {'label': 'En Yeni', 'value': 'newest'},
                {'label': 'En Çok Okunan', 'value': 'views'},
                {'label': 'En Faydalı', 'value': 'likes'},
                {'label': 'En Eski', 'value': 'oldest'},
            ],
            value='newest',
            clearable=False,
        ))
    ], className="mb-4")
    category_card = dbc.Card([
        dbc.CardHeader("Kategoriler"),
        dbc.CardBody(dcc.Dropdown(
            id='category-dropdown',
            options=category_options,
            placeholder="Tüm Kategoriler",
            clearable=True
        ))
    ], className="mb-4")
    return html.Div([search_card, sort_card, category_card])


def create_anasayfa_content_layout():
    """Anasayfanın Dash ile kontrol edilen içeriğini (sidebar, postlar) döndürür."""
    return html.Div([
        dcc.Store(id='filter-state-store'),
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div(id='post-container'),
                    html.Div(id='pagination-container', children=[
                        dbc.Pagination(id='pagination-ui', max_value=1, active_page=1, className="d-none")
                    ], className="mt-4")
                ], md=8),
                dbc.Col(get_sidebar(), md=4),
            ])
        ], className="mt-4")
    ])


@app.callback(
    Output('post-container', 'children'),
    Output('filter-state-store', 'data'),
    # Artık pagination bileşenini yeniden oluşturmuyoruz, sadece özelliklerini güncelliyoruz.
    Output('pagination-ui', 'max_value'),
    Output('pagination-ui', 'active_page'),
    Output('pagination-ui', 'className'),  # Görünürlüğünü kontrol etmek için

    Input('search-input', 'value'),
    Input('category-dropdown', 'value'),
    Input('sort-by-dropdown', 'value'),
    Input('pagination-ui', 'active_page'),

    State('filter-state-store', 'data'),
    prevent_initial_call=False
)
def master_filter_and_paginate(search_term, category_id, sort_by, active_page, stored_filters):
    current_filters = {
        'search': search_term, 'category': category_id, 'sort': sort_by
    }

    if (stored_filters or {}) != current_filters:
        page = 1
    else:
        page = active_page if active_page else 1

    queryset = GeneratedArticle.objects.select_related('category').filter(status='tamamlandi')

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if search_term and len(search_term.strip()) > 2:
        queryset = queryset.filter(Q(title__icontains=search_term) | Q(turkish_abstract__icontains=search_term))

    sort_order = '-created_at'
    if sort_by == 'views':
        sort_order = '-view_count'
    elif sort_by == 'likes':
        sort_order = '-likes'
    elif sort_by == 'oldest':
        sort_order = 'created_at'
    queryset = queryset.order_by(sort_order)

    paginator = Paginator(queryset, 5)
    page_obj = paginator.get_page(page)

    new_cards = create_post_cards(page_obj)

    pagination_classname = "pagination justify-content-center" if paginator.num_pages > 1 else "d-none"

    return new_cards, current_filters, paginator.num_pages, page, pagination_classname

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open