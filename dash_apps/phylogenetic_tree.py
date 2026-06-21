import base64
import io

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash
from django.shortcuts import reverse

from Bio import SeqIO

app = DjangoDash('PhylogeneticTreeApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])


def create_phylo_layout(lang='tr'):
    """Filogenetik Ağaç aracı sayfası: FASTA yükleme + yöntem + ağaç + yorum."""
    from dash_apps.i18n_helper import t

    sidebar = dbc.Col([
        html.H4([html.I(className="fas fa-sitemap me-2"), t('ph_title', lang)]),
        html.P(t('ph_subtitle', lang), className="text-muted small"),
        html.Hr(),

        dbc.Label(t('ph_upload_label', lang), className="fw-bold"),
        dcc.Upload(
            id='ph-upload',
            children=html.Div([
                html.I(className="fas fa-file-upload fa-2x mb-2 text-success"),
                html.Br(),
                html.Span(t('ph_upload_hint', lang)),
            ]),
            style={
                'width': '100%', 'height': '120px', 'lineHeight': '1.5',
                'borderWidth': '2px', 'borderStyle': 'dashed',
                'borderRadius': '8px', 'textAlign': 'center',
                'paddingTop': '20px', 'cursor': 'pointer',
                'borderColor': '#2E8B57', 'backgroundColor': '#f8fff8',
            },
            multiple=False,
        ),
        html.Div(id='ph-upload-status', className="small mt-2"),

        html.Hr(),
        dbc.Label(t('ph_or_paste', lang), className="fw-bold"),
        dbc.Textarea(
            id='ph-paste',
            placeholder=">tur1\nATCG...\n>tur2\nATCG...",
            style={'height': '120px', 'fontFamily': 'monospace', 'fontSize': '0.8rem'},
        ),

        html.Hr(),
        dbc.Label(t('ph_method', lang), className="fw-bold"),
        dbc.Select(
            id='ph-method',
            options=[
                {'label': 'Neighbor-Joining (NJ)', 'value': 'nj'},
                {'label': 'UPGMA', 'value': 'upgma'},
            ], value='nj'),
        html.Small(t('ph_method_hint', lang), className="text-muted d-block mt-1"),

        dbc.Button(
            [html.I(className="fas fa-project-diagram me-2"), t('ph_build', lang)],
            id='ph-build-btn', color='success', className='w-100 mt-3'),
    ], md=4, className="p-4", style={'backgroundColor': '#fafafa',
                                     'height': '100vh', 'overflowY': 'auto'})

    content = dbc.Col([
        html.H4(t('ph_results', lang)),
        html.Hr(),
        dcc.Store(id='ph-fasta-store'),
        dcc.Store(id='ph-tree-store'),
        dcc.Loading(
            html.Div(id='ph-result',
                     children=html.P(t('ph_placeholder', lang),
                                     className="text-muted")),
        ),
    ], md=8, className="p-4", style={'height': '100vh', 'overflowY': 'auto'})

    return dbc.Container([
        dcc.Location(id='ph-url', refresh=False),
        dcc.Store(id='ph-lang-store', data=lang),
        html.H2([html.I(className="fas fa-sitemap me-2"), t('ph_title', lang)],
                className="mt-4"),
        html.P(t('ph_page_desc', lang), className="text-muted"),
        html.Hr(),
        dbc.Row([sidebar, content]),
    ], fluid=True)


def _read_fasta(contents, paste_text):
    """Upload içeriği veya yapıştırılan metinden FASTA dizilerini okur."""
    text = ''
    if contents:
        try:
            _ctype, b64 = contents.split(',', 1)
            text = base64.b64decode(b64).decode('utf-8', errors='ignore')
        except Exception:
            text = ''
    if not text and paste_text:
        text = paste_text
    if not text:
        return None, "Dosya/metin bulunamadı."
    try:
        records = list(SeqIO.parse(io.StringIO(text), 'fasta'))
        if not records:
            return None, "Geçerli FASTA dizisi bulunamadı."
        return records, None
    except Exception as e:
        return None, f"FASTA okunamadı: {e}"


@app.callback(
    Output('ph-upload-status', 'children'),
    Output('ph-fasta-store', 'data'),
    Input('ph-upload', 'contents'),
    State('ph-upload', 'filename'),
    prevent_initial_call=True
)
def on_upload(contents, filename):
    if not contents:
        return no_update, no_update
    records, err = _read_fasta(contents, None)
    if err:
        return dbc.Alert(err, color="danger", className="py-1 mb-0 small"), None
    # Sadece ham metni sakla (yeniden parse edilecek)
    _ctype, b64 = contents.split(',', 1)
    import base64 as _b64
    raw = _b64.b64decode(b64).decode('utf-8', errors='ignore')
    return (dbc.Alert(f"✓ {filename}: {len(records)} dizi yüklendi",
                      color="success", className="py-1 mb-0 small"),
            raw)


@app.callback(
    Output('ph-result', 'children'),
    Output('ph-tree-store', 'data'),
    Input('ph-build-btn', 'n_clicks'),
    State('ph-fasta-store', 'data'),
    State('ph-paste', 'value'),
    State('ph-method', 'value'),
    State('ph-lang-store', 'data'),
    prevent_initial_call=True
)
def build_tree(n_clicks, stored_fasta, paste_text, method, lang, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'tr'
    if not n_clicks:
        return no_update, no_update

    # Kredi kontrolü (filogeni analizi)
    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_phylogenetics', cost=5, lang=lang,
                             description="Filogenetik ağaç analizi")
    if not ok:
        return msg, no_update

    records, err = _read_fasta(
        f"data:text/plain;base64,{base64.b64encode((stored_fasta or '').encode()).decode()}"
        if stored_fasta else None,
        paste_text)
    if err or not records:
        return dbc.Alert(err or t('ph_no_input', lang), color="warning"), no_update

    if len(records) < 3:
        return dbc.Alert(t('ph_need3', lang), color="warning"), no_update

    try:
        from dash_apps.phylo_helper import (build_phylo_tree, tree_to_plotly,
                                            interpret_tree_ai)
        tree_result = build_phylo_tree(records, method=method or 'nj')
        if not tree_result.get('success'):
            return dbc.Alert(tree_result.get('error', t('ph_error', lang)),
                             color="danger"), no_update

        children = [
            dbc.Alert(
                f"✓ {tree_result['n_taxa']} {t('ph_taxa', lang)} · "
                f"{tree_result['method']} · {tree_result['aln_length']} {t('ph_positions', lang)}",
                color="success"),
        ]

        fig = tree_to_plotly(tree_result)
        if fig is not None:
            children.append(dcc.Graph(figure=fig, config={'displayModeBar': True}))

        if tree_result.get('distance_summary'):
            children.append(html.P(tree_result['distance_summary'],
                                   className="text-muted small mt-2"))

        # AI evrimsel yorum
        interpretation = interpret_tree_ai(tree_result, lang=lang)
        if interpretation:
            children.append(html.Hr())
            children.append(html.H5([html.I(className="fas fa-dna me-2"),
                                     t('ph_interpret', lang)]))
            children.append(html.P(interpretation,
                                   style={'whiteSpace': 'pre-wrap'}))

        # Newick (katlanabilir)
        children.append(html.Details([
            html.Summary("Newick", className="text-muted"),
            html.Code(tree_result['newick'],
                      className="d-block mt-1 p-2 bg-light rounded small",
                      style={'wordBreak': 'break-all'}),
        ], className="mt-3"))

        # Makaleye dönüştür bölümü
        children.append(html.Hr())
        children.append(dbc.Card([
            dbc.CardBody([
                html.H6([html.I(className="fas fa-file-medical-alt me-2"),
                         t('ph_publish_title', lang)], className="mb-2"),
                html.P(t('ph_publish_desc', lang), className="small text-muted mb-3"),
                dbc.Button([html.I(className="fas fa-magic me-2"),
                            t('ph_publish_btn', lang)],
                           id='ph-publish-btn', color='primary', className='w-100'),
                dcc.Loading(html.Div(id='ph-publish-result', className="mt-3")),
            ])
        ], className="border-primary"))

        return html.Div(children), tree_result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"{t('ph_error', lang)}: {e}", color="danger"), no_update


