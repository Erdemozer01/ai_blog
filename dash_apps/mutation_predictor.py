# -*- coding: utf-8 -*-
import base64
import os
import re
import tempfile
import platform
import zlib


import dash
import requests
import numpy as np


import mdtraj as md

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State
from django.conf import settings
from django.shortcuts import reverse
from django_plotly_dash import DjangoDash

# Biyoinformatik ve Makine Öğrenmesi Kütüphaneleri
from Bio.PDB import PDBParser, PDBIO, Select

from Bio.PDB.ResidueDepth import ResidueDepth
from sklearn.tree import DecisionTreeClassifier, export_text
from billing.dash_helpers import build_confirm_modal

# --- UYGULAMA BAŞLATMA ---
app = DjangoDash(
    name='MutationPredictorApp',
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
)


# --- YARDIMCI FONKSİYONLAR ---

class StandardResiduesSelect(Select):
    def accept_residue(self, residue):
        return residue.get_id()[0] == ' '


def clean_pdb_content(pdb_content):
    parser = PDBParser(QUIET=True)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as tmp_in:
        tmp_in.write(pdb_content)
        in_filename = tmp_in.name
    structure = parser.get_structure("original", in_filename)
    io = PDBIO()
    io.set_structure(structure)
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.pdb', delete=False) as tmp_out:
        out_filename = tmp_out.name
        io.save(out_filename, select=StandardResiduesSelect())
        tmp_out.seek(0)
        cleaned_content = tmp_out.read()
    os.unlink(in_filename)
    os.unlink(out_filename)
    return cleaned_content


def fetch_pdb_from_rcsb(pdb_id):
    pdb_id = pdb_id.upper()
    if len(pdb_id) != 4:
        return None, "Geçersiz PDB ID formatı."
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        cleaned_content = clean_pdb_content(response.text)
        return cleaned_content, None
    except requests.exceptions.RequestException as e:
        return None, f"RCSB'den veri çekilemedi: {e}"


def get_uploaded_data(contents, filenames):
    if not contents: return [], []
    data_dict, messages = {}, []
    for content_str, filename in zip(contents, filenames):
        try:
            _, content_string = content_str.split(',')
            decoded = base64.b64decode(content_string)
            file_content_raw = zlib.decompress(decoded, 16 + zlib.MAX_WBITS).decode('utf-8',
                                                                                    'ignore') if filename.lower().endswith(
                '.gz') else decoded.decode('utf-8', 'ignore')
            file_content = clean_pdb_content(file_content_raw)
            file_id = os.path.splitext(filename)[0]
            data_dict[file_id] = {'filename': filename, 'content': file_content}
            messages.append(
                dbc.Alert(f"'{filename}' başarıyla yüklendi ve temizlendi.", color="success", duration=3000))
        except Exception as e:
            messages.append(
                dbc.Alert(f"'{filename}' yüklenemedi veya temizlenemedi: {e}", color="danger", duration=5000))
    return data_dict, messages


