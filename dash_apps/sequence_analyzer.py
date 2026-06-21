import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from django_plotly_dash import DjangoDash
import base64
import io
from django.shortcuts import reverse

# Biopython kütüphanesini import ediyoruz
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from Bio import SeqIO

app = DjangoDash('SequenceAnalyzerApp', external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])


# --- Arka Plan Analiz Fonksiyonu (Değişiklik Yok) ---
def parse_and_analyze_sequence(file_content, file_type, seq_type, lang='en'):
    """
    Verilen dosya içeriğini ve formatını kullanarak sekansı analiz eder.
    """
    from dash_apps.i18n_helper import t, credit_label
    if not file_content:
        return {"error": t('sa_no_input', lang)}

    try:
        string_io_file = io.StringIO(file_content)
        record = next(SeqIO.parse(string_io_file, file_type))
        sequence = str(record.seq).upper()
    except Exception as e:
        return {"error": f"{t('sa_file_error', lang)}: {e}. {t('sa_file_format_hint', lang)}"}

    if not sequence:
        return {"error": t('sa_no_valid_seq', lang)}

    results = {"sequence": sequence, "length": len(sequence), "id": record.id, "description": record.description}

    try:
        if seq_type == 'dna':
            dna_seq = Seq(sequence)
            results['type'] = 'DNA'
            results['gc_content'] = f"{gc_fraction(dna_seq) * 100:.2f}%"
            results['transcribed_rna'] = str(dna_seq.transcribe())
            results['complement'] = str(dna_seq.complement())
            results['reverse_complement'] = str(dna_seq.reverse_complement())

        elif seq_type == 'rna':
            rna_seq = Seq(sequence)
            results['type'] = 'RNA'
            results['gc_content'] = f"{gc_fraction(rna_seq) * 100:.2f}%"
            results['back_transcribed_dna'] = str(rna_seq.back_transcribe())
            results['protein_translation'] = str(rna_seq.translate())

        elif seq_type == 'protein':
            if 'U' in sequence:
                return {"error": t('sa_no_uracil', lang)}
            protein_seq = ProteinAnalysis(sequence)
            results['type'] = 'Protein'
            results['molecular_weight'] = f"{protein_seq.molecular_weight():.2f} Da"
            aa_percent = protein_seq.get_amino_acids_percent()
            results['amino_acid_percent'] = {k: f"{v * 100:.2f}%" for k, v in aa_percent.items()}
    except Exception as e:
        return {"error": f"{t('sa_analysis_error', lang)}: {str(e)}"}

    return results


