import json
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from billing.decorators import require_credits, check_credits
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.db.models import F

import markdown
import re
import base64
import dash_bootstrap_components as dbc
from dash import html, dcc

from .models import GeneratedArticle, Profile
from dash_apps.generate import app as generate_app
from dash_apps.article_detail import app as article_detail_app
from dash_apps.blog import app as blog_app, create_blog_content_layout
from dash_apps.anasayfa import app as anasayfa_app, create_anasayfa_content_layout
from dash_apps.resume import app as resume_app, create_resume_layout
from dash_apps.contact import app as contact_app
import dash_apps.article_edit  # noqa: F401 — ArticleEditApp callback'lerini kaydeder
from dash_apps.article_search import app as article_search_app, create_article_search_layout
from dash_apps.admin_dash import app as admin_dash_app




def create_main_navbar(request):
    """
    Tüm sayfalarda tutarlı, dinamik ve mobil uyumlu bir Navbar oluşturur.
    Tüm linkler sağa yaslanmış ve harici link olarak ayarlanmıştır.
    """
    from dash_apps.i18n_helper import get_lang, t
    lang = get_lang(request)

    # Tüm navigasyon öğelerini tutacak tek bir liste oluştur
    nav_items = []

    # Herkesin görebileceği ana linkleri listeye ekle
    nav_items.append(dbc.NavItem(dbc.NavLink(t('nav_blog', lang), href=reverse('blog:blog_list'), active="exact", external_link=True)))

    # --- Makale dropdown'ı (AI oluştur / oluştur / ara) ---
    makale_children = []
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
        makale_children.append(
            dbc.DropdownMenuItem(t('nav_generate', lang),
                                 href=reverse('blog:generate_article'),
                                 external_link=True, id="nav_generate_item"))
    if request.user.is_authenticated:
        makale_children.append(
            dbc.DropdownMenuItem(t('nav_create_article', lang),
                                 href=reverse('blog:create_article'),
                                 external_link=True, id="nav_create_item"))
    makale_children.append(
        dbc.DropdownMenuItem(t('nav_article_search', lang),
                             href=reverse('blog:article_search'),
                             external_link=True, id="nav_search_item"))

    makale_dropdown = dbc.DropdownMenu(
        label=t('nav_makale', lang),
        children=makale_children,
        nav=True,
        in_navbar=True,
    )
    nav_items.append(makale_dropdown)
    bio_tools_dropdown = dbc.DropdownMenu(
        label=t('nav_biotools', lang),
        children=[
            # --- Temel Araçlar ---
            dbc.DropdownMenuItem(t('nav_basic_tools', lang), header=True),
            dbc.DropdownMenuItem(t('nav_seq_analyzer', lang), href=reverse('bio_tools:sequence_analyzer'),
                                 external_link=True, id="sequence_analyzer"),
            dbc.DropdownMenuItem(t('nav_phylo_tree', lang), href=reverse('bio_tools:phylogenetic_tree'),
                                 external_link=True, id="phylogenetic_tree"),
            dbc.DropdownMenuItem(t('nav_seq_alignment', lang), href=reverse('bio_tools:sequence_alignment'),
                                 external_link=True, id="sequence_alignment"),
            dbc.DropdownMenuItem(t('nav_molecule_viewer', lang), href=reverse('bio_tools:molecule_viewer'),
                                 external_link=True, id="molecule_viewer"),
            dbc.DropdownMenuItem(t('nav_mutation', lang), href=reverse('bio_tools:mutation_predictor'),
                                 external_link=True, id="mutation_predictor"),
            dbc.DropdownMenuItem(t('nav_bacterial', lang), href=reverse('bio_tools:bacterial_designer'),
                                 external_link=True, id="bacterial_designer"),
            dbc.DropdownMenuItem(t('nav_pipeline', lang), href=reverse('bio_tools:pipline_designer_view'),
                                 external_link=True, id="pipline_designer_view"),
            dbc.DropdownMenuItem(t('nav_primer', lang), href=reverse('bio_tools:primer_design'),
                                 external_link=True, id="primer_design"),
            dbc.DropdownMenuItem(t('nav_restriction', lang), href=reverse('bio_tools:restriction_analysis'),
                                 external_link=True, id="restriction_analysis"),
            dbc.DropdownMenuItem(t('nav_crispr', lang), href=reverse('bio_tools:crispr_designer'),
                                 external_link=True, id="crispr_designer"),
            dbc.DropdownMenuItem(t('nav_plasmid', lang), href=reverse('bio_tools:plasmid_map'),
                                 external_link=True, id="plasmid_map"),
            dbc.DropdownMenuItem(t('nav_fastq', lang), href="/bio-tools/fastq-analyzer/",
                                 external_link=True, id="fastq_analyzer"),

            dbc.DropdownMenuItem(divider=True),

            # --- Hassas Tıp ---
            dbc.DropdownMenuItem(t('nav_precision_med', lang), header=True),
            dbc.DropdownMenuItem(t('nav_pharma', lang), href=reverse('bio_tools:pharmacogenomics'),
                                 external_link=True, id="pharmacogenomics"),
            dbc.DropdownMenuItem(t('nav_variant', lang), href=reverse('bio_tools:variant_prioritization'),
                                 external_link=True, id="variant_prioritization"),
            dbc.DropdownMenuItem(t('nav_federated', lang), href=reverse('bio_tools:federated_learning'),
                                 external_link=True, id="federated_learning"),
        ],
        nav=True,
        in_navbar=True,
    )

    nav_items.append(bio_tools_dropdown)

    # Kullanıcının durumuna göre değişecek olan öğeleri listeye ekle
    if request.user.is_authenticated:
        # --- KULLANICI GİRİŞ YAPMIŞSA ---
        dropdown_items = []
        if request.user.is_superuser:
            dropdown_items.append(dbc.DropdownMenuItem(t('nav_admin_dash', lang), href=reverse('blog:admin_dashboard'), external_link=True))
            dropdown_items.append(dbc.DropdownMenuItem(t('nav_django_admin', lang), href="/admin/", external_link=True))
        if request.user.is_superuser or request.user.is_staff:
            dropdown_items.append(dbc.DropdownMenuItem(divider=True))

        dropdown_items.append(dbc.DropdownMenuItem(t('nav_profile', lang), href=reverse('blog:resume_user', kwargs={'username': request.user.username}), external_link=True))
        dropdown_items.append(dbc.DropdownMenuItem(t('nav_credits', lang), href=reverse('billing:credits'), external_link=True))
        dropdown_items.append(dbc.DropdownMenuItem(divider=True))
        dropdown_items.append(dbc.DropdownMenuItem(t('nav_logout', lang), href=reverse('blog:logout'), external_link=True))

        user_menu = dbc.DropdownMenu(
            label=request.user.username,
            children=dropdown_items,
            nav=True,
            in_navbar=True,
            align_end=True,
        )
        nav_items.append(user_menu)

        # Bildirim çanı (sadece superuser) — okunmamış sayısı rozetiyle
        if request.user.is_superuser:
            try:
                from blog.models import Notification
                unread = Notification.objects.filter(is_read=False).count()
            except Exception:
                unread = 0
            bell_children = [html.I(className="fas fa-bell")]
            if unread > 0:
                bell_children.append(
                    dbc.Badge(str(unread), color="danger", pill=True,
                              className="ms-1",
                              style={"fontSize": "0.65rem", "verticalAlign": "top"})
                )
            nav_items.append(dbc.NavItem(dbc.NavLink(
                bell_children,
                href="/admin/blog/notification/",
                external_link=True,
            )))

        nav_items.append(dbc.NavItem(dbc.NavLink(t('nav_contact', lang), href=reverse('blog:contact'), external_link=True, active="exact")))

    else:
        # --- KULLANICI GİRİŞ YAPMAMIŞSA ---
        nav_items.append(dbc.NavItem(dbc.NavLink(t('nav_login', lang), href="/admin/login/", external_link=True)))
        nav_items.append(dbc.NavItem(dbc.NavLink(t('nav_register', lang), href=reverse('blog:register'), external_link=True)))

    # --- DİL SEÇİMİ (herkes görür) ---
    current_lang = lang
    lang_label = "🌐 TR" if current_lang == 'tr' else "🌐 EN"
    lang_dropdown = dbc.DropdownMenu(
        label=lang_label,
        children=[
            dbc.DropdownMenuItem("Türkçe", href="/set-language/tr/", external_link=True),
            dbc.DropdownMenuItem("English", href="/set-language/en/", external_link=True),
        ],
        nav=True,
        in_navbar=True,
        align_end=True,
    )
    nav_items.append(lang_dropdown)

    # Navbar'ın ana yapısı
    navbar = dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(html.I(className="fas fa-brain fa-2x me-2 text-primary")),
                    dbc.Col(dbc.NavbarBrand("AI Blog", className="ms-2")),
                ], align="center", className="g-0"),
                href="/", style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                # Tek bir Nav bileşeni içinde tüm öğeleri topla ve sağa yasla
                dbc.Nav(nav_items, className="ms-auto", navbar=True),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),
        ]),
        color="dark",
        dark=True,
        className="mb-4 shadow",
        sticky="top",
    )
    return navbar

