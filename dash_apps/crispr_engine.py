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


# ---------------------------------------------------------------------------
# Doench 2014 (Rule Set 1) on-target verim skoru
# ---------------------------------------------------------------------------
# Katsayılar Doench et al. 2014 (Nature Biotechnology) makalesinden gelir;
# referans uygulama: CRISPOR (maximilianh/crisporWebsite, MIT). Bu, eğitilmiş,
# hakemli bir modeldir (sezgisel değildir). Girdi 30-mer olmalıdır:
#   4 nt yukarı akış + 20 nt kılavuz + 3 nt PAM + 3 nt aşağı akış
# Çıktı 0-1 arası olasılıktır (yüksek = daha verimli kesim beklentisi).
_RS1_INTERCEPT = 0.59763615
_RS1_GC_HIGH = -0.1665878
_RS1_GC_LOW = -0.2026259
_RS1_PARAMS = [
    (1, 'G', -0.2753771), (2, 'A', -0.3238875), (2, 'C', 0.17212887), (3, 'C', -0.1006662),
    (4, 'C', -0.2018029), (4, 'G', 0.24595663), (5, 'A', 0.03644004), (5, 'C', 0.09837684),
    (6, 'C', -0.7411813), (6, 'G', -0.3932644), (11, 'A', -0.466099), (14, 'A', 0.08537695),
    (14, 'C', -0.013814), (15, 'A', 0.27262051), (15, 'C', -0.1190226), (15, 'T', -0.2859442),
    (16, 'A', 0.09745459), (16, 'G', -0.1755462), (17, 'C', -0.3457955), (17, 'G', -0.6780964),
    (18, 'A', 0.22508903), (18, 'C', -0.5077941), (19, 'G', -0.4173736), (19, 'T', -0.054307),
    (20, 'G', 0.37989937), (20, 'T', -0.0907126), (21, 'C', 0.05782332), (21, 'T', -0.5305673),
    (22, 'T', -0.8770074), (23, 'C', -0.8762358), (23, 'G', 0.27891626), (23, 'T', -0.4031022),
    (24, 'A', -0.0773007), (24, 'C', 0.28793562), (24, 'T', -0.2216372), (27, 'G', -0.6890167),
    (27, 'T', 0.11787758), (28, 'C', -0.1604453), (29, 'G', 0.38634258), (1, 'GT', -0.6257787),
    (4, 'GC', 0.30004332), (5, 'AA', -0.8348362), (5, 'TA', 0.76062777), (6, 'GG', -0.4908167),
    (11, 'GG', -1.5169074), (11, 'TA', 0.7092612), (11, 'TC', 0.49629861), (11, 'TT', -0.5868739),
    (12, 'GG', -0.3345637), (13, 'GA', 0.76384993), (13, 'GC', -0.5370252), (16, 'TG', -0.7981461),
    (18, 'GG', -0.6668087), (18, 'TC', 0.35318325), (19, 'CC', 0.74807209), (19, 'TG', -0.3672668),
    (20, 'AC', 0.56820913), (20, 'CG', 0.32907207), (20, 'GA', -0.8364568), (20, 'GG', -0.7822076),
    (21, 'TC', -1.029693), (22, 'CG', 0.85619782), (22, 'CT', -0.4632077), (23, 'AA', -0.5794924),
    (23, 'AG', 0.64907554), (24, 'AG', -0.0773007), (24, 'CG', 0.28793562), (24, 'TG', -0.2216372),
    (26, 'GT', 0.11787758), (28, 'GG', -0.69774),
]


def doench_rs1_score(thirty_mer):
    """
    Doench 2014 (Rule Set 1) skoru. Girdi 30-mer (4+20+3+3). Dönüş 0-1 veya
    bağlam uygun değilse None. Pozisyonlar 30-mer üzerinde 0-tabanlıdır.
    """
    import math
    s = (thirty_mer or "").upper()
    if len(s) != 30 or any(b not in "ACGT" for b in s):
        return None
    score = _RS1_INTERCEPT
    guide = s[4:24]
    gc = guide.count("G") + guide.count("C")
    gc_weight = _RS1_GC_LOW if gc <= 10 else _RS1_GC_HIGH
    score += abs(10 - gc) * gc_weight
    for pos, model_seq, weight in _RS1_PARAMS:
        if s[pos:pos + len(model_seq)] == model_seq:
            score += weight
    return 1.0 / (1.0 + math.exp(-score))


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

            # Doench 2014 (RS1) yalnızca standart SpCas9 (NGG, 20nt kılavuz, 3nt PAM)
            # için ve yeterli yan-dizi bağlamı (30-mer) olduğunda geçerlidir.
            score_type = "heuristic"
            if enzyme == "SpCas9" and side == "3prime":
                ctx_start = i - glen - 4   # kılavuzun 4 nt yukarısı
                ctx_end = i + plen + 3     # PAM'in 3 nt aşağısı
                if ctx_start >= 0 and ctx_end <= len(strand_seq):
                    rs1 = doench_rs1_score(strand_seq[ctx_start:ctx_end])
                    if rs1 is not None:
                        sc = round(rs1 * 100, 1)
                        score_type = "doench"

            results.append({
                "guide": guide,
                "pam": pam,
                "strand": strand,
                "start": disp_start,
                "end": disp_end,
                "gc": gc_content(guide),
                "score": sc,
                "score_type": score_type,
                "uniqueness": uniq,
                "reasons": reasons,
            })

    scan(seq, "+")
    scan(reverse_complement(seq), "-")

    if not results:
        return [], None

    # Önce skor tipine göre (gerçek RS1 modeli, sezgisel/uç bölgenin üstünde),
    # sonra skora göre (yüksek→düşük), eşitlikte benzersizliğe göre sırala.
    # Tek-tip (örn. SpCas9 dışı tüm sezgisel) listelerde tip etkisizdir.
    _type_rank = {"doench": 1, "heuristic": 0}
    results.sort(
        key=lambda g: (_type_rank.get(g["score_type"], 0), g["score"], -g["uniqueness"]),
        reverse=True,
    )
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
        "high": sum(1 for g in guides if g["score"] >= 60),
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
