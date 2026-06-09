# analysis/tasks.py
# NOT: Celery kaldırıldı — task'lar artık düz Python fonksiyonları.
# FASTQ analizi view katmanında threading ile arka planda çalıştırılır.

import os
import gzip
import time
from collections import Counter
from typing import Optional, Callable, Dict, List

from django.utils import timezone
from datetime import timedelta
from .models import FastqUpload, AnalysisJob
import logging

logger = logging.getLogger(__name__)

# --- Eski Dash uygulamasından taşınan yardımcı fonksiyonlar (Değişiklik Yok) ---

TOP_N_SEQUENCES = 50
UPDATE_FREQUENCY_READS = 100_000 # Veritabanını güncelleme sıklığı

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
):
    opener = gzip.open if is_gzip_file(path) else open
    sums, counts = [], []
    gc_contents: List[float] = []
    base_counts: Dict[str, int] = {'A': 0, 'T': 0, 'G': 0, 'C': 0, 'N': 0}
    sequence_counts = Counter()
    total_size = os.path.getsize(path)
    bytes_read = 0
    read_count = 0

    with opener(path, "rt", errors='ignore') as fh:
        while True:
            header, seq, plus, qual = fh.readline(), fh.readline(), fh.readline(), fh.readline()
            if not qual: break

            read_count += 1
            if read_count % 1000 == 0: # Her 1000 okumada bir ilerlemeyi güncelle
                if read_count_cb: read_count_cb(read_count)

            if total_size and progress_cb:
                bytes_read += len(header) + len(seq) + len(plus) + len(qual)
                pct = min(99, int(bytes_read / max(total_size, 1) * 100))
                progress_cb(pct)

            qline = qual.rstrip("\n")
            L_qual = len(qline)
            if len(sums) < L_qual:
                sums.extend([0.0] * (L_qual - len(sums)))
                counts.extend([0] * (L_qual - len(counts)))
            for i, ch in enumerate(qline):
                sums[i] += ord(ch) - 33
                counts[i] += 1

            sequence = seq.strip().upper()
            L_seq = len(sequence)
            if L_seq > 0:
                sequence_counts.update([sequence])
                for base in sequence:
                    if base in base_counts: base_counts[base] += 1
                gc_count = sequence.count('G') + sequence.count('C')
                gc_contents.append((gc_count / L_seq) * 100)

            if update_cb and read_count % UPDATE_FREQUENCY_READS == 0:
                means = [(s / c) if c else 0 for s, c in zip(sums, counts)]
                top_sequences = sequence_counts.most_common(TOP_N_SEQUENCES)
                update_payload = {
                    "quality_df_data": {"Base Position": list(range(1, len(means) + 1)), "Average Quality Score": means},
                    "gc_data": gc_contents,
                    "base_counts": base_counts,
                    "overrep_sequences": top_sequences,
                }
                update_cb(update_payload)

    # Son bir güncelleme yap
    if update_cb:
        means = [(s / c) if c else 0 for s, c in zip(sums, counts)]
        top_sequences = sequence_counts.most_common(TOP_N_SEQUENCES)
        final_payload = {
            "quality_df_data": {"Base Position": list(range(1, len(means) + 1)), "Average Quality Score": means},
            "gc_data": gc_contents,
            "base_counts": base_counts,
            "overrep_sequences": top_sequences,
        }
        update_cb(final_payload)
    if read_count_cb: read_count_cb(read_count)


# --- FASTQ ANALİZ FONKSİYONU ---

def process_fastq_file(job_id: str, file_path: str):
    """
    FASTQ dosyasını analiz eder. View katmanında threading ile arka planda çağrılır.
    """
    try:
        job = AnalysisJob.objects.get(job_id=job_id)
        job.status = 'RUNNING'
        job.save()
    except AnalysisJob.DoesNotExist:
        # Eğer bir şekilde iş veritabanında yoksa, görevi sonlandır.
        return f"Hata: {job_id} ID'li iş bulunamadı."

    start_time = time.time()
    last_db_update = 0

    def can_update_db():
        """Veritabanını çok sık güncelleyerek yormamak için bir kontrol."""
        nonlocal last_db_update
        if time.time() - last_db_update > 2: # En az 2 saniyede bir güncelle
            last_db_update = time.time()
            return True
        return False

    # Veritabanını güncelleyecek yeni callback fonksiyonlarımız
    def progress_cb(pct: int):
        if can_update_db():
            job.progress = pct
            job.save(update_fields=['progress'])

    def read_count_cb(count: int):
        job.reads_processed = count
        if can_update_db(): # Sadece 'can_update_db' true ise kaydet
            job.save(update_fields=['reads_processed'])

    def update_cb(payload: Dict):
        job.quality_scores_json = payload.get("quality_df_data")
        job.gc_histogram_data_json = payload.get("gc_data")
        job.base_composition_json = payload.get("base_counts")
        job.overrepresented_seqs_json = payload.get("overrep_sequences")
        if can_update_db(): # Sadece 'can_update_db' true ise kaydet
            job.save(update_fields=[
                'quality_scores_json', 'gc_histogram_data_json',
                'base_composition_json', 'overrepresented_seqs_json'
            ])

    try:
        compute_quality_means_streaming(
            path=file_path,
            progress_cb=progress_cb,
            update_cb=update_cb,
            read_count_cb=read_count_cb
        )
        duration = time.time() - start_time
        job.set_done(duration)

    except Exception as e:
        duration = time.time() - start_time
        job.set_error(str(e), duration)
        # Hatanın tekrar denenmemesi için yeniden raise etmiyoruz.
        return f"İş {job_id} hata ile sonlandı: {e}"

    return f"İş {job_id} başarıyla tamamlandı."


