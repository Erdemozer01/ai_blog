"""
dash_apps.offtarget — Genom çapında off-target taraması (NCBI BLAST).

CHOPCHOP gibi: guide'ı REFERANS GENOMA hizalar ve off-target'ları uyumsuzluk
sayısına göre MM0/MM1/MM2/MM3 olarak raporlar. Genom barındırmadan, hizalamayı
NCBI'nin uzak BLAST servisine yaptırırız (Biopython).

Önemli:
  - Veritabanı 'refseq_genomic' (RefSeq referans genomları) + organizma filtresi.
    'nt'nin aksine mRNA/EST/patent/çoklu assembly tekrarı YOKtur; sayılar temizdir.
  - Uyumsuzluk, guide'ın 20 bp'lik hedef bölgesi üzerinden sayılır (Hsu 2013 yöntemi).
  - MM0 (tam eşleşme) hedefin KENDİSİNİ de içerir (beklenen ≥1).
  - Yavaştır (NCBI kuyruğu): guide başına ~30-90 sn; bu yüzden yalnız birkaç guide.
  - Ağ/servis erişilemezse nazikçe hata döner, çökmemez.
"""
import logging

logger = logging.getLogger(__name__)

# BLAST'tan en çok bu kadar hizalama iste.
HITLIST = 100
# Guide'ın en az bu kadarı hizalanmış olsun (uçlarda küçük tolerans).
MIN_COVER_SLACK = 3


def blast_offtarget(guide, organism="Homo sapiens", hitlist=HITLIST):
    """Bir guide için genom çapında off-target taraması.

    Döner: dict
      {'ok': True, 'mm': {0:int, 1:int, 2:int, 3:int}}
      {'ok': False, 'error': '<kod>'}   ('biopython_missing' | 'blast_error' |
                                         'guide_too_short')
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
            database="refseq_genomic",          # referans genomlar (nt DEĞİL)
            sequence=guide,
            expect=1000,
            word_size=7,                          # kısa dizi için
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
        mm = {0: 0, 1: 0, 2: 0, 3: 0}
        for aln in record.alignments:
            for hsp in aln.hsps:
                # guide'ın büyük kısmını kaplamayan kısa hizalamaları at
                if hsp.align_length < glen - MIN_COVER_SLACK:
                    continue
                # uyumsuzluk ~ (hizada uymayan + boşluk) + (hizalanmayan uçlar)
                mismatches = (hsp.align_length - hsp.identities) + (glen - hsp.align_length)
                if 0 <= mismatches <= 3:
                    mm[mismatches] += 1
        return {"ok": True, "mm": mm}

    except Exception as e:
        logger.warning(f"BLAST off-target failed: {e}")
        return {"ok": False, "error": "blast_error"}


def risk_label(mm, lang="en"):
    """MM0-3 dağılımından kaba risk etiketi.

    Hedefin kendisi 1 adet MM0 sayılır; hedef DIŞI MM0 varsa yüksek risk.
    """
    mm = mm or {}
    extra0 = max(0, int(mm.get(0, 0)) - 1)        # hedef dışı tam eşleşme
    mm1 = int(mm.get(1, 0))
    mm23 = int(mm.get(2, 0)) + int(mm.get(3, 0))

    if extra0 > 0:
        return ("Yüksek risk" if lang == "tr" else "High risk", "danger")
    if mm1 > 0:
        return ("Orta risk" if lang == "tr" else "Moderate risk", "warning")
    if mm23 >= 5:
        return ("Düşük-orta risk" if lang == "tr" else "Low-moderate risk", "warning")
    return ("Düşük risk" if lang == "tr" else "Low risk", "success")