@login_required
def admin_dashboard_view(request):
    # Yonetim paneli yalnizca superuser'lara acik (veri sizintisini onler).
    if not request.user.is_superuser:
        raise Http404()
    admin_dash_app
    return render(request, "admin_dashboard.html")


def blog_list_view(request):
    """Blog: tüm makalelerin listesi (eski anasayfa içeriği)."""
    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang
    dash_content = create_blog_content_layout(get_lang(request))
    _blog_layout = html.Div([main_navbar, dash_content])

    def serve_blog_layout():
        return _blog_layout

    blog_app.layout = serve_blog_layout
    return render(request, 'blog/blog_list.html')


def anasayfa_view(request):
    """Anasayfa — Dash uygulaması (navbar diğer sayfalarla tutarlı)."""
    from dash_apps.i18n_helper import get_lang
    lang = get_lang(request)
    main_navbar = create_main_navbar(request)
    dash_content = create_anasayfa_content_layout(lang)
    _anasayfa_layout = html.Div([main_navbar, dash_content])

    def serve_anasayfa_layout():
        return _anasayfa_layout

    anasayfa_app.layout = serve_anasayfa_layout

    if lang == 'en':
        meta_title = "AI Blog — AI-Powered Bioinformatics Tools & Articles"
        meta_description = ("Free online bioinformatics tools — CRISPR sgRNA design, "
                            "sequence analysis, primer design and more — plus AI-generated "
                            "academic articles.")
    else:
        meta_title = "AI Blog — Yapay Zeka Destekli Biyoinformatik Araçları ve Makaleler"
        meta_description = ("Ücretsiz çevrimiçi biyoinformatik araçları — CRISPR sgRNA "
                            "tasarımı, sekans analizi, primer tasarımı ve daha fazlası — ve "
                            "yapay zeka destekli akademik makaleler.")
    return render(request, 'blog/anasayfa.html', {
        'meta_title': meta_title,
        'meta_description': meta_description,
    })


