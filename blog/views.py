import json
import re
from urllib.parse import quote_plus

import dash_bootstrap_components as dbc
from dash import html, dcc
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.utils.text import slugify
from weasyprint import HTML, CSS # YENİ

from django.conf import settings # YENİ


from dash_apps.admin_dash import app as admin_dash_app
from dash_apps.article_detail import app as article_detail_app
from dash_apps.contact import app as contact_app
from dash_apps.generate import app as generate_app
from dash_apps.resume import app as resume_app, create_resume_layout
from dash_apps.statik_anasayfa import app as anasayfa_app, create_anasayfa_content_layout
# Modeller
from .models import GeneratedArticle, Profile

from django.http import HttpResponse
from django.template.loader import render_to_string
import plotly.express as px
import base64
import markdown

# === YARDIMCI FONKSİYON: SİTE GENELİ NAVBAR ===
def create_main_navbar(request):
    """Tüm sayfalarda tutarlı, dinamik ve mobil uyumlu bir Navbar oluşturur."""
    nav_items_right = []

    if request.user.is_authenticated:
        dropdown_items = []
        if request.user.is_superuser:
            dropdown_items.append(dbc.DropdownMenuItem("Yönetici Paneli", href="/admin/", external_link=True))
            dropdown_items.append(dbc.DropdownMenuItem(divider=True))

        dropdown_items.append(dbc.DropdownMenuItem("Yeni Makale Üret", href="/generate-article/", external_link=True))
        dropdown_items.append(dbc.DropdownMenuItem("Özgeçmiş", href="/resume/", external_link=True)),
        dropdown_items.append(dbc.DropdownMenuItem("Admin Dashboard", href="/admin-dashboard/", external_link=True)),

        dropdown_items.append(dbc.DropdownMenuItem(divider=True))
        dropdown_items.append(dbc.DropdownMenuItem("Çıkış Yap", href="/logout/", external_link=True))

        user_menu = dbc.DropdownMenu(
            label=f"{request.user.username}",
            children=dropdown_items,
            nav=True, in_navbar=True, align_end="end", className="ms-lg-2"
        )
        nav_items_right.append(user_menu)

    nav_items_right.append(dbc.NavItem(dbc.NavLink("İletişim", href="/contact/", external_link=True)))

    navbar = dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(html.I(className="fas fa-brain fa-2x me-2 text-primary")),
                    dbc.Col(dbc.NavbarBrand("AI Blog", className="ms-2")),
                ], align="center", className="g-0"),
                href="/", style={"textDecoration": "none", "color": "inherit"},
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                dbc.Nav(nav_items_right, className="ms-auto", navbar=True),
                id="navbar-collapse", is_open=False, navbar=True,
            ),
        ]),
        color="dark", dark=True, className="mb-4 shadow"
    )
    return navbar


# ... (Diğer view fonksiyonları aynı kalacak)
def admin_dashboard_view(request):
    admin_dash_app
    return render(request, "admin_dashboard.html")


def anasayfa_view(request):
    main_navbar = create_main_navbar(request)
    dash_content = create_anasayfa_content_layout()
    anasayfa_app.layout = html.Div([main_navbar, dash_content])
    return render(request, 'blog/anasayfa.html')


