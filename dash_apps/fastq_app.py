# dash_apps/fastq_app.py
"""
Django ile entegre FASTQ Analiz Dash Uygulaması
ÖZELLİK: Batch Comparison - Birden fazla dosya karşılaştırma
"""
import os
import gzip
import pathlib
from collections import deque
import uuid

import dash
from dash import dcc, html, Input, Output, State, no_update, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from django.conf import settings

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Upload dizini
UPLOAD_ROOT = getattr(settings, 'FASTQ_UPLOAD_DIR',
                      os.path.join(settings.MEDIA_ROOT, 'fastq_uploads'))
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# Sabitler
CHUNK_SIZE_MB = 10
MAX_READS_TO_PROCESS = 100_000
PHRED_SCORE_RANGE = 42
MAX_GC_SAMPLES = 100_000
MAX_FILES = 2  # Maksimum dosya sayısı (2 dosya, her biri 5 MB)

# Dash uygulaması (DjangoDash — diğer bio-tool'lar ile aynı yapı)
from django_plotly_dash import DjangoDash

app = DjangoDash(
    'FastqAnalyzerApp',
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
    ],
    suppress_callback_exceptions=True,
)


# ------------------------------------------------------------------------------
# Yardımcı Fonksiyonlar
# ------------------------------------------------------------------------------

def safe_join(base_dir: str, filename: str) -> str:
    """Path traversal ataklarını önlemek için güvenli dosya yolu birleştirme."""
    base_path = pathlib.Path(base_dir).resolve()
    safe_filename = os.path.basename(filename)
    file_path = (base_path / safe_filename).resolve()
    try:
        file_path.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Path traversal detected: {filename}")
    return str(file_path)


def is_gzip_file(path: str) -> bool:
    """Bir dosyanın gzip'li olup olmadığını kontrol eder."""
    if path.endswith(".gz"):
        return True
    try:
        with open(path, "rb") as f:
            return f.read(2) == b'\x1f\x8b'
    except Exception:
        return False


# ------------------------------------------------------------------------------
# FASTQ İşleme
# ------------------------------------------------------------------------------

def analyze_fastq(path: str, max_reads: int = MAX_READS_TO_PROCESS):
    """
    FASTQ dosyasını okur ve analiz eder.
    Returns: (quality_df, distributions, gc_data, base_counts, reads_processed, read_lengths)
    """
    is_gzipped = is_gzip_file(path)
    opener = gzip.open if is_gzipped else open

    estimated_read_length = 150

    # Veri yapılarını başlat
    if NUMPY_AVAILABLE:
        sums = np.zeros(estimated_read_length, dtype=np.float64)
        counts = np.zeros(estimated_read_length, dtype=np.int64)
    else:
        sums = [0.0] * estimated_read_length
        counts = [0] * estimated_read_length

    distributions = [[0] * PHRED_SCORE_RANGE for _ in range(estimated_read_length)]
    gc_contents = deque(maxlen=MAX_GC_SAMPLES)
    base_counts = {'A': 0, 'T': 0, 'G': 0, 'C': 0, 'N': 0}
    read_lengths = []

    read_count = 0

    try:
        with opener(path, "rt", errors='ignore') as fh:
            while read_count < max_reads:
                # FASTQ bloğunu oku (4 satır)
                header = fh.readline()
                if not header:
                    break

                seq = fh.readline()
                plus = fh.readline()
                qual = fh.readline()

                if not qual:
                    break

                read_count += 1

                # Kalite skorları
                qline = qual.rstrip("\n")
                L_qual = len(qline)
                read_lengths.append(L_qual)

                if L_qual > 0:
                    # Dizileri genişlet
                    if NUMPY_AVAILABLE:
                        if len(sums) < L_qual:
                            extend_len = L_qual - len(sums)
                            sums = np.concatenate([sums, np.zeros(extend_len, dtype=np.float64)])
                            counts = np.concatenate([counts, np.zeros(extend_len, dtype=np.int64)])
                            distributions.extend([[0] * PHRED_SCORE_RANGE for _ in range(extend_len)])

                        qline_arr = np.frombuffer(qline.encode(), dtype=np.uint8) - 33
                        valid_mask = (qline_arr >= 0) & (qline_arr < PHRED_SCORE_RANGE)

                        for i in range(min(L_qual, len(sums))):
                            if i < len(qline_arr) and valid_mask[i]:
                                q = int(qline_arr[i])
                                sums[i] += q
                                counts[i] += 1
                                distributions[i][q] += 1
                    else:
                        if len(sums) < L_qual:
                            extend_len = L_qual - len(sums)
                            sums.extend([0.0] * extend_len)
                            counts.extend([0] * extend_len)
                            distributions.extend([[0] * PHRED_SCORE_RANGE for _ in range(extend_len)])

                        for i, ch in enumerate(qline):
                            if i >= len(sums):
                                break
                            q = ord(ch) - 33
                            if 0 <= q < PHRED_SCORE_RANGE:
                                sums[i] += q
                                counts[i] += 1
                                distributions[i][q] += 1

                # GC ve Baz İçeriği
                sequence = seq.strip().upper()
                L_seq = len(sequence)

                if L_seq > 0:
                    for base in sequence:
                        if base in base_counts:
                            base_counts[base] += 1

                    gc_count = sequence.count('G') + sequence.count('C')
                    gc_contents.append((gc_count / L_seq) * 100)

        # Ortalama kaliteleri hesapla
        if NUMPY_AVAILABLE:
            means = [float(s / c) if c > 0 else None for s, c in zip(sums, counts)]
        else:
            means = [(s / c) if c > 0 else None for s, c in zip(sums, counts)]

        quality_df = pd.DataFrame({
            "Base Position": list(range(1, len(means) + 1)),
            "Average Quality Score": means
        })

        return quality_df, distributions, list(gc_contents), base_counts, read_count, read_lengths

    except Exception as e:
        raise Exception(f"FASTQ işleme hatası: {str(e)}")


