# -*- coding: utf-8 -*-
import os
import re
import pandas as pd

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import dash_bio

# Django Entegrasyonu
from django_plotly_dash import DjangoDash
from django.shortcuts import reverse

# --- UYGULAMA BAŞLATMA ---
app = DjangoDash(
    name='BacterialDesignerApp',
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    external_scripts=["https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"]
)

# ==============================================================================
# SABİTLER VE YAPILANDIRMA
# ==============================================================================
DESIGN_MODEL_NAME = 'gemini-2.5-pro'
SEQUENCE_MODEL_NAME = 'gemini-2.5-pro'



# ==============================================================================
# YARDIMCI PROMPT VE PARSING FONKSİYONLARI
# ==============================================================================
def generate_design_prompt(target_organism, design_goals):
    return f"""Sen, sentetik biyoloji uzmanı bir yapay zeka asistanısın.\n**Görev:** '{target_organism}' için şu gereksinimlere göre bir genetik devre taslağı oluştur: {design_goals}.\n**Kurallar:** Cevabında HİÇBİR AÇIKLAMA METNİ OLMADAN, doğrudan sadece 2 bölüm ver:\n1. MermaidJS Grafiği\n2. Kritik Genler Tablosu (Sütunlar: Gen Adı, Fonksiyon, Kaynak Organizma)."""


def generate_sequence_design_prompt(gene_name, organism):
    return f"""Sen, moleküler biyoloji ve gen dizilimi tasarımı konusunda uzman bir yapay zeka asistanısın.\n**Görev:** '{organism}' organizmasında bulunabilecek '{gene_name}' geni için biyolojik olarak mantıklı, varsayımsal bir protein dizilimi ve bu proteini kodlayan bir DNA dizilimi (CDS) tasarla.\n**Kurallar:** Protein dizilimi 300-450 amino asit, DNA dizilimi standart start/stop kodonları içermeli. Cevap sadece 2 FASTA bloğu olmalı.\n**Çıktı Formatı:**\n```fasta\n>protein|{gene_name}\n[PROTEIN DIZILIMI]\n```\n```fasta\n>nucleotide|{gene_name}\n[DNA DIZILIMI]\n```"""


def parse_ai_response_for_design(markdown_text):
    mermaid_graph = ""
    mermaid_match = re.search(r"```mermaid\n(.*?)\n```", markdown_text, re.DOTALL)
    if mermaid_match: mermaid_graph = mermaid_match.group(0)
    gene_df = None
    table_match = re.search(r"\|.*Gen Adı.*\|\n\|.*-.*\|\n((?:\|.*\|\n?)*)", markdown_text, re.MULTILINE)
    if table_match:
        table_str = table_match.group(0)
        header = [h.strip() for h in table_str.split('\n')[0].strip('|').split('|')]
        rows = [row.strip().split('|')[1:-1] for row in table_match.group(1).strip().split('\n')]
        if rows and len(rows[0]) == len(header): gene_df = pd.DataFrame(rows, columns=header)
    return mermaid_graph, gene_df


def parse_ai_fasta_sequence(ai_response_text):
    protein_fasta, nucleotide_fasta = ">protein|parse_error\n", ">nucleotide|parse_error\n"
    protein_match = re.search(r"```fasta\s*>protein.*?```", ai_response_text, re.DOTALL)
    if protein_match: protein_fasta = protein_match.group(0).replace("```fasta", "").replace("```", "").strip()
    nucleotide_match = re.search(r"```fasta\s*>nucleotide.*?```", ai_response_text, re.DOTALL)
    if nucleotide_match: nucleotide_fasta = nucleotide_match.group(0).replace("```fasta", "").replace("```", "").strip()
    return protein_fasta, nucleotide_fasta


def combine_sequences_to_fasta(sequence_data, seq_type):
    """Belirtilen türdeki (protein/nucleotide) tüm sekansları tek bir FASTA metninde birleştirir."""
    fasta_list = [data[seq_type] for data in sequence_data.values() if
                  data.get(seq_type) and f'>{seq_type}' in data[seq_type]]
    return "\n".join(fasta_list)


# ==============================================================================
# LAYOUT
# ==============================================================================
def get_about_text():
    return dcc.Markdown(
        """**Sentetik Biyoloji Bakteri Tasarım Asistanı'na Hoş Geldiniz!**\n\nBu araç, Google Gemini yapay zeka modelini kullanarak sentetik biyoloji iş akışınızı hızlandırmak için tasarlanmıştır.\n\n**Nasıl Çalışır?**\n1. **Tasarım Girişi:** Hedef organizma ve tasarım amacınızı girin.\n2. **AI Destekli Sonuçlar:** Yapay zeka, bir genetik devre şeması, kritik genler listesi ve bu genler için varsayımsal sekanslar üretir.\n3. **Analiz:** Üretilen sekansları toplu olarak indirebilir veya **Sekans Hizalama (MSA)** sekmesinde karşılaştırabilirsiniz.""")


