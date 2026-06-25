"""
blog.pubmed_sources — PubMed / PMC tabanlı gerçek kaynak toplayıcı.

Amaç: collect_real_sources_for_topic (CrossRef) ile AYNI dönüş şeklinde
kaynak üretmek; böylece dash_apps.generate.get_base_prompt'a hiç dokunmadan
'real_sources' yuvasına takılır.

Üstüne iki ek:
  - 'pmid' / 'pmcid' alanları (atıf ve tam metin erişimi için)
  - 'fulltext' alanı: SADECE PMC'de açık erişimli VE ticari kullanıma uygun
    (CC BY / CC0 / public domain) makaleler için. Aksi halde None kalır.

Dönüş şekli (CrossRef ile uyumlu):
    {
        'title', 'authors' (str), 'year', 'container', 'doi',
        'abstract', 'citation',
        'pmid', 'pmcid', 'fulltext' (str|None), 'license' (str|None)
    }

Dürüstlük notları:
  - Özet (abstract) PubMed'de neredeyse her makalede VAR → geniş kapsam.
  - Tam metin yalnızca PMC açık erişim alt kümesinde; paywall'lı makalede None.
  - Ticari kullanım için tam metin SADECE CC BY/CC0/public-domain lisanslılarda
    doldurulur (NC ve ND lisanslılar dışlanır).
  - NCBI'a erişim yoksa (PythonAnywhere ücretsiz whitelist vb.) fonksiyon
    sessizce boş liste döner; çağıran taraf CrossRef'e düşebilir.
"""
import os
import re
import time
from xml.etree import ElementTree as ET

try:
    from Bio import Entrez
except Exception:
    Entrez = None

# --- Ayarlar: önce Django settings, sonra ortam değişkeni ------------------
def _cfg(name, default=None):
    try:
        from django.conf import settings
        val = getattr(settings, name, None)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(name, default)


# Ticari kullanıma uygun lisans kalıpları (tam metin için)
_COMMERCIAL_OK = (
    'creativecommons.org/licenses/by/',     # CC BY
    'creativecommons.org/licenses/by-sa/',  # CC BY-SA
    'creativecommons.org/publicdomain/',    # CC0 / public domain
)
# Açıkça dışlananlar (ticari kullanıma kapalı)
_COMMERCIAL_NO = (
    'licenses/by-nc',   # NonCommercial
    'licenses/by-nd',   # NoDerivatives
)

# Tam metin token bütçesi (kaba: ~4 kar/token). Tek makale çok yer kaplamasın.
MAX_FULLTEXT_CHARS = 6000


def _configure_entrez():
    """Entrez.email zorunlu; api_key opsiyonel (rate limit 3->10/sn)."""
    if Entrez is None:
        return False
    email = _cfg('NCBI_EMAIL')
    if not email:
        return False
    Entrez.email = email
    api_key = _cfg('NCBI_API_KEY')
    if api_key:
        Entrez.api_key = api_key
    return True


def _sleep():
    time.sleep(0.12 if getattr(Entrez, 'api_key', None) else 0.34)


def _txt(el):
    """Bir XML elemanının altındaki tüm metni boşlukla birleştir."""
    if el is None:
        return ''
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


# --- Anahtar kelime üretimi: mümkünse reference_check ile aynı mantık -------
def _keywords(topic, lang='tr'):
    try:
        from blog.reference_check import _ai_topic_to_keywords
        kw = _ai_topic_to_keywords(topic, lang=lang)
        if kw:
            return kw
    except Exception:
        pass
    # Yedek: konunun kendisini tek sorgu olarak kullan
    return [topic]


def _relevant(abstract, title, topic):
    """Alaka kontrolü: mümkünse reference_check yardımcılarını kullan."""
    try:
        from blog.reference_check import _topic_core_terms, _abstract_is_relevant
        return _abstract_is_relevant(abstract, title, _topic_core_terms(topic))
    except Exception:
        return True  # yardımcı yoksa ele


# --- PubMed arama + özet çekme ---------------------------------------------
def _search_pmids(query, retmax=12, recent_years=6):
    """PubMed'de ara, alaka sırasına göre PMID listesi döndür."""
    from datetime import date
    min_year = date.today().year - recent_years
    term = f'{query} AND ("{min_year}"[Date - Publication] : "3000"[Date - Publication])'
    h = Entrez.esearch(db='pubmed', term=term, retmax=retmax, sort='relevance')
    rec = Entrez.read(h)
    h.close()
    _sleep()
    return rec.get('IdList', [])


def _fetch_summaries(pmids):
    """Birden çok PMID için başlık/özet/yazar/yıl/dergi/DOI çek (tek istek)."""
    if not pmids:
        return {}
    h = Entrez.efetch(db='pubmed', id=','.join(pmids), rettype='abstract', retmode='xml')
    rec = Entrez.read(h)
    h.close()
    _sleep()

    out = {}
    for art in rec.get('PubmedArticle', []):
        try:
            mc = art['MedlineCitation']
            pmid = str(mc['PMID'])
            article = mc['Article']
            title = str(article.get('ArticleTitle', '')).strip()

            # Özet (birden çok parça olabilir)
            abs_parts = article.get('Abstract', {}).get('AbstractText', [])
            abstract = ' '.join(str(x) for x in abs_parts).strip()

            # Yazarlar -> "Soyad et al."
            authors = article.get('AuthorList', [])
            author_str = ''
            if authors:
                a0 = authors[0]
                author_str = (a0.get('LastName') or a0.get('CollectiveName') or '').strip()
                if author_str and len(authors) > 1:
                    author_str += ' et al.'
            if not author_str:
                author_str = 'Anonim'

            # Yıl
            year = ''
            pubdate = article.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
            year = str(pubdate.get('Year', '')) or ''

            # Dergi
            container = str(article.get('Journal', {}).get('Title', '')).strip()

            # DOI (PubmedData/ArticleIdList içinde)
            doi = ''
            for aid in art.get('PubmedData', {}).get('ArticleIdList', []):
                if aid.attributes.get('IdType') == 'doi':
                    doi = str(aid)
                    break

            out[pmid] = {
                'pmid': pmid, 'title': title, 'authors': author_str,
                'year': year, 'container': container, 'doi': doi,
                'abstract': abstract,
            }
        except Exception:
            continue
    return out