# ------------------------------------------------------------------------------
# Grafik Oluşturma
# ------------------------------------------------------------------------------

def create_fastqc_style_plot(distributions_data, mean_data_df, title, lang='en'):
    from dash_apps.i18n_helper import t
    """FastQC benzeri kutu (boxplot) ve çizgi grafiği oluşturur."""
    fig = go.Figure()

    # Arka plan renk bölgeleri
    fig.add_shape(
        type="rect", xref="paper", x0=0, x1=1, yref="y", y0=0, y1=20,
        fillcolor="rgba(255, 0, 0, 0.2)", layer="below", line_width=0
    )
    fig.add_shape(
        type="rect", xref="paper", x0=0, x1=1, yref="y", y0=20, y1=28,
        fillcolor="rgba(255, 215, 0, 0.2)", layer="below", line_width=0
    )
    fig.add_shape(
        type="rect", xref="paper", x0=0, x1=1, yref="y", y0=28, y1=42,
        fillcolor="rgba(0, 255, 0, 0.2)", layer="below", line_width=0
    )

    positions = []
    p10_list, p25_list, p50_list, p75_list, p90_list = [], [], [], [], []

    for i, binned_scores in enumerate(distributions_data):
        total_count = sum(binned_scores)
        if total_count == 0:
            continue
        positions.append(i + 1)

        p10_list.append(_find_percentile(binned_scores, 10, total_count))
        p25_list.append(_find_percentile(binned_scores, 25, total_count))
        p50_list.append(_find_percentile(binned_scores, 50, total_count))
        p75_list.append(_find_percentile(binned_scores, 75, total_count))
        p90_list.append(_find_percentile(binned_scores, 90, total_count))

    fig.update_layout(
        title=title,
        xaxis_title=t('fq_g_base_pos', lang),
        yaxis_title=t('fq_g_quality_score', lang),
        yaxis_range=[0, 42],
        template="plotly_white",
        height=500
    )

    if not positions:
        return fig

    fig.add_trace(go.Box(
        x=positions,
        q1=p25_list,
        median=p50_list,
        q3=p75_list,
        lowerfence=p10_list,
        upperfence=p90_list,
        name=t('fq_g_quality_dist', lang),
        fillcolor='rgba(255, 255, 0, 0.7)',
        line=dict(color='black', width=1),
        marker_opacity=0,
        boxpoints=False
    ))

    fig.add_trace(go.Scatter(
        x=positions,
        y=p50_list,
        mode='lines',
        line=dict(color='red', width=2),
        name=t('fq_g_median', lang)
    ))

    if mean_data_df is not None and not mean_data_df.empty:
        fig.add_trace(go.Scatter(
            x=mean_data_df["Base Position"],
            y=mean_data_df["Average Quality Score"],
            mode='lines',
            line=dict(color='blue', width=2),
            name=t('fq_g_mean', lang)
        ))

    return fig


def _find_percentile(binned_scores, p, total_count):
    """Gruplandırılmış veriden percentile bulur."""
    if total_count == 0:
        return 0
    p_count = (p / 100.0) * total_count
    cumulative_count = 0
    for score, count in enumerate(binned_scores):
        cumulative_count += count
        if cumulative_count >= p_count:
            return score
    return PHRED_SCORE_RANGE - 1


