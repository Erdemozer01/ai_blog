# -*- coding: utf-8 -*-
import base64
import io
import os
import shlex
import json
import zlib
from io import StringIO

import dash
import dash_bio
import requests
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, dash_table, no_update, clientside_callback, ClientsideFunction
from dash.exceptions import PreventUpdate
from django_plotly_dash import DjangoDash

# Biyoinformatik ve AI kütüphaneleri
from Bio.PDB import PDBParser, Superimposer, PDBIO


from django.shortcuts import reverse
from billing.dash_helpers import build_confirm_modal


# === Django modelini içe aktar ===

# --- UYGULAMA BAŞLATMA VE SABİTLER ---
app = DjangoDash(
    name='MoleculeViewerApp',
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
)


# --- API ANAHTARI: ai_engine.services üzerinden havuz/fallback ile kullanılır ---

# --- SABİTLER ---
REPRESENTATIONS = ['axes', 'axes+box', 'backbone', 'ball+stick', 'cartoon', 'helixorient',
                   'hyperball', 'licorice', 'line', 'ribbon', 'rope', 'spacefill',
                   'surface', 'trace', 'tube', 'unitcell']

COLORS = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00',
          '#ffff33', '#a65628', '#f781bf', '#999999']

DATA_PLACEHOLDER = {
    'filename': 'placeholder', 'ext': '', 'selectedValue': 'placeholder', 'chain': 'ALL',
    'aaRange': 'ALL', 'color': '#e41a1c', 'config': {'type': '', 'input': ''},
    'resetView': False, 'chosen': {'atoms': '', 'residues': ''}
}
COMPONENT_ID = 'ngl-molecule-viewer'


# --- YARDIMCI FONKSİYONLAR ---
def fetch_pdb_from_rcsb(pdb_id):
    pdb_id = pdb_id.upper()
    if len(pdb_id) != 4:
        return None, "Geçersiz PDB ID formatı."
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text, None
    except requests.exceptions.RequestException as e:
        return None, f"RCSB'den veri çekilemedi: {e}"


def extract_info_from_content(content, ext, info_type='pdb_id'):
    if not content: return "N/A"
    lines = content.splitlines()
    try:
        if ext.lower() == 'pdb':
            if info_type == 'pdb_id':
                for line in lines:
                    if line.startswith('HEADER'): return line[62:66].strip()
            elif info_type == 'protein_name':
                compound_lines = [line[10:].strip() for line in lines if line.startswith('COMPND')]
                full = ' '.join(compound_lines)
                if 'MOLECULE:' in full: return full.split('MOLECULE:')[1].split(';')[0].strip()
            elif info_type == 'organism':
                for line in lines:
                    if 'ORGANISM_SCIENTIFIC' in line: return line.split('ORGANISM_SCIENTIFIC:')[1].replace(';',
                                                                                                           '').strip()
    except Exception:
        return "N/A"
    return "N/A"


def create_ngl_dict(filename, ext, selectedValue, content, color, resetView=False):
    return {
        'filename': filename, 'ext': ext, 'selectedValue': selectedValue, 'chain': 'ALL',
        'aaRange': 'ALL', 'color': color, 'config': {'type': 'text/plain', 'input': content},
        'resetView': resetView, 'chosen': {'atoms': '', 'residues': ''}
    }


def get_uploaded_data(contents, filenames, colors):
    if not contents: return [], []
    data_list, messages = [], []
    for i, (content_str, filename) in enumerate(zip(contents, filenames)):
        try:
            _content_type, content_string = content_str.split(',', 1)
            decoded = base64.b64decode(content_string)
            file_content = zlib.decompress(decoded, 16 + zlib.MAX_WBITS).decode('utf-8',
                                                                                'ignore') if filename.lower().endswith(
                '.gz') else decoded.decode('utf-8', 'ignore')
            ext = 'cif' if filename.lower().endswith('.cif') or (
                    'loop_' in file_content and '_atom_site.id' in file_content) else 'pdb'
            pdb_id = extract_info_from_content(file_content, ext, 'pdb_id')
            if pdb_id == "N/A": pdb_id = os.path.splitext(filename)[0]
            data_list.append(create_ngl_dict(filename, ext, pdb_id, file_content, colors[i % len(colors)], True))
            messages.append(dbc.Alert(f"'{filename}' başarıyla yüklendi.", color="success", duration=3000))
        except Exception as e:
            messages.append(dbc.Alert(f"'{filename}' yüklenemedi: {e}", color="danger", duration=5000))
    return data_list, messages


def parse_pdb_for_table(pdb_content):
    if not pdb_content: return []
    atom_lines = [line for line in pdb_content.split('\n') if line.startswith(('ATOM', 'HETATM'))]
    records = []
    for line in atom_lines:
        try:
            records.append({
                'atom_type': line[0:6].strip(), 'atom_no': int(line[6:11].strip()),
                'atom_name': line[12:16].strip(), 'residue_name': line[17:20].strip(),
                'chain': line[21:22].strip(), 'residue_no': int(line[22:26].strip()),
                'x': float(line[30:38].strip()), 'y': float(line[38:46].strip()),
                'z': float(line[46:54].strip()), 'element': line[76:78].strip()
            })
        except (ValueError, IndexError):
            continue
    return records


