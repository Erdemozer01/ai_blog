"""
Anasayfa (landing) — Dash uygulaması.

Karşılama sayfasını (hero, neden, araçlar, AI özelliği, son makaleler, CTA)
Dash bileşenleriyle üretir. Navbar `blog.views.create_main_navbar` ile
diğer sayfalarla tutarlı şekilde eklenir.

İlgili CSS sınıfları (.lp-hero, .tool-card, .article-card vb.)
templates/blog/anasayfa.html içindeki {% block stylesheet %} bölümündedir.
"""
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
from django.urls import reverse
from django.templatetags.static import static
from django.utils.html import strip_tags
from django_plotly_dash import DjangoDash

from blog.models import GeneratedArticle

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('Anasayfa', external_stylesheets=external_stylesheets)


def _tool_card(href, color, icon, title, desc, badge=None):
    head = [title]
    if badge:
        head.append(
            html.Span(badge, className="badge bg-success ms-1",
                      style={"fontSize": ".6rem", "verticalAlign": "middle"})
        )
    return dbc.Col(
        html.A(
            [
                html.Div(html.I(className=icon), className="tool-ico",
                         style={"background": color}),
                html.H5(head, className="mb-1"),
                html.P(desc, className="text-muted small mb-0"),
            ],
            href=href, className="tool-card p-4",
        ),
        md=6, lg=3,
    )


def _feature(icon, title, desc):
    return dbc.Col(
        [
            html.Div(html.I(className=icon), className="lp-feature-ico mb-2"),
            html.H6(title, className="fw-bold"),
            html.P(desc, className="text-muted small mb-0"),
        ],
        md=4,
    )


def _article_card(article, en):
    cover = (
        html.Img(className="cover", src=article.cover_image.url, alt=article.title)
        if getattr(article, "cover_image", None) else
        html.Div(html.I(className="fas fa-newspaper",
                        style={"fontSize": "2rem", "opacity": ".4"}),
                 className="cover d-flex align-items-center justify-content-center text-muted")
    )
    if en:
        abstract = article.english_abstract or article.turkish_abstract or ""
    else:
        abstract = article.turkish_abstract or article.english_abstract or ""
    abstract = strip_tags(abstract)
    if len(abstract) > 150:
        abstract = abstract[:150].rstrip() + "…"

    body_children = []
    if getattr(article, "category", None):
        body_children.append(
            html.Span(article.category.name, className="badge bg-light text-primary mb-2")
        )
    title = article.title if len(article.title) <= 70 else article.title[:70] + "…"
    body_children += [
        html.H6(html.A(title, href=article.get_absolute_url(),
                       className="text-dark text-decoration-none"), className="fw-bold"),
        html.P(abstract, className="text-muted small mb-2"),
        html.A(("Read more →" if en else "Devamını oku →"),
               href=article.get_absolute_url(),
               className="small fw-semibold text-decoration-none"),
    ]
    return dbc.Col(
        html.Div([cover, html.Div(body_children, className="p-3")], className="article-card"),
        md=6, lg=4,
    )


