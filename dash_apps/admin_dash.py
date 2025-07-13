# dash_apps/admin_dashboard.py

import datetime
import locale

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django_plotly_dash import DjangoDash

from blog.models import GeneratedArticle, Category, ContactMessage

try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'tr_TR')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'turkish')
        except locale.Error:
            print("Uyarı: Türkçe locale ayarlanamadı. Tarihler İngilizce görünebilir.")

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('AdminDashboard', external_stylesheets=external_stylesheets)


def get_offcanvas_content():
    return html.Div([
        html.H4("Admin Panel", className="text-center mb-4"),
        html.Hr(),
        dbc.Nav([
            dbc.NavLink([html.I(className="fas fa-tachometer-alt me-2"), "Dashboard"],
                        href="#", id="nav-dashboard", active=True, className="mb-2"),
            dbc.NavLink([html.I(className="fas fa-newspaper me-2"), "Makaleler"],
                        href="#", id="nav-articles", className="mb-2"),
            dbc.NavLink([html.I(className="fas fa-list me-2"), "Kategoriler"],
                        href="#", id="nav-categories", className="mb-2"),
            dbc.NavLink([html.I(className="fas fa-envelope me-2"), "Mesajlar"],
                        href="#", id="nav-messages", className="mb-2"),
            dbc.NavLink([html.I(className="fas fa-cog me-2"), "Ayarlar"],
                        href="#", id="nav-settings", className="mb-2"),
            dbc.NavLink([html.I(className="fas fa-chart-bar me-2"), "Analizler"],
                        href="#", id="nav-analytics", className="mb-2"),
        ], vertical=True, pills=True, className="mb-3"),
        html.Hr(),
        html.A([html.I(className="fas fa-home me-2"), "Siteye Dön"],
               href="/", className="btn btn-outline-primary w-100")
    ])


def get_dashboard_content():
    # Son 7 gün için tarih aralığı oluştur
    today = timezone.now()
    seven_days_ago = today - datetime.timedelta(days=7)

    # Son 7 gündeki makale sayısı
    recent_articles_count = GeneratedArticle.objects.filter(
        created_at__gte=seven_days_ago).count()

    # Toplam makale sayısı
    total_articles = GeneratedArticle.objects.count()

    # Toplam kategori sayısı
    total_categories = Category.objects.count()

    # Okunmamış mesaj sayısı
    unread_messages = ContactMessage.objects.filter(is_read=False).count()

    # İstatistik kartları
    stats_cards = dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H2(total_articles, className="card-title text-primary"),
                html.P("Toplam Makale", className="card-text"),
                html.Span([html.I(className="fas fa-file-alt me-2")], className="text-muted")
            ])
        ], className="shadow-sm"), width=3),

        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H2(recent_articles_count, className="card-title text-success"),
                html.P("Son 7 Günde Yazılan", className="card-text"),
                html.Span([html.I(className="fas fa-calendar-alt me-2")], className="text-muted")
            ])
        ], className="shadow-sm"), width=3),

        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H2(total_categories, className="card-title text-info"),
                html.P("Toplam Kategori", className="card-text"),
                html.Span([html.I(className="fas fa-list-alt me-2")], className="text-muted")
            ])
        ], className="shadow-sm"), width=3),

        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H2(unread_messages, className="card-title text-warning"),
                html.P("Okunmamış Mesaj", className="card-text"),
                html.Span([html.I(className="fas fa-envelope me-2")], className="text-muted")
            ])
        ], className="shadow-sm"), width=3),
    ], className="mb-4")

    # Kategori bazlı makale dağılımı grafiği
    try:
        category_counts = GeneratedArticle.objects.values('category__name') \
            .annotate(count=Count('id')) \
            .order_by('-count')

        categories = [item['category__name'] or 'Kategorisiz' for item in category_counts]
        counts = [item['count'] for item in category_counts]

        if categories and counts:
            fig = px.pie(
                names=categories,
                values=counts,
                title="Kategorilere Göre Makale Dağılımı",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        else:
            fig = px.pie(
                names=['Veri Yok'],
                values=[1],
                title="Kategorilere Göre Makale Dağılımı",
                hole=0.4
            )
    except Exception as e:
        print(f"Grafik oluşturma hatası: {e}")
        fig = px.pie(
            names=['Veri Yok'],
            values=[1],
            title="Kategorilere Göre Makale Dağılımı",
            hole=0.4
        )

    category_graph = dbc.Card([
        dbc.CardHeader("Kategori Analizi"),
        dbc.CardBody(dcc.Graph(figure=fig))
    ], className="shadow-sm mb-4")

    # Son eklenen makaleler tablosu
    recent_articles = GeneratedArticle.objects.select_related('category').order_by('-created_at')[:5]

    rows = []
    for idx, article in enumerate(recent_articles, 1):
        rows.append(html.Tr([
            html.Td(idx),
            html.Td(html.A(article.title, href=f"/article/{article.id}/{article.slug}/")),
            html.Td(article.category.name if article.category else "Kategorisiz"),
            html.Td(article.created_at.strftime('%d %B %Y')),
            html.Td(article.view_count)
        ]))

    recent_articles_table = dbc.Card([
        dbc.CardHeader("Son Eklenen Makaleler"),
        dbc.CardBody([
            dbc.Table([
                html.Thead(html.Tr([
                    html.Th("#"),
                    html.Th("Başlık"),
                    html.Th("Kategori"),
                    html.Th("Tarih"),
                    html.Th("Görüntülenme")
                ])),
                html.Tbody(rows)
            ], striped=True, bordered=True, hover=True, responsive=True)
        ])
    ], className="shadow-sm")

    return html.Div([
        html.H1("Dashboard", className="mb-4"),
        stats_cards,
        dbc.Row([
            dbc.Col(category_graph, md=6),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Performans Özeti"),
                dbc.CardBody([
                    html.P("Son 30 günde toplam görüntülenme: 1,245", className="mb-2"),
                    html.P("Ortalama makale okunma süresi: 3.2 dakika", className="mb-2"),
                    html.P("En popüler kategori: Teknoloji", className="mb-2"),
                ])
            ], className="shadow-sm mb-4"), md=6)
        ]),
        recent_articles_table
    ])