def parse_cif_for_table(cif_content):
    if not cif_content: return []
    lines, records, atom_site_headers, in_atom_site_loop = cif_content.split('\n'), [], [], False
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if clean_line.startswith('_atom_site.'):
            if i > 0 and lines[i - 1].strip() == 'loop_': in_atom_site_loop = True
            if in_atom_site_loop: atom_site_headers.append(clean_line)
        elif in_atom_site_loop and not clean_line.startswith('_'):
            break
    if not in_atom_site_loop or not atom_site_headers: return []
    key_map = {'_atom_site.group_PDB': 'atom_type', '_atom_site.id': 'atom_no', '_atom_site.label_atom_id': 'atom_name',
               '_atom_site.label_comp_id': 'residue_name', '_atom_site.auth_asym_id': 'chain',
               '_atom_site.auth_seq_id': 'residue_no', '_atom_site.Cartn_x': 'x', '_atom_site.Cartn_y': 'y',
               '_atom_site.Cartn_z': 'z', '_atom_site.type_symbol': 'element'}
    header_indices = {key_map[h]: i for i, h in enumerate(atom_site_headers) if h in key_map}
    data_started = False
    for line in lines:
        clean_line = line.strip()
        if not in_atom_site_loop: continue
        if not data_started and len(clean_line.split()) >= len(atom_site_headers): data_started = True
        if not data_started or not clean_line or clean_line.startswith(('_', '#', ';', 'loop_')): continue
        try:
            parts = shlex.split(clean_line)
            if len(parts) < len(atom_site_headers): continue

            def get_part(key, default_val):
                index = header_indices.get(key)
                return parts[index] if index is not None and index < len(parts) and parts[index] not in ['.',
                                                                                                         '?'] else default_val

            records.append({'atom_type': get_part('atom_type', 'ATOM'), 'atom_no': int(get_part('atom_no', 0)),
                            'atom_name': get_part('atom_name', 'N/A'), 'residue_name': get_part('residue_name', 'UNK'),
                            'chain': get_part('chain', 'A'), 'residue_no': int(get_part('residue_no', 0)),
                            'x': float(get_part('x', 0.0)), 'y': float(get_part('y', 0.0)),
                            'z': float(get_part('z', 0.0)), 'element': get_part('element', '')})
        except (ValueError, IndexError):
            continue
    return records


def get_ai_report(protein_name, organism, lang='en'):
    from dash_apps.i18n_helper import t, credit_label
    if not protein_name or protein_name == "N/A":
        return None, t('mv_no_protein', lang)
    if lang == 'tr':
        prompt = (
            f"Lütfen '{protein_name}' ({organism}) proteini hakkında bilinen biyolojik fonksiyonlarını, "
            f"hücresel konumunu ve varsa önemli mutasyonlarını özetleyen, tamamen Türkçe ve bilimsel bir "
            f"rapor oluştur. Cevabını Markdown formatında, başlıklar kullanarak düzenle.")
    else:
        prompt = (
            f"Please create a scientific report in English about the protein '{protein_name}' ({organism}), "
            f"summarizing its known biological functions, cellular localization and important mutations if any. "
            f"Format your answer in Markdown using headings.")
    try:
        from ai_engine.services import generate_with_pool
        text, _key = generate_with_pool(prompt, service_name="Google Gemini", model_name="gemini-2.5-flash")
        return dcc.Markdown(text), None
    except Exception as e:
        return None, f"{t('mv_ai_error', lang)}: {e}"


def get_ai_removal_analysis(pdb_content, removed_items):
    prompt = f"""
    Sen, yapısal biyoinformatik ve hesaplamalı biyoloji alanında uzman bir yapay zeka asistanısın.
    Sana bir proteinin orijinal 3D yapısı ve bu yapıdan hesaplamalı olarak çıkarılan bileşenlerin bir listesi verilecek.
    Görevin, **sadece çıkarılan bu bileşenlerin** orijinal yapıdaki önemini analiz ederek, çıkarılmalarının olası sonuçları hakkında TÜRKÇE ve bilimsel bir rapor hazırlamaktır.

    --- ORİJİNAL YAPI ---
    {pdb_content[:4000]} 
    --- (dosyanın devamı kısaltıldı) ---

    --- BU YAPI ÜZERİNDEN KALDIRILAN BİLEŞENLER ---
    - {', '.join(removed_items)}

    Lütfen raporunu Markdown formatında ve aşağıdaki başlıklara göre oluştur:

    ### 1. Kaldırılan Bileşenlerin Analizi
    - Listelenen her bir bileşenin (kalıntı, iyon veya zincir) orijinal yapıdaki konumu ve olası rolü nedir? (Örn: "HOH molekülleri proteinin yüzeyinde bir hidrasyon kabuğu oluşturur", "A Zinciri, proteinin dimerik yapısının bir parçasıdır ve aktif bölgeyi oluşturur", "MG iyonu, ATP'ye bağlanarak enzimatik aktivite için gereklidir").

    ### 2. Yapısal Stabilite (Kararlılık) Üzerindeki Potansiyel Etkiler
    - Bu bileşenlerin yokluğu, proteinin genel katlanmasını veya yapısal bütünlüğünü nasıl etkileyebilir? (Örn: "Yapısal su moleküllerinin kaybı, belirli bölgelerde esnekliği artırabilir veya kararlılığı azaltabilir", "Bir alt birimin kaybı kuaterner yapıyı tamamen bozacaktır").

    ### 3. Fonksiyonel Etki Analizi
    - Bu değişikliklerin, proteinin bilinen biyolojik fonksiyonu, enzimatik aktivitesi veya ligand bağlanma afinitesi üzerindeki olası etkilerini yorumla.
    - Özellikle bağlanma cebi veya aktif bölgeyi etkileyen değişikliklere odaklan. (Örn: "Aktif bölgedeki A zincirinin çıkarılması, substrat bağlanmasını tamamen engelleyeceği için enzimatik aktivitenin kaybolmasına neden olacaktır", "Bağlanma cebindeki bir su molekülünün çıkarılması, ligand için yeni bir hidrofobik cep oluşturarak afiniteyi artırabilir veya azaltabilir.").

    ### 4. Sonuç ve Özet
    - Analizinin kısa bir özetini sun ve bu yapısal modifikasyonun genel olarak ne anlama geldiğini belirt.
    """
    try:
        from ai_engine.services import generate_with_pool
        text, _key = generate_with_pool(prompt, service_name="Google Gemini", model_name="gemini-2.5-flash")
        return dcc.Markdown(text), None
    except Exception as e:
        return None, f"Yapay zeka analizi sırasında hata: {e}"


