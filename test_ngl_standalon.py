# -*- coding: utf-8 -*-
"""
Büyük FASTQ (.fastq, .fastq.gz) dosyaları için Gelişmiş Dash Uygulaması

YENİ ÖZELLİKLER (Kullanıcı İsteği):
- HATA DÜZELTMESİ: 'Callback error... ValueError: Invalid property...
  'medianline' hatası düzeltildi.
- GÜNCELLEME: FastQC stili kırmızı medyan çizgisi artık 'go.Box'
  içinde değil, 'go.Scatter' ile ayrıca çiziliyor.
- GÜNCELLEME: Grafik efsanesi (legend) 'Ortalama' ve 'Medyan'
  çizgilerini gösterecek şekilde ayarlandı.
- YENİ: 'Kalite Skoru' grafiği, FastQC (Box Plot) stiline
  dönüştürüldü.
- YENİ: Grafik artık Ortalama (mavi çizgi), Medyan (kırmızı çizgi),
  Çeyrekler (sarı kutu) ve 10./90. Yüzdelik Dilimleri (bıyıklar)
  gösteriyor.
- YENİ: Grafiğe FastQC stili Kırmızı/Sarı/Yeşil arkaplan bölgeleri
  eklendi.
- GÜNCELLEME: 'compute_quality_means_streaming' fonksiyonu artık
  her pozisyon için tam kalite skoru dağılımını hesaplıyor.
- GÜNCELLEME: Gzip (.gz) dosyaları için de analiz ilerleme çubuğu
  desteği eklendi (sıkıştırılmış dosya boyutu üzerinden).
- YENİ GÜNCELLEMELER (KULLANICI İSTEĞİ - 2):
- YENİ: Analiz İlerleme Çubuğu ('parse-progress') mantığı değiştirildi:
    - "Tümü" modu: Dosya boyutuna göre ilerler.
    - "Parça" (Chunk) modu: Başlangıç pozisyonuna kadar tararken 0% kalır,
      sadece seçilen parçayı işlerken 0-100% arası ilerler.
- YENİ: "Analizi Başlat" düğmesi artık dinamik:
    - Tıklanınca: "Analiz Başlatılıyor..." (Disabled / Danger) olur.
    - Çalışırken: "Durdur" (Danger) düğmesine dönüşür.
    - Durdurulunca: "Durduruluyor..." (Disabled / Warning) olur.
- YENİ: Analizi "Durdur" düğmesiyle iptal etme özelliği eklendi.
- HATA DÜZELTMESİ: Yeni bir analiz başlatıldığında eski analiz verilerinin
  grafiklere sızması (state contamination) hatası düzeltildi.
  Artık her "Analizi Başlat" komutu, önceki tüm iş verilerini
  hafızadan temizler (JOBS.clear()).

YENİ GÜNCELLEMELER (KULLANICI İSTEĞİ - 4):
- HATA DÜZELTMESİ: 'A nonexistent object was used...' hatası düzeltildi.
  Dinamik "Başlat/Durdur" düğmeleri için string ID'ler yerine
  Dash "Pattern Matching" (Kalıp Eşleştirme) callback'leri
  (id={'type': 'btn-analysis', 'index': ...}) kullanılmaya başlandı.

- Çalıştırma: python app.py
"""
import os
import gzip
import threading
import time
import uuid
import json
from typing import Optional, Callable, Dict, List, Any

import dash
from dash import dcc, html, Input, Output, State, no_update, callback_context, ALL
import dash_bootstrap_components as dbc
import dash_uploader as du
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------------------------
# Yapılandırmalar
# ------------------------------------------------------------------------------

UPLOAD_ROOT = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

BACKGROUND_UPDATE_INTERVAL_SECONDS = 0.5
CHUNK_SIZE_MB = 100
READS_PER_CHUNK = 1_000_000
MAX_CHUNKS_TO_GENERATE = 10