def bacterial_create_layout():
    control_panel = dbc.Card(dbc.CardBody(dbc.Tabs(id="control-tabs", active_tab="tab-input", children=[
        dbc.Tab(label="Hakkında", tab_id="tab-about", children=html.Div(get_about_text(), className="p-3")),
        dbc.Tab(label="Tasarım Girişi", tab_id="tab-input", children=html.Div(className="p-3", children=[
            dbc.Label("Hedef Organizma:", className="fw-bold mt-3"),
            dbc.Input(id="target-organism-input", value="Escherichia coli", type="text"),
            dbc.Label("Tasarım Gereksinimleri:", className="fw-bold mt-3"),
            dcc.Textarea(id='design-goals-input', placeholder="Örn: Çevresel strese dayanıklı likopen üreten devre...",
                         style={'width': '100%', 'height': 150}),
            html.Hr(),
            dbc.Button("Tasarımı ve Sekansları Oluştur", id="btn-generate-design", color="primary", className="w-100"),
        ])),
    ])))

    result_panel = dbc.Card([
        dbc.CardHeader("Sonuçlar"),
        dbc.CardBody(dcc.Loading(id="loading-results-spinner",
                                 children=dbc.Tabs(id="results-tabs", active_tab="tab-design", children=[
                                     dbc.Tab(label="Tasarım ve Sekanslar", tab_id="tab-design",
                                             children=html.Div(id="design-and-sequence-output", className="p-3",
                                                               children=html.P(
                                                                   "Başlamak için bilgileri girip butona tıklayın.",
                                                                   className="text-muted"))),
                                     dbc.Tab(label="Sekans Hizalama (MSA)", tab_id="tab-msa", id="tab-msa-component",
                                             disabled=True, children=html.Div(className="p-3", children=[
                                             dcc.Dropdown(id='msa-sequence-type-select',
                                                          options=[{'label': 'Protein Sekansları', 'value': 'protein'},
                                                                   {'label': 'Nükleotit Sekansları',
                                                                    'value': 'nucleotide'}], value='protein',
                                                          clearable=False, className="mb-3"),
                                             html.Div(id="alignment-chart-container")
                                         ])),
                                 ])))
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False), html.H2("Bakteri Tasarım"), html.Hr(),
        dcc.Store(id='sequence-data-store'),
        dcc.Download(id='download-fasta'),
        dcc.Store(id='protein-clicks-store', data=0),
        dcc.Store(id='nucleotide-clicks-store', data=0),
        dbc.Row([dbc.Col(control_panel, width=12, lg=4), dbc.Col(result_panel, width=12, lg=8)])
    ])


app.layout = bacterial_create_layout()