def interpret_rmsd(rmsd):
    if rmsd < 1.0:
        color, level, desc = "success", "Mükemmel Eşleşme", "İki yapı neredeyse özdeştir."
    elif rmsd < 2.0:
        color, level, desc = "success", "Yüksek Benzerlik", "Yapılar aynı protein ailesine aittir."
    elif rmsd < 4.0:
        color, level, desc = "warning", "Orta Düzey Benzerlik", "Yapılar uzak akraba olabilir."
    else:
        color, level, desc = "danger", "Düşük Benzerlik", "Yapıların katlanmaları farklıdır."
    return dbc.Alert([html.H5(f"RMSD: {rmsd:.3f} Å - {level}"), html.P(desc)], color=color)


def _cif_headers_and_start(lines):
    headers, start_idx, in_atom_site, loop_found = [], -1, False, False
    for i, line in enumerate(lines):
        s = line.strip()
        if s == 'loop_':
            loop_found, in_atom_site, headers = True, False, []
        elif loop_found and s.startswith('_atom_site.'):
            in_atom_site = True
            headers.append(s)
        elif in_atom_site and s and not s.startswith(('_', '#')):
            start_idx = i;
            break
    if not in_atom_site: headers = []
    return headers, start_idx


def _cif_pick(headers, candidates):
    for key in candidates:
        if key in headers: return key, headers.index(key)
    return None, -1


def _normalize_codes(values): return {str(v).upper() for v in values if v is not None}


def process_content_remove_residues(content, ext, residues_to_remove):
    if not content or not residues_to_remove: return content, None
    lines, kept_lines, residues_set = content.split('\n'), [], _normalize_codes(residues_to_remove)
    if ext.lower() == 'pdb':
        for line in lines:
            if line.startswith(('ATOM', 'HETATM')) and line[17:20].strip().upper() in residues_set: continue
            kept_lines.append(line)
        return '\n'.join(kept_lines), None
    elif ext.lower() == 'cif':
        headers, start_idx = _cif_headers_and_start(lines)
        if not headers or start_idx == -1: return content, "CIF: _atom_site bloğu bulunamadı."
        _comp_key, comp_idx = _cif_pick(headers, ['_atom_site.label_comp_id', '_atom_site.auth_comp_id'])
        if comp_idx == -1: return content, "CIF: kalıntı (comp_id) kolonu bulunamadı."
        for i, line in enumerate(lines):
            s = line.strip()
            if i < start_idx or not s or s.startswith(('#', '_', 'loop_')): kept_lines.append(line); continue
            parts = shlex.split(s)
            if comp_idx < len(parts) and str(parts[comp_idx]).upper() in residues_set: continue
            kept_lines.append(line)
        return '\n'.join(kept_lines), None
    return content, "Desteklenmeyen dosya formatı."


def process_content_remove_chains(content, ext, chains_to_remove):
    if not content or not chains_to_remove: return content, None
    lines, kept_lines, chains_set = content.split('\n'), [], _normalize_codes(chains_to_remove)
    if ext.lower() == 'pdb':
        for line in lines:
            if line.startswith(('ATOM', 'HETATM')) and line[21:22].strip().upper() in chains_set: continue
            kept_lines.append(line)
        return '\n'.join(kept_lines), None
    elif ext.lower() == 'cif':
        headers, start_idx = _cif_headers_and_start(lines)
        if not headers or start_idx == -1: return content, "CIF: _atom_site bloğu bulunamadı."
        _chain_key, chain_idx = _cif_pick(headers, ['_atom_site.auth_asym_id', '_atom_site.label_asym_id'])
        if chain_idx == -1: return content, "CIF: zincir kolonu bulunamadı."
        for i, line in enumerate(lines):
            s = line.strip()
            if i < start_idx or not s or s.startswith(('#', '_', 'loop_')): kept_lines.append(line); continue
            parts = shlex.split(s)
            if chain_idx < len(parts) and str(parts[chain_idx]).upper() in chains_set: continue
            kept_lines.append(line)
        return '\n'.join(kept_lines), None
    return content, "Desteklenmeyen dosya formatı."