def analyze_mutation_impact(pdb_content, mutation_str):
    tmp = tempfile.NamedTemporaryFile(mode='w+', suffix='.pdb', delete=False)
    windows_pdb_filepath = tmp.name

    try:
        tmp.write(pdb_content)
        tmp.close()

        try:
            traj = md.load_pdb(windows_pdb_filepath)
            dssp_codes = md.compute_dssp(traj, simplified=True)[0]
        except Exception as e:
            return None, f"MDTraj ile PDB dosyası işlenemedi. Dosya formatını kontrol edin. Hata: {e}"

        if platform.system() == "Windows":
            msms_executable_path = os.path.join(settings.BASE_DIR, "programs", "msms.exe")
        elif platform.system() == "Linux":
            home_dir = os.path.expanduser('~')
            programs_dir = os.path.join(home_dir, 'bin')
            msms_executable_path = os.path.join(programs_dir, 'msms_linux')
        else:
            msms_executable_path = "msms"

        match = re.match(r"([A-Z])([0-9]+)([A-Z])", mutation_str.upper())
        if not match: return None, "Geçersiz mutasyon formatı. Örnek: A123G"
        original_aa_one, position, new_aa_one = match.groups()
        position = int(position)
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("protein", windows_pdb_filepath)
        model = structure[0]

        try:
            rd = ResidueDepth(model=model, msms_exec=msms_executable_path)
        except Exception as e:
            return None, f"MSMS programı çalıştırılamadı: '{msms_executable_path}'. Hata: {e}"

        target_residue_md = next((r for r in traj.topology.residues if r.resSeq == position), None)
        if not target_residue_md:
            return None, f"Belirtilen pozisyonda ({position}) kalıntı bulunamadı (yapıda eksik olabilir)."

        target_residue_bio = next(
            (r for r in model.get_residues() if r.get_id()[1] == position and r.get_id()[0] == ' '), None)
        if not target_residue_bio:
            return None, f"Derinlik hesaplaması için {position} pozisyonunda kalıntı bulunamadı."

        ss_code = dssp_codes[target_residue_md.index]
        ss_map = {'H': 1, 'E': 2, 'C': 3}  # Helix, Strand (Sheet), Coil (Diğerleri)
        ss_feature = ss_map.get(ss_code, 3)

        residue_key = target_residue_bio.get_full_id()[2:]
        try:
            depth = rd[residue_key][0]
        except KeyError:
            return None, f"Derinlik hesaplanamadı. {position} pozisyonu yüzeyde veya MSMS tarafından işlenemedi."

        aa_properties = {
            'A': {'vol': 88.6, 'hyd': 1.8}, 'R': {'vol': 173.4, 'hyd': -4.5},
            'N': {'vol': 114.1, 'hyd': -3.5}, 'D': {'vol': 111.1, 'hyd': -3.5},
            'C': {'vol': 108.5, 'hyd': 2.5}, 'E': {'vol': 138.4, 'hyd': -3.5},
            'Q': {'vol': 143.8, 'hyd': -3.5}, 'G': {'vol': 60.1, 'hyd': -0.4},
            'H': {'vol': 153.2, 'hyd': -3.2}, 'I': {'vol': 166.7, 'hyd': 4.5},
            'L': {'vol': 166.7, 'hyd': 3.8}, 'K': {'vol': 168.6, 'hyd': -3.9},
            'M': {'vol': 162.9, 'hyd': 1.9}, 'F': {'vol': 189.9, 'hyd': 2.8},
            'P': {'vol': 112.7, 'hyd': -1.6}, 'S': {'vol': 89.0, 'hyd': -0.8},
            'T': {'vol': 116.1, 'hyd': -0.7}, 'W': {'vol': 227.8, 'hyd': -0.9},
            'Y': {'vol': 193.6, 'hyd': -1.3}, 'V': {'vol': 140.0, 'hyd': 4.2}
        }
        vol_change = abs(
            aa_properties.get(new_aa_one, {'vol': 0})['vol'] - aa_properties.get(original_aa_one, {'vol': 0})['vol'])
        hyd_change = abs(
            aa_properties.get(new_aa_one, {'hyd': 0})['hyd'] - aa_properties.get(original_aa_one, {'hyd': 0})['hyd'])

        features = [vol_change, hyd_change, depth, ss_feature]
        feature_names = ['Hacim Değişimi', 'Hidrofobiklik Değişimi', 'Derinlik (Å)', 'İkincil Yapı Tipi']

        return features, feature_names

    except Exception as e:
        return None, f"Mutasyon analizi sırasında genel hata: {e}"
    finally:
        if os.path.exists(windows_pdb_filepath):
            os.unlink(windows_pdb_filepath)


def train_and_predict_mutation_effect(features):
    X_train = np.array([
        [100, 5.0, 0.5, 0], [130, 0.5, 1.2, 1], [20, 6.0, 4.0, 0], [80, 2.0, 0.8, 2],
        [90, -4.0, 2.0, 1], [140, 1.0, 0.3, 0], [10, 1.0, 5.0, 0], [5, 0.2, 6.0, 2],
        [15, 0.1, 8.0, 3], [2, 0.5, 7.5, 0], [20, 0.3, 4.5, 1],
    ])
    y_train = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    feature_names = ['Hacim Değişimi', 'Hidrofobiklik Değişimi', 'Derinlik (Å)', 'İkincil Yapı Tipi']
    model = DecisionTreeClassifier(random_state=42, max_depth=3)
    model.fit(X_train, y_train)
    prediction = model.predict(np.array(features).reshape(1, -1))
    tree_rules = export_text(model, feature_names=feature_names)
    return "Muhtemelen ZARARLI" if prediction[0] == 1 else "Muhtemelen ZARARSİZ", tree_rules