def detect_batch_issues(batch_results, lang='en'):
    """Batch'ler arasındaki anormallikleri tespit eder."""
    from dash_apps.i18n_helper import t
    warnings = []

    if len(batch_results) < 2:
        return warnings

    # Metrikleri topla
    qualities = {name: r['mean_quality'] for name, r in batch_results.items()}
    gcs = {name: r['mean_gc'] for name, r in batch_results.items()}
    lengths = {name: r['mean_length'] for name, r in batch_results.items()}
    read_counts = {name: r['reads_processed'] for name, r in batch_results.items()}

    # 1. Kalite Farkı Kontrolü
    max_qual = max(qualities.values())
    min_qual = min(qualities.values())
    qual_diff = max_qual - min_qual

    if qual_diff > 5:
        max_file = max(qualities, key=qualities.get)
        min_file = min(qualities, key=qualities.get)
        warnings.append({
            'level': 'danger',
            'icon': 'fa-exclamation-triangle',
            'title': t('fq_anom_crit_quality', lang),
            'message': t('fq_msg_crit_quality', lang).replace('{diff}', f'{qual_diff:.1f}').replace('{maxf}', max_file).replace('{maxq}', f'{max_qual:.1f}').replace('{minf}', min_file).replace('{minq}', f'{min_qual:.1f}')
        })
    elif qual_diff > 3:
        warnings.append({
            'level': 'warning',
            'icon': 'fa-exclamation-circle',
            'title': t('fq_anom_mid_quality', lang),
            'message': t('fq_msg_mid_quality', lang).replace('{diff}', f'{qual_diff:.1f}')
        })

    # 2. GC İçeriği Kontrolü
    max_gc = max(gcs.values())
    min_gc = min(gcs.values())
    gc_diff = max_gc - min_gc

    if gc_diff > 10:
        max_file = max(gcs, key=gcs.get)
        min_file = min(gcs, key=gcs.get)
        warnings.append({
            'level': 'danger',
            'icon': 'fa-dna',
            'title': t('fq_anom_gc_incons', lang),
            'message': t('fq_msg_gc_incons', lang).replace('{diff}', f'{gc_diff:.1f}').replace('{maxf}', max_file).replace('{maxg}', f'{max_gc:.1f}').replace('{minf}', min_file).replace('{ming}', f'{min_gc:.1f}')
        })
    elif gc_diff > 5:
        warnings.append({
            'level': 'warning',
            'icon': 'fa-dna',
            'title': 'GC İçeriği Farklılığı',
            'message': f"GC içeriği %{gc_diff:.1f} fark gösteriyor. Örnekler farklı dokulardan olabilir."
        })

    # 3. Read Length Kontrolü
    max_len = max(lengths.values())
    min_len = min(lengths.values())
    len_ratio = max_len / min_len if min_len > 0 else 0

    if len_ratio > 2:
        max_file = max(lengths, key=lengths.get)
        min_file = min(lengths, key=lengths.get)
        warnings.append({
            'level': 'danger',
            'icon': 'fa-ruler',
            'title': 'Read Length Uyumsuzluğu',
            'message': f"Read length'ler {len_ratio:.1f}x farklı! "
                       f"En uzun: {max_file} ({max_len:.0f} bp), "
                       f"En kısa: {min_file} ({min_len:.0f} bp). "
                       f"Farklı teknolojiler mi kullanıldı?"
        })
    elif len_ratio > 1.5:
        warnings.append({
            'level': 'warning',
            'icon': 'fa-ruler',
            'title': 'Read Length Farklılığı',
            'message': f"Read length'ler {len_ratio:.1f}x farklı. Trimming farklılıkları olabilir."
        })

    # 4. Okuma Sayısı Dengesizliği
    max_reads = max(read_counts.values())
    min_reads = min(read_counts.values())
    reads_ratio = max_reads / min_reads if min_reads > 0 else 0

    if reads_ratio > 10:
        max_file = max(read_counts, key=read_counts.get)
        min_file = min(read_counts, key=read_counts.get)
        warnings.append({
            'level': 'warning',
            'icon': 'fa-balance-scale',
            'title': 'Dengesiz Okuma Sayısı',
            'message': f"Okuma sayıları {reads_ratio:.1f}x farklı! "
                       f"En fazla: {max_file} ({max_reads:,}), "
                       f"En az: {min_file} ({min_reads:,}). "
                       f"Multiplexing problemi olabilir."
        })

    # 5. AT/GC Oranı Kontrolü (Base Composition)
    for name, result in batch_results.items():
        base_pct = result['base_pct']
        at_content = base_pct.get('A', 0) + base_pct.get('T', 0)
        gc_content = base_pct.get('G', 0) + base_pct.get('C', 0)

        # Chargaff kuralı: A≈T ve G≈C
        a_t_diff = abs(base_pct.get('A', 0) - base_pct.get('T', 0))
        g_c_diff = abs(base_pct.get('G', 0) - base_pct.get('C', 0))

        if a_t_diff > 5 or g_c_diff > 5:
            warnings.append({
                'level': 'warning',
                'icon': 'fa-dna',
                'title': f"{t('fq_anom_chargaff', lang)} ({name})",
                'message': t('fq_msg_chargaff', lang).replace('{at}', f'{a_t_diff:.1f}').replace('{gc}', f'{g_c_diff:.1f}')
            })

    # 6. Genel Değerlendirme
    if not warnings:
        warnings.append({
            'level': 'success',
            'icon': 'fa-check-circle',
            'title': 'Batchler Uyumlu',
            'message': 'Tüm batchler benzer kalite ve kompozisyon gösteriyor.Birleştirilebilir.'
        })

    return warnings