@login_required
def request_publish_view(request, article_id):
    """
    Makale sahibinin, makalesinin anasayfada yayınlanması için talep göndermesi.
    Yalnızca makale sahibi (superuser değil) kullanabilir.
    """
    article = get_object_or_404(GeneratedArticle, id=article_id)

    if article.owner_id != request.user.id:
        messages.error(request, "Bu makale için talep gönderme yetkiniz yok.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    if request.user.is_superuser:
        messages.info(request, "Yönetici makaleleri zaten otomatik yayınlanır.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    if request.method == 'POST':
        if article.is_published:
            messages.info(request, "Makaleniz zaten yayında.")
        elif article.yayin_talebi:
            messages.info(request, "Yayın talebiniz zaten alındı, inceleniyor.")
        else:
            article.yayin_talebi = True
            article.save(update_fields=['yayin_talebi'])
            messages.success(request, "Yayın talebiniz alındı! Yöneticiler inceledikten sonra "
                                      "uygunsa makaleniz anasayfada yayınlanacaktır.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    # GET ile gelinirse (modal yerine doğrudan link) makaleye dön
    return redirect('blog:article_detail', article_id=article.id, slug=article.slug)


@login_required
def edit_article_view(request, article_id):
    """
    Kullanıcının kendi makalesini düzenlemesi (Dash sayfası).
    full_content yer tutucuların etrafından parçalanır; kullanıcı yalnızca metin
    parçalarını düzenler. Grafik/tablo yer tutucuları kilitli gösterilir ve
    kaydetme Dash callback'inde yapılır (ArticleEditApp).
    """
    from .edit_helpers import split_content_for_editing
    from dash_apps.article_edit import app as edit_app, build_edit_content

    article = get_object_or_404(GeneratedArticle, id=article_id)

    # Superuser bu sayfayı kullanmaz, admin panelini kullanır
    if request.user.is_superuser:
        return redirect('admin:blog_generatedarticle_change', article.id)

    # Normal kullanıcı yalnızca kendi makalesini düzenleyebilir
    if article.owner_id != request.user.id:
        messages.error(request, "Bu makaleyi düzenleme yetkiniz yok.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    main_navbar = create_main_navbar(request)
    parts = split_content_for_editing(article.full_content)
    content = build_edit_content(article, parts)
    _layout = html.Div([main_navbar, content])
    edit_app.layout = lambda: _layout

    return render(request, 'blog/edit_article.html', {
        'meta_title': f"Düzenle: {article.title}",
    })


def request_correction_view(request, article_id):
    """
    Kullanıcının makalesini düzelttikten sonra superuser'lara tekrar inceleme
    talebi göndermesi. Superuser'lara e-posta atar.
    """
    article = get_object_or_404(GeneratedArticle, id=article_id)

    if article.owner_id != request.user.id:
        messages.error(request, "Bu makale için talep gönderme yetkiniz yok.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    # Kandırma önlemi: son AI incelemesinden sonra makale gerçekten düzenlenmiş mi?
    if article.ai_reviewed_at and article.last_edited_at:
        if article.last_edited_at <= article.ai_reviewed_at:
            messages.warning(request, "Son incelemeden bu yana makalede bir değişiklik yapılmamış. "
                                      "Lütfen önce önerilen düzeltmeleri uygulayın, sonra tekrar "
                                      "inceleme talep edin.")
            return redirect('blog:article_detail', article_id=article.id, slug=article.slug)
    elif article.ai_reviewed_at and not article.last_edited_at:
        # İncelenmiş ama hiç düzenlenmemiş
        messages.warning(request, "Makalede henüz bir düzenleme yapmadınız. "
                                  "Lütfen önce önerilen düzeltmeleri uygulayın.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    if request.method == 'POST':
        user_message = (request.POST.get('message') or '').strip()
        from .ai_review import notify_superusers_correction_request
        sent, err = notify_superusers_correction_request(article, user_message)
        if sent:
            messages.success(request, "Düzeltme talebiniz yöneticilere iletildi. "
                                      "En kısa sürede makaleniz tekrar incelenecektir.")
        else:
            messages.warning(request, f"Talebiniz alındı ancak bildirim e-postası gönderilemedi: {err} "
                                      "Yöneticiler yine de admin panelinden görebilir.")

    return redirect('blog:article_detail', article_id=article.id, slug=article.slug)


@login_required
def delete_article_view(request, article_id):
    """Makale sahibi (veya superuser) makalesini siler. Onay POST ile gelir."""
    article = get_object_or_404(GeneratedArticle, id=article_id)

    if article.owner_id != request.user.id and not request.user.is_superuser:
        messages.error(request, "Bu makaleyi silme yetkiniz yok.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f"'{title}' başlıklı makale silindi.")
        return redirect('blog:anasayfa')

    # GET: onay sayfası göster
    return render(request, 'blog/delete_article_confirm.html', {
        'article': article,
        'meta_title': 'Makaleyi Sil',
    })


def _build_bibliography_items(article, references_list, apa_style, show_badges=True):
    """
    Her kaynağı listeler; doğrulama yapıldıysa yanına durum işareti koyar:
      ✓ yeşil  = CrossRef'te bulundu (+ içerik ilgili)
      ⚠ sarı   = bulundu ama içerik alakasız (şüpheli atıf)
      ? gri    = bulunamadı / doğrulanamadı
    """
    import re as _re

    full_content = getattr(article, 'full_content', '') or ''

    result = getattr(article, 'reference_check_result', None)
    # num -> sonuç eşlemesi
    status_by_num = {}
    if show_badges and result and isinstance(result, dict):
        for r in result.get('results', []):
            try:
                status_by_num[int(r['num'])] = r
            except (ValueError, KeyError, TypeError):
                continue

    items = []
    for idx, ref in enumerate(references_list, start=1):
        clean_ref = _re.sub(r'^\d+\.\s*', '', ref)
        # Bu kaynağın numarasını metinden çıkar (varsa), yoksa sıra numarası
        m = _re.match(r'^\[?(\d+)', ref)
        num = int(m.group(1)) if m else idx

        badge = None
        info = status_by_num.get(num)
        if info:
            status = info.get('status')
            relevance = info.get('content_relevance')
            if status == 'verified':
                if relevance == 'unrelated':
                    badge = html.Span("⚠", title="Kaynak gerçek ama içerik alakasız görünüyor (şüpheli atıf)",
                                      className="ms-2", style={'color': '#f0ad4e', 'cursor': 'help'})
                else:
                    badge = html.Span("✓", title="Kaynak CrossRef'te doğrulandı",
                                      className="ms-2", style={'color': '#28a745', 'cursor': 'help'})
            elif status == 'not_found':
                badge = html.Span("?", title="Kaynak CrossRef'te bulunamadı (şüpheli)",
                                  className="ms-2", style={'color': '#6c757d', 'cursor': 'help',
                                                           'fontWeight': 'bold'})
            # unreachable ise işaret koyma (doğrulama yapılamamış)

        children = [clean_ref]
        if badge is not None:
            children.append(badge)
        items.append(html.Li(children, style=apa_style, className="mb-2"))

    return items


def _build_reference_check_badge(article):
    """
    Kaynak doğrulama sonucunu şeffaf bir bilgi kutusu olarak gösterir.
    Doğrulama yapılmamışsa boş döner.
    """
    result = getattr(article, 'reference_check_result', None)
    if not result:
        return html.Div()

    total = result.get('total', 0)
    verified = result.get('verified', 0)
    not_found = result.get('not_found', 0)

    if total == 0:
        return html.Div()

    # İçerik kontrolü yapıldı mı
    content_checked = result.get('content_checked', False)
    content_unrelated = result.get('content_unrelated', 0)
    content_relevant = result.get('content_relevant', 0)

    # Renk: çoğu doğrulandıysa yeşil, şüpheli varsa sarı
    if not_found == 0 and content_unrelated == 0:
        color, icon = "success", "fa-check-circle"
    elif verified > not_found:
        color, icon = "warning", "fa-exclamation-triangle"
    else:
        color, icon = "danger", "fa-times-circle"

    # İçerik kontrolü satırı (yapıldıysa)
    content_line = html.Span("")
    if content_checked:
        if content_unrelated > 0:
            content_line = html.Div([
                html.I(className="fas fa-search me-2"),
                html.Strong("İçerik kontrolü: "),
                html.Span(f"{content_relevant} kaynak konuyla ilgili, "),
                html.Span(f"{content_unrelated} kaynak alakasız görünüyor (şüpheli atıf).",
                          className="fw-bold text-danger"),
            ], className="mb-1 mt-1")
        else:
            content_line = html.Div([
                html.I(className="fas fa-search me-2"),
                html.Strong("İçerik kontrolü: "),
                html.Span(f"Kontrol edilen {content_relevant} kaynak konuyla ilgili görünüyor.",
                          className="text-success"),
            ], className="mb-1 mt-1")

    # Açıklama notu (içerik kontrolü yapıldıysa farklı)
    if content_checked:
        note = ("Bu kontrol kaynakların varlığını CrossRef'te doğrular ve AI ile "
                "atıf-kaynak konu ilgisini değerlendirir. Yine de tam içerik doğruluğu "
                "(kaynağın iddiayı birebir desteklemesi) garanti edilemez; kaynakları "
                "kendiniz de değerlendiriniz.")
    else:
        note = ("Bu kontrol kaynakların gerçekten var olup olmadığını doğrular. "
                "Ancak her atfın ilgili kaynağı içerik olarak doğru yansıtıp yansıtmadığı "
                "otomatik teyit edilmemiştir; kaynakları kendiniz de değerlendiriniz.")

    return dbc.Alert([
        html.Div([
            html.I(className=f"fas {icon} me-2"),
            html.Strong(f"Kaynak Doğrulama: {verified}/{total} kaynak CrossRef'te bulundu"),
            (html.Span(f" — {not_found} kaynak bulunamadı (şüpheli).",
                       className="ms-1") if not_found else html.Span("")),
        ], className="mb-1"),
        content_line,
        html.Small([
            html.I(className="fas fa-info-circle me-1"),
            note,
        ], className="text-muted d-block mt-1"),
    ], color=color, className="mb-3")


def article_detail_view(request, article_id, slug):
    main_navbar = create_main_navbar(request)
    article = get_object_or_404(
        GeneratedArticle.objects.select_related('owner__profile', 'category'),
        id=article_id
    )

    if article.slug != slug:
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    heading_pattern = re.compile(r'^(#{2,3})\s+(.*)$')
    # Tamamen kalin yazilmis satirlari da baslik say (or. **Giris**, **Sonuc**).
    # Sadece tum satiri kaplayan kalinlari yakalar; paragraf ici kalinlari degil.
    bold_heading_pattern = re.compile(r'^\s*\*\*(.+?)\*\*\s*$')
    headings = []
    content_parts = re.split(r'(_\|\|_STRUCTURED_DATA_\d+_\|\|_)', article.full_content or "")
    for part in content_parts:
        if part.startswith('_||_'):
            continue
        for line in part.splitlines():
            md_match = heading_pattern.match(line)
            if md_match:
                level = len(md_match.group(1))
                raw_title = md_match.group(2).strip()
                display_title = raw_title.replace("**", "").title()
            else:
                bold_match = bold_heading_pattern.match(line)
                if not bold_match:
                    continue
                level = 2
                raw_title = bold_match.group(1).strip()
                # Yazarin yazdigi buyuk/kucuk harfi koru (Turkce .title() bozmasin)
                display_title = raw_title.replace("**", "").strip()
            headings.append({
                "display_title": display_title,
                "slug": slugify(raw_title, allow_unicode=True),
                "level": level,
                "raw_title": raw_title
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
                        [html.I(className="fas fa-chevron-right me-2 text-small"), h['display_title']],
                        href=f"#{h['slug']}",
                        external_link=True,
                        className=f"py-1 toc-link {className}",
                        style={"font-size": "0.8rem"}
                    )
                )
            )
        toc_links.append(dbc.Nav(nav_items, vertical=True, pills=True))
    toc_sidebar = html.Div(
        toc_links,
        className="p-4 shadow-sm mb-4 toc-sidebar rounded-3",
    )

    GeneratedArticle.objects.filter(pk=article.id).update(view_count=F('view_count') + 1)
    article.refresh_from_db()

    author_name = "Yazar Bilinmiyor"
    if hasattr(article.owner, 'profile') and article.owner.profile.first_name and article.owner.profile.last_name:
        author_name = f"{article.owner.profile.first_name} {article.owner.profile.last_name}"
    else:
        author_name = article.owner.get_full_name() or article.owner.username
    author_email = article.owner.email

    if article.cover_image:
        meta_image_url = request.build_absolute_uri(article.cover_image.url)
    else:
        meta_image_url = request.build_absolute_uri('/static/images/default_cover.png')

    modified_full_content = article.full_content or ""
    for h in headings:
        pattern_to_replace = re.compile(
            r'(#{' + str(h['level']) + r'}\s+' + re.escape(h['raw_title']) + r')\s*$',
            re.MULTILINE
        )
        replacement = r'\1 ' + f'{{#{h["slug"]}}}'
        modified_full_content = pattern_to_replace.sub(replacement, modified_full_content)

    article_data_for_dash = {
        'article_id': article.id,
        'full_content': modified_full_content,
        'structured_data': article.structured_data or {},
    }

    raw_bibliography = article.bibliography or ""
    references_list = [ref.strip() for ref in raw_bibliography.splitlines() if ref.strip()]
    apa_style = {'paddingLeft': '1.5em', 'textIndent': '-1.5em'}
    _is_owner_for_badges = request.user.is_authenticated and (article.owner_id == request.user.id or request.user.is_superuser)
    formatted_bibliography_items = _build_bibliography_items(article, references_list, apa_style, show_badges=_is_owner_for_badges)

    total_votes = article.likes + article.dislikes
    average_rating = 0
    if total_votes > 0:
        average_rating = round((article.likes / total_votes) * 4 + 1, 2)

    structured_data = {
        "@context": "https://schema.org", "@type": "Article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": request.build_absolute_uri(article.get_absolute_url())},
        "headline": article.title, "image": meta_image_url, "datePublished": article.created_at.isoformat(),
        "dateModified": article.created_at.isoformat(),
        "author": {"@type": "Person", "name": author_name, "email": author_email},
        "publisher": {"@type": "Organization", "name": "AI Blog",
                      "logo": {"@type": "ImageObject", "url": request.build_absolute_uri('/static/images/logo.png')}},
        "description": article.turkish_abstract or article.english_abstract, "articleBody": article.full_content,
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": str(average_rating),
                            "reviewCount": str(total_votes)} if total_votes > 0 else None
    }
    structured_data = {k: v for k, v in structured_data.items() if v is not None}

    keywords_list = [keyword.strip() for keyword in (article.keywords or "").split(',') if keyword.strip()]

    page_url = request.build_absolute_uri()
    encoded_title = quote_plus(article.title or "AI Blog Makalesi")

    share_buttons = html.Div([
        html.H6("Paylaş:", className="mb-2"),
        dbc.ButtonGroup([
            dbc.Button(
                [html.I(className="fab fa-twitter me-1"), " Twitter"],
                href=f"https://twitter.com/intent/tweet?url={page_url}&text={encoded_title}",
                target="_blank", color="info", outline=True, size="sm", className="me-2"
            ),
            dbc.Button(
                [html.I(className="fab fa-linkedin-in me-1"), " LinkedIn"],
                href=f"https://www.linkedin.com/shareArticle?mini=true&url={page_url}&title={encoded_title}",
                target="_blank", color="primary", size="sm"
            )
        ])
    ])

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

    # --- Aksiyon menüsü (⋮): PDF İndir herkese, Düzenle/Sil sadece yetkililere ---
    action_icons = []
    is_owner = request.user.is_authenticated and article.owner_id == request.user.id

    # PDF İndir herkese açık → menüye her zaman eklenir
    pdf_url = reverse('blog:download_article_pdf', args=[article.id])
    menu_items = [
        dbc.DropdownMenuItem([html.I(className="fas fa-file-pdf me-2"), "PDF İndir"],
                             href=pdf_url, external_link=True),
    ]

    if request.user.is_superuser or is_owner:
        # Superuser düzenlemeyi admin panelinden, sahip edit sayfasından yapar
        if request.user.is_superuser:
            edit_url = reverse('admin:blog_generatedarticle_change', args=[article.id])
            edit_label = "Makaleyi Düzenle (Admin)"
        else:
            edit_url = f"/article/{article.id}/duzenle/"
            edit_label = "Makale Düzenle"
        delete_url = f"/article/{article.id}/delete/"

        menu_items += [
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem([html.I(className="fas fa-pencil-alt me-2"), edit_label],
                                 href=edit_url, external_link=True),
            dbc.DropdownMenuItem([html.I(className="fas fa-trash-alt me-2"), "Makale Sil"],
                                 href=delete_url, external_link=True,
                                 className="text-danger"),
        ]

    menu_dropdown = dbc.DropdownMenu(
        label="Menü",
        children=menu_items,
        nav=False,
        in_navbar=False,
        align_end=True,
        size="sm",
        color="link",
        toggle_class_name="article-menu-toggle",
        className="d-inline-block",
    )

    # Yayın talep ikonu (uçak) — sadece sahip, superuser değil, henüz yayında/talep yoksa
    yayin_icon = None
    if is_owner and not request.user.is_superuser:
        if article.is_published:
            yayin_icon = html.Span([html.I(className="fas fa-check-circle")],
                                   className="text-success", title="Anasayfada yayında")
        elif article.yayin_talebi:
            yayin_icon = html.Span([html.I(className="fas fa-clock")],
                                   className="text-info", title="Yayın talebiniz inceleniyor")
        else:
            yayin_icon = html.A([html.I(className="fas fa-paper-plane")],
                                href="#", className="text-primary",
                                title="Yayınlanması için talep gönder",
                                **{"data-bs-toggle": "modal", "data-bs-target": "#publishModal"})

    full_layout = html.Div([
        dcc.Store(id='article-data-store', data=article_data_for_dash),
        dcc.Store(id='feedback-button-store'),
        html.Div(id='like-toast-container', style={"position": "fixed", "bottom": 20, "right": 20, "zIndex": 1050}),
        html.Div(id='clientside-dummy-output'),
        main_navbar,
        dbc.Container([
            dbc.Row([
                dbc.Col(toc_sidebar, lg=3, className="d-none d-lg-block toc-col"),
                dbc.Col([
                    html.Header([
                        html.H2(article.title or "Başlık Belirtilmemiş", className="mb-4 mt-5"),
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
                                    html.Span(" | ", className="mx-2"),
                                    menu_dropdown,
                                ] + ([html.Span(" | ", className="mx-2"), yayin_icon] if yayin_icon else []),
                                   className="text-muted small mb-0 d-flex flex-wrap align-items-center"),
                                width="auto"
                            ),
                        ], align="center", className="border-bottom pb-3 mb-4")
                    ]),

                    html.Div([
                        html.H4("Abstract"),
                        html.P(html.Em(article.english_abstract or "İngilizce özet mevcut değil.")),
                        html.Hr(className="my-3"),
                        html.H4("Özet"),
                        html.P(html.Em(article.turkish_abstract or "Türkçe özet mevcut değil."))
                    ], className="p-4 rounded mb-4 article-abstract-box"),

                    html.Div([
                        html.H5("Anahtar Kelimeler:", className="d-inline-block me-2"),
                        *[dbc.Badge(keyword, color="secondary", className="me-2 p-2") for keyword in keywords_list]
                    ], className="mb-4"),

                    html.Div(id='dynamic-article-content'),

                    html.Hr(className="my-5"),
                    html.H4("Kaynakça"),
                    (_build_reference_check_badge(article) if (is_owner or request.user.is_superuser) else html.Div()),
                    html.Ol(formatted_bibliography_items),

                ], lg=9, className="bg-white px-4 px-md-5 py-5 my-4 rounded-3 shadow-sm article-content-col"),
            ])
        ], className="article-detail-container py-4"),
        dbc.Container([
            dbc.Row([
                dbc.Col(feedback_buttons, md=6, className="mb-3"),
                dbc.Col(share_buttons, md=6, className="text-md-end mb-3"),
            ]),
            html.Div(html.A("← Tüm Makalelere Geri Dön", href="/blog/", className="btn btn-secondary mt-5"),
                     className="text-center")
        ])
    ])

    _article_detail_layout = full_layout

    def serve_article_detail_layout():
        return _article_detail_layout

    article_detail_app.layout = serve_article_detail_layout

    return render(request, 'blog/article_detail.html', {
        'article': article,
        'meta_title': article.title,
        'meta_description': article.turkish_abstract or "",
        'meta_keywords': article.keywords or "",
        'structured_data_json': json.dumps(structured_data, indent=4),
        'meta_image_url': meta_image_url,
        'request': request,
    })