PHRED_SCORE_RANGE = 42

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.MATERIA],
    suppress_callback_exceptions=True,
)
server = app.server
du.configure_upload(app, UPLOAD_ROOT, use_upload_id=True)


# ------------------------------------------------------------------------------
# dash-uploader yol yardımcısı (Değişiklik Yok)
# ------------------------------------------------------------------------------

def du_get_upload_path(root: str, upload_id: str) -> str:
    import dash_uploader as du
    get_path = getattr(du, "get_upload_path", None)
    if callable(get_path):
        try:
            return get_path(root, upload_id)
        except TypeError:
            pass
    return os.path.join(root, upload_id)


# ------------------------------------------------------------------------------
# FASTQ Yardımcıları (Değişiklik Yok)
# ------------------------------------------------------------------------------

def is_gzip_file(path: str) -> bool:
    if path.endswith(".gz"): return True
    try:
        with open(path, "rb") as f:
            return f.read(2) == b'\x1f\x8b'
    except Exception:
        return False


def compute_quality_means_streaming(
        path: str,
        progress_cb: Optional[Callable[[int], None]] = None,
        update_cb: Optional[Callable[[Dict], None]] = None,
        read_count_cb: Optional[Callable[[int], None]] = None,
        start_read: Optional[int] = None,
        end_read: Optional[int] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
):
    is_gzipped = is_gzip_file(path)
    opener = gzip.open if is_gzipped else open

    sums, counts = [], []
    distributions: List[List[int]] = []
    gc_contents: List[float] = []
    base_counts: Dict[str, int] = {'A': 0, 'T': 0, 'G': 0, 'C': 0, 'N': 0}

    try:
        total_size = os.path.getsize(path)
    except Exception:
        total_size = None

    bytes_read = 0
    last_update_time = time.time()

    start_at = int(start_read) if start_read and start_read > 0 else 1
    end_at = int(end_read) if end_read and end_read > 0 else float('inf')

    read_count = 0
    reads_processed_in_range = 0

    with opener(path, "rt", errors='ignore') as fh:
        while True:
            if cancel_check and cancel_check():
                break

            header = fh.readline()
            if not header: break

            seq, plus, qual = fh.readline(), fh.readline(), fh.readline()
            if not qual: break

            read_count += 1

            if read_count_cb: read_count_cb(read_count)

            if read_count < start_at:
                continue

            if read_count > end_at:
                break

            reads_processed_in_range += 1

            if progress_cb:
                if end_read is None or end_read == float('inf'):
                    # "Tümü" modu - dosya boyutunu kullan
                    if total_size:
                        if is_gzipped:
                            try:
                                compressed_bytes_read = fh.buffer.tell()
                                pct = min(99, int(compressed_bytes_read / max(total_size, 1) * 100))
                                progress_cb(pct)
                            except Exception:
                                pass
                        else:
                            bytes_read += len(header) + len(seq) + len(plus) + len(qual)
                            pct = min(99, int(bytes_read / max(total_size, 1) * 100))
                            progress_cb(pct)
                else:
                    # "Parça" modu - sadece işlenen okuma sayısını kullan
                    total_target_reads = end_at - start_at + 1
                    pct = min(99, int(reads_processed_in_range / max(total_target_reads, 1) * 100))
                    progress_cb(pct)

            qline = qual.rstrip("\n")

            L_qual = len(qline)
            if len(sums) < L_qual:
                extend_len = L_qual - len(sums)
                sums.extend([0.0] * extend_len)
                counts.extend([0] * extend_len)
                distributions.extend([[0] * PHRED_SCORE_RANGE for _ in range(extend_len)])

            for i, ch in enumerate(qline):
                q = ord(ch) - 33
                sums[i] += q
                counts[i] += 1
                if 0 <= q < PHRED_SCORE_RANGE:
                    distributions[i][q] += 1

            sequence = seq.strip().upper()
            L_seq = len(sequence)

            if L_seq > 0:
                for base in sequence:
                    if base in base_counts:
                        base_counts[base] += 1
                gc_count = sequence.count('G') + sequence.count('C')
                gc_contents.append((gc_count / L_seq) * 100)

            current_time = time.time()
            if update_cb and (current_time - last_update_time > BACKGROUND_UPDATE_INTERVAL_SECONDS):
                means = [(s / c) if c else None for s, c in zip(sums, counts)]
                update_payload = {
                    "quality_df_data": {"Base Position": list(range(1, len(means) + 1)),
                                        "Average Quality Score": means},
                    "distributions_data": distributions,
                    "gc_data": gc_contents,
                    "base_counts": base_counts,
                    "reads_processed_in_range": reads_processed_in_range
                }
                update_cb(update_payload)
                last_update_time = current_time

    if update_cb:
        means = [(s / c) if c else None for s, c in zip(sums, counts)]
        final_payload = {
            "quality_df_data": {"Base Position": list(range(1, len(means) + 1)), "Average Quality Score": means},
            "distributions_data": distributions,
            "gc_data": gc_contents,
            "base_counts": base_counts,
            "reads_processed_in_range": reads_processed_in_range
        }
        update_cb(final_payload)