def mutation_create_layout(lang='en'):
    from dash_apps.i18n_helper import t, credit_label
    control_panel = dbc.Card([
        dbc.CardHeader(t('mp_menu', lang)),
        dbc.CardBody([
            dbc.Tabs([
                dbc.Tab(label=t('mp_data_upload', lang), children=[
                    html.Div([
                        dbc.Label(t('mv_pdb_label', lang), html_for="pdb-id-input", className="fw-bold mt-3"),
                        dbc.InputGroup([
                            dbc.Input(id="pdb-id-input", placeholder=t('mp_pdb_placeholder', lang), type="text"),
                            dbc.Button(t('mp_load', lang), id="btn-load-pdb", n_clicks=0)
                        ]),
                        html.Hr(),
                        dbc.Label(t('mp_file_upload', lang), html_for="upload-data", className="fw-bold"),
                        dcc.Upload(
                            id='upload-data', multiple=True,
                            children=html.Div([t('mv_drag_drop', lang)],
                                              style={'textAlign': 'center', 'padding': '20px',
                                                     'border': '2px dashed #ccc', 'borderRadius': '5px'})
                        ),
                        html.Div(id="upload-status", className="mt-2",
                                 style={'maxHeight': '100px', 'overflowY': 'auto'}),
                    ], className="p-3")
                ]),
                dbc.Tab(label=t('mp_mutation_predict', lang), children=[
                    html.Div([
                        dbc.Label(t('mp_mol_to_analyze', lang), className="fw-bold mt-3"),
                        dcc.Dropdown(id='mutation-mol-selector', placeholder=t('mv_select_filter_mol', lang)),
                        dbc.Label(t('mp_mutations_label', lang), className="fw-bold mt-3"),
                        dcc.Textarea(
                            id='mutation-input',
                            placeholder="A123G\nC45D\nW117A\n...",
                            style={'width': '100%', 'height': 100},
                        ),
                        html.Hr(),
                        dbc.Label(t('mp_method_select', lang), className="fw-bold"),
                        dbc.Row([
                            dbc.Col(dbc.Button(f"{t('mp_list_harmful', lang)} {credit_label('bio_tool_ai', lang)}", id="btn-ask-ai", n_clicks=0,
                                               color="info",
                                               className="w-100"), width=6),
                            dbc.Col(
                                dbc.Button(f"{t('mp_predict_detailed', lang)} {credit_label('bio_mutation_predictor', lang)}", id="btn-calculate-program", n_clicks=0,
                                           color="primary",
                                           className="w-100"), width=6),
                        ], className="mb-2"),
                        html.Small(
                            t('mp_method_note', lang),
                            className="text-muted"),
                    ], className="p-3")
                ])
            ])
        ])
    ])

    result_panel = dbc.Card([
        dbc.CardHeader(t('mp_results', lang)),
        dbc.CardBody([
            dcc.Loading(
                id="loading-results",
                type="default",
                children=html.Div(id="results-output-area",
                                  children=html.P(t('mp_select_method', lang),
                                                  className="text-muted"))
            ),
            html.Div(id='gemini-button-container', style={'display': 'none'}, children=[
                html.Hr(),
                html.H5(t('mp_interpret_results', lang)),
                dbc.Button(f"{t('mp_interpret_ai', lang)} {credit_label('bio_tool_ai', lang)}", id="btn-ask-gemini-interpret", color="success",
                           className="w-100 mt-2"),
                dcc.Loading(id="loading-gemini", children=[html.Div(id='gemini-output-div', className="mt-3")])
            ])
        ])
    ])

    return dbc.Container(fluid=True, className="py-3", children=[
        dcc.Location(id='url', refresh=False),
        build_confirm_modal('mp-calc-modal', lang=lang),
        build_confirm_modal('mp-ai-modal', lang=lang),
        dcc.Store(id='mp-lang-store', data=lang),
        dcc.Store(id='molecules-store', storage_type='memory'),
        dcc.Store(id='analysis-results-store', storage_type='memory'),
        dcc.Store(id='button-clicks-store', storage_type='memory'),
        html.H2(t('mp_title', lang)),
        html.P(t('mp_subtitle', lang)),
        html.Hr(),
        dbc.Row([
            dbc.Col(control_panel, width=12, lg=4),
            dbc.Col(result_panel, width=12, lg=8),
        ])
    ])


app.layout = mutation_create_layout()


# ==============================================================================
# CALLBACK'LER
# ==============================================================================

