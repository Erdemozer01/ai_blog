import base64
import io

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash

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

    from billing.dash_helpers import build_confirm_modal
    return dbc.Container([
        dcc.Location(id='ph-url', refresh=False),
        dcc.Store(id='ph-lang-store', data=lang),
        # Kredi onay modalları
        build_confirm_modal('ph-tree-modal', lang=lang),
        build_confirm_modal('ph-publish-modal', lang=lang),
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
    Output('ph-tree-modal', 'is_open'),
    Output('ph-tree-modal-body', 'children'),
    Output('ph-tree-modal-confirm', 'disabled'),
    Input('ph-build-btn', 'n_clicks'),
    Input('ph-tree-modal-cancel', 'n_clicks'),
    Input('ph-tree-modal-confirm', 'n_clicks'),
    State('ph-fasta-store', 'data'),
    State('ph-paste', 'value'),
    State('ph-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_tree_modal(open_click, cancel_click, confirm_click, stored_fasta, paste_text, lang, **kwargs):
    """Ağaç Oluştur butonu → onay modalını aç. İptal/Onay → kapat."""
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    # django-plotly-dash uyumlu: tetikleyen bileşeni prop_id'den çöz
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'ph-build-btn' and open_click:
        # FASTA yoksa modal açma, doğrudan uyarı yerine modalda bilgi ver
        if not stored_fasta and not paste_text:
            from dash_apps.i18n_helper import t
            import dash_bootstrap_components as dbc
            return True, dbc.Alert(t('ph_no_input', lang), color="warning",
                                   className="mb-0"), True
        body, can_proceed = confirm_modal_body(kwargs, 'bio_phylogenetics',
                                               cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, no_update, no_update


@app.callback(
    Output('ph-result', 'children'),
    Output('ph-tree-store', 'data'),
    Input('ph-tree-modal-confirm', 'n_clicks'),
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
        from dash_apps.phylo_helper import build_phylo_tree, tree_to_plotly
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

        # Dal uzunlukları tablosu — her taksonun terminal dal uzunluğu (akrabalık)
        branch_lengths = tree_result.get('branch_lengths') or []
        if branch_lengths:
            bl_rows = [html.Tr([
                html.Td(b['taxon']),
                html.Td(f"{b['branch_length']:.4f}"),
            ]) for b in branch_lengths]
            children.append(html.Hr())
            children.append(html.H6([html.I(className="fas fa-ruler-horizontal me-2"),
                                     t('ph_branch_title', lang)], className="mb-1"))
            children.append(html.P(t('ph_branch_desc', lang),
                                   className="text-muted small mb-2"))
            children.append(dbc.Table([
                html.Thead(html.Tr([
                    html.Th(t('ph_taxon', lang)),
                    html.Th(t('ph_branch_len', lang)),
                ])),
                html.Tbody(bl_rows),
            ], bordered=True, hover=True, size="sm", responsive=True, className="mb-3"))

        # Mesafe MATRİSİ — taksonlar arası uzaklıklar (kare tablo)
        matrix = tree_result.get('distance_matrix') or []
        taxa_list = tree_result.get('taxa') or []
        if matrix and taxa_list:
            n = len(taxa_list)
            # Kısa etiketler (matris başlığı için): T1, T2...
            short_labels = [f"T{i+1}" for i in range(n)]

            # Üst başlık satırı: boş köşe + T1..Tn
            header = html.Thead(html.Tr(
                [html.Th("", style={'minWidth': '110px'})] +
                [html.Th(short_labels[j], className="text-center small",
                         style={'minWidth': '60px'}) for j in range(n)]
            ))

            # Gövde: her satır = bir takson; ilk hücre tam ad, sonra mesafeler
            body_rows = []
            for i in range(n):
                cells = [html.Th([
                    html.Span(short_labels[i], className="fw-bold me-1 text-primary"),
                    html.Span(taxa_list[i], className="small text-muted"),
                ], className="text-nowrap", style={'fontSize': '0.75rem'})]
                for j in range(n):
                    val = matrix[i][j]
                    if i == j:
                        # köşegen
                        cells.append(html.Td("—", className="text-center text-muted"))
                    elif val is None:
                        cells.append(html.Td("·", className="text-center"))
                    else:
                        # Yakınlığa göre renklendir: küçük mesafe = yeşil tonu
                        intensity = max(0, min(1, val))  # 0..1 aralığına sıkıştır
                        # küçük mesafe -> daha koyu yeşil arkaplan
                        green = int(220 - (1 - intensity) * 90)
                        bg = f"rgb({green},{240 - int((1-intensity)*40)},{green})"
                        cells.append(html.Td(
                            f"{val:.3f}", className="text-center small",
                            style={'backgroundColor': bg if val < 0.5 else 'transparent'}))
                body_rows.append(html.Tr(cells))

            children.append(html.Details([
                html.Summary([html.I(className="fas fa-border-all me-2"),
                              t('ph_matrix_title', lang)],
                             className="fw-bold mb-2"),
                html.P(t('ph_matrix_desc', lang), className="text-muted small mb-2"),
                dbc.Table([header, html.Tbody(body_rows)],
                          bordered=True, hover=True, size="sm", responsive=True,
                          className="mt-2", style={'fontSize': '0.8rem'}),
            ], open=True, className="mb-2"))

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

        # Store'a SADECE JSON-uyumlu alanları kaydet (Tree nesnesi serileştirilemez)
        tree_store = {
            'success': tree_result.get('success'),
            'newick': tree_result.get('newick'),
            'taxa': tree_result.get('taxa'),
            'method': tree_result.get('method'),
            'n_taxa': tree_result.get('n_taxa'),
            'aln_length': tree_result.get('aln_length'),
            'distance_summary': tree_result.get('distance_summary'),
            'branch_lengths': tree_result.get('branch_lengths'),
            'distance_matrix': tree_result.get('distance_matrix'),
        }
        return html.Div(children), tree_store

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"{t('ph_error', lang)}: {e}", color="danger"), no_update


@app.callback(
    Output('ph-publish-modal', 'is_open'),
    Output('ph-publish-modal-body', 'children'),
    Output('ph-publish-modal-confirm', 'disabled'),
    Input('ph-publish-btn', 'n_clicks'),
    Input('ph-publish-modal-cancel', 'n_clicks'),
    Input('ph-publish-modal-confirm', 'n_clicks'),
    State('ph-tree-store', 'data'),
    State('ph-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_publish_modal(open_click, cancel_click, confirm_click, tree_data, lang, **kwargs):
    """Makaleye dönüştür butonu → onay modalını aç. İptal/Onay → kapat."""
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'ph-publish-btn' and open_click:
        if not tree_data:
            return False, "", True
        body, can_proceed = confirm_modal_body(kwargs, 'makale_uretim',
                                               cost=15, lang=lang)
        return True, body, (not can_proceed)
    return False, no_update, no_update


@app.callback(
    Output('ph-publish-result', 'children'),
    Input('ph-publish-modal-confirm', 'n_clicks'),
    State('ph-tree-store', 'data'),
    State('ph-lang-store', 'data'),
    prevent_initial_call=True
)
def publish_phylo_to_article(n_clicks, tree_data, lang, **kwargs):
    """Onay sonrası: filogenetik analizi akademik makaleye dönüştürür."""
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
        ok_credit, credit_msg = can_use(user, 'makale_uretim', default_cost=15)
        if not ok_credit:
            return dbc.Alert(credit_msg, color="danger")

    try:
        from dash_apps.generate import run_ai_generation_with_pool
        from blog.models import GeneratedArticle, Category

        taxa = tree_data.get('taxa', [])
        method = tree_data.get('method', 'NJ')
        branch_lengths = tree_data.get('branch_lengths') or []
        matrix = tree_data.get('distance_matrix') or []
        # Konu: filogenetik karşılaştırma
        sample = ', '.join(taxa[:4])
        topic = f"{sample} filogenetik analizi ve evrimsel ilişkileri"

        # Dal uzunluklarını metne dök
        bl_text = "; ".join(
            f"{b['taxon']}: {b['branch_length']:.4f}" for b in branch_lengths)

        bio_context_lines = [
            "Analiz türü: Filogenetik Ağaç Analizi",
            f"Yöntem: {method}",
            f"Takson sayısı: {tree_data.get('n_taxa')}",
            f"Taksonlar: {', '.join(taxa)}",
            f"Hizalama uzunluğu: {tree_data.get('aln_length')} pozisyon",
            f"Mesafe özeti: {tree_data.get('distance_summary', '')}",
            f"Dal uzunlukları (terminal): {bl_text}",
            f"Newick: {tree_data.get('newick', '')}",
            "ÖNEMLİ: Makale, bu filogenetik analizi temel almalı; taksonların "
            "evrimsel akrabalık ilişkilerini, kümelenmelerini ve bunların biyolojik "
            "anlamını literatür ışığında değerlendirmelidir. Ayrı bir "
            "'Filogenetik ve Evrimsel Analiz' bölümü içermelidir.",
            "TABLO YERLEŞTİRME: Makalenin filogenetik analiz bölümünde, dal "
            "uzunlukları ve tür-arası mesafe matrisi için tam olarak şu iki "
            "placeholder'ı uygun yerlere ekle: `_||_STRUCTURED_DATA_91_||_` "
            "(dal uzunlukları tablosu) ve `_||_STRUCTURED_DATA_92_||_` "
            "(mesafe matrisi). Bu iki placeholder'ı MUTLAKA kullan; verilerini "
            "ben hazır sağlayacağım, sen sadece yerleştir.",
        ]
        bio_context = "\n".join(bio_context_lines)

        ai_data, _used = run_ai_generation_with_pool(
            topic, word_count=1500, bio_context=bio_context)

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise TypeError("Yapay zekadan beklenen formatta yanıt alınamadı.")

        # --- FİLOGENİ TABLOLARINI MAKALEYE ENJEKTE ET ---
        # Dal uzunlukları + mesafe matrisi tablolarını structured_data'ya ekle.
        sdata = ai_data.get("structured_data") or {}
        if not isinstance(sdata, dict):
            sdata = {}
        content = ai_data.get("content") or ""

        # 1) Dal uzunlukları tablosu (placeholder 91)
        if branch_lengths:
            sdata["91"] = {
                "type": "table",
                "title": ("Tablo: Taksonların Terminal Dal Uzunlukları" if lang == 'tr'
                          else "Table: Terminal Branch Lengths of Taxa"),
                "columns": (["Takson", "Dal Uzunluğu"] if lang == 'tr'
                            else ["Taxon", "Branch Length"]),
                "data": [[b['taxon'], f"{b['branch_length']:.4f}"]
                         for b in branch_lengths],
                "description": ("Kısa dal = diğerlerine yakın/benzer; uzun dal = daha ayrık."
                                if lang == 'tr'
                                else "Short branch = close/similar; long branch = more divergent."),
            }
        # 2) Mesafe matrisi tablosu (placeholder 92)
        if matrix and taxa:
            # Matris başlıkları: kısa etiket + tam ad alt satırda olmadığından T1.. kullan
            short = [f"T{i+1}" for i in range(len(taxa))]
            cols = [("Takson" if lang == 'tr' else "Taxon")] + short
            mrows = []
            for i, row in enumerate(matrix):
                cells = [f"{short[i]} = {taxa[i]}"]
                for v in row:
                    cells.append("—" if (v == 0.0) else (f"{v:.4f}" if v is not None else "·"))
                mrows.append(cells)
            sdata["92"] = {
                "type": "table",
                "title": ("Tablo: Türler Arası Mesafe Matrisi" if lang == 'tr'
                          else "Table: Inter-Taxon Distance Matrix"),
                "columns": cols,
                "data": mrows,
                "description": ("Hücreler taksonlar arası evrimsel uzaklığı gösterir "
                                "(0 = aynı, küçük değer = yakın akraba)." if lang == 'tr'
                                else "Cells show evolutionary distance between taxa "
                                "(0 = identical, smaller = closer)."),
            }

        # AI placeholder'ları koymadıysa, makale sonuna manuel ekle (garanti)
        if "_||_STRUCTURED_DATA_91_||_" not in content and branch_lengths:
            content += "\n\n_||_STRUCTURED_DATA_91_||_\n"
        if "_||_STRUCTURED_DATA_92_||_" not in content and matrix:
            content += "\n\n_||_STRUCTURED_DATA_92_||_\n"

        ai_data["content"] = content
        ai_data["structured_data"] = sdata
        # --- ENJEKSİYON BİTTİ ---

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
                charge(user, 'makale_uretim', default_cost=15,
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