def create_anasayfa_content_layout(lang='en'):
    """Anasayfa (landing) içeriğini Dash bileşenleri olarak döndürür."""
    en = (lang == 'en')

    def L(tr, en_text):
        return en_text if en else tr

    # --- HERO ---
    hero = html.Header(
        dbc.Container(
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H1(L("Tarayıcınızda, yapay zeka destekli biyoinformatik.",
                                      "AI-powered bioinformatics, in your browser.")),
                            html.P(
                                L("CRISPR kılavuzları tasarlayın, sekansları analiz edin, primer "
                                  "planlayın ve daha fazlası — ücretsiz çevrimiçi araçlar ve yapay "
                                  "zeka destekli akademik makaleler. Kurulum gerekmez.",
                                  "Design CRISPR guides, analyze sequences, plan primers and more — "
                                  "free online tools, plus AI-generated academic articles. No "
                                  "installation required."),
                                className="lead mt-3",
                            ),
                            html.Div(
                                [
                                    html.A([html.I(className="fas fa-toolbox me-2"),
                                            L("Araçları Keşfet", "Explore Tools")],
                                           href="#tools",
                                           className="btn btn-light btn-lg fw-semibold text-primary"),
                                    html.A([html.I(className="fas fa-dna me-2"),
                                            L("CRISPR Aracını Dene", "Try CRISPR Designer")],
                                           href=reverse('bio_tools:crispr_designer'),
                                           className="btn btn-lg btn-light-soft"),
                                ],
                                className="d-flex flex-wrap gap-2 mt-4",
                            ),
                        ],
                        lg=7,
                    ),
                    dbc.Col(
                        html.Iframe(
                            src=static('anim/crystal-brain.html'),
                            title=L("Yapay zeka — kristal beyin", "AI — crystal brain"),
                            className="hero-brain",
                        ),
                        lg=5, className="text-center mt-4 mt-lg-0",
                    ),
                ],
                className="align-items-center g-4",
            )
        ),
        className="lp-hero",
    )

    # --- NEDEN / KAYNAĞA DAYALI ---
    why = html.Section(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div(L("Neden AI Blog", "Why AI Blog"), className="lp-eyebrow"),
                        html.H2(L("Bilgi kaynağından — uydurma değil",
                                  "Information from the source — not invented"), className="mt-1"),
                        html.P(
                            L("Sonuçlar kabul görmüş algoritmalardan ve doğrulanmış "
                              "veritabanlarından gelir; her çıktının kaynağı açıkça belirtilir — "
                              "gördüğünüze güvenip doğrulayabilirsiniz.",
                              "Results come from established algorithms and validated databases, "
                              "with the source of every output made clear — so you can trust and "
                              "verify what you see."),
                            className="text-muted mx-auto", style={"maxWidth": "680px"},
                        ),
                    ],
                    className="text-center mb-5",
                ),
                dbc.Row(
                    [
                        _feature("fas fa-database",
                                 L("Kaynağa dayalı", "Grounded in real data"),
                                 L("Araçlar; gerçek algoritmalardan (Doench, kesim haritaları, Tm) "
                                   "ve seçkin veritabanlarından — ClinVar, CIViC, PharmGKB — "
                                   "deterministik sonuç hesaplar; AI tahmini değil.",
                                   "Tools compute deterministic results from real algorithms "
                                   "(Doench, restriction maps, Tm) and curated databases — ClinVar, "
                                   "CIViC, PharmGKB — not AI guesses.")),
                        _feature("fas fa-eye",
                                 L("Şeffaf kaynak", "Transparent sources"),
                                 L("Her çıktı nereden geldiğini gösterir — örn. bir kılavuz skoru "
                                   "\"Doench\" mi \"sezgisel\" mi — ve sınırlar gizlenmeden açıkça "
                                   "belirtilir.",
                                   "Every output shows where it comes from — e.g. a guide score "
                                   "labeled \"Doench\" vs \"heuristic\" — and the limits are stated "
                                   "openly, never hidden.")),
                        _feature("fas fa-check-double",
                                 L("Doğrulanabilir, uydurma değil", "Verifiable, not fabricated"),
                                 L("Hesaplamalar tekrarlanabilir; makale kaynakları PubMed'den "
                                   "gelir, CrossRef'te doğrulanır ve her atıf kaynağına sadakat "
                                   "için denetlenir.",
                                   "Computations are reproducible; article references come from "
                                   "PubMed, are verified in CrossRef, and every citation is checked "
                                   "for faithfulness to its source.")),
                    ],
                    className="g-4 text-center",
                ),
            ]
        ),
        className="lp-section", style={"background": "#fff"},
    )

    # --- ARAÇLAR ---
    tools = html.Section(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div(L("Biyoinformatik Araç Seti", "Bioinformatics Toolkit"),
                                 className="lp-eyebrow"),
                        html.H2(L("Moleküler biyoloji ve genomik araçları",
                                  "Tools for molecular biology & genomics"), className="mt-1"),
                        html.P(L("Her aracı hemen açıp kullanın — giriş yalnızca kredili "
                                 "analizleri çalıştırmak için gerekir.",
                                 "Open and use any tool right away — login is only needed to run "
                                 "credit-based analyses."), className="text-muted"),
                    ],
                    className="text-center mb-5",
                ),
                dbc.Row(
                    [
                        _tool_card(reverse('bio_tools:crispr_designer'), "#2563eb", "fas fa-dna",
                                   "CRISPR sgRNA",
                                   L("PAM bulun, Doench modeliyle skorlanan kılavuz RNA'lar "
                                     "tasarlayın.",
                                     "Find PAMs and design guide RNAs, scored with the Doench "
                                     "model."),
                                   badge=L("YENİ", "NEW")),
                        _tool_card(reverse('bio_tools:sequence_analyzer'), "#0ea5e9",
                                   "fas fa-magnifying-glass-chart",
                                   L("Sekans Analizi", "Sequence Analyzer"),
                                   L("DNA/RNA için GC oranı, ORF, çeviri ve bileşim analizi.",
                                     "GC content, ORFs, translation and composition of DNA/RNA.")),
                        _tool_card(reverse('bio_tools:primer_design'), "#10b981", "fas fa-vials",
                                   L("Primer Tasarımı", "Primer Design"),
                                   L("Tm, GC ve özgüllük kontrolleriyle PCR primerleri tasarlayın.",
                                     "Design PCR primers with Tm, GC and specificity checks.")),
                        _tool_card(reverse('bio_tools:restriction_analysis'), "#f59e0b",
                                   "fas fa-scissors",
                                   L("Restriksiyon Analizi", "Restriction Analysis"),
                                   L("Dizinizdeki restriksiyon enzim kesim bölgelerini "
                                     "haritalayın.",
                                     "Map restriction enzyme cut sites along your sequence.")),
                        _tool_card(reverse('bio_tools:plasmid_map'), "#8b5cf6",
                                   "fas fa-circle-nodes",
                                   L("Plazmit Haritası", "Plasmid Map"),
                                   L("Plazmitleri öğeler, ORF'ler ve enzim bölgeleriyle "
                                     "görselleştirin.",
                                     "Visualize plasmids with features, ORFs and enzyme sites.")),
                        _tool_card(reverse('bio_tools:pharmacogenomics'), "#7c3aed", "fas fa-pills",
                                   L("Farmakogenomik", "Pharmacogenomics"),
                                   L("Genler, ilaçlar ve metabolizör fenotipleri üzerine AI "
                                     "araştırması.",
                                     "AI research on genes, drugs and metabolizer phenotypes.")),
                        _tool_card(reverse('bio_tools:variant_prioritization'), "#ef4444",
                                   "fas fa-list-ol",
                                   L("Varyant Önceliklendirme", "Variant Prioritization"),
                                   L("Varyantları klinik öneme göre sıralayın (ClinVar, CIViC).",
                                     "Rank variants by clinical significance (ClinVar, CIViC).")),
                        _tool_card(reverse('bio_tools:mutation_predictor'), "#14b8a6",
                                   "fas fa-wave-square",
                                   L("Mutasyon Tahmini", "Mutation Predictor"),
                                   L("Protein mutasyonlarının işlevsel etkisini tahmin edin.",
                                     "Predict the functional impact of protein mutations.")),
                    ],
                    className="g-4",
                ),
            ]
        ),
        className="lp-section", id="tools",
    )

    # --- AI MAKALE ÜRETİCİ ---
    ai_feature = html.Section(
        dbc.Container(
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(L("AI Makale Üretici", "AI Article Generator"),
                                     className="lp-eyebrow"),
                            html.H2(L("Bir konudan yapılandırılmış akademik makaleye",
                                      "From a topic to a structured academic article"),
                                    className="mt-1"),
                            html.P(L("Bir konu girin; yapay zeka özetler, bölümler ve kaynaklarla "
                                     "yapılandırılmış, iki dilli ve okumaya hazır bir makale "
                                     "taslağı üretsin.",
                                     "Enter a topic and the AI drafts a structured article with "
                                     "abstracts, sections and references — bilingual and ready to "
                                     "read."), className="text-muted"),
                            html.Ul(
                                [
                                    html.Li(L("Türkçe ve İngilizce özet",
                                              "Turkish & English abstracts")),
                                    html.Li(L(["Kaynaklar ",
                                               html.Strong("PubMed"),
                                               "'den çekilir ve ",
                                               html.Strong("CrossRef"),
                                               " ile doğrulanır"],
                                              ["References pulled from ",
                                               html.Strong("PubMed"),
                                               " and verified against ",
                                               html.Strong("CrossRef")])),
                                    html.Li(L("Her atıf, kaynağına sadakat için otomatik "
                                              "denetlenir ve gerekirse düzeltilir",
                                              "Every citation is auto-checked for faithfulness "
                                              "to its source — and corrected when needed")),
                                    html.Li(L("Gerektiğinde grafik ve tablolar",
                                              "Charts & tables where relevant")),
                                ],
                                className="text-muted",
                            ),
                            html.Div(
                                [
                                    html.Span(L("Kaynak altyapısı:", "Powered by:"),
                                              className="text-muted small me-1"),
                                    html.Span(
                                        [html.I(className="fas fa-book-medical me-1"), "PubMed"],
                                        className="badge rounded-pill",
                                        style={"background": "#e0edff", "color": "#1d4ed8",
                                               "fontSize": ".8rem", "padding": ".45em .8em"}),
                                    html.Span(
                                        [html.I(className="fas fa-link me-1"), "CrossRef"],
                                        className="badge rounded-pill",
                                        style={"background": "#dcfce7", "color": "#15803d",
                                               "fontSize": ".8rem", "padding": ".45em .8em"}),
                                ],
                                className="d-flex align-items-center flex-wrap gap-2 mb-3",
                            ),
                            html.A([html.I(className="fas fa-robot me-2"),
                                    L("Makale üret", "Generate an article")],
                                   href=reverse('blog:generate_article'),
                                   className="btn btn-primary mt-2"),
                        ],
                        lg=6,
                    ),
                    dbc.Col(
                        html.I(className="fas fa-file-lines lp-feature-ico",
                               style={"fontSize": "8rem", "color": "#e0e7ff"}),
                        lg=6, className="text-center",
                    ),
                ],
                className="align-items-center g-5",
            )
        ),
        className="lp-section", style={"background": "#fff"},
    )

    # --- SON MAKALELER ---
    recent = list(
        GeneratedArticle.objects.select_related('category')
        .filter(status='tamamlandi', is_published=True)
        .order_by('-created_at')[:6]
    )
    recent_section = None
    if recent:
        recent_section = html.Section(
            dbc.Container(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(L("Blog'dan", "From the Blog"),
                                             className="lp-eyebrow"),
                                    html.H2(L("Son makaleler", "Latest articles"),
                                            className="mt-1 mb-0"),
                                ]
                            ),
                            html.A(L("Tüm makaleler →", "All articles →"),
                                   href=reverse('blog:blog_list'),
                                   className="btn btn-outline-primary"),
                        ],
                        className="d-flex justify-content-between align-items-end mb-4",
                    ),
                    dbc.Row([_article_card(a, en) for a in recent], className="g-4"),
                ]
            ),
            className="lp-section",
        )

    # --- CTA ---
    cta = html.Section(
        dbc.Container(
            html.Div(
                [
                    html.H2(L("Keşfetmeye başlayın — ücretsiz",
                              "Start exploring — it's free"), className="fw-bold"),
                    html.P(L("Herhangi bir aracı şimdi açın. Analiz çalıştırmak ve makale üretmek "
                             "için hesap oluşturun.",
                             "Open any tool now. Create an account to run analyses and generate "
                             "articles."), className="opacity-75 mb-4"),
                    html.Div(
                        [
                            html.A(L("Araçlara göz at", "Browse tools"), href="#tools",
                                   className="btn btn-light btn-lg fw-semibold text-dark"),
                            html.A(L("Ücretsiz hesap oluştur", "Create free account"),
                                   href=reverse('blog:register'),
                                   className="btn btn-primary btn-lg"),
                        ],
                        className="d-flex flex-wrap gap-2 justify-content-center",
                    ),
                ],
                className="lp-cta text-center p-5",
            )
        ),
        className="lp-section",
    )

    children = [dcc.Location(id='url', refresh=False), hero, why, tools, ai_feature]
    if recent_section is not None:
        children.append(recent_section)
    children.append(cta)
    return html.Div(children)


@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n_clicks, is_open):
    return not is_open
