"""
CRISPR sgRNA Tasarımcısı — Hesaplama Motoru (Django/Dash'ten bağımsız).

Bu modül saf Python'dur; Django veya Dash gerektirmez, böylece tek başına
test edilebilir. Görevleri:
  - DNA dizisini temizleme
  - Seçilen Cas enzimine göre PAM bulma (her iki iplikte)
  - Aday sgRNA (kılavuz RNA) dizilerini çıkarma
  - Her adaya verim/uygunluk skoru hesaplama (GC + homopolimer + uç bölge)
  - Basit benzersizlik (off-target göstergesi) hesaplama

ÖNEMLİ: Buradaki skorlama EĞİTİM ve ÖN-TASARIM amaçlı sezgisel bir
modeldir (Doench/Rule Set 2 gibi eğitilmiş bir model değildir). Gerçek
deney öncesi genom çapında off-target analizi (CRISPOR, Benchling) şarttır.
"""
import re

# ---------------------------------------------------------------------------
# Cas enzimi tanımları
# ---------------------------------------------------------------------------
# pam_side: PAM'in kılavuza göre konumu.
#   '3prime' → PAM kılavuzun 3' (sağ) tarafında (SpCas9 ailesi): 5'-[guide][PAM]-3'
#   '5prime' → PAM kılavuzun 5' (sol) tarafında (Cas12a):        5'-[PAM][guide]-3'
ENZYMES = {
    "SpCas9": {
        "pam": "NGG", "pam_side": "3prime", "guide_len": 20,
        "label_tr": "SpCas9 (PAM: NGG) — standart",
        "label_en": "SpCas9 (PAM: NGG) — standard",
    },
    "SpCas9-NG": {
        "pam": "NG", "pam_side": "3prime", "guide_len": 20,
        "label_tr": "SpCas9-NG / SpG (PAM: NG) — esnek",
        "label_en": "SpCas9-NG / SpG (PAM: NG) — flexible",
    },
    "SaCas9": {
        "pam": "NNGRRT", "pam_side": "3prime", "guide_len": 21,
        "label_tr": "SaCas9 (PAM: NNGRRT) — kompakt",
        "label_en": "SaCas9 (PAM: NNGRRT) — compact",
    },
    "Cas12a": {
        "pam": "TTTV", "pam_side": "5prime", "guide_len": 23,
        "label_tr": "Cas12a / Cpf1 (PAM: TTTV) — PAM solda",
        "label_en": "Cas12a / Cpf1 (PAM: TTTV) — PAM on 5' side",
    },
}

# IUPAC belirsizlik kodları → düzenli ifade karakter sınıfı
_IUPAC = {
    "A": "A", "C": "C", "G": "G", "T": "T",
    "R": "[AG]", "Y": "[CT]", "S": "[GC]", "W": "[AT]",
    "K": "[GT]", "M": "[AC]", "B": "[CGT]", "D": "[AGT]",
    "H": "[ACT]", "V": "[ACG]", "N": "[ACGT]",
}

_COMPLEMENT = str.maketrans("ACGTacgt", "TGCAtgca")


def clean_sequence(sequence):
    """Diziden ATGC dışındaki karakterleri (FASTA başlığı, boşluk, sayı) temizler."""
    if not sequence:
        return ""
    lines = [ln for ln in sequence.splitlines() if not ln.strip().startswith(">")]
    joined = "".join(lines)
    return re.sub(r"[^ATGCatgc]", "", joined).upper()


def reverse_complement(seq):
    """Bir DNA dizisinin ters komplementini döndürür."""
    return seq.translate(_COMPLEMENT)[::-1]


def pam_to_regex(pam):
    """IUPAC PAM motifini düzenli ifadeye çevirir (örn. NGG → [ACGT]GG)."""
    return "".join(_IUPAC.get(base, base) for base in pam.upper())


def gc_content(seq):
    """GC yüzdesi (0-100)."""
    if not seq:
        return 0.0
    gc = sum(1 for b in seq if b in "GC")
    return round(100.0 * gc / len(seq), 1)