@app.callback(
    Output('molecules-store', 'data'),
    Output('upload-status', 'children'),
    Input('btn-load-pdb', 'n_clicks'),
    Input('upload-data', 'contents'),
    State('pdb-id-input', 'value'),
    State('upload-data', 'filename'),
    State('molecules-store', 'data'),
    prevent_initial_call=True
)
def handle_data_loading(pdb_clicks, upload_contents, pdb_id, upload_filenames, current_mols):
    triggered_id = dash.callback_context.triggered[0]['prop_id'].split('.')[
        0] if dash.callback_context.triggered else 'unknown'
    all_mols = current_mols if current_mols else {}
    messages = []
    if triggered_id == 'btn-load-pdb' and pdb_id:
        pdb_id = pdb_id.strip()
        if pdb_id not in all_mols:
            content, msg = fetch_pdb_from_rcsb(pdb_id)
            if content:
                all_mols[pdb_id] = {'filename': f"{pdb_id}.pdb", 'content': content}
                messages.append(dbc.Alert(f"'{pdb_id}' başarıyla yüklendi.", color="success"))
            else:
                messages.append(dbc.Alert(msg, color="danger"))
        else:
            messages.append(dbc.Alert(f"'{pdb_id}' zaten yüklü.", color="warning"))
    elif triggered_id == 'upload-data' and upload_contents:
        new_data, upload_messages = get_uploaded_data(upload_contents, upload_filenames)
        all_mols.update(new_data)
        messages.extend(upload_messages)
    return all_mols, messages


@app.callback(
    Output('mutation-mol-selector', 'options'),
    Output('mutation-mol-selector', 'value'),
    Input('molecules-store', 'data')
)
def update_molecule_selector(all_mols):
    if not all_mols: return [], None
    options = [{'label': data['filename'], 'value': key} for key, data in all_mols.items()]
    default_value = list(all_mols.keys())[0] if all_mols else None
    return options, default_value