def get_articles_content(search_term=""):
    # Arama filtrelemesi
    try:
        if search_term:
            articles = GeneratedArticle.objects.select_related('category').filter(
                Q(title__icontains=search_term) | Q(user_request__icontains=search_term)
            ).order_by('-created_at')
        else:
            articles = GeneratedArticle.objects.select_related('category').order_by('-created_at')

        rows = []
        for idx, article in enumerate(articles, 1):
            try:
                edit_url = reverse('admin:blog_generatedarticle_change', args=[article.id])
            except:
                edit_url = f"/admin/blog/generatedarticle/{article.id}/change/"

            rows.append(html.Tr([
                html.Td(idx),
                html.Td(html.A(article.title, href=f"/article/{article.id}/{article.slug}/")),
                html.Td(article.category.name if article.category else "Kategorisiz"),
                html.Td(article.created_at.strftime('%d %B %Y')),
                html.Td(article.view_count),
                html.Td([
                    html.A(html.I(className="fas fa-edit text-primary"), href=edit_url, className="me-2"),
                    html.A(html.I(className="fas fa-external-link-alt text-info"),
                           href=f"/article/{article.id}/{article.slug}/", className="me-1")
                ])
            ]))

        # Sonuç sayısı gösterimi
        total_count = articles.count()
        results_text = f"Toplam {total_count} makale"
        if search_term:
            results_text += f" ('{search_term}' için arama sonucu)"

    except Exception as e:
        print(f"Makale listesi hatası: {e}")
        rows = []
        results_text = "Makale listesi yüklenirken hata oluştu"

    return html.Div([
        html.H1("Makaleler", className="mb-4"),
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col(html.H5("Tüm Makaleler"), width="auto"),
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.Input(
                                placeholder="Makale başlığında ara...",
                                type="search",
                                id="article-search-input",
                                value=search_term,
                                debounce=True
                            ),
                            dbc.Button(
                                html.I(className="fas fa-search"),
                                color="primary",
                                id="article-search-button"
                            ),
                            dbc.Button(
                                html.I(className="fas fa-times"),
                                color="secondary",
                                id="article-clear-button",
                                outline=True
                            )
                        ])
                    ], width="auto", className="ms-auto")
                ])
            ]),
            dbc.CardBody([
                html.P(results_text, className="text-muted mb-3"),
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("#"),
                        html.Th("Başlık"),
                        html.Th("Kategori"),
                        html.Th("Tarih"),
                        html.Th("Görüntülenme"),
                        html.Th("İşlemler")
                    ])),
                    html.Tbody(rows)
                ], striped=True, bordered=True, hover=True, responsive=True)
            ])
        ], className="shadow-sm")
    ])