def _max_homopolymer(seq):
    """En uzun ardışık aynı-baz dizisinin uzunluğu (örn. AATTTTG → 4)."""
    best = cur = 0
    prev = ""
    for b in seq:
        cur = cur + 1 if b == prev else 1
        prev = b
        best = max(best, cur)
    return best


def _has_poly_t(seq):
    """Pol III terminatörü riski: ardışık 4+ T (TTTT)."""
    return "TTTT" in seq


def score_guide(guide, pam_side="3prime"):
    """
    Bir kılavuz diziye 0-100 arası sezgisel verim skoru verir.
    Bileşenler: GC dengesi + homopolimer cezası + uç (seed) bölge GC'si.
    Eğitim amaçlı; eğitilmiş bir model (Doench 2016) DEĞİLDİR.
    Dönüş: (score: float, reasons: list[str])
    """
    reasons = []
    score = 100.0
    g = guide.upper()
    n = len(g)
    if n == 0:
        return 0.0, ["bos"]

    # 1) GC içeriği — ideal %40-60
    gc = gc_content(g)
    if 40 <= gc <= 60:
        reasons.append("gc_ideal")
    elif 30 <= gc < 40 or 60 < gc <= 70:
        score -= 12
        reasons.append("gc_borderline")
    else:
        score -= 28
        reasons.append("gc_extreme")

    # 2) Homopolimer / poli-T (Pol III terminatörü)
    if _has_poly_t(g):
        score -= 25
        reasons.append("poly_t")
    homo = _max_homopolymer(g)
    if homo >= 5:
        score -= 15
        reasons.append("homopolymer5")
    elif homo == 4:
        score -= 8
        reasons.append("homopolymer4")

    # 3) Seed (PAM'e yakın) bölge GC'si — SpCas9 için son ~10 nt önemlidir
    #    3prime PAM → seed kılavuzun 3' ucunda; 5prime PAM → 5' ucunda
    seed = g[-10:] if pam_side == "3prime" else g[:10]
    seed_gc = gc_content(seed)
    if seed_gc < 20:
        score -= 10
        reasons.append("seed_low_gc")
    elif seed_gc > 80:
        score -= 6
        reasons.append("seed_high_gc")
    else:
        reasons.append("seed_ok")

    # 4) Çok düşük çeşitlilik (örn. tek bazdan ibaret) ek ceza
    if len(set(g)) <= 2:
        score -= 20
        reasons.append("low_complexity")

    return max(0.0, min(100.0, round(score, 1))), reasons


def _uniqueness(guide, full_seq, pam_side="3prime"):
    """
    Basit off-target göstergesi: kılavuzun seed bölgesinin (PAM'e yakın 12 nt)
    verilen dizide (her iki iplik) kaç kez geçtiğini sayar. 1 = benzersiz (iyi).
    NOT: gerçek off-target genom çapında aranır; bu sadece girdiyle sınırlıdır.
    """
    seed = guide[-12:] if pam_side == "3prime" else guide[:12]
    if len(seed) < 12:
        seed = guide
    both = full_seq + "N" + reverse_complement(full_seq)
    return both.count(seed)