# ==============================================================================
# ANA CALLBACK'LER
# ==============================================================================
@app.callback(
    Output('design-and-sequence-output', 'children'),
    Output('sequence-data-store', 'data'),
    Output('tab-msa-component', 'disabled'),
    Output('results-tabs', 'active_tab'),
    Input('btn-generate-design', 'n_clicks'),
    State('design-goals-input', 'value'),
    State('target-organism-input', 'value'),
    prevent_initial_call=True
)
def handle_design_and_sequence_generation(n_clicks, design_goals, target_organism, **kwargs):
    if not design_goals or not target_organism:
        return dbc.Alert("Lütfen tüm alanları doldurun.", color="warning"), dash.no_update, True, 'tab-design'

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_bacterial_designer', cost=5,
                             description="Bakteri tasarımı")
    if not ok:
        return msg, dash.no_update, True, 'tab-design'

    try:
        from ai_engine.services import generate_with_pool
        design_text, _key = generate_with_pool(
            generate_design_prompt(target_organism, design_goals),
            service_name='Google Gemini', model_name='gemini-2.5-flash')
        mermaid_graph, gene_df = parse_ai_response_for_design(design_text)
    except Exception as e:
        return dbc.Alert(f"Tasarım oluşturulurken hata: {e}", color="danger"), None, True, 'tab-design'

    output_components = [html.H4("Genetik Devre Şeması"), dcc.Markdown(mermaid_graph)] if mermaid_graph else [
        dbc.Alert("Devre şeması oluşturulamadı.", color="warning")]
    if gene_df is None or gene_df.empty:
        output_components.append(dbc.Alert("Kritik genler bulunamadı.", color="info"))
        return output_components, None, True, 'tab-design'

    sequences_to_store = {}
    for index, row in gene_df.iterrows():
        try:
            gene_name, organism = row['Gen Adı'].strip(), row['Kaynak Organizma'].strip()
            if not gene_name or not organism: continue
        except KeyError:
            continue
        try:
            seq_text, _key = generate_with_pool(
                generate_sequence_design_prompt(gene_name, organism),
                service_name='Google Gemini', model_name='gemini-2.5-flash')
            protein_fasta, nucleotide_fasta = parse_ai_fasta_sequence(seq_text)
        except Exception as e:
            protein_fasta, nucleotide_fasta = f">protein|error|{gene_name}\n{e}", f">nucleotide|error|{gene_name}"
        sequences_to_store[gene_name] = {'protein': protein_fasta, 'nucleotide': nucleotide_fasta}

    if sequences_to_store:
        output_components.extend([
            html.Hr(), html.H4("Oluşturulan Sekansları İndir"),
            html.P("Tüm genler için üretilen sekansları FASTA formatında indirin."),
            dbc.Row([
                dbc.Col(dbc.Button("Protein Sekanslarını İndir (.fasta)", id="btn-download-protein", color="primary",
                                   outline=True, className="w-100"), width=6),
                dbc.Col(dbc.Button("Nükleotit Sekanslarını İndir (.fasta)", id="btn-download-nucleotide", color="info",
                                   outline=True, className="w-100"), width=6),
            ])
        ])

    msa_tab_disabled = not bool(sequences_to_store)
    return output_components, sequences_to_store, msa_tab_disabled, 'tab-design'


@app.callback(
    Output('download-fasta', 'data'),
    Output('protein-clicks-store', 'data'),
    Output('nucleotide-clicks-store', 'data'),
    Input('btn-download-protein', 'n_clicks'),
    Input('btn-download-nucleotide', 'n_clicks'),
    State('sequence-data-store', 'data'),
    State('protein-clicks-store', 'data'),
    State('nucleotide-clicks-store', 'data'),
    prevent_initial_call=True
)
def download_sequences(protein_clicks, nucleotide_clicks, stored_sequences, prev_protein_clicks,
                       prev_nucleotide_clicks):
    protein_clicks = protein_clicks or 0
    nucleotide_clicks = nucleotide_clicks or 0

    if not stored_sequences:
        raise dash.exceptions.PreventUpdate

    if protein_clicks > prev_protein_clicks:
        fasta_content = combine_sequences_to_fasta(stored_sequences, 'protein')
        return dcc.send_string(fasta_content, "protein_sequences.fasta"), protein_clicks, nucleotide_clicks
    elif nucleotide_clicks > prev_nucleotide_clicks:
        fasta_content = combine_sequences_to_fasta(stored_sequences, 'nucleotide')
        return dcc.send_string(fasta_content, "nucleotide_sequences.fasta"), protein_clicks, nucleotide_clicks
    else:
        raise dash.exceptions.PreventUpdate


@app.callback(
    Output('alignment-chart-container', 'children'),
    Input('sequence-data-store', 'data'),
    Input('msa-sequence-type-select', 'value'),
    prevent_initial_call=True
)
def update_alignment_chart(stored_sequences, seq_type):
    if not stored_sequences: return dbc.Alert("Hizalama için veri yok.", color="info")

    sequences = [data.get(seq_type) for data in stored_sequences.values() if
                 data.get(seq_type) and f'>{seq_type}' in data.get(seq_type)]
    if len(sequences) < 2: return dbc.Alert(f"MSA için en az 2 adet {seq_type} sekansı gereklidir.", color="warning")

    msa_data = combine_sequences_to_fasta(stored_sequences, seq_type)
    return dash_bio.AlignmentChart(id='my-alignment-viewer', data=msa_data, colorscale='clustal2', height=800,
                                   width=1000)


# ==============================================================================
# NAVBAR CALLBACK'LERİ
# ==============================================================================
@app.callback(Output("navbar-collapse", "is_open"), [Input("navbar-toggler", "n_clicks")],
              [State("navbar-collapse", "is_open")])
def toggle_navbar_collapse(n, is_open):
    if n: return not is_open
    return is_open


@app.callback(Output("bacterial_designer", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    try:
        return pathname == reverse('bio_tools:bacterial_designer')
    except:
        return False