# ------------------------------------------------------------------------------
# İş Yöneticisi (Job Manager) (Değişiklik Yok)
# ------------------------------------------------------------------------------

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def start_quality_job(
        job_id: str,
        path: str,
        start_read: Optional[int],
        end_read: Optional[int],
        selection_label: str,
):
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "running",
            "progress": 0,
            "error": None,
            "reads_scanned": 0,
            "reads_processed": 0,
            "start_time": time.time(),
            "data": None,
            "distributions": None,
            "gc_data": None,
            "base_counts": None,
            "data_version": 0,
            "selection_label": selection_label,
            "start_read": start_read,
            "end_read": end_read,
            "cancel_requested": False,
        }

    def cancel_check() -> bool:
        with JOBS_LOCK:
            if job_id in JOBS:
                return JOBS[job_id].get("cancel_requested", False)
            return True

    def progress_cb(pct: int):
        with JOBS_LOCK:
            if job_id in JOBS: JOBS[job_id]["progress"] = int(pct)

    def update_cb(current_payload: Dict):
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["data"] = current_payload.get("quality_df_data")
                JOBS[job_id]["distributions"] = current_payload.get("distributions_data")
                JOBS[job_id]["gc_data"] = current_payload.get("gc_data")
                JOBS[job_id]["base_counts"] = current_payload.get("base_counts")
                JOBS[job_id]["reads_processed"] = current_payload.get("reads_processed_in_range", 0)
                JOBS[job_id]["data_version"] += 1

    def read_count_cb(count: int):
        with JOBS_LOCK:
            if job_id in JOBS: JOBS[job_id]["reads_scanned"] = count

    try:
        compute_quality_means_streaming(
            path=path,
            progress_cb=progress_cb,
            update_cb=update_cb,
            read_count_cb=read_count_cb,
            start_read=start_read,
            end_read=end_read,
            cancel_check=cancel_check
        )

        was_cancelled = False
        with JOBS_LOCK:
            if job_id in JOBS:
                was_cancelled = JOBS[job_id].get("cancel_requested", False)

        if was_cancelled:
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["status"] = "cancelled"
                    JOBS[job_id]["error"] = "Kullanıcı tarafından durduruldu."
        else:
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["progress"] = 100
                    JOBS[job_id]["status"] = "done"

    except Exception as e:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["error"] = str(e)
                JOBS[job_id]["status"] = "error"


# ------------------------------------------------------------------------------
# FastQC Grafik Yardımcı Fonksiyonları (Değişiklik Yok)
# ------------------------------------------------------------------------------

def _find_percentile_from_binned(binned_scores, p, total_count):
    if total_count == 0:
        return 0

    p_count = (p / 100.0) * total_count
    cumulative_count = 0

    for score, count in enumerate(binned_scores):
        cumulative_count += count
        if cumulative_count >= p_count:
            return score
    return PHRED_SCORE_RANGE - 1