def find_guides(sequence, enzyme="SpCas9", max_results=200):
    """
    Verilen dizide seçilen enzime göre aday sgRNA'ları bulur (her iki iplik).

    Dönüş: (guides: list[dict], error: str|None)
    Her guide: {
        rank, guide, pam, strand ('+'/'-'), start, end (1-bazlı, ileri iplik koord.),
        gc, score, uniqueness, reasons
    }
    """
    seq = clean_sequence(sequence)
    enz = ENZYMES.get(enzyme)
    if enz is None:
        return None, {"code": "unknown_enzyme", "enzyme": enzyme}

    glen = enz["guide_len"]
    plen = len(enz["pam"])
    side = enz["pam_side"]
    pam_re = re.compile(pam_to_regex(enz["pam"]))

    min_len = glen + plen
    if len(seq) < min_len:
        return None, {"code": "too_short", "min": min_len, "got": len(seq)}

    results = []
    L = len(seq)

    def scan(strand_seq, strand):
        # strand_seq üzerinde PAM ara; konumları ileri iplik koordinatına çevir.
        for m in _iter_overlapping(pam_re, strand_seq):
            i = m.start()  # PAM başlangıcı (strand_seq üzerinde)
            if side == "3prime":
                gstart = i - glen
                gend = i  # PAM kılavuzun hemen sağında
                if gstart < 0:
                    continue
                guide = strand_seq[gstart:gend]
                pam = strand_seq[i:i + plen]
                # kılavuzun strand_seq üzerindeki aralığı: [gstart, gend)
                span = (gstart, gend)
            else:  # 5prime (Cas12a): PAM solda, kılavuz sağda
                gstart = i + plen
                gend = gstart + glen
                if gend > len(strand_seq):
                    continue
                guide = strand_seq[gstart:gend]
                pam = strand_seq[i:i + plen]
                span = (gstart, gend)

            if len(guide) != glen or "N" in guide:
                continue

            # İleri iplik koordinatına dönüştür (görüntüleme için 1-bazlı)
            if strand == "+":
                disp_start = span[0] + 1
                disp_end = span[1]
            else:
                # ters iplikteki [a,b) → ileri iplikte (L-b, L-a)
                disp_start = L - span[1] + 1
                disp_end = L - span[0]

            sc, reasons = score_guide(guide, side)
            uniq = _uniqueness(guide, seq, side)
            results.append({
                "guide": guide,
                "pam": pam,
                "strand": strand,
                "start": disp_start,
                "end": disp_end,
                "gc": gc_content(guide),
                "score": sc,
                "uniqueness": uniq,
                "reasons": reasons,
            })

    scan(seq, "+")
    scan(reverse_complement(seq), "-")

    if not results:
        return [], None

    # Skora göre (yüksek→düşük), eşitlikte benzersizliğe göre sırala
    results.sort(key=lambda g: (g["score"], -g["uniqueness"]), reverse=True)
    for idx, g in enumerate(results[:max_results], start=1):
        g["rank"] = idx
    return results[:max_results], None


def _iter_overlapping(compiled_re, text):
    """Örtüşen eşleşmeleri de bulur (PAM'ler örtüşebilir)."""
    pos = 0
    while pos <= len(text):
        m = compiled_re.match(text, pos)
        if m:
            yield m
            pos += 1
        else:
            pos += 1


def summarize(guides):
    """Aday listesi için özet metrikler döndürür."""
    if not guides:
        return {"total": 0, "plus": 0, "minus": 0, "high": 0, "unique": 0, "best": None}
    return {
        "total": len(guides),
        "plus": sum(1 for g in guides if g["strand"] == "+"),
        "minus": sum(1 for g in guides if g["strand"] == "-"),
        "high": sum(1 for g in guides if g["score"] >= 70),
        "unique": sum(1 for g in guides if g["uniqueness"] <= 1),
        "best": guides[0] if guides else None,
    }


# Demo dizi: insan HBB (beta-globin) geninden örnek bir bölge (eğitim amaçlı)
EXAMPLE_SEQUENCE = (
    "ATGGTGCACCTGACTCCTGAGGAGAAGTCTGCCGTTACTGCCCTGTGGGGCAAGGTGAACGTG"
    "GATGAAGTTGGTGGTGAGGCCCTGGGCAGGCTGCTGGTGGTCTACCCTTGGACCCAGAGGTTC"
    "TTTGAGTCCTTTGGGGATCTGTCCACTCCTGATGCTGTTATGGGCAACCCTAAGGTGAAGGCT"
    "CATGGCAAGAAAGTGCTCGGTGCCTTTAGTGATGGCCTGGCTCACCTGGACAACCTCAAGGGC"
)