def get_categories_content():
    try:
        categories = Category.objects.annotate(
            article_count=Count('generatedarticle')
        ).order_by('name')

        rows = []
        for idx, category in enumerate(categories, 1):
            edit_url = f"/admin/blog/category/{category.id}/change/"
            rows.append(html.Tr([
                html.Td(idx),
                html.Td(category.name),
                html.Td(category.article_count),
                html.Td(category.created_at.strftime('%d %B %Y')),
                html.Td([
                    html.A(html.I(className="fas fa-edit text-primary"), href=edit_url, className="me-2"),
                    html.A(html.I(className="fas fa-trash text-danger"), href="#", className="me-1")
                ])
            ]))
    except Exception as e:
        print(f"Kategori listesi hatası: {e}")
        rows = []

    return html.Div([
        html.H1("Kategoriler", className="mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Yeni Kategori Ekle"),
                    dbc.CardBody([
                        dbc.Input(placeholder="Kategori adı", className="mb-3"),
                        dbc.Button("Ekle", color="success")
                    ])
                ], className="shadow-sm mb-4")
            ], md=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Kategori Listesi"),
                    dbc.CardBody([
                        dbc.Table([
                            html.Thead(html.Tr([
                                html.Th("#"),
                                html.Th("Ad"),
                                html.Th("Makale Sayısı"),
                                html.Th("Oluşturulma Tarihi"),
                                html.Th("İşlemler")
                            ])),
                            html.Tbody(rows)
                        ], striped=True, bordered=True, hover=True, responsive=True)
                    ])
                ], className="shadow-sm")
            ], md=8)
        ])
    ])


def get_messages_content():
    try:
        messages = ContactMessage.objects.all().order_by('-created_at')

        rows = []
        for idx, message in enumerate(messages[:10], 1):
            rows.append(html.Tr([
                html.Td(idx),
                html.Td(message.name),
                html.Td(message.email),
                html.Td(message.subject),
                html.Td(message.created_at.strftime('%d %B %Y')),
                html.Td([html.I(className="fas fa-circle text-danger") if not message.is_read else ""]),
                html.Td([
                    dbc.Button(html.I(className="fas fa-eye"), color="primary", size="sm", className="me-1"),
                    dbc.Button(html.I(className="fas fa-trash"), color="danger", size="sm")
                ])
            ]))
    except Exception as e:
        print(f"Mesaj listesi hatası: {e}")
        rows = []

    return html.Div([
        html.H1("İletişim Mesajları", className="mb-4"),
        dbc.Card([
            dbc.CardHeader("Gelen Mesajlar"),
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("#"),
                        html.Th("Gönderen"),
                        html.Th("E-posta"),
                        html.Th("Konu"),
                        html.Th("Tarih"),
                        html.Th("Durum"),
                        html.Th("İşlemler")
                    ])),
                    html.Tbody(rows)
                ], striped=True, bordered=True, hover=True, responsive=True)
            ])
        ], className="shadow-sm")
    ])