def create_fastqc_style_plot(distributions_data, mean_data_df, title):
    fig = go.Figure()

    # 1. Arkaplan Bölgeleri
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=0, y1=20,
                  fillcolor="rgba(255, 0, 0, 0.2)", layer="below", line_width=0)
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=20, y1=28,
                  fillcolor="rgba(255, 215, 0, 0.2)", layer="below", line_width=0)
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=28, y1=42,
                  fillcolor="rgba(0, 255, 0, 0.2)", layer="below", line_width=0)

    # 2. Box plot verilerini hesapla
    positions = []
    p10_list, p25_list, p50_list, p75_list, p90_list = [], [], [], [], []

    for i, binned_scores in enumerate(distributions_data):
        total_count = sum(binned_scores)
        if total_count == 0:
            continue

        positions.append(i + 1)
        p10_list.append(_find_percentile_from_binned(binned_scores, 10, total_count))
        p25_list.append(_find_percentile_from_binned(binned_scores, 25, total_count))
        p50_list.append(_find_percentile_from_binned(binned_scores, 50, total_count))
        p75_list.append(_find_percentile_from_binned(binned_scores, 75, total_count))
        p90_list.append(_find_percentile_from_binned(binned_scores, 90, total_count))

    # 5. Layout Ayarları (Önce ayarla)
    fig.update_layout(
        title=title,
        xaxis_title="Baz Pozisyonu",
        yaxis_title="Ortalama Kalite Skoru",
        yaxis_range=[0, 42],
        template="plotly_white",
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99)
    )

    if not positions:
        return fig

        # 3. Box plot'u ekle
    fig.add_trace(go.Box(
        x=positions,
        q1=p25_list,
        median=p50_list,
        q3=p75_list,
        lowerfence=p10_list,
        upperfence=p90_list,
        name="Kalite Dağılımı (10-90p)",
        fillcolor='rgba(255, 255, 0, 0.7)',
        line=dict(color='black', width=1),
        marker_opacity=0,
        boxpoints=False,
        showlegend=False
    ))

    # 4. Medyan (Median) çizgisini AYRI BİR TRACE olarak ekle
    fig.add_trace(go.Scatter(
        x=positions,
        y=p50_list,
        mode='lines',
        line=dict(color='red', width=2),
        name="Medyan Kalite"
    ))

    # 5. Ortalama (Mean) çizgisini ekle
    if mean_data_df is not None:
        fig.add_trace(go.Scatter(
            x=mean_data_df["Base Position"],
            y=mean_data_df["Average Quality Score"],
            mode='lines',
            line=dict(color='blue', width=2),
            name="Ortalama Kalite"
        ))

    return fig


# ------------------------------------------------------------------------------
# Arayüz (Layout) (GÜNCELLENDİ)
# ------------------------------------------------------------------------------

# <<< GÜNCELLENDİ: Düğmeler artık "Pattern Matching" için dictionary ID kullanıyor
default_start_button = dbc.Button("Analizi Başlat", id={"type": "btn-analysis", "index": "start"}, color="primary",
                                  className="mt-2 w-100", n_clicks=0)
loading_button = dbc.Button("Analiz Başlatılıyor...", id={"type": "btn-analysis", "index": "loading"}, color="danger",
                            disabled=True, className="mt-2 w-100")
stop_button = dbc.Button("Durdur", id={"type": "btn-analysis", "index": "stop"}, color="danger", className="mt-2 w-100",
                         n_clicks=0)
cancelling_button = dbc.Button("Durduruluyor...", id={"type": "btn-analysis", "index": "cancelling"}, color="warning",
                               disabled=True, className="mt-2 w-100")