def get_unique_residues_from_content(content, ext):
    residues = set()
    if not content: return []
    if ext.lower() == 'pdb':
        for line in content.split('\n'):
            if line.startswith(('ATOM', 'HETATM')): residues.add(line[17:20].strip())
    elif ext.lower() == 'cif':
        lines = content.split('\n')
        headers, start_idx = _cif_headers_and_start(lines)
        if not headers or start_idx == -1: return []
        _comp_key, comp_idx = _cif_pick(headers, ['_atom_site.label_comp_id', '_atom_site.auth_comp_id'])
        if comp_idx == -1: return []
        for line in lines[start_idx:]:
            s = line.strip()
            if not s or s.startswith(('#', '_', 'loop_')): continue
            parts = shlex.split(s)
            if comp_idx < len(parts): residues.add(parts[comp_idx])
    return sorted([r for r in _normalize_codes(residues) if r])


def get_unique_chains_from_content(content, ext):
    chains = set()
    if not content: return []
    if ext.lower() == 'pdb':
        for line in content.split('\n'):
            if line.startswith(('ATOM', 'HETATM')): chains.add(line[21:22].strip())
    elif ext.lower() == 'cif':
        lines = content.split('\n')
        headers, start_idx = _cif_headers_and_start(lines)
        if not headers or start_idx == -1: return []
        _chain_key, chain_idx = _cif_pick(headers, ['_atom_site.auth_asym_id', '_atom_site.label_asym_id'])
        if chain_idx == -1: return []
        for line in lines[start_idx:]:
            s = line.strip()
            if not s or s.startswith(('#', '_', 'loop_')): continue
            parts = shlex.split(s)
            if chain_idx < len(parts): chains.add(parts[chain_idx])
    return sorted([c for c in _normalize_codes(chains) if c])


# --- UYGULAMA YERLEŞİMİ (LAYOUT) ---
def create_molecule_viewer_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label
    data_tab = dbc.CardBody([
        dbc.Label(t('mv_pdb_label', lang), html_for="pdb-id-input", className="fw-bold"),
        dbc.InputGroup([dbc.Input(id="pdb-id-input", placeholder=t('mv_pdb_placeholder', lang), type="text"),
                        dbc.Button(t('mv_load', lang), id="btn-load-pdb", n_clicks=0)]),
        html.Hr(),
        dbc.Label(t('mv_file_label', lang), html_for="upload-data", className="fw-bold"),
        dcc.Upload(id='upload-data', multiple=True, children=html.Div([t('mv_drag_drop', lang)],
                                                                      style={'textAlign': 'center', 'padding': '20px',
                                                                             'border': '2px dashed #ccc',
                                                                             'borderRadius': '5px'})),
        html.Div(id="upload-status", className="mt-2", style={'maxHeight': '100px', 'overflowY': 'auto'}),
    ])
    view_tab = dbc.CardBody([
        dbc.Label(t('mv_style', lang), html_for="representation-style", className="fw-bold"),
        dcc.Dropdown(id="representation-style", options=REPRESENTATIONS, value=['cartoon'], multi=True),
        html.Hr(),
        dbc.Label(t('mv_bg_color', lang), html_for="bg-color", className="fw-bold"),
        dcc.Dropdown(id="bg-color", options=['black', 'white'], value='white'), html.Br(),
        dbc.Label(t('mv_camera', lang), html_for="camera-type", className="fw-bold"),
        dcc.Dropdown(id="camera-type", options=['perspective', 'orthographic'], value='perspective'), html.Br(),
        dbc.Label(t('mv_quality', lang), html_for="quality-type", className="fw-bold"),
        dcc.Dropdown(id="quality-type", options=['low', 'medium', 'high'], value='medium'),
    ])
    analysis_tab = dbc.CardBody([
        dbc.Label(t('mv_superpose', lang), className="fw-bold"),
        dcc.Dropdown(id='fixed-mol-dropdown', placeholder=t('mv_ref_mol', lang), className="mb-2"),
        dcc.Dropdown(id='moving-mol-dropdown', placeholder=t('mv_moving_mol', lang)),
        dbc.Button(t('mv_align_btn', lang), id="btn-superpose", n_clicks=0, className="w-100 mt-2"),
        html.Hr(),
        dbc.Label(t('mv_clean', lang), className="fw-bold"),
        dcc.Dropdown(id='mol-to-clean-dropdown', placeholder=t('mv_select_filter_mol', lang), className="mt-3 mb-2"),
        dcc.Dropdown(id='residues-to-remove-dropdown', multi=True, placeholder=t('mv_remove_residues', lang),
                     className="mb-2"),
        dcc.Dropdown(id='chains-to-remove-dropdown', multi=True, placeholder=t('mv_remove_chains', lang)),
        dbc.Button(t('mv_apply_filters', lang), id="btn-apply-filters", color="primary", className="w-100 mt-2"),
        html.Hr(),
        dbc.Label(t('mv_ai_report_label', lang), className="fw-bold"),
        dcc.Dropdown(id='ai-mol-dropdown', placeholder=t('mv_select_report_mol', lang)),
        dbc.Button(f"{t('mv_generate_report', lang)} {credit_label('bio_tool_ai', lang)}", id="btn-get-ai-report", n_clicks=0, className="w-100 mt-2"),
        html.Hr(),
        dcc.Loading(html.Div(id="main-status-output", className="mt-2 text-center")),
    ])
    interaction_tab = dbc.CardBody([
        dbc.Label(t('mv_download_image_label', lang), html_for="btn-download-image", className="fw-bold"),
        dbc.Button(t('mv_download_current', lang), id="btn-download-image", n_clicks=0, className="w-100")
    ])
    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('mv-modal', lang=lang),
        dcc.Store(id='mv-lang-store', data=lang),
        dcc.Store(id='original-molecules-store', storage_type='memory'),
        dcc.Store(id='processed-molecules-store', storage_type='memory'),
        dcc.Store(id='table-data-store', storage_type='memory'),
        dcc.Store(id='removed-components-store', storage_type='memory'),
        html.Div(id='dummy-clear-output', style={'display': 'none'}),
        dbc.Row(className="mb-3", align="center", children=[
            dbc.Col(html.H2(t('mv_title', lang)), width="auto"),
            dbc.Col(dbc.Button(t('mv_clear_all', lang), id="btn-clear-all", color="danger"), width="auto",
                    className="ms-auto")
        ]),
        dbc.Row([
            dbc.Col(width=12, lg=4, children=[dbc.Card(dbc.Tabs([
                dbc.Tab(data_tab, label=t('mv_tab_data', lang)), dbc.Tab(view_tab, label=t('mv_tab_view', lang)),
                dbc.Tab(analysis_tab, label=t('mv_tab_analysis', lang)), dbc.Tab(interaction_tab, label=t('mv_tab_interaction', lang))
            ]))]),
            dbc.Col(dcc.Loading(id="loading-viewer", children=html.Div(id='ngl-viewer-container', children=[
                dash_bio.NglMoleculeViewer(id=COMPONENT_ID, data=[DATA_PLACEHOLDER])
            ])), width=12, lg=8, style={'minHeight': '600px'})
        ]),
        dbc.Row(className="mt-4", children=[dbc.Col(dbc.Card([
            dbc.CardHeader(html.H4(t('mv_results_title', lang))),
            dbc.CardBody([
                dcc.Loading(html.Div(id="ai-report-output", className="mb-4")),
                html.Hr(),
                html.H5(t('mv_atom_table', lang)),
                html.Div(id='table-selector-container', style={'display': 'none'}, children=[
                    dbc.Label(t('mv_select_table_mol', lang)),
                    dcc.Dropdown(id='table-molecule-selector')
                ]),
                dbc.ButtonGroup([
                    dbc.Button(t('mv_download_csv', lang), id="btn-download-csv", outline=True, color="primary", size="sm"),
                    dbc.Button(t('mv_download_xlsx', lang), id="btn-download-xlsx", outline=True, color="primary", size="sm")
                ], className="mt-2"),
                dcc.Download(id="download-csv"), dcc.Download(id="download-xlsx"),
                dcc.Loading(id="loading-table", children=html.Div(id="table-container", className="mt-2")),

            ])
        ]))])
    ])