def download_article_as_pdf(request, article_id):
    """
    WeasyPrint kullanarak, istenmeyen numaralandırma hatası giderilmiş,
    nihai PDF oluşturan fonksiyon.
    """
    # Ağır kütüphaneler sadece PDF üretiminde yüklenir (lazy import — hız için)
    from weasyprint import HTML, CSS
    import plotly.express as px

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

    pattern = r'(_\|\|_STRUCTURED_DATA_(\d+)_\|\|_)'
    content_parts = re.split(pattern, full_content)

    final_html_parts = []

    # --- DÖNGÜ DÜZELTİLDİ ---
    i = 0
    while i < len(content_parts):
        text_part = content_parts[i]
        if text_part.strip():
            final_html_parts.append(markdown.markdown(text_part, extensions=['extra']))

        if i + 2 < len(content_parts):
            placeholder_num = content_parts[i + 2]
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
        i += 3
    # --- DÜZELTME BİTTİ ---

    final_html_content = "".join(final_html_parts)

    if article.bibliography:
        references_list = [ref.strip() for ref in article.bibliography.splitlines() if ref.strip()]

        list_items_html = "".join(["<li>{}</li>".format(re.sub(r'^\d+\.\s*', '', ref)) for ref in references_list])
        bibliography_html = f"<h3>Kaynakça</h3><ol>{list_items_html}</ol>"
        final_html_content += bibliography_html

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
def ckeditor_upload_image(request):
    """
    CKEditor simpleUpload endpoint'i. Resmi alır, media/article_images/ altına
    kaydeder, CKEditor'ın beklediği {url: ...} JSON'ını döner.
    """
    from django.http import JsonResponse
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os
    import uuid

    if request.method != 'POST':
        return JsonResponse({'error': {'message': 'Yalnızca POST.'}}, status=405)

    upload = request.FILES.get('upload')
    if not upload:
        return JsonResponse({'error': {'message': 'Dosya bulunamadı.'}}, status=400)

    # Tip ve boyut kontrolü
    if not upload.content_type.startswith('image/'):
        return JsonResponse({'error': {'message': 'Yalnızca resim dosyaları yüklenebilir.'}}, status=400)
    if upload.size > 5 * 1024 * 1024:
        return JsonResponse({'error': {'message': 'Resim 5MB\'den küçük olmalı.'}}, status=400)

    # Güvenli benzersiz ad
    ext = os.path.splitext(upload.name)[1].lower() or '.jpg'
    safe_name = f"article_images/{uuid.uuid4().hex}{ext}"
    path = default_storage.save(safe_name, ContentFile(upload.read()))
    url = default_storage.url(path)

    # CKEditor simpleUpload formatı
    return JsonResponse({'url': url})


