"""
Kaynak Doğrulama Servisi (CrossRef tabanlı).

AI'ın ürettiği kaynakçadaki her atfı CrossRef veritabanında arar:
  - Bulunursa  → kaynak GERÇEK (DOI ile)
  - Bulunmazsa → ŞÜPHELİ (uydurma olabilir)

ÖNEMLİ KISITLAR (dürüstlük):
  - Bu yalnızca kaynağın VARLIĞINI doğrular, atfın İÇERİK doğruluğunu DEĞİL.
    Yani "[1] gerçek bir makale mi?" sorusuna cevap verir; "[1] gerçekten
    bu cümleyi destekliyor mu?" sorusuna veremez (tam metin erişimi gerekir).
  - PythonAnywhere ücretsiz hesapta dış erişim whitelist'le sınırlıdır;
    api.crossref.org erişilemezse fonksiyon nazikçe 'doğrulanamadı' döner.
"""
import re
import json
import urllib.request
import urllib.parse


CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "AIBlog/1.0 (academic reference verification)"


def _parse_bibliography(bibliography_text):
    """
    Kaynakça metnini tek tek kaynaklara böler.
    '1. ...', '[1] ...', '1) ...' gibi numaralı formatları yakalar.
    Döner: [{'num': '1', 'text': 'kaynak metni'}, ...]
    """
    if not bibliography_text:
        return []

    text = bibliography_text.strip()
    # Satır başındaki numara kalıplarına göre böl: "1.", "[1]", "1)"
    # Her kaynağı yakala
    entries = []
    # Önce satırlara göre dene
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]

    current_num = None
    current_text = []
    num_pattern = re.compile(r'^\[?(\d+)[\].\)]\s*(.*)')

    for line in lines:
        m = num_pattern.match(line)
        if m:
            # Yeni kaynak başladı — öncekini kaydet
            if current_num is not None:
                entries.append({'num': current_num, 'text': ' '.join(current_text).strip()})
            current_num = m.group(1)
            current_text = [m.group(2)]
        else:
            # Önceki kaynağın devamı
            if current_num is not None:
                current_text.append(line)

    # Son kaynağı ekle
    if current_num is not None:
        entries.append({'num': current_num, 'text': ' '.join(current_text).strip()})

    return entries


def _extract_search_query(ref_text):
    """
    Kaynak metninden aranabilir bir sorgu çıkarır.
    Tırnak içindeki başlığı veya en uzun anlamlı kısmı alır.
    """
    # Tırnak içi başlık varsa onu al (düz ve akıllı tırnaklar)
    quoted = re.findall(r'["\u201c\u201d\u2018\u2019\']([^"\u201c\u201d\u2018\u2019\']{15,})["\u201c\u201d\u2018\u2019\']', ref_text)
    if quoted:
        return quoted[0]
    # DOI varsa onu çıkar (doğrudan kontrol için)
    # Aksi halde metnin tamamını sorgu olarak kullan (CrossRef bibliographic arama yapar)
    # Yıl ve sayfa numaralarını biraz temizle ama başlık/yazar kalsın
    return ref_text[:300]


def _extract_doi(ref_text):
    """Kaynak metninde DOI varsa çıkarır."""
    m = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', ref_text)
    return m.group(0).rstrip('.') if m else None