# --- BU FONKSİYON BAŞTAN SONA GÜNCELLENDİ ---
def article_detail_view(request, article_id, slug):
    main_navbar = create_main_navbar(request)  # Bu fonksiyonun dosyanızda tanımlı olduğunu varsayıyorum
    article = get_object_or_404(
        GeneratedArticle.objects.select_related('owner__profile', 'category'),
        id=article_id
    )

    if article.slug != slug:
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    # === Başlıkları Ayıklama ve Sidebar Oluşturma ===
    md_extensions = ['extra', 'toc', 'attr_list']
    md = markdown.Markdown(extensions=md_extensions)
    heading_pattern = re.compile(r'^(#{2,3})\s+(.*)', re.MULTILINE)
    headings = []
    content_parts = re.split(r'(_\|\|_STRUCTURED_DATA_\d+_\|\|_)', article.full_content or "")
    for part in content_parts:
        if not part.startswith('_||_'):
            found_headings = heading_pattern.findall(part)
            for heading in found_headings:
                level = len(heading[0])
                title = heading[1].strip()
                headings.append({
                    "title": title.replace("**", "").title(),
                    "slug": slugify(title, allow_unicode=True),
                    "level": level
                })

    toc_links = []
    if headings:
        toc_links.append(html.H5("İçindekiler", className="mb-4"))
        nav_items = []
        for h in headings:
            className = "ms-3" if h['level'] == 3 else ""
            nav_items.append(
                dbc.NavItem(
                    dbc.NavLink(
                        [html.I(className="fas fa-chevron-right me-2 text-small"), h['title']],
                        href=f"#{h['slug']}", external_link=True, className=f"py-1 {className}",
                        style={"font-size": "0.8rem"}
                    )
                )
            )
        toc_links.append(dbc.Nav(nav_items, vertical=True, pills=True))
    toc_sidebar = html.Div(
        toc_links,
        className="sticky-top p-5 shadow-lg mb-4",
        style={"top": "11.5%"},
    )

    GeneratedArticle.objects.filter(pk=article.id).update(view_count=F('view_count') + 1)
    article.refresh_from_db()

    author_name = "Yazar Bilinmiyor"
    if hasattr(article.owner, 'profile') and article.owner.profile.first_name and article.owner.profile.last_name:
        author_name = f"{article.owner.profile.first_name} {article.owner.profile.last_name}"
    else:
        author_name = article.owner.get_full_name() or article.owner.username
    author_email = article.owner.email

    article_data_for_dash = {
        'article_id': article.id,
        'full_content': article.full_content or "",
        'structured_data': article.structured_data or {},
        'headings': headings
    }

    # --- KAYNAKÇA NUMARALANDIRMA KODU GERİ EKLENDİ ---
    raw_bibliography = article.bibliography or ""
    references_list = [ref.strip() for ref in raw_bibliography.splitlines() if ref.strip()]
    apa_style = {'paddingLeft': '1.5em', 'textIndent': '-1.5em'}
    formatted_bibliography_items = [html.Li(re.sub(r'^\d+\.\s*', '', ref), style=apa_style, className="mb-2") for ref in
                                    references_list]

    total_votes = article.likes + article.dislikes
    average_rating = 0
    if total_votes > 0:
        average_rating = round((article.likes / total_votes) * 4 + 1, 2)
    logo_url = request.build_absolute_uri('/staticfiles/images/logo.png')
    structured_data = {
        "@context": "https://schema.org", "@type": "Article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": request.build_absolute_uri(article.get_absolute_url())},
        "headline": article.title, "image": logo_url, "datePublished": article.created_at.isoformat(),
        "dateModified": article.created_at.isoformat(),
        "author": {"@type": "Person", "name": author_name, "email": author_email},
        "publisher": {"@type": "Organization", "name": "AI Blog", "logo": {"@type": "ImageObject", "url": logo_url}},
        "description": article.turkish_abstract or article.english_abstract, "articleBody": article.full_content,
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": str(average_rating),
                            "reviewCount": str(total_votes)} if total_votes > 0 else None
    }
    structured_data = {k: v for k, v in structured_data.items() if v is not None}

    keywords_list = [keyword.strip() for keyword in (article.keywords or "").split(',') if keyword.strip()]

    page_url = request.build_absolute_uri()
    encoded_title = quote_plus(article.title or "AI Blog Makalesi")

    share_buttons = html.Div(
        [html.H5("İşlemler:", className="mb-3"),
         dbc.ButtonGroup(
             [dbc.Button([html.I(className="fas fa-file-pdf me-1"), " PDF İndir"],
                         href=reverse('blog:download_article_pdf', args=[article.id]), external_link=True,
                         color="danger", outline=True, size="sm", className="me-2"),
              dbc.Button([html.I(className="fab fa-twitter me-1"), " Twitter"],
                         href=f"https://twitter.com/intent/tweet?url={page_url}&text={encoded_title}", target="_blank",
                         color="info", outline=True, size="sm"),
              dbc.Button([html.I(className="fab fa-linkedin-in me-1"), " LinkedIn"],
                         href=f"https://www.linkedin.com/shareArticle?mini=true&url={page_url}&title={encoded_title}",
                         target="_blank", color="primary", size="sm")])])

    feedback_buttons = html.Div(
        [html.H5("Bu içerik faydalı oldu mu?", className="mb-3"),
         dbc.ButtonGroup(
             [dbc.Button([html.I(className="fas fa-thumbs-up me-2"), "Faydalı ",
                          html.Span(f"({article.likes})", id="like-count")], id="like-button", color="success",
                         outline=True, size="sm", n_clicks=0),
              dbc.Button([html.I(className="fas fa-thumbs-down me-2"), "Faydasız ",
                          html.Span(f"({article.dislikes})", id="dislike-count")], id="dislike-button", color="danger",
                         outline=True, size="sm", n_clicks=0)])]
    )

    edit_button = None
    if request.user.is_superuser:
        edit_url = reverse('admin:blog_generatedarticle_change', args=[article.id])
        edit_button = html.A([html.I(className="fas fa-pencil-alt me-2 text-warning float-end")], href=edit_url,
                             className="mb-4", title="Düzenle")

    full_layout = html.Div([
        dcc.Store(id='article-data-store', data=article_data_for_dash),
        dcc.Store(id='feedback-button-store'),
        html.Div(id='like-toast-container', style={"position": "fixed", "bottom": 20, "right": 20, "zIndex": 1050}),
        html.Div(id='clientside-dummy-output'),
        main_navbar,
        dbc.Container([
            dbc.Row([
                dbc.Col(toc_sidebar, lg=2, className="d-none d-lg-block"),
                dbc.Col([
                    html.Header([
                        html.H2(article.title or "Başlık Belirtilmemiş", className="mb-4 mt-5",
                                style={"text-align": "justify"}),
                        dbc.Row([
                            dbc.Col(
                                html.P([
                                    html.Span([html.I(className="fas fa-user-edit me-1"), f" {author_name}"]),
                                    html.Span(" | ", className="mx-2"),
                                    html.A([html.I(className="fas fa-envelope me-1"), f" {author_email}"],
                                           href=f"mailto:{author_email}", className="text-muted text-decoration-none"),
                                    html.Span(" | ", className="mx-2"),
                                    html.Span([html.I(className="fas fa-calendar-alt me-1"),
                                               f" {article.created_at.strftime('%d %B %Y')}"]),
                                    html.Span(" | ", className="mx-2"),
                                    html.Span([html.I(className="fas fa-folder-open me-1"),
                                               f" Kategori: {article.category.name if article.category else 'Yok'}"]),
                                    html.Span(" | ", className="mx-2"),
                                    html.Span([html.I(className="fas fa-eye me-1"), f" {article.view_count} Okunma"]),
                                ], className="text-muted small mb-0"),
                                width="auto"
                            ),
                            dbc.Col(edit_button if edit_button else ""),
                        ], justify="between", align="center", className="border-bottom pb-3 mb-4")
                    ]),
                    html.Div([
                        html.H4("Abstract"),
                        html.P(html.Em(article.english_abstract or "İngilizce özet mevcut değil.")),
                        html.Hr(className="my-3"),
                        html.H4("Özet"),
                        html.P(html.Em(article.turkish_abstract or "Türkçe özet mevcut değil."))
                    ], className="p-4 bg-light rounded mb-4"),
                    html.Div([
                        html.H5("Anahtar Kelimeler:", className="d-inline-block me-2"),
                        *[dbc.Badge(keyword, color="secondary", className="me-2 p-2") for keyword in keywords_list]
                    ], className="mb-4"),
                    html.Div(id='dynamic-article-content'),

                    # --- GÜNCELLENEN BÖLÜM: Kaynakça tekrar numaralı liste oldu ---
                    html.Hr(className="my-5"),
                    html.H4("Kaynakça"),
                    html.Ol(formatted_bibliography_items),
                    # --- GÜNCELLEME BİTTİ ---

                ], lg=8, className="bg-white p-4 p-md-5 my-4 rounded shadow-lg"),
            ])
        ], fluid=True, className="px-md-5"),
        dbc.Container([
            dbc.Row([
                dbc.Col(feedback_buttons, md=6, className="mb-3"),
                dbc.Col(share_buttons, md=6, className="text-md-end mb-3"),
            ]),
            html.Div(html.A("← Tüm Makalelere Geri Dön", href="/", className="btn btn-secondary mt-5"),
                     className="text-center")
        ])
    ])

    article_detail_app.layout = full_layout

    return render(request, 'blog/article_detail.html', {
        'article': article,
        'meta_title': article.title,
        'meta_description': article.turkish_abstract or "",
        'meta_keywords': article.keywords or "",
        'structured_data_json': json.dumps(structured_data, indent=4)
    })