@app.callback(
    Output('results-output-area', 'children'),
    Output('analysis-results-store', 'data'),
    Output('gemini-button-container', 'style'),
    Output('button-clicks-store', 'data'),
    Input('mp-calc-modal-confirm', 'n_clicks'),
    Input('mp-ai-modal-confirm', 'n_clicks'),
    State('mutation-mol-selector', 'value'),
    State('mutation-input', 'value'),
    State('molecules-store', 'data'),
    State('button-clicks-store', 'data'),
    State('mp-lang-store', 'data'),
    prevent_initial_call=True
)
def master_results_callback(calc_clicks, ai_clicks, selected_mol_id, mutation_str, all_mols, prev_clicks, lang=None, **kwargs):
    from dash_apps.i18n_helper import t
    lang = lang or 'en'
    calc_clicks = calc_clicks or 0
    ai_clicks = ai_clicks or 0
    if prev_clicks is None:
        prev_clicks = {'calc': 0, 'ai': 0}

    triggered_button = None
    if calc_clicks > prev_clicks.get('calc', 0):
        triggered_button = 'calculate'
    elif ai_clicks > prev_clicks.get('ai', 0):
        triggered_button = 'ai'

    current_clicks = {'calc': calc_clicks, 'ai': ai_clicks}
    if triggered_button is None:
        return dash.no_update, dash.no_update, dash.no_update, current_clicks

    # Hesaplama → analiz fiyatı; AI yorumu → AI fiyatı
    from billing.dash_helpers import try_charge
    if triggered_button == 'calculate':
        _key, _desc = 'bio_mutation_predictor', "Mutasyon hesaplama"
    else:
        _key, _desc = 'bio_tool_ai', "Mutasyon AI yorumu"
    ok, msg, _u = try_charge(kwargs, _key, cost=5, lang=lang, description=_desc)
    if not ok:
        return msg, dash.no_update, dash.no_update, current_clicks

    if triggered_button == 'calculate':
        initial_outputs = (None, {'display': 'none'})
        if not selected_mol_id or not mutation_str:
            alert = dbc.Alert("Lütfen bir molekül seçin ve analiz edilecek mutasyonları girin.", color="warning")
            return alert, *initial_outputs, current_clicks

        molecule_data = (all_mols or {}).get(selected_mol_id)
        if not molecule_data or not molecule_data.get('content'):
            alert = dbc.Alert("Seçilen molekül için içerik bulunamadı.", color="danger")
            return alert, *initial_outputs, current_clicks

        pdb_content = molecule_data['content']

        mutations_to_process = [m.strip() for m in mutation_str.strip().split('\n') if m.strip()]

        if not mutations_to_process:
            alert = dbc.Alert("Lütfen analiz edilecek en az bir mutasyon girin.", color="warning")
            return alert, *initial_outputs, current_clicks

        table_rows = []
        failed_results = []
        feature_names_for_header = ['Hacim Değişimi', 'Hidrofobiklik Değişimi', 'Derinlik (Å)', 'İkincil Yapı Tipi']

        for mutation in mutations_to_process:
            features, error_msg = analyze_mutation_impact(pdb_content, mutation)

            if features:
                prediction, tree_rules = train_and_predict_mutation_effect(features)
                result_color = "danger" if "ZARARLI" in prediction else "success"

                table_rows.append(html.Tr([
                    html.Td(mutation),
                    html.Td(html.Span(prediction, className=f"fw-bold text-{result_color}")),
                    html.Td(f"{features[0]:.2f}"),
                    html.Td(f"{features[1]:.2f}"),
                    html.Td(f"{features[2]:.2f}"),
                    html.Td(str(features[3])),
                ]))
            else:
                failure_alert = dbc.Alert(
                    f"Mutasyon '{mutation}': {error_msg}",
                    color="warning",
                    className="mb-2"
                )
                failed_results.append(failure_alert)

        table_header = [
            html.Thead(html.Tr([
                                   html.Th(t('mp_mutation', lang)),
                                   html.Th(t('mp_prediction', lang)),
                               ] + [html.Th(name) for name in feature_names_for_header]))
        ]

        results_table = dbc.Table(table_header + [html.Tbody(table_rows)], bordered=True, striped=True, hover=True,
                                  size="sm")

        output_layout = html.Div([
            html.H4(t('mp_batch_results', lang)),
            html.Hr(),
            html.H5(t('mp_successful', lang), className="mt-4"),
            results_table if table_rows else dbc.Alert(t('mp_none_analyzed', lang), color="info"),

            html.H5(t('mp_errors_warnings', lang), className="mt-4"),
            html.Div(failed_results) if failed_results else dbc.Alert("OK",
                                                                      color="success"),
        ])

        return output_layout, None, {'display': 'none'}, current_clicks

    if triggered_button == 'ai':
        initial_outputs = (None, {'display': 'none'})
        if not selected_mol_id:
            alert = dbc.Alert(t('mp_select_mol_first', lang), color="warning")
            return alert, *initial_outputs, current_clicks

        prompt = f"""
        Sen, protein yapıları ve bunlarla ilişkili genetik mutasyonlar konusunda uzman bir biyoinformatik asistanısın.
        Görevin, sana PDB ID'si verilen protein için literatürde ve veritabanlarında (ClinVar, HGMD vb.) bilinen **tüm** "Zararlı" (Pathogenic) veya "Muhtemelen Zararlı" (Likely Pathogenic) mutasyonları listelemektir.

        Cevabını verirken UYMAN GEREKEN EN ÖNEMLİ KURAL: Mutasyonları **tek harfli amino asit kodu formatında (örn: E6V)** listelemelisin. Üç harfli kod ve 'p.' ön ekini KULLANMA (örn: p.Glu7Val YERİNE E6V YAZ). Örneğin, Hemoglobin beta zinciri (HBB geni) için Orak Hücreli Anemi'ye neden olan mutasyon **E6V** olarak listelenmelidir.

        Cevabını aşağıdaki formatta, Markdown listesi olarak ver:

        - **[Mutasyon Kodu 1 (örn: E6V)]**: [İlişkili Hastalık] - [Kanıt/Referans]
        - **[Mutasyon Kodu 2 (örn: Q39X)]**: [İlişkili Hastalık] - [Kanıt/Referans]
        - **[Mutasyon Kodu 3]**: [İlişkili Hastalık] - [Kanıt/Referans]

        Eğer bu protein için literatürde bilinen zararlı bir mutasyon kaydı bulamazsan, SADECE şunu yaz: "Bu protein (PDB ID: {selected_mol_id}) için bilinen ve kanıtlanmış bir zararlı mutasyon kaydı bulunamadı."

        Başka hiçbir ek açıklama veya selamlama cümlesi kullanma.

        Protein PDB ID: {selected_mol_id}
        """
        try:
            from ai_engine.services import generate_with_pool
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            ai_response_text, _key = generate_with_pool(
                prompt, service_name='Google Gemini', model_name='gemini-3.5-flash', safety_settings=safety_settings)
        except Exception as e:
            alert = dbc.Alert(f"Gemini API'ından cevap alınırken hata oluştu: {e}", color="danger")
            return alert, *initial_outputs, current_clicks

        output_layout = html.Div([
            html.H5(f"{selected_mol_id} İçin Bilinen Zararlı Mutasyonlar", className="mb-3"),
            dbc.Card(dbc.CardBody([dcc.Markdown(ai_response_text, style={'whiteSpace': 'pre-wrap'})]))
        ])

        return output_layout, None, {'display': 'none'}, current_clicks

    return dash.no_update, dash.no_update, dash.no_update, current_clicks


