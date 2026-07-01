"""
dash_apps.ensembl_fetch — Ensembl REST API'den gen dizisi çekme.

Kullanıcı bir gen adı (ör. TP53) yazınca, Ensembl'in halka açık REST
servisinden (rest.ensembl.org) o genin Ensembl kimliğini ve GENOMİK dizisini
çeker. Böylece kullanıcı diziyi elle yapıştırmak zorunda kalmaz.

Notlar / dürüstlük:
  - Yalnız stdlib (urllib) kullanır; yeni bağımlılık yok.
  - Genomik dizi intronları da içerir; çok uzun genlerde GENOMIC_MAX ile kırpılır.
  - Ağ erişimi yoksa / gen bulunamazsa nazikçe hata kodu döner, çökmemez.
  - Bu adım yalnız 'diziyi getirir'; off-target taraması AYRI bir iştir
    (bkz. dash_apps/offtarget.py) — gen çekmek off-target'ı çözmez.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

ENSEMBL_REST = "https://rest.ensembl.org"
GENOMIC_MAX = 25000          # aşırı uzun dizileri kırp (tarayıcı + hesap yükü)
_TIMEOUT = 20

# Arayüzde sunulan türler: (ensembl_species, blast_organism, etiket_tr, etiket_en)
SPECIES = [
    ("homo_sapiens",      "Homo sapiens",       "İnsan",         "Human"),
    ("mus_musculus",      "Mus musculus",       "Fare",          "Mouse"),
    ("rattus_norvegicus", "Rattus norvegicus",  "Sıçan",         "Rat"),
    ("danio_rerio",       "Danio rerio",        "Zebra balığı",  "Zebrafish"),
    ("drosophila_melanogaster", "Drosophila melanogaster", "Meyve sineği", "Fruit fly"),
    ("saccharomyces_cerevisiae", "Saccharomyces cerevisiae", "Maya", "Yeast"),
]

# ensembl_species -> blast_organism (off-target için)
BLAST_ORGANISM = {row[0]: row[1] for row in SPECIES}


def _get_json(path):
    url = f"{ENSEMBL_REST}{path}"
    req = urllib.request.Request(
        url,
        headers={"Content-Type": "application/json",
                 "User-Agent": "ai_blog-crispr/1.0"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_gene_sequence(symbol, species="homo_sapiens", max_len=GENOMIC_MAX):
    """Gen adı -> (seq, meta, error).

    Başarılıysa: (dizi_str, meta_dict, None)
    Aksi halde:  (None, None, hata_kodu)  ->  'empty' | 'not_found' | 'no_seq' |
                                              'http_<kod>' | 'network' | 'error'
    """
    symbol = (symbol or "").strip()
    if not symbol:
        return None, None, "empty"
    species = (species or "homo_sapiens").strip()

    try:
        # 1) Gen adı -> Ensembl gen kimliği + koordinatlar
        look = _get_json(
            f"/lookup/symbol/{urllib.parse.quote(species)}/"
            f"{urllib.parse.quote(symbol)}?expand=0"
        )
        gid = look.get("id")
        if not gid:
            return None, None, "not_found"

        # 2) Gen kimliği -> genomik dizi
        seq_json = _get_json(f"/sequence/id/{urllib.parse.quote(gid)}?type=genomic")
        seq = (seq_json.get("seq") or "").upper()
        if not seq:
            return None, None, "no_seq"

        truncated = False
        if max_len and len(seq) > max_len:
            seq = seq[:max_len]
            truncated = True

        meta = {
            "id": gid,
            "symbol": look.get("display_name") or symbol,
            "species": species,
            "biotype": look.get("biotype"),
            "chr": look.get("seq_region_name"),
            "start": look.get("start"),
            "end": look.get("end"),
            "strand": look.get("strand"),
            "assembly": look.get("assembly_name"),
            "length": len(seq),
            "truncated": truncated,
        }
        return seq, meta, None

    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            return None, None, "not_found"
        logger.warning(f"Ensembl HTTP {e.code} for {symbol}/{species}")
        return None, None, f"http_{e.code}"
    except urllib.error.URLError as e:
        logger.warning(f"Ensembl network error: {e}")
        return None, None, "network"
    except Exception as e:
        logger.warning(f"Ensembl fetch error: {e}")
        return None, None, "error"
