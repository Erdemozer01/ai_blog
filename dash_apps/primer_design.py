"""
Primer Tasarım Aracı (Primer3 tabanlı, lab standardı).

Özellikler:
  - DNA dizisi yapıştırma ile primer tasarımı
  - Gen adı/accession ile EBI ENA'dan dizi çekme (yedek)
  - Forward/Reverse primer çiftleri: dizi, Tm, GC%, ürün boyu
  - Opsiyonel AI yorumu (ai_engine havuzu, 5 kredi)
"""
import re
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, dash_table, Input, Output, State

app = DjangoDash('PrimerDesignApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True)


# ----------------------------- Çekirdek mantık -----------------------------

def clean_sequence(sequence):
    """Diziden ATGC dışındaki karakterleri temizler (FASTA başlığı, boşluk, sayı)."""
    lines = [ln for ln in sequence.splitlines() if not ln.strip().startswith('>')]
    joined = ''.join(lines)
    return re.sub(r'[^ATGCatgc]', '', joined).upper()


def design_primers_core(sequence, product_min=100, product_max=300, num_return=5):
    """Primer3 ile primer çiftleri tasarlar. Hata durumunda {'error': ...} döner."""
    import primer3
    seq = clean_sequence(sequence)
    if len(seq) < 50:
        return {'error': 'Dizi çok kısa. En az 50 baz gerekli.'}
    if len(seq) > 10000:
        return {'error': 'Dizi çok uzun (maks. 10.000 baz). Daha kısa bir bölge seçin.'}
    try:
        res = primer3.design_primers(
            {'SEQUENCE_ID': 'user_seq', 'SEQUENCE_TEMPLATE': seq},
            {
                'PRIMER_NUM_RETURN': num_return,
                'PRIMER_OPT_SIZE': 20, 'PRIMER_MIN_SIZE': 18, 'PRIMER_MAX_SIZE': 25,
                'PRIMER_OPT_TM': 60.0, 'PRIMER_MIN_TM': 57.0, 'PRIMER_MAX_TM': 63.0,
                'PRIMER_MIN_GC': 40.0, 'PRIMER_MAX_GC': 60.0,
                'PRIMER_PRODUCT_SIZE_RANGE': [[product_min, product_max]],
            }
        )
    except Exception as e:
        return {'error': f'Primer tasarım hatası: {e}'}

    n = res.get('PRIMER_PAIR_NUM_RETURNED', 0)
    if n == 0:
        return {'error': 'Uygun primer bulunamadı. Ürün boyu aralığını genişletmeyi deneyin.'}

    pairs = []
    for i in range(n):
        pairs.append({
            'No': i + 1,
            'Forward (5→3)': res[f'PRIMER_LEFT_{i}_SEQUENCE'],
            'Forward Tm': round(res[f'PRIMER_LEFT_{i}_TM'], 1),
            'Forward GC%': round(res[f'PRIMER_LEFT_{i}_GC_PERCENT'], 1),
            'Reverse (5→3)': res[f'PRIMER_RIGHT_{i}_SEQUENCE'],
            'Reverse Tm': round(res[f'PRIMER_RIGHT_{i}_TM'], 1),
            'Reverse GC%': round(res[f'PRIMER_RIGHT_{i}_GC_PERCENT'], 1),
            'Ürün (bp)': res[f'PRIMER_PAIR_{i}_PRODUCT_SIZE'],
        })
    return {'pairs': pairs, 'seq_length': len(seq)}


def fetch_sequence_from_ebi(accession):
    """
    EBI ENA'dan accession/gen ID ile nükleotid dizisi çeker (FASTA).
    PythonAnywhere whitelist'inde .ebi.ac.uk var. Başarısızsa None döner.
    """
    import urllib.request
    acc = accession.strip()
    if not acc:
        return None, "Accession boş."
    url = f"https://www.ebi.ac.uk/ena/browser/api/fasta/{acc}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AIBlog-PrimerTool'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read().decode('utf-8', errors='ignore')
        seq = clean_sequence(data)
        if len(seq) < 50:
            return None, f"'{acc}' için yeterli dizi bulunamadı."
        return seq, None
    except Exception as e:
        return None, f"Dizi çekilemedi ({acc}): {e}. Lütfen diziyi elle yapıştırın."


# ----------------------------- Layout -----------------------------

def create_primer_layout():
    return dbc.Container([
        html.H2([html.I(className="fas fa-dna me-2"), "Primer Tasarım Aracı"],
                className="my-4"),
        html.P("PCR primer tasarımı (Primer3 motoru). DNA dizinizi yapıştırın "
               "veya gen accession numarası girin.", className="text-muted"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Giriş"),
                    dbc.CardBody([
                        dbc.Label("DNA Dizisi (yapıştır)"),
                        dbc.Textarea(id="primer-seq-input", rows=6,
                                     placeholder="5'-ATGC... dizinizi buraya yapıştırın "
                                                 "(FASTA da olur)",
                                     className="mb-2", style={'fontFamily': 'monospace'}),

                        html.Div("— veya —", className="text-center text-muted my-2"),

                        dbc.Label("Gen Accession / ID (EBI ENA)"),
                        dbc.InputGroup([
                            dbc.Input(id="primer-acc-input",
                                      placeholder="örn: BC003596, NM_000546"),
                            dbc.Button("Diziyi Çek", id="primer-fetch-btn",
                                       color="secondary", n_clicks=0),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Ürün boyu (min)"),
                                dbc.Input(id="primer-prod-min", type="number",
                                          value=100, min=50, max=2000),
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Ürün boyu (max)"),
                                dbc.Input(id="primer-prod-max", type="number",
                                          value=300, min=60, max=3000),
                            ], width=6),
                        ], className="mb-3"),

                        dbc.Button([html.I(className="fas fa-cogs me-2"), "Primer Tasarla"],
                                   id="primer-design-btn", color="primary",
                                   className="w-100", n_clicks=0),
                    ]),
                ], className="shadow-sm mb-3"),
            ], md=4),

            dbc.Col([
                dcc.Loading(html.Div(id="primer-fetch-status", className="mb-2")),
                dcc.Loading(html.Div(id="primer-results")),
                html.Div(id="primer-ai-section", className="mt-3"),
                html.Div(id="primer-ai-result", className="mt-3"),
                dcc.Store(id="primer-seq-store"),
                dcc.Store(id="primer-results-store"),
            ], md=8),
        ]),
    ], fluid=True, className="pb-5")