def download_article_as_pdf(request, article_id):
    """
    WeasyPrint kullanarak, kaynakçası NUMARALANDIRILMIŞ, yüksek kalitede,
    Türkçe karakter ve grafik destekli tam bir PDF oluşturan nihai fonksiyon.
    """
    article = get_object_or_404(
        GeneratedArticle.objects.select_related('owner__profile'),
        id=article_id
    )

    author_name = "Yazar Bilinmiyor"
    if hasattr(article.owner, 'profile') and article.owner.profile.first_name and article.owner.profile.last_name:
        author_name = f"{article.owner.profile.first_name} {article.owner.profile.last_name}"
    else:
        author_name = article.owner.get_full_name() or article.owner.username
    author_email = article.owner.email

    full_content = article.full_content or ""
    structured_data = article.structured_data or {}

    content_parts = re.split(r'(_\|\|_STRUCTURED_DATA_(\d+)_\|\|_)', full_content)

    final_html_parts = []
    for part in content_parts:
        placeholder_match = re.match(r'_\|\|_STRUCTURED_DATA_(\d+)_\|\|_', part)

        if placeholder_match:
            placeholder_num = placeholder_match.group(1)
            data_item = structured_data.get(placeholder_num)
            if data_item:
                item_type = data_item.get('type')
                if item_type == 'table':
                    columns = data_item.get('columns', [])
                    data = data_item.get('data', [])
                    thead = "".join(f"<th>{col}</th>" for col in columns)
                    tbody = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in data)
                    table_html = f'<div class="pdf-figure"><p class="title">{data_item.get("title", "Tablo")}</p><table class="pdf-table"><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table><p class="description">{data_item.get("description", "")}</p></div>'
                    final_html_parts.append(table_html)
                elif item_type == 'chart':
                    try:
                        chart_type = data_item.get('chart_type', 'bar').lower()
                        fig = None
                        chart_data = data_item.get('data', {})

                        if chart_type == 'bar':
                            fig = px.bar(chart_data, x='x', y='y', template="plotly_white")
                        elif chart_type == 'line':
                            fig = px.line(chart_data, x='x', y='y', markers=True, template="plotly_white")
                        elif chart_type == 'pie':
                            fig = px.pie(chart_data, names='x', values='y', template="plotly_white")
                        elif chart_type == 'scatter':
                            fig = px.scatter(chart_data, x='x', y='y', template="plotly_white")

                        if fig:
                            img_bytes = fig.to_image(format="svg", engine="kaleido")
                            encoded_img = base64.b64encode(img_bytes).decode('utf-8')
                            img_html = f'<div class="pdf-figure"><p class="title">{data_item.get("title", "Grafik")}</p><img src="data:image/svg+xml;base64,{encoded_img}"><p class="description">{data_item.get("description", "")}</p></div>'
                            final_html_parts.append(img_html)
                    except Exception as e:
                        print(f"Grafik resme çevrilirken hata: {e}")
                        final_html_parts.append(f"<p><i>[Grafik oluşturulamadı: {e}]</i></p>")
        elif part.strip():
            final_html_parts.append(markdown.markdown(part, extensions=['extra']))

    final_html_content = "".join(final_html_parts)

    # --- KAYNAKÇA BÖLÜMÜ GÜNCELLENDİ (NUMARALI LİSTE İÇİN) ---
    if article.bibliography:
        # Kaynakçayı satırlara böl
        references_list = [ref.strip() for ref in article.bibliography.splitlines() if ref.strip()]
        # Her satırı <li> etiketi içine al (başındaki numaraları silerek)
        list_items_html = "".join([f"<li>{re.sub(r'^\d+\.\s*', '', ref)}</li>" for ref in references_list])
        # Numaralı liste (<ol>) olarak birleştir
        bibliography_html = f"<h3>Kaynakça</h3><ol>{list_items_html}</ol>"
        final_html_content += bibliography_html
    # --- GÜNCELLEME BİTTİ ---

    font_config_css = CSS(
        string='@font-face { font-family: "Noto Sans"; src: url("/static/fonts/NotoSans-Regular.ttf"); }')

    html_string = render_to_string('blog/article_pdf.html', {
        'article': article,
        'author_name': author_name,
        'author_email': author_email,
        'final_html_content': final_html_content,
    })

    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf(stylesheets=[font_config_css])

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{article.slug}.pdf"'
    return response