def verify_single_reference(ref_text, timeout=10):
    """
    Tek bir kaynağı CrossRef'te doğrular.
    Döner: dict {
        'status': 'verified' | 'not_found' | 'unreachable',
        'doi': str|None,
        'matched_title': str|None,
    }
    """
    # Önce DOI varsa doğrudan onu kontrol et
    doi = _extract_doi(ref_text)
    if doi:
        try:
            url = f"{CROSSREF_API}/{urllib.parse.quote(doi)}"
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            msg = data.get('message', {})
            title = (msg.get('title') or ['?'])[0]
            return {'status': 'verified', 'doi': doi, 'matched_title': title}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass  # DOI bulunamadı, başlıkla aramaya devam et
            else:
                return {'status': 'unreachable', 'doi': None, 'matched_title': None}
        except Exception:
            return {'status': 'unreachable', 'doi': None, 'matched_title': None}

    # Başlık/bibliyografik arama
    query = _extract_search_query(ref_text)
    try:
        params = urllib.parse.urlencode({'query.bibliographic': query, 'rows': 3})
        url = f"{CROSSREF_API}?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        items = data.get('message', {}).get('items', [])
        if not items:
            return {'status': 'not_found', 'doi': None, 'matched_title': None}

        # En iyi eşleşme — CrossRef relevance'a göre sıralı döner
        top = items[0]
        found_title = (top.get('title') or ['?'])[0]
        found_doi = top.get('DOI')

        # Basit benzerlik: aranan başlık kelimelerinin ne kadarı eşleşmede var
        score = _title_similarity(query, found_title)
        if score >= 0.4:  # makul eşleşme eşiği
            return {'status': 'verified', 'doi': found_doi, 'matched_title': found_title}
        else:
            return {'status': 'not_found', 'doi': None, 'matched_title': found_title}

    except Exception:
        return {'status': 'unreachable', 'doi': None, 'matched_title': None}


def _title_similarity(a, b):
    """İki başlık arasındaki basit kelime örtüşme oranı (0-1)."""
    if not a or not b:
        return 0.0
    wa = set(re.findall(r'\w+', a.lower()))
    wb = set(re.findall(r'\w+', b.lower()))
    # çok kısa kelimeleri çıkar
    wa = {w for w in wa if len(w) > 3}
    wb = {w for w in wb if len(w) > 3}
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def verify_bibliography(bibliography_text, max_refs=20):
    """
    Tüm kaynakçayı doğrular.
    Döner: dict {
        'total': int,
        'verified': int,
        'not_found': int,
        'unreachable': int,
        'reachable': bool,   # API'ye hiç ulaşılabildi mi
        'results': [{'num', 'text', 'status', 'doi', 'matched_title'}, ...]
    }
    """
    entries = _parse_bibliography(bibliography_text)
    entries = entries[:max_refs]

    results = []
    counts = {'verified': 0, 'not_found': 0, 'unreachable': 0}

    for entry in entries:
        res = verify_single_reference(entry['text'])
        counts[res['status']] = counts.get(res['status'], 0) + 1
        results.append({
            'num': entry['num'],
            'text': entry['text'],
            'status': res['status'],
            'doi': res['doi'],
            'matched_title': res['matched_title'],
        })

    # Hiçbir kaynağa ulaşılamadıysa (hepsi unreachable) API erişimi yok demektir
    reachable = not (len(entries) > 0 and counts['unreachable'] == len(entries))

    return {
        'total': len(entries),
        'verified': counts['verified'],
        'not_found': counts['not_found'],
        'unreachable': counts['unreachable'],
        'reachable': reachable,
        'results': results,
    }


def check_article_references(article):
    """
    Bir makalenin kaynakçasını doğrular ve sonucu modele kaydeder.
    (ok: bool, mesaj: str) döner.
    """
    from django.utils import timezone

    if not article.bibliography:
        return False, "Makalede kaynakça bulunamadı."

    result = verify_bibliography(article.bibliography)

    # API'ye hiç ulaşılamadıysa (whitelist sorunu) kaydetme, uyar
    if not result['reachable']:
        return False, ("CrossRef API'sine ulaşılamadı. PythonAnywhere'de "
                       "api.crossref.org adresinin whitelist'te olduğundan emin olun.")

    article.reference_check_result = result
    article.reference_checked_at = timezone.now()
    article.save(update_fields=['reference_check_result', 'reference_checked_at'])

    msg = (f"Kaynak doğrulama tamamlandı. {result['verified']}/{result['total']} kaynak "
           f"doğrulandı, {result['not_found']} bulunamadı (şüpheli).")
    return True, msg