def create_batch_comparison_plots(batch_results, lang='en'):
    """Batch'leri karşılaştıran grafikler oluşturur."""
    from dash_apps.i18n_helper import t

    # 1. Kalite Karşılaştırma
    fig_quality = go.Figure()

    colors = px.colors.qualitative.Plotly
    for i, (file_name, result) in enumerate(batch_results.items()):
        quality_df = result['quality_df']
        fig_quality.add_trace(go.Scatter(
            x=quality_df["Base Position"],
            y=quality_df["Average Quality Score"],
            mode='lines',
            name=file_name,
            line=dict(color=colors[i % len(colors)], width=2)
        ))

    fig_quality.update_layout(
        title=t('fq_g_batch_quality', lang),
        xaxis_title=t('fq_g_base_pos', lang),
        yaxis_title=t('fq_g_avg_quality', lang),
        template="plotly_white",
        height=500,
        hovermode='x unified'
    )

    # 2. GC İçerik Karşılaştırma
    fig_gc = go.Figure()

    for i, (file_name, result) in enumerate(batch_results.items()):
        gc_data = result['gc_data']
        fig_gc.add_trace(go.Histogram(
            x=gc_data,
            name=file_name,
            opacity=0.6,
            nbinsx=50
        ))

    fig_gc.update_layout(
        title=t('fq_g_batch_gc', lang),
        xaxis_title=t('fq_g_gc_content', lang),
        yaxis_title=t('fq_g_frequency', lang),
        template="plotly_white",
        height=500,
        barmode='overlay'
    )

    # 3. Read Length Karşılaştırma
    fig_length = go.Figure()

    for i, (file_name, result) in enumerate(batch_results.items()):
        read_lengths = result['read_lengths']
        fig_length.add_trace(go.Violin(
            y=read_lengths,
            name=file_name,
            box_visible=True,
            meanline_visible=True
        ))

    fig_length.update_layout(
        title=t('fq_g_batch_length', lang),
        yaxis_title=t('fq_g_read_length', lang),
        template="plotly_white",
        height=500
    )

    # 4. Özet İstatistikler Tablosu
    stats_data = []
    for file_name, result in batch_results.items():
        stats_data.append({
            t('fq_col_file', lang): file_name,
            t('fq_col_reads', lang): f"{result['reads_processed']:,}",
            t('fq_col_quality', lang): f"{result['mean_quality']:.2f}",
            t('fq_col_gc', lang): f"{result['mean_gc']:.2f}",
            t('fq_col_length', lang): f"{result['mean_length']:.1f}",
            'A (%)': f"{result['base_pct']['A']:.1f}",
            'T (%)': f"{result['base_pct']['T']:.1f}",
            'G (%)': f"{result['base_pct']['G']:.1f}",
            'C (%)': f"{result['base_pct']['C']:.1f}",
        })

    df_stats = pd.DataFrame(stats_data)

    return fig_quality, fig_gc, fig_length, df_stats


# ------------------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------------------