app.layout = create_molecule_viewer_layout()


# ==============================================================================
# STABİL MİMARİ: TEK BUTON KONTROLLÜ MASTER PROCESSOR
# ==============================================================================

@app.callback(
    Output('original-molecules-store', 'data'),
    Output('upload-status', 'children'),
    Input('btn-load-pdb', 'n_clicks'),
    Input('upload-data', 'contents'),
    State('pdb-id-input', 'value'),
    State('upload-data', 'filename'),
    State('original-molecules-store', 'data'),
    prevent_initial_call=True
)
def handle_data_loading(pdb_clicks, upload_contents, pdb_id, upload_filenames, current_mols):
    triggered_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    all_mols = current_mols if current_mols else {}
    messages = []
    if triggered_id == 'btn-load-pdb' and pdb_id:
        pdb_id = pdb_id.upper()
        if pdb_id not in all_mols:
            content, msg = fetch_pdb_from_rcsb(pdb_id)
            if content:
                all_mols[pdb_id] = create_ngl_dict(f"{pdb_id}.pdb", "pdb", pdb_id, content,
                                                   COLORS[len(all_mols) % len(COLORS)])
            messages.append(dbc.Alert(msg if msg else f"{pdb_id} yüklendi.", color="danger" if msg else "success"))
        else:
            messages.append(dbc.Alert(f"'{pdb_id}' zaten yüklü.", color="warning"))
    elif triggered_id == 'upload-data' and upload_contents:
        data_list, upload_messages = get_uploaded_data(upload_contents, upload_filenames, COLORS)
        messages.extend(upload_messages)
        for data_dict in data_list:
            if data_dict['selectedValue'] not in all_mols:
                all_mols[data_dict['selectedValue']] = data_dict
    return all_mols, messages