# ----------------------------- Callbacks -----------------------------

@app.callback(
    [Output("primer-seq-input", "value"),
     Output("primer-fetch-status", "children")],
    Input("primer-fetch-btn", "n_clicks"),
    State("primer-acc-input", "value"),
    prevent_initial_call=True,
)
def fetch_sequence(n_clicks, accession):
    if not accession:
        return "", dbc.Alert("Lütfen bir accession/ID girin.", color="warning")
    seq, err = fetch_sequence_from_ebi(accession)
    if err:
        return "", dbc.Alert(err, color="danger")
    return seq, dbc.Alert(f"✓ Dizi çekildi ({len(seq)} baz). Şimdi 'Primer Tasarla'ya basın.",
                          color="success")


@app.callback(
    [Output("primer-results", "children"),
     Output("primer-results-store", "data"),
     Output("primer-seq-store", "data"),
     Output("primer-ai-section", "children"),
     Output("primer-ai-result", "children")],
    Input("primer-design-btn", "n_clicks"),
    [State("primer-seq-input", "value"),
     State("primer-prod-min", "value"),
     State("primer-prod-max", "value")],
    prevent_initial_call=True,
)
def run_design(n_clicks, sequence, pmin, pmax):
    if not sequence:
        return dbc.Alert("Lütfen bir DNA dizisi girin veya çekin.", color="warning"), None, None, "", ""

    result = design_primers_core(sequence, product_min=int(pmin or 100),
                                 product_max=int(pmax or 300))
    if 'error' in result:
        return dbc.Alert(result['error'], color="danger"), None, None, "", ""

    pairs = result['pairs']
    table = dash_table.DataTable(
        data=pairs,
        columns=[{'name': k, 'id': k} for k in pairs[0].keys()],
        style_cell={'fontFamily': 'monospace', 'fontSize': '13px',
                    'textAlign': 'center', 'padding': '6px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
        style_table={'overflowX': 'auto'},
    )

    results_card = dbc.Card([
        dbc.CardHeader([html.I(className="fas fa-check-circle text-success me-2"),
                        f"{len(pairs)} primer çifti bulundu "
                        f"(dizi: {result['seq_length']} baz)"]),
        dbc.CardBody(table),
    ], className="shadow-sm")

    ai_button = dbc.Card(dbc.CardBody([
        html.P("Primer sonuçlarını yapay zeka ile yorumlatmak ister misiniz? "
               "(spesifiklik, dimer riski, öneriler)", className="mb-2 text-muted"),
        dbc.Button([html.I(className="fas fa-robot me-2"),
                    "AI ile Yorumla (5 kredi)"],
                   id="primer-ai-btn", color="info", outline=True, n_clicks=0),
    ]), className="shadow-sm")

    return results_card, pairs, clean_sequence(sequence), ai_button, ""


@app.callback(
    Output("primer-ai-result", "children"),
    Input("primer-ai-btn", "n_clicks"),
    [State("primer-results-store", "data"),
     State("primer-seq-store", "data")],
    prevent_initial_call=True,
)
def ai_comment(n_clicks, pairs, seq):
    if not n_clicks or not pairs:
        return ""
    summary_lines = []
    for p in pairs[:3]:
        summary_lines.append(
            f"Çift {p['No']}: F={p['Forward (5→3)']} (Tm {p['Forward Tm']}, "
            f"GC {p['Forward GC%']}%), R={p['Reverse (5→3)']} "
            f"(Tm {p['Reverse Tm']}, GC {p['Reverse GC%']}%), ürün {p['Ürün (bp)']} bp")
    summary = "\n".join(summary_lines)

    prompt = (
        "Aşağıda PCR primer tasarım sonuçları var. Bir moleküler biyolog gözüyle "
        "kısa ve pratik bir değerlendirme yap (Türkçe): primerlerin Tm uyumu, GC içeriği, "
        "olası primer-dimer/hairpin riski ve laboratuvarda dikkat edilmesi gerekenler. "
        "Maddeler halinde, öz ve net ol.\n\n"
        f"Primer çiftleri:\n{summary}\n\n"
        f"Hedef dizi uzunluğu: {len(seq)} baz."
    )

    try:
        from ai_engine.services import generate_with_pool
        text, _key = generate_with_pool(
            prompt, service_name="Google Gemini", model_name="gemini-2.5-flash",
            max_tokens=800, temperature=0.4)
    except Exception as e:
        return dbc.Alert(f"AI yorumu alınamadı: {e}", color="warning")

    return dbc.Card([
        dbc.CardHeader([html.I(className="fas fa-robot me-2"), "AI Değerlendirmesi"]),
        dbc.CardBody(dcc.Markdown(text)),
    ], className="shadow-sm")


app.layout = html.Div()