# --- Ön Yüz: Dash Layout Fonksiyonu (Dropdown Güncellendi) ---
def create_sequence_analyzer_layout(lang='en'):
    """Sekans Analiz Aracı sayfasının iki sütunlu ve dosya yüklemeli içeriğini oluşturur."""
    from dash_apps.i18n_helper import t, credit_label

    sidebar = dbc.Col(
        [
            html.H4(t('sa_control_panel', lang)),
            html.Hr(),

            dbc.Label(t('sa_file_format', lang), html_for="file-type-input", className="fw-bold"),
            dcc.Dropdown(
                id='file-type-input',
                options=[
                    {'label': 'FASTA (.fasta, .fa)', 'value': 'fasta'},
                    {'label': 'GenBank (.gb, .gbk)', 'value': 'genbank'},
                    {'label': 'EMBL (.embl)', 'value': 'embl'},
                    {'label': 'Swiss-Prot (.swissprot)', 'value': 'swiss'},
                ],
                value='fasta',
                clearable=False,
                className="mb-3"
            ),

            dbc.Label(t('sa_seq_type', lang), html_for="seq-type-input", className="fw-bold"),
            dcc.Dropdown(
                id='seq-type-input',
                options=[
                    {'label': t('sa_dna', lang), 'value': 'dna'},
                    {'label': t('sa_rna', lang), 'value': 'rna'},
                    {'label': t('sa_protein', lang), 'value': 'protein'},
                ],
                value='dna',
                clearable=False,
                className="mb-3"
            ),

            dcc.Upload(
                id='upload-sequence-file',
                children=html.Div([t('sa_drag_drop', lang), html.A(t('sa_select_file', lang))]),
                style={
                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                    'borderWidth': '1px', 'borderStyle': 'dashed',
                    'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'
                },
            ),

            dbc.Label(t('sa_seq_data_label', lang), html_for="sequence-input", className="fw-bold"),
            dcc.Textarea(
                id="sequence-input",
                placeholder=t('sa_seq_placeholder', lang),
                style={'width': '100%', 'height': 200},
                className="form-control mb-3 font-monospace"
            ),
            dbc.Button([html.I(className="fas fa-cogs me-2"), f"{t('sa_analyze_btn', lang)} {credit_label('bio_sequence_analyzer', lang)}"], id="analyze-button", color="primary",
                       className="w-100"),
        ],
        md=4,
        className="bg-light p-4 border-end"
    )

    content = dbc.Col(
        [
            html.H4(t('sa_results_title', lang)),
            html.Hr(),
            dcc.Loading(
                id="loading-results",
                children=html.Div(id="analysis-results-container",
                                  children=html.P(t('sa_results_placeholder', lang)))
            )
        ],
        md=8,
        className="p-4",
        style={"height": "100vh", "overflowY": "auto"}
    )

    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='sequence-file-store'),
        dcc.Store(id='sa-lang-store', data=lang),
        dcc.Store(id='sa-bio-results-store'),
        html.H2(t('sa_title', lang), className="mt-4"),
        html.P(t('sa_subtitle', lang),
               className="text-muted"),
        html.Hr(),
        dbc.Row([
            sidebar,
            content
        ])
    ], fluid=True)


# --- Callback'ler (Değişiklik Yok) ---

@app.callback(
    Output('sequence-file-store', 'data'),
    Output('sequence-input', 'value'),
    Input('upload-sequence-file', 'contents'),
    State('upload-sequence-file', 'filename'),
    prevent_initial_call=True
)
def update_file_content(contents, filename):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            file_content = decoded.decode('utf-8')
            return file_content, file_content
        except Exception as e:
            print(f"Dosya okuma hatası: {e}")
            error_message = f"Hata: '{filename}' dosyası okunamadı. Lütfen dosyanın UTF-8 formatında olduğundan emin olun."
            return None, error_message
    return no_update, no_update