@app.callback(
    Output('processed-molecules-store', 'data'),
    Output('main-status-output', 'children'),
    Output('removed-components-store', 'data'),
    Input('btn-apply-filters', 'n_clicks'),
    Input('btn-superpose', 'n_clicks'),
    Input('btn-load-pdb', 'n_clicks'),
    Input('upload-data', 'contents'),
    Input('btn-clear-all', 'n_clicks'),
    [
        State('mol-to-clean-dropdown', 'value'),
        State('residues-to-remove-dropdown', 'value'),
        State('chains-to-remove-dropdown', 'value'),
        State('fixed-mol-dropdown', 'value'),
        State('moving-mol-dropdown', 'value'),
        State('original-molecules-store', 'data'),
        State('processed-molecules-store', 'data')
    ],
    prevent_initial_call=True
)
def master_processor_callback(
        filter_clicks, superpose_clicks,
        load_clicks, upload_contents, clear_clicks,
        selected_mol_id, residues_to_remove, chains_to_remove,
        fixed_mol_id, moving_mol_id,
        original_mols, processed_mols
):
    triggered_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == 'btn-apply-filters':
        if not selected_mol_id: return no_update, dbc.Alert("Lütfen filtrelenecek bir molekül seçin.",
                                                            color="warning"), no_update

        if not residues_to_remove and not chains_to_remove:
            return no_update, dbc.Alert("Lütfen temizlemek için bir kalıntı veya zincir seçin.", color="warning",
                                        duration=4000), no_update

        all_mols = {**(original_mols or {}), **{m['selectedValue']: m for m in (processed_mols or [])}}

        source_mol_data = all_mols.get(selected_mol_id)
        if not source_mol_data: return no_update, dbc.Alert(f"'{selected_mol_id}' ID'li molekül bulunamadı.",
                                                            color="danger"), no_update

        content, ext = source_mol_data.get('config', {}).get('input'), source_mol_data.get('ext')
        if not content or not ext: return no_update, dbc.Alert("Seçili molekülün içeriği eksik.",
                                                               color="danger"), no_update

        processed_content, err, actions, removed_items = content, None, [], []

        if residues_to_remove:
            processed_content, err = process_content_remove_residues(processed_content, ext, residues_to_remove)
            if err: return no_update, dbc.Alert(f"Kalıntı temizleme hatası: {err}", color="danger"), no_update
            actions.append(f"kalıntılar ({', '.join(residues_to_remove)})")
            removed_items.extend(residues_to_remove)

        if chains_to_remove:
            processed_content, err = process_content_remove_chains(processed_content, ext, chains_to_remove)
            if err: return no_update, dbc.Alert(f"Zincir temizleme hatası: {err}", color="danger"), no_update
            actions.append(f"zincirler ({', '.join(chains_to_remove)})")
            removed_items.extend(chains_to_remove)

        if processed_content == content: return no_update, dbc.Alert("Değişiklik yapılmadı.", color="info"), no_update

        base_id = selected_mol_id.split('_cleaned')[0]
        new_id = f"{base_id}_cleaned"
        new_filename = f"{os.path.splitext(source_mol_data['filename'].split('_cleaned')[0])[0]}_cleaned.{ext}"

        cleaned_mol_data = create_ngl_dict(new_filename, ext, new_id, processed_content, '#ff7f00', True)
        status_msg = f"Filtre uygulandı: ({' ve '.join(actions)} kaldırıldı)."

        return [cleaned_mol_data], dbc.Alert(status_msg, color="success"), removed_items

    elif triggered_id == 'btn-superpose':
        all_mols = {**(original_mols or {}), **{m['selectedValue']: m for m in (processed_mols or [])}}
        if not fixed_mol_id or not moving_mol_id or not all_mols: return no_update, dbc.Alert(
            "Lütfen hizalama için iki molekül seçin.", color="warning"), no_update
        if fixed_mol_id == moving_mol_id: return no_update, dbc.Alert("Lütfen iki FARKLI molekül seçin.",
                                                                      color="warning"), no_update
        fixed_mol_data, moving_mol_data = all_mols.get(fixed_mol_id), all_mols.get(moving_mol_id)
        if not fixed_mol_data or not moving_mol_data: return no_update, dbc.Alert(
            "Seçilen molekül verileri bulunamadı.", color="danger"), no_update
        try:
            parser = PDBParser(QUIET=True)
            fixed_structure, moving_structure = parser.get_structure("fixed", StringIO(
                fixed_mol_data['config']['input'])), parser.get_structure("moving",
                                                                          StringIO(moving_mol_data['config']['input']))
            fixed_atoms, moving_atoms = [a for a in fixed_structure.get_atoms() if a.get_name() == 'CA'], [a for a in
                                                                                                           moving_structure.get_atoms()
                                                                                                           if
                                                                                                           a.get_name() == 'CA']
            if not fixed_atoms or not moving_atoms: return no_update, dbc.Alert(
                "Hizalama için C-alfa atomları bulunamadı.", color="danger"), no_update
            min_len = min(len(fixed_atoms), len(moving_atoms))
            super_imposer = Superimposer()
            super_imposer.set_atoms(fixed_atoms[:min_len], moving_atoms[:min_len])
            super_imposer.apply(moving_structure.get_atoms())
            io_string, pdb_io = StringIO(), PDBIO()
            pdb_io.set_structure(moving_structure)
            pdb_io.save(io_string)
            aligned_pdb = io_string.getvalue()
            fixed_mol_display, aligned_moving_display = fixed_mol_data.copy(), create_ngl_dict(
                f"aligned_{moving_mol_data['selectedValue']}", moving_mol_data['ext'], f"aligned_{moving_mol_id}",
                aligned_pdb, '#377eb8', True)
            fixed_mol_display['color'] = '#e41a1c'
            return [fixed_mol_display, aligned_moving_display], interpret_rmsd(super_imposer.rms), no_update
        except Exception as e:
            return no_update, dbc.Alert(f"Hizalama hatası: {e}", color="danger"), no_update

    elif triggered_id in ['btn-load-pdb', 'upload-data', 'btn-clear-all']:
        return None, None, None
    return no_update, no_update, no_update