@app.callback(
    Output('gemini-output-div', 'children'),
    Input('btn-ask-gemini-interpret', 'n_clicks'),
    [State('analysis-results-store', 'data')],
    prevent_initial_call=True
)
def generate_interpretation_callback(n_clicks, analysis_data):
    if not n_clicks or not analysis_data:
        return ""

    prediction = analysis_data.get('prediction', 'Bilinmiyor')
    mutation_str = analysis_data.get('mutation_str', 'Bilinmiyor')
    features = analysis_data.get('features', [])
    feature_names = analysis_data.get('feature_names', [])
    features_text = "\n".join([f"- {name}: {value:.2f}" for name, value in zip(feature_names, features)])

    prompt = f"""
    Sen, moleküler biyoloji ve yapısal biyoinformatik alanında uzman bir yapay zeka asistanısın.
    Aşağıdaki analiz sonuçlarını, bir biyoloji öğrencisinin anlayacağı şekilde, bilimsel ve detaylı bir dille yorumla.
    Moleküler düzeyde ne anlama geldiğini, proteinin yapısını ve fonksiyonunu nasıl etkileyebileceğini açıkla.
    Cevabını Markdown formatında, başlıklar ve listeler kullanarak structure bir şekilde sun.

    **Analiz Bilgileri:**
    - **Mutasyon:** {mutation_str}
    - **Model Tahmini:** Bu mutasyon **{prediction}** olarak sınıflandırıldı.
    - **Hesaplanan Biyofiziksel Özellikler:**
    {features_text}
    """
    try:
        from ai_engine.services import generate_with_pool
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        interpretation_text, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-3.5-flash', safety_settings=safety_settings)
    except Exception as e:
        print(f"Gemini API Hatası (generate_interpretation_callback): {e}")
        return dbc.Alert(f"Gemini API'ından cevap alınırken hata oluştu: {e}", color="danger")

    return dbc.Card(
        dbc.CardBody([dcc.Markdown(interpretation_text, dangerously_allow_html=True)]),
        className="mt-3", style={"backgroundColor": "#f0f8ff"}
    )


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
    Output("mutation_predictor", "active"),
    Input("url", "pathname")
)
def toggle_mutation_predictor(pathname):
    return pathname == reverse('bio_tools:mutation_predictor')


# --- Kredi onay modalı: btn-calculate-program ---
@app.callback(
    Output('mp-calc-modal', 'is_open'),
    Output('mp-calc-modal-body', 'children'),
    Output('mp-calc-modal-confirm', 'disabled'),
    Input('btn-calculate-program', 'n_clicks'),
    Input('mp-calc-modal-cancel', 'n_clicks'),
    Input('mp-calc-modal-confirm', 'n_clicks'),
    State('mp-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_mp_calc(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'btn-calculate-program' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_mutation_predictor', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update


# --- Kredi onay modalı: btn-ask-ai ---
@app.callback(
    Output('mp-ai-modal', 'is_open'),
    Output('mp-ai-modal-body', 'children'),
    Output('mp-ai-modal-confirm', 'disabled'),
    Input('btn-ask-ai', 'n_clicks'),
    Input('mp-ai-modal-cancel', 'n_clicks'),
    Input('mp-ai-modal-confirm', 'n_clicks'),
    State('mp-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_mp_ai(open_click, cancel_click, confirm_click, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'tr'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'btn-ask-ai' and open_click:
        body, can_proceed = confirm_modal_body(kwargs, 'bio_tool_ai', cost=5, lang=lang)
        return True, body, (not can_proceed)
    return False, dash.no_update, dash.no_update