def get_settings_content():
    return html.Div([
        html.H1("Ayarlar", className="mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Genel Ayarlar"),
                    dbc.CardBody([
                        html.Div([
                            dbc.Label("Site Başlığı"),
                            dbc.Input(value="AI Blog", type="text", className="mb-3")
                        ], className="mb-3"),
                        html.Div([
                            dbc.Label("Site Açıklaması"),
                            dbc.Textarea(
                                value="Çeşitli konularda üretilmiş akademik makaleleri ve analizleri keşfedin.",
                                className="mb-3")
                        ], className="mb-3"),
                        html.Div([
                            dbc.Label("İletişim E-postası"),
                            dbc.Input(value="iletisim@aiblog.com", type="email", className="mb-3")
                        ], className="mb-3"),
                        dbc.Button("Kaydet", color="primary")
                    ])
                ], className="shadow-sm mb-4")
            ], md=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("API Ayarları"),
                    dbc.CardBody([
                        html.Div([
                            dbc.Label("API Anahtarı"),
                            dbc.Input(value="***********************", type="password", className="mb-3")
                        ], className="mb-3"),
                        html.Div([
                            dbc.Label("API URL"),
                            dbc.Input(value="https://api.example.com/v1/", type="text", className="mb-3")
                        ], className="mb-3"),
                        dbc.Button("Kaydet", color="primary")
                    ])
                ], className="shadow-sm")
            ], md=6)
        ])
    ])


def get_analytics_content():
    try:
        articles_queryset = GeneratedArticle.objects.all().values(
            'title', 'view_count', 'likes', 'dislikes', 'category__name', 'created_at'
        )
        df_articles = pd.DataFrame(list(articles_queryset))

        if df_articles.empty:
            return html.Div([
                html.H1("Analizler ve İstatistikler", className="mb-4"),
                dbc.Alert("Grafik oluşturmak için makale verisi bulunamadı.", color="info",
                          className="text-center mt-4")
            ])

        # Rename 'category__name' to 'category' for easier use with Plotly Express
        if 'category__name' in df_articles.columns:
            df_articles.rename(columns={'category__name': 'category'}, inplace=True)
        else:
            df_articles['category'] = 'Kategorisiz'

        if 'created_at' in df_articles.columns:
            df_articles['created_at'] = pd.to_datetime(df_articles['created_at']).dt.date
        else:
            df_articles['created_at'] = pd.to_datetime('today').date()

        # Most Viewed Articles
        df_most_viewed = df_articles.sort_values(by='view_count', ascending=False).head(10)
        df_most_viewed = df_most_viewed.copy()
        df_most_viewed['short_title'] = df_most_viewed['title'].apply(lambda x: x[:25] + '...' if len(x) > 25 else x)

        fig_most_viewed = px.bar(df_most_viewed, x='short_title', y='view_count',
                                 title='En Çok Görüntülenen Makaleler',
                                 labels={'short_title': 'Makale Başlığı', 'view_count': 'Görüntülenme Sayısı'},
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_most_viewed.update_layout(height=400, margin=dict(t=50, b=60, l=0, r=0))
        fig_most_viewed.update_xaxes(tickangle=45)

        # Likes vs Dislikes per Article
        df_articles_copy = df_articles.copy()
        df_articles_copy['short_title'] = df_articles_copy['title'].apply(
            lambda x: x[:20] + '...' if len(x) > 20 else x)

        fig_likes_dislikes = go.Figure()
        fig_likes_dislikes.add_trace(go.Bar(
            x=df_articles_copy['short_title'][:10],
            y=df_articles_copy['likes'][:10],
            name='Beğeni',
            marker_color='green'
        ))
        fig_likes_dislikes.add_trace(go.Bar(
            x=df_articles_copy['short_title'][:10],
            y=df_articles_copy['dislikes'][:10],
            name='Beğenmeme',
            marker_color='red'
        ))
        fig_likes_dislikes.update_layout(
            barmode='group',
            title='Makale Başına Beğeni vs Beğenmeme',
            height=400,
            margin=dict(t=50, b=60, l=0, r=0)
        )
        fig_likes_dislikes.update_xaxes(title='Makale Başlığı', tickangle=45)
        fig_likes_dislikes.update_yaxes(title='Sayı')

        # Percentage of Positive Feedback Gauge
        total_likes = df_articles['likes'].sum()
        total_dislikes = df_articles['dislikes'].sum()
        total_feedback = total_likes + total_dislikes

        percentage_likes = (total_likes / total_feedback) * 100 if total_feedback > 0 else 0

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=percentage_likes,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Pozitif Geri Bildirim Yüzdesi"},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "lightgreen"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 50], 'color': 'lightcoral'},
                    {'range': [50, 75], 'color': 'lightgoldenrodyellow'},
                    {'range': [75, 100], 'color': 'lightgreen'}
                ],
                'threshold': {
                    'line': {'color': "darkblue", 'width': 4},
                    'thickness': 0.75,
                    'value': 75
                }
            }
        ))
        fig_gauge.update_layout(height=300, margin=dict(t=50, b=0, l=0, r=0))

        # Articles by Category
        df_category_counts = df_articles.groupby('category').size().reset_index(name='article_count')
        fig_categories = px.pie(df_category_counts, values='article_count', names='category',
                                title='Kategorilere Göre Makale Dağılımı',
                                color_discrete_sequence=px.colors.qualitative.Set3)
        fig_categories.update_layout(height=400, margin=dict(t=50, b=0, l=0, r=0))

        # Daily Trends for Views, Likes, Dislikes
        df_daily_trends = df_articles.groupby('created_at').agg(
            total_views=('view_count', 'sum'),
            total_likes=('likes', 'sum'),
            total_dislikes=('dislikes', 'sum')
        ).reset_index()
        df_daily_trends = df_daily_trends.sort_values(by='created_at')

        fig_daily_trends = px.line(df_daily_trends, x='created_at', y=['total_views', 'total_likes', 'total_dislikes'],
                                   title='Günlük Trendler (Görüntülenme, Beğeni, Beğenmeme)',
                                   labels={'created_at': 'Tarih', 'value': 'Sayı'},
                                   markers=True,
                                   color_discrete_map={'total_views': 'blue', 'total_likes': 'green',
                                                       'total_dislikes': 'red'})
        fig_daily_trends.update_xaxes(type='category', title='Tarih')
        fig_daily_trends.update_yaxes(title='Sayı')
        fig_daily_trends.update_layout(height=450, margin=dict(t=50, b=0, l=0, r=0))

        return html.Div([
            html.H1("Analizler ve İstatistikler", className="mb-4"),
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5("En Çok Görüntülenen Makaleler", className="card-title"),
                    dcc.Graph(figure=fig_most_viewed)
                ]), className="shadow-sm mb-4"), md=6),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5("Makale Başına Beğeni vs Beğenmeme", className="card-title"),
                    dcc.Graph(figure=fig_likes_dislikes)
                ]), className="shadow-sm mb-4"), md=6),
            ]),
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5("Pozitif Geri Bildirim Yüzdesi", className="card-title"),
                    dcc.Graph(figure=fig_gauge)
                ]), className="shadow-sm mb-4"), md=4),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5("Kategorilere Göre Makale Dağılımı", className="card-title"),
                    dcc.Graph(figure=fig_categories)
                ]), className="shadow-sm mb-4"), md=8),
            ]),
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5("Günlük Trendler", className="card-title"),
                    dcc.Graph(figure=fig_daily_trends)
                ]), className="shadow-sm mb-4"), md=12),
            ])
        ])

    except Exception as e:
        print(f"Analiz grafiği hatası: {e}")
        return html.Div([
            html.H1("Analizler ve İstatistikler", className="mb-4"),
            dbc.Alert(f"Grafik oluşturulurken hata oluştu: {str(e)}", color="danger", className="text-center mt-4")
        ])


