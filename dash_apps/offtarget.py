"""
dash_apps.offtarget — Kaba (yaklaşık) genom çapında off-target taraması.

CHOPCHOP gibi araçlar off-target'ı kendi barındırdıkları indeksli genoma
Bowtie/BWA ile hizalayarak bulur. Biz genom BARINDIRMADAN, NCBI BLAST'ın
uzak servisine guide'ı gönderip hizalamayı ONLARA yaptırıyoruz (Biopython).

Dürüstlük / sınırlar:
  - Bu YAKLAŞIK bir taramadır. BLAST kısa diziler için ayarlanır (word_size=7)
    ama CHOPCHOP'un CFD/MIT özgüllük skoru kadar hassas DEĞİLDİR.
  - Yavaştır (NCBI kuyruğu): guide başına ~30-90 sn sürebilir; bu yüzden yalnız
    en iyi birkaç guide için çalıştırılır.
  - 'Mükemmel eşleşme' sayısında hedefin KENDİSİ de görünür (beklenen ≥1).
  - Ağ/servis erişilemezse nazikçe 'doğrulanamadı' döner, çökmemez.
"""
import logging

logger = logging.getLogger(__name__)

# Guide üzerinde bu kadar veya daha az uyumsuzluk 'yakın off-target' sayılır.
NEAR_MISMATCH = 3
# BLAST'tan en çok bu kadar hizalama iste.
HITLIST = 50


def blast_offtarget(guide, organism="Homo sapiens", hitlist=HITLIST):
    """Bir guide için kaba off-target taraması.

    Döner: dict
      {'ok': True, 'perfect': int, 'near': int, 'total': int}
      {'ok': False, 'error': '<kod>'}   ('biopython_missing' | 'blast_error')
    """
    guide = (guide or "").strip().upper()
    if len(guide) < 15:
        return {"ok": False, "error": "guide_too_short"}

    try:
        from Bio.Blast import NCBIWWW, NCBIXML
    except Exception:
        return {"ok": False, "error": "biopython_missing"}

    try:
        handle = NCBIWWW.qblast(
            program="blastn",
            database="nt",
            sequence=guide,
            expect=1000,
            word_size=7,
            hitlist_size=hitlist,
            megablast=False,
            entrez_query=f"{organism}[Organism]",
        )
        record = NCBIXML.read(handle)
        try:
            handle.close()
        except Exception:
            pass

        glen = len(guide)
        perfect = near = total = 0
        for aln in record.alignments:
            for hsp in aln.hsps:
                # guide'ın büyük kısmını kaplamayan hizalamaları at
                if hsp.align_length < glen - 4:
                    continue
                # toplam uyumsuzluk ~ (hizada uymayan) + (hizalanmayan uçlar)
                mism = (hsp.align_length - hsp.identities) + (glen - hsp.align_length)
                total += 1
                if mism == 0:
                    perfect += 1
                elif mism <= NEAR_MISMATCH:
                    near += 1
        return {"ok": True, "perfect": perfect, "near": near, "total": total}

    except Exception as e:
        logger.warning(f"BLAST off-target failed: {e}")
        return {"ok": False, "error": "blast_error"}


def risk_label(perfect, near, lang="en"):
    """Kaba risk etiketi. Hedefin kendisi 1 mükemmel eşleşme sayılır."""
    extra_perfect = max(0, perfect - 1)   # hedef dışı mükemmel eşleşmeler
    if extra_perfect > 0:
        return ("Yüksek risk" if lang == "tr" else "High risk", "danger")
    if near >= 5:
        return ("Orta risk" if lang == "tr" else "Moderate risk", "warning")
    if near >= 1:
        return ("Düşük-orta risk" if lang == "tr" else "Low-moderate risk", "warning")
    return ("Düşük risk" if lang == "tr" else "Low risk", "success")