def create_static_navbar():
    """Statik navbar — ana navbar (create_main_navbar) ile görsel uyumlu."""
    bio_tools_dropdown = dbc.DropdownMenu(
        label="Biyoinformatik Araçları",
        children=[
            dbc.DropdownMenuItem("Temel Araçlar", header=True),
            dbc.DropdownMenuItem("Sekans Analiz Aracı", href="/bio-tools/sequence-analyzer/", external_link=True),
            dbc.DropdownMenuItem("Sekans Hizalama Aracı", href="/bio-tools/sequence-alignment/", external_link=True),
            dbc.DropdownMenuItem("3D Molekül Görüntüleyici", href="/bio-tools/molecule-viewer/", external_link=True),
            dbc.DropdownMenuItem("Mutasyon Etki Tahmincisi", href="/bio-tools/mutation-predictor/", external_link=True),
            dbc.DropdownMenuItem("Bakteri Tasarımcısı", href="/bio-tools/bacterial-designer/", external_link=True),
            dbc.DropdownMenuItem("Pipeline Tasarımcısı", href="/bio-tools/pipeline-designer/", external_link=True),
            dbc.DropdownMenuItem("Primer Tasarımı", href="/bio-tools/primer-design/", external_link=True),
            dbc.DropdownMenuItem("FASTQ Analizi", href="/bio-tools/fastq-analyzer/", external_link=True, active=True),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Hassas Tıp", header=True),
            dbc.DropdownMenuItem("Farmakogenomik Analiz", href="/bio-tools/pharmacogenomics/", external_link=True),
            dbc.DropdownMenuItem("Varyant Önceliklendirme", href="/bio-tools/variant-prioritization/", external_link=True),
            dbc.DropdownMenuItem("Birleşik Öğrenme (FL)", href="/bio-tools/federated-learning/", external_link=True),
        ],
        nav=True,
        in_navbar=True,
    )

    # Ana navbar'daki "kullanıcı menüsü" dropdown'ını taklit et
    user_dropdown = dbc.DropdownMenu(
        label="Hesabım",
        children=[
            dbc.DropdownMenuItem("Profil / Özgeçmiş", href="/resume/", external_link=True),
            dbc.DropdownMenuItem("Kredilerim", href="/billing/credits/", external_link=True),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Çıkış Yap", href="/logout/", external_link=True),
        ],
        nav=True,
        in_navbar=True,
        align_end=True,
    )

    # Dil seçici (ana navbar ile aynı)
    language_dropdown = dbc.DropdownMenu(
        label="🌐 TR/EN",
        children=[
            dbc.DropdownMenuItem("Türkçe", href="/set-language/tr/", external_link=True),
            dbc.DropdownMenuItem("English", href="/set-language/en/", external_link=True),
        ],
        nav=True,
        in_navbar=True,
        align_end=True,
    )

    nav_items = [
        dbc.NavItem(dbc.NavLink("Blog", href="/", active="exact", external_link=True)),
        dbc.NavItem(dbc.NavLink("Makale Arama", href="/article-search/", active="exact", external_link=True)),
        bio_tools_dropdown,
        dbc.NavItem(dbc.NavLink("İletişim", href="/contact/", external_link=True, active="exact")),
        user_dropdown,
        language_dropdown,
    ]

    return dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(html.I(className="fas fa-brain fa-2x me-2 text-primary")),
                    dbc.Col(dbc.NavbarBrand("AI Blog", className="ms-2")),
                ], align="center", className="g-0"),
                href="/",
                style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                dbc.Nav(nav_items, className="ms-auto", navbar=True),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),
        ]),
        color="dark",
        dark=True,
        className="mb-4 shadow",
        sticky="top",
    )