@login_required
def resume_view(request):
    main_navbar = create_main_navbar(request)
    profile = Profile.objects.filter(user=request.user).first()
    resume_content = create_resume_layout(profile)
    full_layout = html.Div([main_navbar, resume_content])
    resume_app.layout = full_layout
    return render(request, 'blog/resume.html')


@login_required
def generate_article_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Bu sayfaya erişim yetkiniz bulunmamaktadır.")
        return redirect('anasayfa')

    # YENİ: Profil Ad/Soyad kontrolü
    try:
        # Django'nun OneToOneField'ı sayesinde request.user.profile ile doğrudan erişebiliriz
        profile = request.user.profile
        if not profile.first_name or not profile.last_name:
            # Eğer ad veya soyad boşsa, bir "DoesNotExist" hatası fırlatmış gibi davranalım
            raise Profile.DoesNotExist
    except Profile.DoesNotExist:
        # Profil yoksa veya ad/soyad boşsa, uyarı ver ve admin paneline yönlendir
        messages.warning(request, "Makale oluşturmadan önce lütfen profilinizdeki Ad ve Soyad alanlarını doldurun.")
        # Kullanıcının kendi profilini admin panelinde düzenlemesi için yönlendirme
        # Not: Bu linkin çalışması için kullanıcının admin paneline erişim izni olmalı.
        return redirect(reverse('admin:auth_user_change', args=[request.user.id]))

    main_navbar = create_main_navbar(request)
    # ... (fonksiyonun geri kalanı aynı) ...
    generate_content = dbc.Row(dbc.Col(html.Div([
        dcc.Store(id='user-session-store', data={'user_id': request.user.id}),
        dcc.Location(id='url', refresh=True),
        html.Div([html.I(className="fas fa-magic fa-3x text-success mb-3"), html.H1("Yeni Makale Fikri"),
                  html.P("AI Asistanınız için yeni bir görev oluşturun.", className="lead text-muted")],
                 className="text-center mb-5"),
        dbc.Card(dbc.CardBody([
            html.P(
                "Lütfen hakkında akademik bir makale üretilmesini istediğiniz konuyu, spesifik bir soruyu veya anahtar kelimeleri aşağıya detaylı bir şekilde girin.",
                className="card-text"),
            dcc.Textarea(id='request-textarea',
                         placeholder="Örn: 'Kuantum bilgisayarların kriptografi üzerine etkileri'",
                         style={'width': '100%', 'height': 150}, className="form-control form-control-lg mb-3"),
            dcc.Loading(id="loading-spinner", type="border", children=[
                html.Div(className="d-grid mt-4", children=[
                    dbc.Button([html.I(className="fas fa-paper-plane me-2"), "Üretimi Başlat"],
                               id='submit-request-button', color="success", size="lg")]),
                html.Div(id='form-feedback-message', className="mt-3")])
        ]), className="p-md-5 p-3 shadow-lg"),
        html.Div(html.A("← Anasayfaya Dön", href="/", className="mt-3 d-inline-block"), className="text-center")
    ]), md=8, className="mx-auto"))
    full_layout = html.Div([main_navbar, dbc.Container(generate_content, className="my-5")])
    generate_app.layout = full_layout
    return render(request, 'blog/generate_article.html')


