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
def parse_and_analyze_sequence(file_content, file_type, seq_type):
    """
    Verilen dosya içeriğini ve formatını kullanarak sekansı analiz eder.
    """
    if not file_content:
        return {"error": "Lütfen analiz için bir dosya yükleyin veya sekans girin."}

    try:
        string_io_file = io.StringIO(file_content)
        record = next(SeqIO.parse(string_io_file, file_type))
        sequence = str(record.seq).upper()
    except Exception as e:
        return {"error": f"Dosya okunurken bir hata oluştu: {e}. Lütfen dosya formatını doğru seçtiğinizden emin olun."}

    if not sequence:
        return {"error": "Dosya içinde geçerli bir sekans bulunamadı."}

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
                return {"error": "Protein sekansında 'U' (Urasil) bulunamaz."}
            protein_seq = ProteinAnalysis(sequence)
            results['type'] = 'Protein'
            results['molecular_weight'] = f"{protein_seq.molecular_weight():.2f} Da"
            aa_percent = protein_seq.get_amino_acids_percent()
            results['amino_acid_percent'] = {k: f"{v * 100:.2f}%" for k, v in aa_percent.items()}
    except Exception as e:
        return {"error": f"Analiz sırasında bir hata oluştu: {str(e)}"}

    return results


# --- Ön Yüz: Dash Layout Fonksiyonu (Dropdown Güncellendi) ---
def create_sequence_analyzer_layout():
    """Sekans Analiz Aracı sayfasının iki sütunlu ve dosya yüklemeli içeriğini oluşturur."""

    sidebar = dbc.Col(
        [
            html.H4("Kontrol Paneli"),
            html.Hr(),

            dbc.Label("Dosya Formatı:", html_for="file-type-input", className="fw-bold"),
            dcc.Dropdown(
                id='file-type-input',
                # --- DEĞİŞİKLİK BURADA ---
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

            dbc.Label("Sekans Tipi:", html_for="seq-type-input", className="fw-bold"),
            dcc.Dropdown(
                id='seq-type-input',
                options=[
                    {'label': 'DNA', 'value': 'dna'},
                    {'label': 'RNA', 'value': 'rna'},
                    {'label': 'Protein', 'value': 'protein'},
                ],
                value='dna',
                clearable=False,
                className="mb-3"
            ),

            dcc.Upload(
                id='upload-sequence-file',
                children=html.Div(['Sürükleyip Bırakın veya ', html.A('Dosya Seçin')]),
                style={
                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                    'borderWidth': '1px', 'borderStyle': 'dashed',
                    'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'
                },
            ),

            dbc.Label("Sekans Verisi (veya dosyadan okunan içerik):", html_for="sequence-input", className="fw-bold"),
            dcc.Textarea(
                id="sequence-input",
                placeholder="Dosya yükleyin veya sekansı buraya yapıştırın...",
                style={'width': '100%', 'height': 200},
                className="form-control mb-3 font-monospace"
            ),
            dbc.Button([html.I(className="fas fa-cogs me-2"), "Analiz Et"], id="analyze-button", color="primary",
                       className="w-100"),
        ],
        md=4,
        className="bg-light p-4 border-end"
    )

    content = dbc.Col(
        [
            html.H4("Analiz Sonuçları"),
            html.Hr(),
            dcc.Loading(
                id="loading-results",
                children=html.Div(id="analysis-results-container",
                                  children=html.P("Lütfen soldaki menüden bir sekans girip analizi başlatın."))
            )
        ],
        md=8,
        className="p-4",
        style={"height": "100vh", "overflowY": "auto"}
    )

    return dbc.Container([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='sequence-file-store'),
        html.H2("Sekans Analiz Aracı", className="mt-4"),
        html.P("DNA, RNA veya Protein sekansınızı dosya yükleyerek veya yapıştırarak analiz edin.",
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
    Input("analyze-button", "n_clicks"),
    State("sequence-input", "value"),
    State("file-type-input", "value"),
    State("seq-type-input", "value"),
    prevent_initial_call=True
)
def update_analysis_results(n_clicks, sequence_content, file_type, seq_type):
    if not sequence_content:
        return dbc.Alert("Lütfen analiz etmek için bir dosya yükleyin veya sekans girin.", color="warning")

    results = parse_and_analyze_sequence(sequence_content, file_type, seq_type)

    if "error" in results:
        return dbc.Alert(results["error"], color="danger")

    result_items = [
        dbc.ListGroupItem([html.Strong("Dosya ID: "), html.Span(results.get('id', 'N/A'))]),
        dbc.ListGroupItem([html.Strong("Açıklama: "), html.Span(results.get('description', 'N/A'))]),
        dbc.ListGroupItem([html.Strong("Analiz Edilen Sekans Tipi: "), html.Span(results.get('type'))]),
        dbc.ListGroupItem([html.Strong("Uzunluk: "), html.Span(f"{results.get('length')} baz/amino asit")]),
    ]

    if 'gc_content' in results:
        result_items.append(dbc.ListGroupItem([html.Strong("GC Oranı: "), html.Span(results['gc_content'])]))

    if 'molecular_weight' in results:
        result_items.append(
            dbc.ListGroupItem([html.Strong("Moleküler Ağırlık: "), html.Span(results['molecular_weight'])]))

    output_card_body = [dbc.ListGroup(result_items, flush=True, className="mb-4")]

    if 'transcribed_rna' in results:
        output_card_body.extend([
            html.H6("Transkripsiyon (DNA -> RNA):"),
            html.P(results['transcribed_rna'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'complement' in results:
        output_card_body.extend([
            html.H6("Tamamlayıcı (Complement) DNA:"),
            html.P(results['complement'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'reverse_complement' in results:
        output_card_body.extend([
            html.H6("Ters-Tamamlayıcı (Reverse Complement) DNA:"),
            html.P(results['reverse_complement'], className="text-break font-monospace small bg-light p-2 rounded")
        ])

    if 'back_transcribed_dna' in results:
        output_card_body.extend([
            html.H6("Ters Transkripsiyon (RNA -> DNA):"),
            html.P(results['back_transcribed_dna'], className="text-break font-monospace small bg-light p-2 rounded")
        ])
    if 'protein_translation' in results:
        output_card_body.extend([
            html.H6("Translasyon (RNA -> Protein):"),
            html.P(results['protein_translation'], className="text-break font-monospace small bg-light p-2 rounded")
        ])

    if 'amino_acid_percent' in results:
        aa_table_header = [html.Thead(html.Tr([html.Th("Amino Asit"), html.Th("Yüzde")]))]
        aa_table_body = [html.Tbody([
            html.Tr([html.Td(aa), html.Td(percent)]) for aa, percent in sorted(results['amino_acid_percent'].items())
        ])]
        aa_table = dbc.Table(aa_table_header + aa_table_body, bordered=True, striped=True, hover=True, size="sm")
        output_card_body.extend([
            html.H6("Amino Asit Yüzdeleri:", className="mt-4"),
            dbc.Row([dbc.Col(aa_table, md=6)])
        ])

    return dbc.Card([
        dbc.CardHeader(html.H5("Analiz Sonuçları")),
        dbc.CardBody(output_card_body)
    ])



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