def build_fastq_content(lang='en'):
    """FASTQ sayfasının içeriği (navbar hariç). Navbar view'da eklenir."""
    from dash_apps.i18n_helper import t
    return html.Div([
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="fq-lang-store", data=lang),
        dbc.Container([
            dcc.Store(id="files-store", data={}),  # {file_id: {path, name}}
        dcc.Store(id="analysis-results-store", data={}),  # {file_name: analysis_result}

        dbc.Row([
            # Sol panel
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(t('fq_files', lang)),
                    dbc.CardBody([
                        dcc.Upload(
                            id="dcc-upload",
                            children=html.Div([
                                html.I(className="fas fa-cloud-upload-alt fa-2x mb-2 text-primary"),
                                html.Br(),
                                t('fq_upload_text', lang).replace('{n}', str(MAX_FILES))
                            ]),
                            style={
                                'width': '100%', 'minHeight': '100px', 'lineHeight': '1.5',
                                'borderWidth': '2px', 'borderStyle': 'dashed',
                                'borderRadius': '8px', 'textAlign': 'center',
                                'padding': '20px', 'cursor': 'pointer'
                            },
                            multiple=True,
                            max_size=5 * 1024 * 1024,  # 5 MB
                        ),

                        html.Div(id="upload-status", className="mt-2"),
                        html.Hr(),
                        html.Div(id="files-list", className="mb-2"),
                        html.Hr(),
                        dbc.Button(
                            t('fq_analyze_all', lang),
                            id="btn-analyze-all",
                            color="primary",
                            className="w-100 mb-2",
                            disabled=True
                        ),
                        dbc.Button(
                            t('fq_compare_batch', lang),
                            id="btn-compare-batch",
                            color="success",
                            className="w-100",
                            disabled=True
                        ),
                        html.Div(id="analysis-status", className="mt-2")
                    ])
                ])
            ], width=12, lg=3),

            # Sağ panel - Grafikler
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5(t('fq_results', lang))),
                    dbc.CardBody([
                        dbc.Tabs(id="analysis-tabs", children=[
                            dbc.Tab(
                                label=t('fq_single_analysis', lang),
                                children=[
                                    html.Div(id="single-file-selector", className="mb-3 mt-3"),
                                    dcc.Loading(
                                        dcc.Graph(
                                            id="quality-plot",
                                            figure=go.Figure().update_layout(
                                                title_text=t('fq_upload_prompt', lang),
                                                template="plotly_white",
                                                height=500
                                            )
                                        )
                                    ),
                                    dcc.Loading(
                                        dcc.Graph(id="gc-histogram")
                                    ),
                                    dcc.Loading(
                                        dcc.Graph(id="base-content-plot")
                                    ),
                                ]
                            ),
                            dbc.Tab(
                                label=t('fq_batch_comparison', lang),
                                children=[
                                    dcc.Loading(
                                        dcc.Graph(
                                            id="batch-quality-comparison",
                                            figure=go.Figure().update_layout(
                                                title_text=t('fq_batch_min_files', lang),
                                                template="plotly_white",
                                                height=500
                                            )
                                        )
                                    ),
                                    dcc.Loading(
                                        dcc.Graph(id="batch-gc-comparison")
                                    ),
                                    dcc.Loading(
                                        dcc.Graph(id="batch-length-comparison")
                                    ),
                                    html.Div(id="batch-stats-table", className="mt-3")
                                ]
                            ),
                        ])
                    ])
                ])
            ], width=12, lg=9),
        ], className="mt-3"),
    ], fluid=True)
])


app.layout = build_fastq_content()


# ------------------------------------------------------------------------------
# Callbacks
# ------------------------------------------------------------------------------

@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
)
def toggle_navbar(n, is_open, **kwargs):
    if n:
        return not is_open
    return is_open


@app.callback(Output("fastq_analyzer", "active"), Input("url", "pathname"))
def toggle_active_link(pathname):
    from django.shortcuts import reverse
    try:
        return pathname == reverse('bio_tools:fastq_analyzer')
    except Exception:
        return False


@app.callback(
    [
        Output("upload-status", "children"),
        Output("files-store", "data"),
        Output("files-list", "children"),
        Output("btn-analyze-all", "disabled"),
    ],
    Input("dcc-upload", "contents"),
    [
        State("dcc-upload", "filename"),
        State("files-store", "data"),
        State("fq-lang-store", "data"),
    ],
)
def handle_upload(contents_list, file_names, current_files, lang=None, **kwargs):
    """dcc.Upload ile gelen base64 içeriği media klasörüne yazar."""
    import base64
    from dash_apps.i18n_helper import t
    lang = lang or 'en'

    if current_files is None:
        current_files = {}

    if not contents_list or not file_names:
        return t('fq_waiting', lang), current_files, _render_files_list(current_files), len(current_files) == 0

    # Tek dosya gelirse listeye çevir
    if not isinstance(contents_list, list):
        contents_list = [contents_list]
        file_names = [file_names]

    # Bu oturum için upload klasörü
    upload_id = str(uuid.uuid4())
    folder = os.path.join(UPLOAD_ROOT, upload_id)
    os.makedirs(folder, exist_ok=True)

    allowed_ext = ('.fastq', '.fq', '.fastq.gz', '.fq.gz', '.gz')
    uploaded_count = 0
    limit_reached = False
    rejected = []

    for content, file_name in zip(contents_list, file_names):
        if not content or not file_name:
            continue

        # Uzantı kontrolü
        if not file_name.lower().endswith(allowed_ext):
            rejected.append(file_name)
            continue

        # Duplicate kontrolü
        if any(f['name'] == file_name for f in current_files.values()):
            continue

        # Dosya sayısı limiti
        if len(current_files) >= MAX_FILES:
            limit_reached = True
            continue

        # base64 çöz ve diske yaz
        try:
            _header, b64data = content.split(',', 1)
            file_bytes = base64.b64decode(b64data)
        except Exception:
            rejected.append(file_name)
            continue

        # 5 MB sunucu tarafı kontrol
        if len(file_bytes) > 5 * 1024 * 1024:
            rejected.append(f"{file_name} (çok büyük)")
            continue

        file_path = os.path.join(folder, file_name)
        try:
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
        except OSError:
            rejected.append(file_name)
            continue

        current_files[str(uuid.uuid4())] = {
            'path': file_path,
            'name': file_name,
            'size_mb': len(file_bytes) / (1024 * 1024)
        }
        uploaded_count += 1

    files_list = _render_files_list(current_files)

    # Durum mesajı
    if limit_reached:
        status = dbc.Alert(
            t('fq_limit_reached', lang).replace('{n}', str(MAX_FILES)),
            color="warning"
        )
    elif rejected:
        status = dbc.Alert(
            t('fq_rejected', lang).replace('{count}', str(uploaded_count)).replace('{names}', ', '.join(rejected)),
            color="warning"
        )
    else:
        status = dbc.Alert(
            t('fq_uploaded', lang).replace('{count}', str(uploaded_count)).replace('{total}', str(len(current_files))),
            color="success" if uploaded_count > 0 else "info"
        )

    return status, current_files, files_list, len(current_files) == 0