@app.callback(
    Output('ngl-viewer-container', 'children'),
    Input('original-molecules-store', 'data'),
    Input('processed-molecules-store', 'data')
)
def update_viewer_display(original_data, processed_data):
    data_to_show = [DATA_PLACEHOLDER]
    if processed_data:
        data_to_show = processed_data
    elif original_data:
        data_to_show = list(original_data.values())
    return dash_bio.NglMoleculeViewer(id=COMPONENT_ID, data=data_to_show)


@app.callback(
    Output('table-selector-container', 'style'),
    Output('table-molecule-selector', 'options'),
    Output('table-molecule-selector', 'value'),
    Input('original-molecules-store', 'data'),
    Input('processed-molecules-store', 'data')
)
def update_table_controls(original_data, processed_data):
    data_source = processed_data if processed_data else (list(original_data.values()) if original_data else [])
    if len(data_source) <= 1: return {'display': 'none'}, [], None
    options = [{'label': mol['filename'], 'value': mol['selectedValue']} for mol in data_source]
    default_value = data_source[0]['selectedValue']
    return {'display': 'block', 'marginBottom': '10px'}, options, default_value


@app.callback(
    Output('table-container', 'children'),
    Output('table-data-store', 'data'),
    Input('table-molecule-selector', 'value'),
    Input('original-molecules-store', 'data'),
    Input('processed-molecules-store', 'data')
)
def update_table_content(selected_mol_id, original_data, processed_data):
    data_source = processed_data if processed_data else (list(original_data.values()) if original_data else [])
    if not data_source: return dbc.Alert("Tabloyu görüntülemek için bir molekül yükleyin.", color="info"), {}
    mol_to_display_id = selected_mol_id if selected_mol_id else data_source[0].get('selectedValue')
    if not mol_to_display_id: return dbc.Alert("Tablo için geçerli bir molekül bulunamadı.", color="warning"), {}
    molecule_to_parse = next((mol for mol in data_source if mol.get('selectedValue') == mol_to_display_id), None)
    if not molecule_to_parse: return dbc.Alert(f"ID'si '{mol_to_display_id}' olan molekül verisi bulunamadı.",
                                               color="warning"), {}
    config, content, ext = molecule_to_parse.get('config', {}), None, None
    if config: content = config.get('input')
    ext = molecule_to_parse.get('ext')
    if not content or not ext: return dbc.Alert(
        f"'{molecule_to_parse.get('filename', 'Bilinmeyen')}' için içerik verisi eksik.", color="danger"), {}
    table_records = parse_cif_for_table(content) if ext.lower() == 'cif' else parse_pdb_for_table(content)
    if not table_records: return dbc.Alert(f"'{molecule_to_parse.get('filename')}' için atom verisi okunamadı.",
                                           color="warning"), {}
    table = dash_table.DataTable(
        data=table_records,
        columns=[{'name': 'Atom Adı', 'id': 'atom_name'}, {'name': 'Kalıntı Adı', 'id': 'residue_name'},
                 {'name': 'Zincir', 'id': 'chain'}, {'name': 'Kalıntı No', 'id': 'residue_no'},
                 {'name': 'X', 'id': 'x'}, {'name': 'Y', 'id': 'y'}, {'name': 'Z', 'id': 'z'}],
        page_size=10, style_table={'overflowX': 'auto'}, sort_action="native", filter_action="native"
    )
    return table, table_records


@app.callback(
    Output('mol-to-clean-dropdown', 'options'),
    Output('fixed-mol-dropdown', 'options'),
    Output('moving-mol-dropdown', 'options'),
    Output('ai-mol-dropdown', 'options'),
    Input('original-molecules-store', 'data'),
    Input('processed-molecules-store', 'data'),
)
def update_all_selector_dropdowns(original_data, processed_data):
    options = []
    if original_data:
        options.extend([{'label': data['filename'], 'value': key} for key, data in original_data.items()])
    if processed_data:
        options.extend([{'label': data['filename'], 'value': data['selectedValue']} for data in processed_data])
    if not options:
        return [], [], [], []
    return options, options, options, options


@app.callback(
    Output('mol-to-clean-dropdown', 'value'),
    Input('original-molecules-store', 'data'),
    Input('processed-molecules-store', 'data')
)
def update_default_cleaning_selection(original_data, processed_data):
    if processed_data:
        return processed_data[0]['selectedValue']
    if original_data:
        return list(original_data.keys())[0]
    return None


@app.callback(
    Output('residues-to-remove-dropdown', 'options'),
    Output('chains-to-remove-dropdown', 'options'),
    Output('residues-to-remove-dropdown', 'value'),
    Output('chains-to-remove-dropdown', 'value'),
    Input('mol-to-clean-dropdown', 'value'),
    [State('original-molecules-store', 'data'),
     State('processed-molecules-store', 'data')],
    prevent_initial_call=True
)
def update_cleaning_options_on_select(selected_mol_id, original_mols, processed_mols):
    if not selected_mol_id: return [], [], [], []

    all_mols = {**(original_mols or {}), **{m['selectedValue']: m for m in (processed_mols or [])}}
    mol_data = all_mols.get(selected_mol_id)

    if not mol_data: return [], [], [], []
    content, ext = mol_data['config']['input'], mol_data['ext']
    unique_residues, unique_chains = get_unique_residues_from_content(content, ext), get_unique_chains_from_content(
        content, ext)
    residue_options = [{'label': res, 'value': res} for res in unique_residues]
    chain_options = [{'label': chain, 'value': chain} for chain in unique_chains]
    return residue_options, chain_options, [], []