@login_required
def create_article_view(request):
    """
    Manuel makale oluşturma (CKEditor ile). Kullanıcı başlık, özet, içerik,
    anahtar kelime ve kapak resmi girip kaydeder. İçerik CKEditor'dan HTML gelir.
    Normal kullanıcının makalesi onay bekler (is_published=False),
    superuser'ınki doğrudan yayınlanır.
    """
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        keywords = (request.POST.get('keywords') or '').strip()
        tr_abstract = (request.POST.get('turkish_abstract') or '').strip()
        en_abstract = (request.POST.get('english_abstract') or '').strip()
        content = (request.POST.get('content') or '').strip()
        bibliography = (request.POST.get('bibliography') or '').strip()
        cover = request.FILES.get('cover_image')

        # Basit doğrulama
        if not title:
            messages.error(request, "Lütfen bir başlık girin.")
            return render(request, 'blog/create_article.html', {'meta_title': 'Makale Oluştur'})
        if not content or len(content) < 50:
            messages.error(request, "Makale içeriği çok kısa (en az 50 karakter).")
            return render(request, 'blog/create_article.html', {'meta_title': 'Makale Oluştur'})

        article = GeneratedArticle(
            owner=request.user,
            user_request=f"[Manuel oluşturuldu] {title}",
            title=title,
            keywords=keywords,
            turkish_abstract=tr_abstract,
            english_abstract=en_abstract,
            full_content=content,
            bibliography=bibliography,
            status='tamamlandi',
            is_published=bool(request.user.is_superuser),
        )
        if cover:
            article.cover_image = cover
        article.save()

        if request.user.is_superuser:
            messages.success(request, "Makaleniz oluşturuldu ve yayınlandı.")
        else:
            messages.success(request, "Makaleniz oluşturuldu. Yönetici onayından sonra yayınlanacak.")
        return redirect('blog:article_detail', article_id=article.id, slug=article.slug)

    return render(request, 'blog/create_article.html', {
        'meta_title': 'Makale Oluştur',
    })