def _render_files_list(current_files):
    """Yüklenen dosyaların listesini gösterir."""
    if not current_files:
        return []
    return dbc.ListGroup([
        dbc.ListGroupItem(f"{info['name']} ({info['size_mb']:.1f} MB)")
        for info in current_files.values()
    ])


def _cleanup_empty_upload_dirs():
    """UPLOAD_ROOT altındaki boş upload_id klasörlerini siler."""
    try:
        if not os.path.isdir(UPLOAD_ROOT):
            return
        for entry in os.listdir(UPLOAD_ROOT):
            sub = os.path.join(UPLOAD_ROOT, entry)
            try:
                if os.path.isdir(sub) and not os.listdir(sub):
                    os.rmdir(sub)
            except OSError:
                pass
    except Exception as e:
        print(f"Boş klasör temizliği hatası: {e}")


@app.callback(
    [
        Output("analysis-results-store", "data"),
        Output("analysis-status", "children"),
        Output("btn-compare-batch", "disabled"),
        Output("single-file-selector", "children"),
    ],
    Input("btn-analyze-all", "n_clicks"),
    State("files-store", "data"),
    prevent_initial_call=True
)
def analyze_all_files(n_clicks, files_data, **kwargs):
    """Tüm dosyaları analiz et"""
    if not n_clicks or not files_data:
        return {}, "", True, ""

    try:
        results = {}

        for file_id, file_info in files_data.items():
            file_path = file_info['path']
            file_name = file_info['name']

            # Analiz yap
            quality_df, distributions, gc_data, base_counts, reads_processed, read_lengths = analyze_fastq(file_path, 2)

            # Özet istatistikler
            mean_quality = quality_df["Average Quality Score"].mean()
            mean_gc = sum(gc_data) / len(gc_data) if gc_data else 0
            mean_length = sum(read_lengths) / len(read_lengths) if read_lengths else 0

            total_bases = sum(base_counts.values())
            base_pct = {base: (count / total_bases * 100) if total_bases > 0 else 0
                        for base, count in base_counts.items()}

            results[file_name] = {
                'quality_df': quality_df.to_dict(),
                'distributions': distributions,
                'gc_data': gc_data,
                'base_counts': base_counts,
                'reads_processed': reads_processed,
                'read_lengths': read_lengths,
                'mean_quality': mean_quality,
                'mean_gc': mean_gc,
                'mean_length': mean_length,
                'base_pct': base_pct,
            }

            # Dosyayı sil (ve klasör boşaldıysa klasörü de sil)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                # Üst klasör (upload_id klasörü) boşsa onu da kaldır
                parent_dir = os.path.dirname(file_path)
                if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
            except Exception as e:
                print(f"Dosya/klasör silinirken hata: {e}")

        # Döngü bitti — UPLOAD_ROOT altındaki boş klasörleri temizle (güvenlik)
        _cleanup_empty_upload_dirs()

        status = dbc.Alert(
            f"✓ {len(results)} dosya analiz edildi!",
            color="success"
        )

        # Tek dosya seçici
        file_selector = dbc.Select(
            id="single-file-select",
            options=[{"label": name, "value": name} for name in results.keys()],
            value=list(results.keys())[0] if results else None
        )

        return results, status, False, file_selector

    except Exception as e:
        error_status = dbc.Alert(f"Hata: {str(e)}", color="danger")
        return {}, error_status, True, ""