# --- PMC tam metin (yalnızca ticari-uygun lisans) --------------------------
def _pmid_to_pmcid(pmid):
    """PMID -> PMCID (yoksa None)."""
    try:
        h = Entrez.elink(dbfrom='pubmed', db='pmc', id=pmid)
        rec = Entrez.read(h)
        h.close()
        _sleep()
        links = rec[0].get('LinkSetDb', [])
        if links and links[0].get('Link'):
            return 'PMC' + str(links[0]['Link'][0]['Id'])
    except Exception:
        pass
    return None


def _license_commercial_ok(license_url):
    """Lisans URL'i ticari kullanıma uygun mu?"""
    if not license_url:
        return False
    u = license_url.lower()
    if any(bad in u for bad in _COMMERCIAL_NO):
        return False
    return any(ok in u for ok in _COMMERCIAL_OK)


def _fetch_pmc_fulltext(pmcid):
    """
    PMC'den JATS XML çek. Döner: (fulltext|None, license_url|None).
    Tam metni SADECE lisans ticari kullanıma uygunsa döndürür.
    """
    try:
        num = pmcid.replace('PMC', '')
        h = Entrez.efetch(db='pmc', id=num, rettype='full', retmode='xml')
        xml = h.read()
        h.close()
        _sleep()
        root = ET.fromstring(xml)
    except Exception:
        return None, None

    # Lisansı bul
    license_url = None
    for lic in root.iter():
        tag = lic.tag.lower()
        if tag.endswith('license'):
            href = (lic.get('{http://www.w3.org/1999/xlink}href')
                    or lic.get('href') or '')
            if href:
                license_url = href
                break
            inner = _txt(lic).lower()
            m = re.search(r'creativecommons\.org/\S+', inner)
            if m:
                license_url = m.group(0)
                break

    if not _license_commercial_ok(license_url):
        return None, license_url  # ticari kullanıma uygun değil → tam metin verme

    # Gövdeyi düz metne çevir (ref-list / tablo / şekil çöpü dışarıda)
    body = root.find('.//body')
    if body is None:
        return None, license_url
    for ref in body.findall('.//ref-list'):
        for child in list(ref):
            ref.remove(child)
    parts = []
    for el in body.iter():
        if el.tag in ('p', 'title'):
            t = _txt(el)
            if t:
                parts.append(t)
    text = '\n'.join(parts).strip()
    if not text:
        return None, license_url
    return text[:MAX_FULLTEXT_CHARS], license_url


# --- Ana giriş noktası ------------------------------------------------------
def collect_pubmed_sources_for_topic(topic, target_count=8, lang='tr',
                                     want_fulltext=True, fulltext_limit=4):
    """
    Konuya göre PubMed'den gerçek kaynaklar toplar (CrossRef ile aynı şekilde).

    want_fulltext=True: PMC'de açık erişimli VE ticari-uygun (CC BY/CC0)
        makalelerin tam metnini de ekler. En fazla 'fulltext_limit' tanesi
        için (her biri ağ isteği + token maliyeti olduğu için sınırlı).

    NCBI'a erişilemezse [] döner (çağıran CrossRef'e düşebilir).
    """
    if not _configure_entrez():
        return []

    queries = _keywords(topic, lang=lang)
    collected = {}
    seen_pmids = set()

    # 1) Arama + özet
    for query in queries:
        if len(collected) >= target_count:
            break
        try:
            pmids = _search_pmids(query, retmax=12)
        except Exception:
            continue
        new = [p for p in pmids if p not in seen_pmids]
        if not new:
            continue
        seen_pmids.update(new)
        try:
            summaries = _fetch_summaries(new)
        except Exception:
            continue

        for pmid, rec in summaries.items():
            if len(collected) >= target_count:
                break
            abstract = rec.get('abstract') or ''
            if len(abstract) < 80:
                continue  # özet yok/çok kısa
            if not _relevant(abstract, rec['title'], topic):
                continue

            citation = f"{rec['authors']} ({rec['year']}). {rec['title']}."
            if rec['container']:
                citation += f" {rec['container']}."
            if rec['doi']:
                citation += f" https://doi.org/{rec['doi']}"
            citation += f" PMID:{pmid}"

            rec['citation'] = citation
            rec['pmcid'] = None
            rec['fulltext'] = None
            rec['license'] = None
            collected[pmid] = rec

    records = list(collected.values())

    # 2) Tam metin (sadece birkaçı, sadece ticari-uygun lisans)
    if want_fulltext:
        added = 0
        for rec in records:
            if added >= fulltext_limit:
                break
            pmcid = _pmid_to_pmcid(rec['pmid'])
            if not pmcid:
                continue
            rec['pmcid'] = pmcid
            fulltext, lic = _fetch_pmc_fulltext(pmcid)
            rec['license'] = lic
            if fulltext:
                rec['fulltext'] = fulltext
                added += 1

    return records[:target_count]