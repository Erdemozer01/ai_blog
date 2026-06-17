"""
Makale Düzenleme (Dash) — dcc.Textarea tabanlı.

Diğer Dash sayfalarıyla tutarlı: navbar gelir, Bootstrap CSS otomatik yüklenir.
full_content yer tutucuların etrafından parçalanır; kullanıcı yalnızca metin
parçalarını düzenler. Grafik/tablo yer tutucuları kilitli kart olarak gösterilir
ve kaydederken aynen korunur.

Layout view tarafından makaleye özel kurulur (build_edit_layout).
"""
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State, ALL, no_update, ctx

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
app = DjangoDash('ArticleEditApp', external_stylesheets=external_stylesheets,
                 suppress_callback_exceptions=True)


def build_edit_content(article, parts):
    """
    Makaleye özel düzenleme içeriği oluşturur.
    parts: blog.edit_helpers.split_content_for_editing çıktısı.
    """
    # İçerik parçaları — metin düzenlenebilir, placeholder kilitli
    content_blocks = []
    for i, p in enumerate(parts):
        if p['type'] == 'text':
            content_blocks.append(
                dcc.Textarea(
                    id={'type': 'edit-text-part', 'index': i},
                    value=p['value'],
                    style={'width': '100%', 'minHeight': '140px',
                           'fontFamily': 'inherit', 'marginBottom': '10px'},
                    className='form-control'
                )
            )
        else:
            content_blocks.append(
                html.Div([
                    html.I(className="fas fa-lock me-2"),
                    html.Strong(p['label']),
                ], className="d-flex align-items-center justify-content-center my-2 p-3 rounded",
                   style={'background': '#f1f3f5', 'border': '2px dashed #adb5bd',
                          'color': '#495057'})
            )

    return dbc.Container([
        # Makale id'sini taşı
        dcc.Store(id='edit-article-id', data=article.id),
        dcc.Store(id='edit-article-slug', data=article.slug),

        html.Div([
            html.H2([html.I(className="fas fa-edit me-2"), "Makaleyi Düzenle"]),
            html.A([html.I(className="fas fa-times me-1"), "İptal"],
                   href=f"/article/{article.id}/{article.slug}/",
                   className="btn btn-outline-secondary btn-sm"),
        ], className="d-flex justify-content-between align-items-center mb-4"),

        # Genel bilgiler
        dbc.Card([
            dbc.CardHeader(html.Strong("Genel Bilgiler")),
            dbc.CardBody([
                dbc.Label("Başlık", className="fw-bold"),
                dbc.Input(id='edit-title', value=article.title or '', className="mb-3"),
                dbc.Label("Anahtar Kelimeler", className="fw-bold"),
                dbc.Input(id='edit-keywords', value=article.keywords or '', className="mb-3"),
                dbc.Label("Türkçe Özet", className="fw-bold"),
                dbc.Textarea(id='edit-tr-abstract', value=article.turkish_abstract or '',
                             rows=3, className="mb-3"),
                dbc.Label("İngilizce Özet (Abstract)", className="fw-bold"),
                dbc.Textarea(id='edit-en-abstract', value=article.english_abstract or '',
                             rows=3, className="mb-3"),
            ])
        ], className="mb-3"),

        # Makale içeriği (parçalar)
        dbc.Card([
            dbc.CardHeader(html.Strong("Makale İçeriği")),
            dbc.CardBody(content_blocks)
        ], className="mb-3"),

        # Kaynakça
        dbc.Card([
            dbc.CardHeader(html.Strong("Kaynakça")),
            dbc.CardBody([
                dbc.Textarea(id='edit-bibliography', value=article.bibliography or '',
                             rows=8, className="form-control")
            ])
        ], className="mb-3"),

        # Kaydet
        html.Div([
            html.A("İptal", href=f"/article/{article.id}/{article.slug}/",
                   className="btn btn-outline-secondary me-2"),
            dbc.Button([html.I(className="fas fa-save me-1"), "Kaydet"],
                       id='edit-save-btn', color="primary"),
        ], className="d-flex justify-content-end mb-3"),

        html.Div(id='edit-feedback', className="mb-5"),
    ], className="my-5", style={'maxWidth': '900px'})


@app.callback(
    Output('edit-feedback', 'children'),
    Input('edit-save-btn', 'n_clicks'),
    State('edit-article-id', 'data'),
    State('edit-article-slug', 'data'),
    State('edit-title', 'value'),
    State('edit-keywords', 'value'),
    State('edit-tr-abstract', 'value'),
    State('edit-en-abstract', 'value'),
    State('edit-bibliography', 'value'),
    State({'type': 'edit-text-part', 'index': ALL}, 'value'),
    State({'type': 'edit-text-part', 'index': ALL}, 'id'),
    prevent_initial_call=True
)
def save_article(n_clicks, article_id, slug, title, keywords, tr_abstract,
                 en_abstract, bibliography, text_values, text_ids, **kwargs):
    if not n_clicks or not article_id:
        return no_update

    # Yetki: oturum kullanıcısı makale sahibi mi
    request = kwargs.get('request')
    user = getattr(request, 'user', None) if request else None
    if user is None or not user.is_authenticated:
        return dbc.Alert("Bu işlem için giriş yapmalısınız.", color="warning")

    from blog.models import GeneratedArticle
    from blog.edit_helpers import (split_content_for_editing, rebuild_content,
                                   has_meaningful_change)
    from django.utils import timezone

    try:
        article = GeneratedArticle.objects.get(id=article_id)
    except GeneratedArticle.DoesNotExist:
        return dbc.Alert("Makale bulunamadı.", color="danger")

    if article.owner_id != user.id:
        return dbc.Alert("Bu makaleyi düzenleme yetkiniz yok.", color="danger")

    # Orijinal parçaları tekrar üret (token'lar için) ve düzenlenen metinleri eşle
    original_parts = split_content_for_editing(article.full_content)
    edited_texts = {}
    for val, id_obj in zip(text_values, text_ids):
        idx = id_obj['index']
        edited_texts[idx] = val if val is not None else ''

    new_content = rebuild_content(original_parts, edited_texts)

    new_title = (title or '').strip()
    new_bibliography = (bibliography or '').strip()
    new_tr = (tr_abstract or '').strip()
    new_en = (en_abstract or '').strip()

    content_changed = (
        has_meaningful_change(article.full_content, new_content)
        or article.title != new_title
        or article.bibliography != new_bibliography
        or article.turkish_abstract != new_tr
        or article.english_abstract != new_en
    )

    article.title = new_title or article.title
    article.keywords = (keywords or '').strip()
    article.turkish_abstract = new_tr
    article.english_abstract = new_en
    article.full_content = new_content
    article.bibliography = new_bibliography
    update_fields = ['title', 'keywords', 'turkish_abstract',
                     'english_abstract', 'full_content', 'bibliography']

    if content_changed:
        article.last_edited_at = timezone.now()
        update_fields.append('last_edited_at')

    article.save(update_fields=update_fields)

    article_url = f"/article/{article.id}/{article.slug}/"
    if content_changed:
        msg = "Makaleniz güncellendi. "
        color = "success"
    else:
        msg = "Kaydedildi (içerikte değişiklik algılanmadı). "
        color = "info"

    return dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        msg,
        html.A("Makaleye dön →", href=article_url, className="alert-link"),
    ], color=color)