@app.callback(
    Output("analysis-results-container", "children"),
    Output("sa-bio-results-store", "data"),
    Input("analyze-button", "n_clicks"),
    State("sequence-input", "value"),
    State("file-type-input", "value"),
    State("seq-type-input", "value"),
    State("sa-lang-store", "data"),
    prevent_initial_call=True
)
def update_analysis_results(n_clicks, sequence_content, file_type, seq_type, lang, **kwargs):
    from dash_apps.i18n_helper import t, credit_label
    lang = lang or 'en'
    if not sequence_content:
        return dbc.Alert(t('sa_no_input', lang), color="warning"), no_update

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_sequence_analyzer', cost=5, lang=lang,
                             description="Sekans analizi")
    if not ok:
        return msg, no_update

    results = parse_and_analyze_sequence(sequence_content, file_type, seq_type, lang=lang)

    if "error" in results:
        return dbc.Alert(results["error"], color="danger"), no_update

    result_items = [
        dbc.ListGroupItem([html.Strong(f"{t('sa_file_id', lang)} "), html.Span(results.get('id', 'N/A'))]),
        dbc.ListGroupItem([html.Strong(f"{t('sa_description', lang)} "), html.Span(results.get('description', 'N/A'))]),
        dbc.ListGroupItem([html.Strong(f"{t('sa_analyzed_type', lang)} "), html.Span(results.get('type'))]),
        dbc.ListGroupItem([html.Strong(f"{t('sa_length', lang)} "), html.Span(f"{results.get('length')} {t('sa_length_unit', lang)}")]),
    ]

    if 'gc_content' in results:
        result_items.append(dbc.ListGroupItem([html.Strong(f"{t('sa_gc_content', lang)}: "), html.Span(results['gc_content'])]))

    if 'molecular_weight' in results:
        result_items.append(
            dbc.ListGroupItem([html.Strong(f"{t('sa_mol_weight', lang)} "), html.Span(results['molecular_weight'])]))

    output_card_body = [dbc.ListGroup(result_items, flush=True, className="mb-4")]

    if 'transcribed_rna' in results:
        output_card_body.extend([
            html.H6(t('sa_transcription', lang)),
            html.P(results['transcribed_rna'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'complement' in results:
        output_card_body.extend([
            html.H6(t('sa_complement', lang)),
            html.P(results['complement'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'reverse_complement' in results:
        output_card_body.extend([
            html.H6(t('sa_rev_complement', lang)),
            html.P(results['reverse_complement'], className="text-break font-monospace small bg-light p-2 rounded")
        ])

    if 'back_transcribed_dna' in results:
        output_card_body.extend([
            html.H6(t('sa_rev_transcription', lang)),
            html.P(results['back_transcribed_dna'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'protein_translation' in results:
        output_card_body.extend([
            html.H6(t('sa_translation', lang)),
            html.P(results['protein_translation'], className="text-break font-monospace small bg-light p-2 rounded")
        ])

    if 'amino_acid_percent' in results:
        aa_table_header = [html.Thead(html.Tr([html.Th(t('sa_amino_acid', lang)), html.Th(t('sa_percent', lang))]))]
        aa_table_body = [html.Tbody([
            html.Tr([html.Td(aa), html.Td(percent)]) for aa, percent in sorted(results['amino_acid_percent'].items())
        ])]
        aa_table = dbc.Table(aa_table_header + aa_table_body, bordered=True, striped=True, hover=True, size="sm")
        output_card_body.extend([
            html.H6(f"{t('sa_aa_dist', lang)}:", className="mt-4"),
            dbc.Row([dbc.Col(aa_table, md=6)])
        ])

    # Makaleye dönüştürme bölümü — sonuçların altında
    publish_section = html.Div([
        html.Hr(className="my-4"),
        dbc.Alert([
            html.H6([html.I(className="fas fa-file-medical-alt me-2"),
                     "Bu analizi akademik makaleye dönüştür"], className="mb-2"),
            html.P("Yapay zeka, bu sonuçları yorumlayıp ilgili literatürü (CrossRef) "
                   "tarayarak gerçek kaynaklı bir makale oluşturur.",
                   className="small text-muted mb-3"),
            dbc.Button([html.I(className="fas fa-magic me-2"), "Sonuçları Yayına Dönüştür"],
                       id="sa-publish-btn", color="primary", className="w-100"),
        ], color="light", className="border"),
        dcc.Loading(
            id="sa-publish-loading",
            children=html.Div(id="sa-publish-result", className="mt-3"),
            type="default",
        ),
    ])

    result_card = dbc.Card([
        dbc.CardHeader(html.H5(t('sa_results_title', lang))),
        dbc.CardBody(output_card_body + [publish_section])
    ])

    return result_card, results



@app.callback(
    Output("sa-publish-result", "children"),
    Input("sa-publish-btn", "n_clicks"),
    State("sa-bio-results-store", "data"),
    State("sa-lang-store", "data"),
    prevent_initial_call=True
)
def publish_bio_to_article(n_clicks, bio_results, lang, **kwargs):
    """
    Sekans analizi sonucunu akademik makaleye dönüştürür:
    1) AI sonucu yorumlar + konu üretir
    2) CrossRef'te o konuyla gerçek literatür toplanır (üretim içinde)
    3) Sonuç + literatür bağdaştırılıp makale yazılır ve kaydedilir
    4) "Makaleye Git" linki gösterilir
    """
    lang = lang or 'tr'
    if not n_clicks or not bio_results:
        return no_update

    # Kullanıcı kimliği (Dash request context'ten)
    from billing.dash_helpers import get_request_user
    try:
        user = get_request_user(kwargs)
    except Exception:
        user = None
    if user is None or not getattr(user, 'is_authenticated', False):
        return dbc.Alert("Makale oluşturmak için giriş yapmanız gerekiyor.", color="warning")

    # Kredi kontrolü (makale üretimi — superuser muaf)
    from billing.services import can_use, charge
    if not user.is_superuser:
        ok_credit, credit_msg = can_use(user, 'makale_uretim', default_cost=10)
        if not ok_credit:
            return dbc.Alert(credit_msg, color="danger")

    try:
        from dash_apps.generate import (generate_topic_from_bio_result,
                                         run_ai_generation_with_pool)
        from blog.models import GeneratedArticle, Category

        # 1) AI sonucu yorumla + konu üret
        topic, interpretation = generate_topic_from_bio_result(
            "Sekans Analizi", bio_results, lang=lang)

        # Bio bağlamı: yorum + ham sonuç özeti
        bio_context_lines = [f"Analiz türü: Sekans Analizi"]
        if interpretation:
            bio_context_lines.append(f"AI yorumu: {interpretation}")
        for k in ('type', 'length', 'gc_content', 'molecular_weight', 'id', 'description'):
            if k in bio_results:
                bio_context_lines.append(f"{k}: {bio_results[k]}")
        bio_context = "\n".join(bio_context_lines)

        # 2+3) CrossRef + makale üretimi (sonuç literatürle bağdaştırılır)
        ai_data, _used = run_ai_generation_with_pool(
            topic, word_count=1500, bio_context=bio_context)

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise TypeError("Yapay zekadan beklenen formatta yanıt alınamadı.")

        category_name = ai_data.get("category_name", "Biyoinformatik").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=category_name)

        new_article = GeneratedArticle.objects.create(
            owner=user,
            user_request=topic,
            title=ai_data.get("title"),
            category=category_obj,
            keywords=ai_data.get("keywords", ""),
            english_abstract=ai_data.get("english_abstract"),
            turkish_abstract=ai_data.get("turkish_abstract"),
            full_content=ai_data.get("content"),
            bibliography=ai_data.get("bibliography"),
            structured_data=ai_data.get("structured_data"),
            status='tamamlandi',
            is_published=bool(user.is_superuser),
        )

        # Makale başarılı → krediyi düş (superuser muaf)
        if not user.is_superuser:
            try:
                charge(user, 'makale_uretim', default_cost=10,
                       description=f"Bio-makale: {ai_data.get('title', '')[:50]}")
            except Exception:
                pass

        # 4) Başarı + Makaleye Git linki
        try:
            article_url = new_article.get_absolute_url()
        except Exception:
            article_url = f"/article/{new_article.id}/{new_article.slug}/"
        return dbc.Alert([
            html.H6([html.I(className="fas fa-check-circle me-2"),
                     "Makaleniz oluşturuldu!"], className="mb-2"),
            html.P(f"Başlık: {ai_data.get('title', '')}", className="small mb-3"),
            dbc.Button([html.I(className="fas fa-arrow-right me-2"), "Makaleye Git"],
                       href=article_url, external_link=True, color="success",
                       className="w-100"),
        ], color="success")

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Hatayı bildirim olarak kaydet (superuser admin'de görür)
        try:
            from blog.models import create_notification
            create_notification(
                category='makale_hatasi',
                title="Bio-makale üretim hatası (Sekans Analizi)",
                message=f"Konu: {topic if 'topic' in dir() else 'bilinmiyor'}",
                technical_detail=traceback.format_exc(),
                related_user=user if user and getattr(user, 'is_authenticated', False) else None,
            )
        except Exception:
            pass
        return dbc.Alert(
            "Sistem şu an yoğun, makale oluşturulamadı. Lütfen biraz sonra tekrar deneyin.",
            color="warning")


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


@app.callback(
    Output("sequence_analyzer", "active"),
    Input("url", "pathname")
)
def toggle_sequence_analyzer(pathname):
    return pathname == reverse('bio_tools:sequence_analyzer')