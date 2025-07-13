# dash_apps/statik_anasayfa.py - Enhanced version

import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models import Q
from django_plotly_dash import DjangoDash

from blog.models import GeneratedArticle, Category

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('Anasayfa', external_stylesheets=external_stylesheets)

def create_post_cards(article_queryset):
    """Enhanced post cards with better styling and info"""
    
    if not article_queryset:
        return [
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-search fa-3x text-muted mb-3"),
                        html.H4("Makale Bulunamadı", className="text-muted"),
                        html.P("Filtre kriterlerinize uygun makale bulunamadı. Lütfen arama terimlerinizi değiştirin.")
                    ], className="text-center py-5")
                ])
            ], className="mb-4")
        ]

    cards = []
    for article in article_queryset:
        detail_url = f"/article/{article.id}/{article.slug}/"

        # Calculate reading time (approximate)
        word_count = len(article.full_content.split()) if article.full_content else 0
        reading_time = max(1, word_count // 200)  # Assuming 200 words per minute

        card = dbc.Card([
            dbc.CardBody([
                html.Div([
                    dbc.Badge(
                        article.category.name if article.category else "Kategorisiz",
                        color="primary",
                        pill=True,
                        className="mb-2"
                    ),
                    html.Div([
                        html.I(className="fas fa-clock me-1"),
                        f"{reading_time} dk okuma"
                    ], className="text-muted small float-end")
                ], className="clearfix"),

                html.H4(
                    html.A(
                        article.title,
                        href=detail_url,
                        className="text-decoration-none text-dark"
                    ),
                    className="mb-3"
                ),
                
                html.P(
                    article.turkish_abstract[:200] + "..." if article.turkish_abstract and len(
                        article.turkish_abstract) > 200
                    else article.turkish_abstract or "Özet mevcut değil.",
                    className="text-muted"
                ),

                html.Div([
                    html.Small([
                        html.I(className="fas fa-calendar-alt me-1"),
                        article.created_at.strftime('%d %B %Y')
                    ], className="text-muted me-3"),
                    html.Small([
                        html.I(className="fas fa-eye me-1"),
                        f"{article.view_count} okunma"
                    ], className="text-muted me-3"),
                    html.Small([
                        html.I(className="fas fa-thumbs-up me-1"),
                        f"{article.likes} beğeni"
                    ], className="text-muted")
                ], className="mb-3"),

                dbc.Button(
                    [html.I(className="fas fa-arrow-right me-2"), "Devamını Oku"],
                    color="primary",
                    outline=True,
                    size="sm",
                    href=detail_url,
                    external_link=True
                )
            ])
        ], className="mb-4 shadow-sm hover-shadow")
        
        cards.append(card)

    return cards

def get_sidebar():
    """Enhanced sidebar with better filters"""

    # Get categories with article counts
    categories = Category.objects.annotate(
        article_count=Count('generatedarticle')
    ).filter(article_count__gt=0)

    category_options = [
        {'label': f"{cat.name} ({cat.article_count})", 'value': str(cat.id)}
        for cat in categories
    ]

    # Advanced search card
    search_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-search me-2"),
            "Gelişmiş Arama"
        ]),
        dbc.CardBody([
            dbc.Input(
                id='search-input',
                placeholder="Başlık, içerik veya özette ara...",
                type="search",
                className="mb-3"
            ),
            dbc.FormText("En az 3 karakter girin", className="text-muted")
        ])
    ], className="mb-4")

    # Sort options
    sort_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-sort me-2"),
            "Sıralama"
        ]),
        dbc.CardBody([
            dcc.Dropdown(
                id='sort-by-dropdown',
                options=[
                    {'label': '📅 En Yeni', 'value': 'newest'},
                    {'label': '👁️ En Çok Okunan', 'value': 'views'},
                    {'label': '👍 En Faydalı', 'value': 'likes'},
                    {'label': '📅 En Eski', 'value': 'oldest'},
                ],
                value='newest',
                clearable=False,
                className="custom-dropdown"
            )
        ])
    ], className="mb-4")

    # Category filter
    category_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-list me-2"),
            "Kategoriler"
        ]),
        dbc.CardBody([
            dcc.Dropdown(
                id='category-dropdown',
                options=category_options,
                placeholder="Tüm Kategoriler",
                clearable=True,
                className="custom-dropdown"
            )
        ])
    ], className="mb-4")

    # Stats card
    stats = cache.get('homepage_stats')
    if stats is None:
        stats = {
            'total_articles': GeneratedArticle.objects.filter(status='tamamlandi').count(),
            'total_views': GeneratedArticle.objects.filter(status='tamamlandi').aggregate(
                total=Sum('view_count')
            )['total'] or 0,
            'categories_count': Category.objects.filter(
                generatedarticle__status='tamamlandi'
            ).distinct().count()
        }
        cache.set('homepage_stats', stats, 300)

    stats_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-chart-bar me-2"),
            "İstatistikler"
        ]),
        dbc.CardBody([
            html.Div([
                html.H5(stats['total_articles'], className="text-primary mb-1"),
                html.Small("Toplam Makale", className="text-muted")
            ], className="text-center mb-2"),
            html.Hr(),
            html.Div([
                html.H5(f"{stats['total_views']:,}", className="text-success mb-1"),
                html.Small("Toplam Okunma", className="text-muted")
            ], className="text-center mb-2"),
            html.Hr(),
            html.Div([
                html.H5(stats['categories_count'], className="text-info mb-1"),
                html.Small("Aktif Kategori", className="text-muted")
            ], className="text-center")
        ])
    ], className="mb-4")

    return html.Div([search_card, sort_card, category_card, stats_card])


# ... (rest of the functions with similar enhancements)
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
        search_query = Q(title__icontains=search_term) | \
                       Q(turkish_abstract__icontains=search_term) | \
                       Q(full_content__icontains=search_term)  # Bu satırı ekleyin
        queryset = queryset.filter(search_query)

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