@login_required
@check_credits('makale_uretim', default_cost=15)
def generate_article_view(request):
    from dash_apps.i18n_helper import get_lang, t
    lang = get_lang(request)
    try:
        profile = request.user.profile
        if not profile.first_name or not profile.last_name:
            raise Profile.DoesNotExist
    except Profile.DoesNotExist:
        messages.warning(request, t('gen_msg_profile', lang))
        try:
            profile_id = request.user.profile.id
            redirect_url = reverse('admin:blog_profile_change', args=[profile_id])
        except (Profile.DoesNotExist, AttributeError):
            redirect_url = reverse('admin:blog_profile_add') + f'?user={request.user.id}'
        return redirect(redirect_url)

    # Aktif sağlayıcı + modelleri çek — her model bir dropdown seçeneği
    from ai_engine.models import Provider
    active_providers = Provider.objects.filter(is_active=True)

    # Dropdown seçenekleri: yalnızca aktif anahtarı OLAN sağlayıcıların
    # aktif modelleri. value = "service_name|model_name"
    api_options = []
    for p in active_providers:
        if p.active_key_count < 1:
            continue
        for m in p.ai_models.filter(is_active=True).order_by('model_name'):
            label_model = m.label or m.model_name
            api_options.append({
                'label': f"{p.service_name} - {label_model}",
                'value': f"{p.service_name}|{m.model_name}",
            })

    if not api_options:
        messages.error(request, t('gen_msg_no_provider', lang))
        return redirect('blog:anasayfa')

    main_navbar = create_main_navbar(request) # Bu fonksiyonun sizde olduğunu varsayıyorum.

    generate_content = dbc.Row(dbc.Col(html.Div([
        dcc.Store(id='user-session-store', data={'user_id': request.user.id}),
        dcc.Store(id='gen-lang-store', data=lang),
        dcc.Location(id='url', refresh=True),
        html.Div([html.I(className="fa-solid fa-wand-magic-sparkles fa-4x text-success mb-3"), html.H1(t('gen_h1', lang)),
                  html.P(t('gen_lead', lang), className="lead text-muted")],
                 className="text-center mb-5"),
        dbc.Card(dbc.CardBody([
            # YENİ: AI Servis Seçimi Dropdown
            dbc.Row([
                dbc.Col(html.Label(t('gen_service_label', lang)), width=12),
                dbc.Col(
                    dcc.Dropdown(
                        id='ai-service-dropdown',
                        options=api_options,
                        value=api_options[0]['value'] if api_options else None,  # İlkini varsayılan yap
                        clearable=False
                    ),
                    width=12
                )
            ], className="mb-4"),

            html.P(
                t('gen_topic_prompt', lang),
                className="card-text"),
            dcc.Textarea(id='request-textarea',
                         placeholder=t('gen_topic_placeholder', lang),
                         style={'width': '100%', 'height': 150}, className="form-control form-control-lg mb-3"),

            # YENİ: Makale uzunluğu seçimi
            dbc.Row([
                dbc.Col([
                    html.Label(t('gen_length_label', lang), className="fw-bold"),
                    dcc.Dropdown(
                        id='article-length-dropdown',
                        options=[
                            {'label': t('gen_len_short', lang), 'value': 500},
                            {'label': t('gen_len_medium', lang), 'value': 1500},
                            {'label': t('gen_len_long', lang), 'value': 2500},
                            {'label': t('gen_len_xlong', lang), 'value': 4000},
                        ],
                        value=1500,
                        clearable=False,
                    ),
                    html.Small(
                        t('gen_length_hint', lang),
                        className="text-muted",
                    ),
                ], width=12),
            ], className="mb-4"),
            dcc.Loading(id="loading-spinner", type="border", children=[
                html.Div(className="d-grid mt-4", children=[
                    dbc.Button([html.I(className="fas fa-paper-plane me-2"), t('gen_submit_btn', lang)],
                               id='submit-request-button', color="success", size="lg")]),
                html.Div(id='form-feedback-message', className="mt-3")])
        ]), className="p-md-5 p-3 shadow-lg"),
        html.Div(html.A(t('gen_back_home', lang), href="/", className="mt-3 d-inline-block"), className="text-center")
    ]), md=8, className="mx-auto"))

    from billing.dash_helpers import build_confirm_modal
    full_layout = html.Div([main_navbar, dbc.Container(generate_content, className="my-5"), build_confirm_modal('gen-modal', lang=lang)])
    # Navbar olmadan direkt container'ı layout olarak atıyorum, siz kendi yapınıza göre düzenleyin
    #full_layout = dbc.Container(generate_content, className="my-5")

    _generate_layout = full_layout

    def serve_generate_layout():
        return _generate_layout

    generate_app.layout = serve_generate_layout

    return render(request, 'blog/generate_article.html')