app.layout = dbc.Container(
    [
        dcc.Store(id="uploaded-files-store", data=[]),
        dcc.Store(id="current-job-id", data=None),
        dcc.Store(id='data-version-store', data=0),
        dcc.Interval(id="poll-progress", interval=1000, n_intervals=0, disabled=True),

        dbc.Row([
            dbc.Col([dbc.Card([
                dbc.CardHeader("Veri Girişi ve Kontrol"),
                dbc.CardBody([
                    dcc.Loading(id="loading-upload", type="circle", children=[
                        du.Upload(id="du-upload", text="FASTQ (.fastq / .fastq.gz) dosyasını buraya bırakın veya seçin",
                                  filetypes=["fastq", "fq", "fastq.gz", "fq.gz", "gz"],
                                  chunk_size=CHUNK_SIZE_MB * 1024 * 1024,
                                  max_file_size=100_000 * 1024 * 1024,  # 100 GB
                                  upload_id=None),
                        html.Div(id="upload-status", style={"marginTop": "8px"}),
                        html.Small(
                            f"Yükleme parçası boyutu: {CHUNK_SIZE_MB} MB",
                            className="text-muted",
                            style={"marginTop": "-6px", "display": "block"}
                        )
                    ]),
                    html.Hr(),

                    dcc.Dropdown(
                        id="file-selector-dropdown",
                        placeholder="Dosya yükleyin, sonra buradan bir parça seçin",
                        className="mb-2"
                    ),

                    html.Div([
                        html.Small("İşleme Durumu: "),
                        html.Span(id="parse-status", children="Beklemede"),
                        dbc.Progress(
                            id="parse-progress", value=0, striped=True, animated=True,
                            label="0 okuma tarandı",
                            style={"marginTop": "6px", "height": "25px", "textAlign": "center"}
                        ),
                        html.Div(id="analysis-button-container", children=[
                            default_start_button
                        ]),
                    ]),
                ]),
            ])], width=12, lg=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Analiz Sonuçları")),
                    dbc.CardBody(
                        dbc.Tabs([
                            dbc.Tab(
                                label="Kalite Skoru",
                                children=[
                                    dcc.Loading(id="loading-plot", type="circle", delay_show=300, children=dcc.Graph(
                                        id="quality-plot",
                                        figure=go.Figure().update_layout(title_text="Analiz için bir dosya yükleyin.",
                                                                         template="plotly_white")
                                    ))
                                ]
                            ),
                            dbc.Tab(
                                label="GC Dağılılımı",
                                children=[
                                    dcc.Loading(id="loading-gc-hist", type="circle", delay_show=300, children=dcc.Graph(
                                        id="gc-histogram",
                                        figure=go.Figure().update_layout(title_text="GC dağılımı için analiz gerekli.",
                                                                         template="plotly_white")
                                    ))
                                ]
                            ),
                            dbc.Tab(
                                label="Baz Kompozisyonu",
                                children=[
                                    dcc.Loading(id="loading-base-plot", type="circle", delay_show=300,
                                                children=dcc.Graph(
                                                    id="base-content-plot",
                                                    figure=go.Figure().update_layout(
                                                        title_text="Baz sayıları için analiz gerekli.",
                                                        template="plotly_white")
                                                ))
                                ]
                            ),
                        ])
                    )
                ])
            ], width=12, lg=8),
        ], className="mt-3"),

    ], fluid=True
)


# ------------------------------------------------------------------------------
# Callback'ler
# ------------------------------------------------------------------------------