def analyze_single_file(file_id):
    """
    Tek bir FASTQ dosyasını analiz eder.
    
    Args:
        file_id: FastqUpload model ID'si (str veya UUID)
    
    Returns:
        dict: Analiz sonuçları
    """
    try:
        upload = FastqUpload.objects.get(id=file_id)
        
        if not upload.absolute_file_path or not os.path.exists(upload.absolute_file_path):
            raise FileNotFoundError(f"Dosya bulunamadı: {file_id}")
        
        upload.status = 'running'
        upload.save()
        
        # Mevcut analyze_fastq_task fonksiyonunu kullan
        # veya burada analiz kodunu çağır
        from dash_apps.fastq_app import analyze_fastq
        
        quality_df, distributions, gc_data, base_counts, reads_processed, read_lengths = \
            analyze_fastq(upload.absolute_file_path)
        
        # Sonuçları kaydet
        upload.total_reads = reads_processed
        upload.status = 'done'
        upload.save()
        
        logger.info(f"Dosya {file_id} başarıyla analiz edildi. {reads_processed} okuma işlendi.")
        
        return {
            'file_id': str(file_id),
            'reads_processed': reads_processed,
            'status': 'success'
        }
        
    except FastqUpload.DoesNotExist:
        logger.error(f"Dosya bulunamadı: {file_id}")
        raise
    except Exception as e:
        logger.error(f"Dosya {file_id} analiz hatası: {str(e)}")
        if 'upload' in locals():
            upload.status = 'error'
            upload.error_message = str(e)
            upload.save()
        raise

def parallel_fastq_analysis(file_ids):
    """
    Birden fazla FASTQ dosyasını sırayla analiz eder.
    (Celery kaldırıldı — group/chord yerine ardışık işleme.)

    Args:
        file_ids: FastqUpload ID'lerinin listesi

    Returns:
        list: Her dosya için analiz sonuçları
    """
    if not file_ids:
        return []

    logger.info(f"Analiz başlatılıyor: {len(file_ids)} dosya")

    results = []
    for file_id in file_ids:
        try:
            results.append(analyze_single_file(file_id))
        except Exception as e:
            logger.error(f"Dosya {file_id} analiz edilemedi: {e}")
            results.append({'file_id': str(file_id), 'status': 'error',
                            'error': str(e)})

    logger.info(f"Analiz tamamlandı: {len(results)} dosya")
    return results

def scheduled_cleanup():
    """
    Eski dosyaları temizleme. Celery Beat kaldırıldı —
    bu fonksiyon manuel veya bir management command / cron ile çağrılabilir.
    """
    threshold = timezone.now() - timedelta(days=7)
    old_files = FastqUpload.objects.filter(created_at__lt=threshold)
    count = old_files.count()
    
    if count > 0:
        logger.info(f"{count} eski dosya silinecek")
        old_files.delete()
        logger.info(f"{count} eski dosya silindi")
    else:
        logger.info("Silinecek eski dosya yok")
    
    return f"{count} eski dosya silindi"

def batch_analyze_and_compare(file_ids, comparison_name=None):
    """
    Batch dosyalarını analiz et ve karşılaştır.
    
    Args:
        file_ids: Karşılaştırılacak dosya ID'leri
        comparison_name: Karşılaştırma için özel isim (opsiyonel)
    
    Returns:
        dict: Karşılaştırma sonuçları
    """
    if len(file_ids) < 2:
        raise ValueError("En az 2 dosya gerekli")
    
    logger.info(f"Batch karşılaştırma başlatılıyor: {len(file_ids)} dosya")
    
    # Önce tüm dosyaları analiz et
    analysis_results = parallel_fastq_analysis(file_ids)
    
    # Karşılaştırma işlemini yap
    # (Bu kısmı ihtiyaca göre genişletebilirsiniz)
    comparison_data = {
        'name': comparison_name or f"Batch_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        'file_count': len(file_ids),
        'results': analysis_results,
        'created_at': timezone.now().isoformat()
    }
    
    logger.info(f"Batch karşılaştırma tamamlandı: {comparison_name}")
    return comparison_data