def contact_view(request):
    main_navbar = create_main_navbar(request)
    from dash_apps.i18n_helper import get_lang, t
    lang = get_lang(request)
    contact_content = dbc.Row(dbc.Col([
        html.Div([html.I(className="fas fa-envelope-open-text fa-3x text-primary mb-3"),
                  html.H1(t('contact_title', lang)),
                  html.P(t('contact_subtitle', lang), className="lead text-muted")],
                 className="text-center mb-5"),
        dbc.Card(dbc.CardBody([
            dbc.Row([dbc.Col(dbc.Input(id='contact-name', placeholder=t('contact_name', lang))),
                     dbc.Col(dbc.Input(id='contact-email', placeholder=t('contact_email', lang)))], className="mb-3"),
            dbc.Input(id='contact-subject', placeholder=t('contact_subject', lang), className="mb-3"),
            dbc.Textarea(id='contact-message', placeholder=t('contact_message', lang), rows=6, className="mb-3"),
            html.Div(className="d-grid",
                     children=[dbc.Button([t('contact_send', lang)], id='submit-contact-button', color="primary")]),
        ]), className="p-4 shadow-sm"),
        html.Div(id='contact-form-feedback', className="mt-4")
    ], md=8, lg=7, className="mx-auto"))
    full_layout = html.Div([main_navbar, dbc.Container(contact_content, className="my-5")])
    _contact_layout = full_layout

    def serve_contact_layout():
        return _contact_layout

    contact_app.layout = serve_contact_layout
    return render(request, 'blog/contact.html', {'meta_title': t('contact_meta_title', lang)})