# <<< Callback 1 (Değişiklik Yok)
@app.callback(
    Output("upload-status", "children"),
    Output("uploaded-files-store", "data"),
    Output("parse-progress", "value", allow_duplicate=True),
    Output("parse-progress", "label", allow_duplicate=True),
    Input("du-upload", "isCompleted"),
    State("du-upload", "fileNames"),
    State("du-upload", "upload_id"),
    State("uploaded-files-store", "data"),
    prevent_initial_call=True,
)
def on_file_upload_and_generate_chunks(is_completed, file_names, upload_id, current_file_list):
    if not is_completed or not file_names or not upload_id:
        return "Yükleme başarısız.", no_update, no_update, no_update

    folder = du_get_upload_path(UPLOAD_ROOT, upload_id)
    file_name = file_names[0]
    path = os.path.join(folder, file_name)

    if not os.path.exists(path):
        return f"Hata: Yüklenen dosya sunucuda bulunamadı: {file_name}", no_update, no_update, no_update

    new_chunks = []

    all_reads_label = f"{file_name} (Tümü)"
    all_reads_value = json.dumps({
        "path": path, "start": 1, "end": None, "label": all_reads_label
    })
    new_chunks.append({"label": all_reads_label, "value": all_reads_value})

    for i in range(MAX_CHUNKS_TO_GENERATE):
        start = (i * READS_PER_CHUNK) + 1
        end = (i + 1) * READS_PER_CHUNK

        start_label = f"{start // 1_000_000}M" if start > 1_000_000 else "1"
        if start == 1: start_label = "1"
        end_label = f"{(end) // 1_000_000}M"

        chunk_label = f"{file_name} (Okuma {start_label} - {end_label})"
        chunk_value = json.dumps({
            "path": path, "start": start, "end": end, "label": chunk_label
        })
        new_chunks.append({"label": chunk_label, "value": chunk_value})

    updated_list = current_file_list + new_chunks
    status_text = f"Yüklendi: {file_name}. Analiz için bir parça seçin."
    return status_text, updated_list, 0, "0 okuma tarandı"


# <<< Callback 2 (Değişiklik Yok)
@app.callback(
    Output("file-selector-dropdown", "options"),
    Output("file-selector-dropdown", "value"),
    Input("uploaded-files-store", "data"),
    prevent_initial_call=True
)
def update_file_dropdown(file_list):
    if not file_list:
        return [], None
    return file_list, file_list[- (MAX_CHUNKS_TO_GENERATE + 1)]['value']