def contact_view(request):
    main_navbar = create_main_navbar(request)
    contact_content = dbc.Row(dbc.Col([
        html.Div([html.I(className="fas fa-envelope-open-text fa-3x text-primary mb-3"), html.H1("Bize Ulaşın"),
                  html.P("Soru, öneri veya geri bildirimleriniz için...", className="lead text-muted")],
                 className="text-center mb-5"),
        dbc.Card(dbc.CardBody([
            dbc.Row([dbc.Col(dbc.Input(id='contact-name', placeholder="Adınız Soyadınız")),
                     dbc.Col(dbc.Input(id='contact-email', placeholder="E-posta Adresiniz"))], className="mb-3"),
            dbc.Input(id='contact-subject', placeholder="Konu", className="mb-3"),
            dbc.Textarea(id='contact-message', placeholder="Mesajınız...", rows=6, className="mb-3"),
            html.Div(className="d-grid",
                     children=[dbc.Button(["Gönder"], id='submit-contact-button', color="primary")]),
        ]), className="p-4 shadow-sm"),
        html.Div(id='contact-form-feedback', className="mt-4")
    ], md=8, lg=7, className="mx-auto"))
    full_layout = html.Div([main_navbar, dbc.Container(contact_content, className="my-5")])
    contact_app.layout = full_layout
    return render(request, 'blog/contact.html')


def custom_logout_view(request):
    logout(request)
    return redirect('blog:anasayfa')


def robots_txt_view(request):
    base_url = f"{request.scheme}://{request.get_host()}"

    return render(request, 'robots.txt', {'base_url': base_url}, content_type="text/plain")