@app.callback(
    [
        Output("quality-plot", "figure"),
        Output("gc-histogram", "figure"),
        Output("base-content-plot", "figure"),
    ],
    Input("single-file-select", "value"),
    State("analysis-results-store", "data"),
    State("fq-lang-store", "data"),
)
def update_single_file_plots(selected_file, results, lang=None, **kwargs):
    """Seçili dosyanın grafiklerini güncelle"""
    from dash_apps.i18n_helper import t
    lang = lang or 'en'
    if not selected_file or not results or selected_file not in results:
        return no_update, no_update, no_update

    result = results[selected_file]

    # Quality plot
    quality_df = pd.DataFrame(result['quality_df'])
    fig_quality = create_fastqc_style_plot(
        result['distributions'],
        quality_df,
        f"{t('fq_g_quality_of', lang)} - {selected_file}",
        lang=lang
    )

    # GC histogram
    df_gc = pd.DataFrame({"GC Content (%)": result['gc_data']})
    fig_gc = px.histogram(
        df_gc,
        x="GC Content (%)",
        title=f"{t('fq_g_gc_dist_of', lang)} - {selected_file}",
        nbins=50
    )
    fig_gc.update_layout(template="plotly_white", height=400)

    # Base content
    df_bases = pd.DataFrame(
        list(result['base_counts'].items()),
        columns=["Baz", "Sayı"]
    )
    fig_base = px.bar(
        df_bases,
        x="Baz",
        y="Sayı",
        title=f"Baz Kompozisyonu - {selected_file}",
        color="Baz"
    )
    fig_base.update_layout(template="plotly_white", height=400)

    return fig_quality, fig_gc, fig_base


@app.callback(
    [
        Output("batch-quality-comparison", "figure"),
        Output("batch-gc-comparison", "figure"),
        Output("batch-length-comparison", "figure"),
        Output("batch-stats-table", "children"),
    ],
    Input("btn-compare-batch", "n_clicks"),
    State("analysis-results-store", "data"),
    State("fq-lang-store", "data"),
    prevent_initial_call=True
)
def compare_batches(n_clicks, results, lang=None, **kwargs):
    """Batch karşılaştırma grafiklerini oluştur"""
    from dash_apps.i18n_helper import t
    lang = lang or 'en'
    if not n_clicks or not results or len(results) < 2:
        return no_update, no_update, no_update, no_update

    try:
        # DataFrame'leri yeniden oluştur
        batch_results = {}
        for file_name, result in results.items():
            batch_results[file_name] = {
                'quality_df': pd.DataFrame(result['quality_df']),
                'gc_data': result['gc_data'],
                'read_lengths': result['read_lengths'],
                'reads_processed': result['reads_processed'],
                'mean_quality': result['mean_quality'],
                'mean_gc': result['mean_gc'],
                'mean_length': result['mean_length'],
                'base_pct': result['base_pct'],
            }

        # Karşılaştırma grafiklerini oluştur
        fig_quality, fig_gc, fig_length, df_stats = create_batch_comparison_plots(batch_results, lang=lang)

        # Otomatik uyarı sistemi
        warnings = detect_batch_issues(batch_results, lang=lang)

        # Uyarı kartları
        warning_cards = []
        for warning in warnings:
            color_map = {
                'success': 'success',
                'warning': 'warning',
                'danger': 'danger'
            }

            warning_cards.append(
                dbc.Alert([
                    html.I(className=f"fas {warning['icon']} me-2"),
                    html.Strong(warning['title'] + ": "),
                    html.Span(warning['message'])
                ], color=color_map.get(warning['level'], 'info'), className="mb-2")
            )

        # İstatistik tablosu
        table_content = html.Div([
            html.H5(t('fq_qc_title', lang), className="mt-3 mb-3"),
            html.Div(warning_cards),
            html.Hr(),
            html.H5(t('fq_detailed_stats', lang), className="mt-3 mb-3"),
            dbc.Table.from_dataframe(
                df_stats,
                striped=True,
                bordered=True,
                hover=True,
                responsive=True,
            )
        ])

        return fig_quality, fig_gc, fig_length, table_content

    except Exception as e:
        error_fig = go.Figure().update_layout(
            title_text=f"Hata: {str(e)}",
            template="plotly_white"
        )
        return error_fig, error_fig, error_fig, dbc.Alert(f"Hata: {str(e)}", color="danger")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)