# <<< Callback 3 - Analiz Başlatma ve Takip Etme (TAMAMEN GÜNCELLENDİ)
@app.callback(
    Output("quality-plot", "figure"),
    Output("gc-histogram", "figure"),
    Output("base-content-plot", "figure"),
    Output("parse-status", "children"),
    Output("parse-progress", "value"),
    Output("poll-progress", "disabled"),
    Output("parse-progress", "label"),
    Output("data-version-store", "data"),
    Output("current-job-id", "data"),
    Output("analysis-button-container", "children"),
    # <<< GÜNCELLENDİ: Hata veren "btn-start" ve "btn-stop" Input'ları
    # "Pattern Matching" (Kalıp Eşleştirme) ile değiştirildi.
    Input({"type": "btn-analysis", "index": ALL}, "n_clicks"),
    Input("poll-progress", "n_intervals"),
    State("file-selector-dropdown", "value"),
    State("current-job-id", "data"),
    State("data-version-store", "data"),
    prevent_initial_call=True,
)
def start_or_poll_or_stop(
        n_clicks_list, n_intervals,  # <<< Değişti
        selected_value_json,
        job_id, last_known_version
):
    ctx = callback_context
    if not ctx.triggered:
        return (no_update,) * 10

    trig_id = ctx.triggered_id
    no_update_all = (no_update,) * 10

    # Hangi bileşenin tetiklediğini belirle
    trigger_type = None
    if trig_id == "poll-progress":
        trigger_type = "poll"
    elif isinstance(trig_id, dict):
        trigger_type = trig_id.get("index")  # "start" veya "stop" olabilir

    # 1. "Analizi Başlat" TIKLANDIĞINDA
    if trigger_type == "start":
        if not selected_value_json:
            status_text = "Lütfen önce bir dosya yükleyin ve bir parça seçin."
            return (no_update, no_update, no_update, status_text, no_update,
                    True, no_update, no_update, no_update, no_update)

        try:
            selection_data = json.loads(selected_value_json)
            path = selection_data['path']
            start_read = selection_data['start']
            end_read = selection_data['end']
            selection_label = selection_data['label']
        except Exception as e:
            status_text = f"Hata: Geçersiz dosya seçimi. {e}"
            return (no_update, no_update, no_update, status_text, no_update,
                    True, no_update, no_update, no_update, no_update)

        with JOBS_LOCK:
            JOBS.clear()

        job_id = str(uuid.uuid4())

        t = threading.Thread(
            target=start_quality_job,
            args=(job_id, path, start_read, end_read, selection_label),
            daemon=True
        )
        t.start()

        fig_calculating = go.Figure().update_layout(title_text="Hesaplanıyor...", template="plotly_white")

        return (fig_calculating, fig_calculating, fig_calculating,
                "Başlatılıyor...", 0, False, "0 okuma tarandı", 0, job_id, loading_button)

    # 2. "Durdur" TIKLANDIĞINDA
    if trigger_type == "stop":
        if job_id:
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["status"] = "cancelling"
                    JOBS[job_id]["cancel_requested"] = True

        return (no_update, no_update, no_update, "Durduruluyor...", no_update,
                False, no_update, no_update, no_update, cancelling_button)

    # 3. "poll-progress" (ZAMANLAYICI) TETİKLENDİĞİNDE
    if trigger_type == "poll":
        if not job_id: return no_update_all
        with JOBS_LOCK:
            job = JOBS.get(job_id)

        if not job:
            return (no_update, no_update, no_update, "Yeni analiz başlatıldı...", 0, True,
                    "Beklemede", no_update, no_update, default_start_button)

        status = job.get("status", "unknown")
        progress = job.get("progress", 0)
        reads_scanned = job.get("reads_scanned", 0)
        reads_processed = job.get("reads_processed", 0)
        start_time = job.get("start_time")
        job_version = job.get("data_version", 0)

        selection_label = job.get("selection_label", "Seçilen Aralık")
        start_read_job = job.get("start_read")
        end_read_job = job.get("end_read")

        formatted_time = ""
        if start_time:
            elapsed_seconds = int(time.time() - start_time)
            minutes, seconds = divmod(elapsed_seconds, 60)
            formatted_time = f"{minutes:02d}:{seconds:02d}"

        status_suffix = f"(İşlenen: {reads_processed:,} / Geçen Süre: {formatted_time})"

        status_text = "İşleniyor..."
        reads_label = f"{reads_scanned:,} okuma tarandı"

        if end_read_job is None:  # "Tümü" modu
            status_text = f"İşleniyor… {status_suffix}"
            reads_label = f"{reads_scanned:,} okuma tarandı"
        else:  # "Parça" modu
            total_target_reads = (end_read_job - start_read_job + 1) if end_read_job else 0
            if reads_processed > 0:
                status_text = f"İşleniyor… {status_suffix}"
                reads_label = f"{reads_processed:,} / {total_target_reads:,} okuma işlendi"
            else:
                status_text = f"Başlangıç pozisyonu taranıyor ({start_read_job:,})... {status_suffix}"
                reads_label = f"{reads_scanned:,} / {start_read_job:,} okuma tarandı"

        if status == "running":
            if job_version > last_known_version:
                data = job.get("data")
                distributions = job.get("distributions")
                gc_data = job.get("gc_data")
                base_counts = job.get("base_counts")

                fig_qual, fig_gc, fig_base = no_update, no_update, no_update

                title_qual = f"FASTQ Kalite Skoru ({selection_label}) (Hesaplanıyor...)"
                title_gc = f"GC İçerik Dağılımı ({selection_label}) (Hesaplanıyor...)"
                title_base = f"Baz Kompozisyonu ({selection_label}) (Hesaplanıyor...)"

                if (distributions is not None and len(distributions) > 0 and
                        data is not None and
                        data.get("Base Position") is not None and
                        data.get("Average Quality Score") is not None and
                        len(data.get("Base Position", [])) > 0):
                    df = pd.DataFrame(data)
                    fig_qual = create_fastqc_style_plot(distributions, df, title_qual)

                if gc_data is not None and len(gc_data) > 0:
                    df_gc = pd.DataFrame({"GC Content (%)": gc_data})
                    fig_gc = px.histogram(df_gc, x="GC Content (%)", title=title_gc)
                if base_counts is not None and len(base_counts) > 0:
                    df_bases = pd.DataFrame(list(base_counts.items()), columns=["Baz", "Sayı"])
                    fig_base = px.bar(df_bases, x="Baz", y="Sayı", title=title_base)

                return (fig_qual, fig_gc, fig_base, status_text, progress, False,
                        reads_label, job_version, no_update, stop_button)
            else:
                return (no_update, no_update, no_update, status_text, progress, False,
                        reads_label, no_update, no_update, stop_button)

        if status == "cancelling":
            return (no_update, no_update, no_update, "Durduruluyor...", progress, False,
                    reads_label, no_update, no_update, cancelling_button)

        if status == "cancelled":
            status_text = f"İptal edildi: Kullanıcı tarafından durduruldu. (Süre: {formatted_time})"
            error_label = f"İptal edildi ({reads_scanned:,} okuma tarandı)"
            return (no_update, no_update, no_update, status_text, progress, True,
                    error_label, no_update, no_update, default_start_button)

        if status == "error":
            err = job.get("error", "Bilinmeyen hata")
            status_text = f"Hata: {err} (Süre: {formatted_time})"
            error_label = f"Hata ({reads_scanned:,} okuma tarandı)"
            return (no_update, no_update, no_update, status_text, progress, True,
                    error_label, no_update, no_update, default_start_button)

        if status == "done":
            data = job.get("data")
            distributions = job.get("distributions")
            gc_data = job.get("gc_data")
            base_counts = job.get("base_counts")

            if (data is None or
                    data.get("Base Position") is None or
                    data.get("Average Quality Score") is None or
                    len(data.get("Base Position", [])) == 0 or
                    distributions is None or len(distributions) == 0 or
                    gc_data is None or len(gc_data) == 0 or
                    base_counts is None or len(base_counts) == 0 or
                    reads_processed == 0):

                if reads_scanned == 0:
                    status_text = "Hata: Dosyada hiç okuma bulunamadı."
                else:
                    start_str = f"{start_read_job:,}" if start_read_job else "1"
                    end_str = f"{end_read_job:,}" if end_read_job else "Tümü"
                    status_text = f"Hata: Seçilen '{selection_label}' aralığında ('{start_str}' - '{end_str}') veri bulunamadı."

                return (no_update, no_update, no_update, status_text, 100, True,
                        f"{reads_scanned:,} okuma (Veri yok)", no_update, no_update, default_start_button)

            title_qual_done = f"FASTQ Kalite Skoru ({selection_label}) (Tamamlandı)"
            title_gc_done = f"GC İçerik Dağılımı ({selection_label}) (Tamamlandı)"
            title_base_done = f"Baz Kompozisyonu ({selection_label}) (Tamamlandı)"

            df = pd.DataFrame(data)
            fig_qual_done = create_fastqc_style_plot(distributions, df, title_qual_done)

            df_gc = pd.DataFrame({"GC Content (%)": gc_data})
            fig_gc_done = px.histogram(df_gc, x="GC Content (%)", title=title_gc_done)

            df_bases = pd.DataFrame(list(base_counts.items()), columns=["Baz", "Sayı"])
            fig_base_done = px.bar(df_bases, x="Baz", y="Sayı", title=title_base_done)

            status_text = f"Tamamlandı (Toplam Süre: {formatted_time})"
            final_label = f"Tamamlandı ({reads_scanned:,} okuma tarandı, {reads_processed:,} işlendi)"
            return (fig_qual_done, fig_gc_done, fig_base_done, status_text, 100, True,
                    final_label, job_version, no_update, default_start_button)

    return no_update_all


# ------------------------------------------------------------------------------
# Ana giriş
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, port=8000)