@app.callback(
    Output('ai-report-output', 'children'),
    Input('mv-modal-confirm', 'n_clicks'),
    [
        State('ai-mol-dropdown', 'value'),
        State('original-molecules-store', 'data'),
        State('removed-components-store', 'data'),
        State('mv-lang-store', 'data')
    ],
    prevent_initial_call=True
)
def generate_ai_report_callback(n_clicks, selected_mol_id, original_mols, removed_items, lang, **kwargs):
    lang = lang or 'en'
    if not selected_mol_id:
        return dbc.Alert("Lütfen rapor oluşturmak için bir molekül seçin.", color="warning")

    from billing.dash_helpers import try_charge
    ok, msg, _u = try_charge(kwargs, 'bio_tool_ai', cost=5, lang=lang,
                             description="Molekül AI raporu")
    if not ok:
        return msg

    # Öncelik 1: Eğer bir temizleme işlemi yapıldıysa, odaklı analiz yap
    if removed_items and selected_mol_id.endswith('_cleaned'):
        original_id = selected_mol_id.split('_cleaned')[0]
        original_mol_data = (original_mols or {}).get(original_id)

        if not original_mol_data:
            return dbc.Alert(f"'{original_id}' ID'li orijinal molekül bulunamadı.", color="danger")

        pdb_content = original_mol_data.get('config', {}).get('input')
        if not pdb_content:
            return dbc.Alert("Orijinal molekül içeriği bulunamadı.", color="danger")

        report, error = get_ai_removal_analysis(pdb_content, removed_items)
        if error:
            return dbc.Alert(f"AI Analizi hatası: {error}", color="danger")
        return report

    # Öncelik 2: Normal raporlama
    else:
        if not original_mols: return dbc.Alert("Molekül deposu boş.", color="danger")
        molecule_data = original_mols.get(selected_mol_id)
        if not molecule_data: return dbc.Alert("Seçilen molekül için veri bulunamadı.", color="danger")

        content, ext = molecule_data.get('config', {}).get('input'), molecule_data.get('ext')
        if not content or not ext: return dbc.Alert("Seçilen molekülün içeriği eksik.", color="danger")

        protein_name = extract_info_from_content(content, ext, 'protein_name')
        organism = extract_info_from_content(content, ext, 'organism')

        report, error = get_ai_report(protein_name, organism, lang=lang)
        if error:
            return dbc.Alert(f"AI Raporu oluşturulurken hata: {error}", color="danger")
        return report


@app.callback(Output(COMPONENT_ID, 'molStyles'), Input('representation-style', 'value'))
def update_molecule_styles(representations): return {'representations': representations} if representations else {
    'representations': ['cartoon']}


@app.callback(Output(COMPONENT_ID, 'stageParameters'), Input('bg-color', 'value'), Input('camera-type', 'value'),
              Input('quality-type', 'value'))
def update_stage_parameters(bgcolor, camera, quality): return {'backgroundColor': bgcolor, 'cameraType': camera,
                                                               'quality': quality}


@app.callback(Output(COMPONENT_ID, 'downloadImage'), Input('btn-download-image', 'n_clicks'), prevent_initial_call=True)
def download_ngl_image(n_clicks): return True


@app.callback(Output("download-csv", "data"), Input("btn-download-csv", "n_clicks"), State("table-data-store", "data"),
              prevent_initial_call=True)
def download_table_as_csv(n_clicks, table_data):
    if not table_data: raise PreventUpdate
    df = pd.DataFrame(table_data)
    return dcc.send_data_frame(df.to_csv, "atom_verileri.csv", index=False)


@app.callback(Output("download-xlsx", "data"), Input("btn-download-xlsx", "n_clicks"),
              State("table-data-store", "data"), prevent_initial_call=True)
def download_table_as_xlsx(n_clicks, table_data):
    if not table_data: raise PreventUpdate
    df, output = pd.DataFrame(table_data), io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False,
                                                                          sheet_name='Atom_Verileri')
    return dcc.send_bytes(output.getvalue(), "atom_verileri.xlsx")


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
    Output("molecule_viewer", "active"),
    Input("url", "pathname")
)
def toggle_molecule_viewer(pathname):
    return pathname == reverse('bio_tools:molecule_viewer')

clientside_callback(
    ClientsideFunction(namespace='clientside', function_name='reloadPage'),
    Output('dummy-clear-output', 'children'),
    Input('btn-clear-all', 'n_clicks'),
    prevent_initial_call=True
)


# --- Kredi onay modalı: btn-get-ai-report tıklanınca onay sor ---
@app.callback(
    Output('mv-modal', 'is_open'),
    Output('mv-modal-body', 'children'),
    Output('mv-modal-confirm', 'disabled'),
    Input('btn-get-ai-report', 'n_clicks'),
    Input('mv-modal-cancel', 'n_clicks'),
    Input('mv-modal-confirm', 'n_clicks'),
    State('mv-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_mv_modal(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'btn-get-ai-report' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