def custom_logout_view(request):
    logout(request)
    return redirect('blog:anasayfa')


def set_language_view(request, lang_code):
    """Kullanıcının dil tercihini cookie'ye yazar ve geldiği sayfaya döner."""
    from dash_apps.i18n_helper import SUPPORTED
    if lang_code not in SUPPORTED:
        lang_code = 'tr'
    # Geldiği sayfaya geri dön (yoksa anasayfa)
    next_url = request.META.get('HTTP_REFERER') or '/'
    response = redirect(next_url)
    # 1 yıl geçerli cookie
    response.set_cookie('site_lang', lang_code, max_age=365 * 24 * 60 * 60)
    return response


def register_view(request):
    """Yeni kullanıcı kaydı (e-posta + şifre). Kayıt sonrası otomatik giriş."""
    from django.contrib.auth import login
    from .forms import SignUpForm

    # Zaten giriş yapmışsa anasayfaya
    if request.user.is_authenticated:
        return redirect('blog:anasayfa')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Hoş geldiniz, {user.username}! Kaydınız oluşturuldu.")
            return redirect('blog:anasayfa')
    else:
        form = SignUpForm()

    return render(request, 'registration/register.html', {'form': form})


def robots_txt_view(request):
    base_url = f"{request.scheme}://{request.get_host()}"
    return render(request, 'robots.txt', {'base_url': base_url}, content_type="text/plain")


def google_verification_view(request):
    """Google Search Console sahiplik doğrulama dosyasını kök adreste sunar."""
    return HttpResponse(
        "google-site-verification: google6648bc38b8876b72.html",
        content_type="text/plain",
    )


@login_required
def resume_view(request, username=None):
    main_navbar = create_main_navbar(request)
    # username verilmişse o kullanıcının profili (açık), yoksa giriş yapanın profili
    if username:
        from django.contrib.auth.models import User
        target_user = User.objects.filter(username=username).first()
        profile = Profile.objects.filter(user=target_user).first() if target_user else None
    elif request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()
    else:
        profile = None
    resume_content = create_resume_layout(profile)
    full_layout = html.Div([main_navbar, resume_content])
    _resume_layout = full_layout

    def serve_resume_layout():
        return _resume_layout

    resume_app.layout = serve_resume_layout
    return render(request, 'blog/resume.html')


def article_search_view(request):
    """
    Makale arama sayfası için navbar'ı ve Dash uygulamasını DOĞRU şekilde birleştirir.
    """
    # 1. Navbar'ı oluştur
    main_navbar = create_main_navbar(request)

    # 2. article_search.py'dan navbar'sız İÇERİK layout'unu SIFIRDAN oluştur
    content_layout = create_article_search_layout()

    # 3. Navbar ve içeriği birleştirerek tam sayfa düzenini oluştur
    full_layout = html.Div([
        main_navbar,
        content_layout
    ])

    _article_search_layout = full_layout

    def serve_article_search_layout():
        return _article_search_layout

    article_search_app.layout = serve_article_search_layout

    # 5. Dash uygulamasını içeren template'i render et
    return render(request, 'blog/article_search.html', {'meta_title': "Makale arama sayfası - AI Blog"})