# Ana uygulama düzeni - Offcanvas ile
app.layout = html.Div([
    # Offcanvas Menu
    dbc.Offcanvas(
        get_offcanvas_content(),
        id="offcanvas-menu",
        title="Admin Panel",
        is_open=False,
        placement="start",
        backdrop=True,
        scrollable=True,
        className="offcanvas-admin"
    ),

    # Ana içerik alanı
    dbc.Container([
        # Üst navbar
        dbc.Row([
            dbc.Col([
                html.Div([
                    dbc.Button(
                        html.I(className="fas fa-bars"),
                        id="offcanvas-toggle",
                        color="light",
                        outline=True,
                        size="sm",
                        className="me-2"
                    ),
                    html.H2("Admin Dashboard", className="d-inline-block mb-0")
                ], className="d-flex align-items-center py-3")
            ])
        ]),

        # İçerik alanı
        dbc.Row([
            dbc.Col([
                html.Div(id="content-container", className="py-3")
            ])
        ])
    ], fluid=True)
])


# Offcanvas açma/kapama callback'i
@app.callback(
    Output("offcanvas-menu", "is_open"),
    Input("offcanvas-toggle", "n_clicks"),
    State("offcanvas-menu", "is_open"),
)
def toggle_offcanvas(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


# Ana içerik display callback'i - navigation ile
@app.callback(
    Output("content-container", "children"),
    [
        Input("nav-dashboard", "n_clicks"),
        Input("nav-articles", "n_clicks"),
        Input("nav-categories", "n_clicks"),
        Input("nav-messages", "n_clicks"),
        Input("nav-settings", "n_clicks"),
        Input("nav-analytics", "n_clicks")
    ],
    prevent_initial_call=False
)
def display_content(dashboard_click, articles_click, categories_click, messages_click, settings_click, analytics_click):
    from dash import callback_context

    if not callback_context.triggered:
        return get_dashboard_content()

    # Hangi butona tıklandığını bul
    clicked_button_id = callback_context.triggered[0]['prop_id'].split('.')[0]

    if clicked_button_id == "nav-dashboard":
        return get_dashboard_content()
    elif clicked_button_id == "nav-articles":
        return get_articles_content()
    elif clicked_button_id == "nav-categories":
        return get_categories_content()
    elif clicked_button_id == "nav-messages":
        return get_messages_content()
    elif clicked_button_id == "nav-settings":
        return get_settings_content()
    elif clicked_button_id == "nav-analytics":
        return get_analytics_content()

    return get_dashboard_content()


# Makaleler sayfasında arama callback'i - Real-time search
@app.callback(
    Output("content-container", "children", allow_duplicate=True),
    [
        Input("article-search-input", "value"),
        Input("article-clear-button", "n_clicks")
    ],
    prevent_initial_call=True
)
def search_articles_realtime(search_value, clear_clicks):
    from dash import callback_context

    if not callback_context.triggered:
        return get_articles_content()

    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "article-clear-button":
        return get_articles_content("")
    elif trigger_id == "article-search-input":
        return get_articles_content(search_value or "")

    return get_articles_content()


# Aktif tab durumu callback'i
@app.callback(
    [
        Output("nav-dashboard", "active"),
        Output("nav-articles", "active"),
        Output("nav-categories", "active"),
        Output("nav-messages", "active"),
        Output("nav-settings", "active"),
        Output("nav-analytics", "active")
    ],
    [
        Input("nav-dashboard", "n_clicks"),
        Input("nav-articles", "n_clicks"),
        Input("nav-categories", "n_clicks"),
        Input("nav-messages", "n_clicks"),
        Input("nav-settings", "n_clicks"),
        Input("nav-analytics", "n_clicks")
    ],
    prevent_initial_call=True
)
def update_active_states(dashboard_click, articles_click, categories_click, messages_click, settings_click,
                         analytics_click):
    from dash import callback_context

    if not callback_context.triggered:
        return True, False, False, False, False, False

    clicked_button_id = callback_context.triggered[0]['prop_id'].split('.')[0]

    dashboard = articles = categories = messages = settings = analytics = False

    if clicked_button_id == "nav-dashboard":
        dashboard = True
    elif clicked_button_id == "nav-articles":
        articles = True
    elif clicked_button_id == "nav-categories":
        categories = True
    elif clicked_button_id == "nav-messages":
        messages = True
    elif clicked_button_id == "nav-settings":
        settings = True
    elif clicked_button_id == "nav-analytics":
        analytics = True

    return dashboard, articles, categories, messages, settings, analytics


# Offcanvas menüsünde tıklama yapıldığında offcanvas'ı kapat
@app.callback(
    Output("offcanvas-menu", "is_open", allow_duplicate=True),
    [
        Input("nav-dashboard", "n_clicks"),
        Input("nav-articles", "n_clicks"),
        Input("nav-categories", "n_clicks"),
        Input("nav-messages", "n_clicks"),
        Input("nav-settings", "n_clicks"),
        Input("nav-analytics", "n_clicks")
    ],
    prevent_initial_call=True
)
def close_offcanvas_on_nav_click(*args):
    return False