@app.callback(
    Output('ph-publish-result', 'children'),
    Input('ph-publish-btn', 'n_clicks'),
    State('ph-tree-store', 'data'),
    State('ph-lang-store', 'data'),
    prevent_initial_call=True
)
def publish_phylo_to_article(n_clicks, tree_data, lang, **kwargs):
    """Filogenetik analizi akademik makaleye dönüştürür."""
    from dash_apps.i18n_helper import t
    lang = lang or 'tr'
    if not n_clicks or not tree_data:
        return no_update

    from billing.dash_helpers import get_request_user
    user = get_request_user(kwargs)
    if user is None or not getattr(user, 'is_authenticated', False):
        return dbc.Alert(t('ph_login_required', lang), color="warning")

    from billing.services import can_use, charge
    if not user.is_superuser:
        ok_credit, credit_msg = can_use(user, 'makale_uretim', default_cost=10)
        if not ok_credit:
            return dbc.Alert(credit_msg, color="danger")

    try:
        from dash_apps.generate import run_ai_generation_with_pool
        from blog.models import GeneratedArticle, Category

        taxa = tree_data.get('taxa', [])
        method = tree_data.get('method', 'NJ')
        # Konu: filogenetik karşılaştırma
        sample = ', '.join(taxa[:4])
        topic = f"{sample} filogenetik analizi ve evrimsel ilişkileri"

        bio_context_lines = [
            "Analiz türü: Filogenetik Ağaç Analizi",
            f"Yöntem: {method}",
            f"Takson sayısı: {tree_data.get('n_taxa')}",
            f"Taksonlar: {', '.join(taxa)}",
            f"Hizalama uzunluğu: {tree_data.get('aln_length')} pozisyon",
            f"Mesafe özeti: {tree_data.get('distance_summary', '')}",
            f"Newick: {tree_data.get('newick', '')}",
            "ÖNEMLİ: Makale, bu filogenetik analizi temel almalı; taksonların "
            "evrimsel akrabalık ilişkilerini, kümelenmelerini ve bunların biyolojik "
            "anlamını literatür ışığında değerlendirmelidir. Ayrı bir "
            "'Filogenetik ve Evrimsel Analiz' bölümü içermelidir.",
        ]
        bio_context = "\n".join(bio_context_lines)

        ai_data, _used = run_ai_generation_with_pool(
            topic, word_count=1500, bio_context=bio_context)

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise TypeError("Yapay zekadan beklenen formatta yanıt alınamadı.")

        category_obj, _ = Category.objects.get_or_create(
            name=ai_data.get("category_name", "Biyoinformatik").strip().title())

        new_article = GeneratedArticle.objects.create(
            owner=user, user_request=topic,
            title=ai_data.get("title"), category=category_obj,
            keywords=ai_data.get("keywords", ""),
            english_abstract=ai_data.get("english_abstract"),
            turkish_abstract=ai_data.get("turkish_abstract"),
            full_content=ai_data.get("content"),
            bibliography=ai_data.get("bibliography"),
            structured_data=ai_data.get("structured_data"),
            status='tamamlandi', is_published=bool(user.is_superuser),
        )

        if not user.is_superuser:
            try:
                charge(user, 'makale_uretim', default_cost=10,
                       description=f"Filogeni makale: {ai_data.get('title','')[:50]}")
            except Exception:
                pass

        try:
            article_url = new_article.get_absolute_url()
        except Exception:
            article_url = f"/article/{new_article.id}/{new_article.slug}/"

        return dbc.Alert([
            html.H6([html.I(className="fas fa-check-circle me-2"),
                     t('ph_article_done', lang)], className="mb-2"),
            html.P(f"{ai_data.get('title', '')}", className="small mb-3"),
            dbc.Button([html.I(className="fas fa-arrow-right me-2"),
                        t('ph_goto_article', lang)],
                       href=article_url, external_link=True,
                       color="success", className="w-100"),
        ], color="success")

    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            from blog.models import create_notification
            create_notification(
                category='makale_hatasi',
                title="Filogeni-makale üretim hatası",
                message=str(e)[:200],
                technical_detail=traceback.format_exc(),
                related_user=user if user and getattr(user, 'is_authenticated', False) else None)
        except Exception:
            pass
        return dbc.Alert(t('ph_article_error', lang), color="warning")


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open