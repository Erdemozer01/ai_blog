"""
blog.citation_check — Atıf SADAKAT doğrulaması (admin/ikinci kontrol).

Ne yapar:
  1) Makalenin kaynakçasını ayrıştırır ([N] -> DOI).
  2) Metinde her [N] atfının geçtiği cümleleri toplar.
  3) O kaynağın metnini (PubMed ÖZET + PMC açık erişimde TAM METİN) çeker.
  4) AI'a sorar: "bu cümledeki iddia bu kaynakta gerçekten geçiyor mu?"
  5) Sonucu article.reference_check_result'a yazar ve sahibine e-posta atar.

Önemli:
  - Yayın kararını DEĞİŞTİRMEZ; yalnızca işaretler (admin karar verir).
  - Kaynak metni alınamazsa (paralı makale / PMID yok / NCBI erişimi yok)
    o atıf 'desteklenmiyor' DEĞİL, 'doğrulanamadı' işaretlenir (haksız RED yok).
  - Fail-safe: her adım try/except; hata site akışını bozmaz.
"""
import re
import json
import logging

logger = logging.getLogger(__name__)

# Maliyet/süre sınırı: bir makalede en çok bu kadar atıf-cümlesi kontrol edilir.
MAX_CLAIMS = 25
# AI'a gönderilecek kaynak metni sınırı (token bütçesi).
SOURCE_TEXT_LIMIT = 5000


# --------------------------------------------------------------------------- #
# Ayrıştırma yardımcıları
# --------------------------------------------------------------------------- #
def _parse_bibliography(biblio_text):
    """Kaynakçayı {num: {'text': str, 'doi': str|None}} sözlüğüne çevirir.

    '[1] ...' veya '1. ...' / '1) ...' ile başlayan satırları yakalar.
    """
    from blog.reference_check import _extract_doi
    out = {}
    if not biblio_text:
        return out
    for line in str(biblio_text).splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[?(\d+)[\].\)]\s*(.+)$', line)
        if not m:
            continue
        num = int(m.group(1))
        text = m.group(2).strip()
        try:
            doi = _extract_doi(text)
        except Exception:
            doi = None
        out[num] = {'text': text, 'doi': doi}
    return out


def _split_sentences(content):
    """Metni kaba biçimde cümlelere böler ([N] işaretleri cümlede kalır."""
    if not content:
        return []
    # Yapısal placeholder'ları temizle
    txt = re.sub(r'_\|\|_[A-Z_]+\d*_\|\|_', ' ', str(content))
    # Markdown başlık/işaretlerini sadeleştir
    txt = txt.replace('\n', ' ')
    parts = re.split(r'(?<=[.!?])\s+', txt)
    return [p.strip() for p in parts if p.strip()]


def _citations_in(sentence):
    """Cümledeki [1], [1,2], [1, 2] gibi atıf numaralarını liste olarak döndürür."""
    nums = []
    for grp in re.findall(r'\[([\d\s,]+)\]', sentence):
        for n in re.findall(r'\d+', grp):
            nums.append(int(n))
    # sırayı koru, tekrarları at
    seen = set()
    uniq = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def _collect_claims(content):
    """Atıf içeren cümleleri (sentence, [nums]) olarak toplar."""
    claims = []
    for s in _split_sentences(content):
        nums = _citations_in(s)
        if nums:
            # atıf işaretini iddiadan çıkar (AI'ı şaşırtmasın)
            clean = re.sub(r'\s*\[[\d\s,]+\]', '', s).strip()
            if len(clean) >= 15:
                claims.append((clean, nums))
    return claims


# --------------------------------------------------------------------------- #
# Kaynak metni çekme (PubMed özet + PMC tam metin)
# --------------------------------------------------------------------------- #
def _abstract_from_pubmed_xml(xml_bytes):
    try:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_bytes)
        parts = []
        for ab in root.iter('AbstractText'):
            if ab.text:
                label = ab.attrib.get('Label')
                parts.append((f"{label}: " if label else "") + ab.text)
        return ' '.join(parts).strip() or None
    except Exception:
        return None


def _fetch_source_text(doi):
    """DOI -> (abstract|None, fulltext|None). PubMed özeti + PMC açık erişim tam metni.

    NCBI erişimi yoksa (None, None) döner (doğrulanamadı).
    """
    if not doi:
        return None, None
    try:
        from blog.pubmed_sources import (
            _configure_entrez, _pmid_to_pmcid, _fetch_pmc_fulltext,
            Entrez, MAX_FULLTEXT_CHARS,
        )
    except Exception:
        return None, None
    if Entrez is None or not _configure_entrez():
        return None, None
    try:
        pmid = None
        for field in ('AID', 'DOI'):
            try:
                h = Entrez.esearch(db='pubmed', term=f'{doi}[{field}]', retmax=1)
                rec = Entrez.read(h)
                h.close()
                ids = rec.get('IdList', [])
                if ids:
                    pmid = ids[0]
                    break
            except Exception:
                continue
        if not pmid:
            return None, None
        abstract = None
        try:
            h = Entrez.efetch(db='pubmed', id=pmid, rettype='abstract', retmode='xml')
            xml_bytes = h.read()
            h.close()
            abstract = _abstract_from_pubmed_xml(xml_bytes)
        except Exception:
            abstract = None
        fulltext = None
        try:
            pmcid = _pmid_to_pmcid(pmid)
            if pmcid:
                ft, _lic = _fetch_pmc_fulltext(pmcid)
                if ft:
                    fulltext = ft[:MAX_FULLTEXT_CHARS]
        except Exception:
            fulltext = None
        return abstract, fulltext
    except Exception:
        return None, None


# --------------------------------------------------------------------------- #
# AI ile sadakat (entailment) kontrolü
# --------------------------------------------------------------------------- #
def _ai_supported(claim, source_text):
    """(supported: bool|None, note: str). None = AI kararı alınamadı."""
    if not source_text:
        return None, "kaynak metni yok"
    try:
        from ai_engine.services import generate_with_fallback
        prompt = (
            "Bir IDDIA ve bir KAYNAK METNI verilecek. Iddia, bu kaynak metninde "
            "ACIKCA destekleniyor/ifade ediliyor mu? Kaynak metni yalnizca ozet ya "
            "da kismi tam metin olabilir; iddia burada ACIKCA yer almiyorsa "
            "'destekleniyor=false' ver. Kendi genel bilgini KULLANMA, sadece verilen "
            "metne bak.\n\n"
            f'IDDIA: "{claim}"\n\n'
            f"KAYNAK METNI:\n{source_text[:SOURCE_TEXT_LIMIT]}\n\n"
            'Yanit SADECE su JSON: {"destekleniyor": true veya false, "not": "<tek kisa cumle, Turkce>"}'
        )
        text, _k = generate_with_fallback(
            prompt, service_name="Google Gemini", model_name="gemini-3.5-flash",
            max_tokens=250, temperature=0.0)
        if not text:
            return None, "AI yaniti bos"
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return None, "AI yaniti islenemedi"
        data = json.loads(m.group())
        return bool(data.get('destekleniyor')), (data.get('not') or '').strip()
    except Exception as e:
        return None, f"AI hatasi: {e}"


# --------------------------------------------------------------------------- #
# Ana giriş noktası
# --------------------------------------------------------------------------- #
def verify_article_citations(article, max_claims=MAX_CLAIMS):
    """Makaleyi doğrular, sonucu kaydeder, sahibine e-posta atar.

    Döner: (ok: bool, mesaj: str)
    """
    from django.utils import timezone

    biblio = _parse_bibliography(article.bibliography)
    claims = _collect_claims(article.full_content)
    if max_claims:
        claims = claims[:max_claims]

    # Kaynak metinlerini bir kez çek, cache'le
    source_cache = {}   # num -> (abstract, fulltext)

    def _src(num):
        if num in source_cache:
            return source_cache[num]
        entry = biblio.get(num)
        doi = entry.get('doi') if entry else None
        res = _fetch_source_text(doi)
        source_cache[num] = res
        return res

    checked = 0
    supported = 0
    unsupported_items = []   # {'claim','nums','note'}
    unverifiable = 0

    for claim, nums in claims:
        # Bir cümle birden çok kaynağa atıf yapabilir; HERHANGI biri destekliyorsa OK.
        verdicts = []
        note_any = ""
        for n in nums:
            abstract, fulltext = _src(n)
            src_text = "\n\n".join(t for t in (fulltext, abstract) if t)
            sup, note = _ai_supported(claim, src_text)
            verdicts.append(sup)
            if note and not note_any:
                note_any = note
        if all(v is None for v in verdicts):
            unverifiable += 1
            continue
        checked += 1
        if any(v is True for v in verdicts):
            supported += 1
        else:
            unsupported_items.append({
                'claim': claim[:300],
                'nums': nums,
                'note': note_any or "Kaynakta bu iddia açıkça bulunamadı.",
            })

    # CrossRef varlık doğrulaması (kaynak gerçekten var mı) — mevcut altyapı
    crossref_summary = None
    try:
        from blog.reference_check import clean_article_references
        ok_cr, msg_cr = clean_article_references(article)
        crossref_summary = {'ok': bool(ok_cr), 'message': str(msg_cr)}
        article.refresh_from_db()
    except Exception as e:
        crossref_summary = {'ok': None, 'message': f"CrossRef çalıştırılamadı: {e}"}

    total = checked
    score = int(round(100 * supported / total)) if total else None

    # Faithfulness sonucu — CrossRef varlık doğrulamasını (eski format) EZMEDEN
    # ayrı 'faithfulness' anahtarı altında saklanır.
    faithfulness = {
        'checked': checked,
        'supported': supported,
        'unverifiable': unverifiable,
        'score': score,
        'unsupported': unsupported_items,
        'crossref': crossref_summary,
        'note': (
            "Kaynak metni alınamayan atıflar 'doğrulanamadı' sayıldı (paralı makale / "
            "PMID yok / NCBI erişimi yok olabilir)."
        ),
    }
    result = faithfulness  # e-posta / dönüş için

    try:
        existing = article.reference_check_result
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged['faithfulness'] = faithfulness
        article.reference_check_result = merged
        article.reference_checked_at = timezone.now()
        article.save(update_fields=['reference_check_result', 'reference_checked_at'])
    except Exception as e:
        logger.warning(f"Atıf doğrulama sonucu kaydedilemedi (article {article.id}): {e}")

    _send_citation_email(article, result)

    if total == 0:
        return True, ("Doğrulanabilir atıf bulunamadı "
                      f"(kaynak metni alınamayan: {unverifiable}).")
    return True, (f"Atıf doğrulama tamam. Desteklenen: {supported}/{total} "
                  f"(skor {score}). Sorunlu: {len(unsupported_items)}, "
                  f"doğrulanamayan: {unverifiable}.")


def _send_citation_email(article, result):
    """Makale sahibine atıf doğrulama sonucunu e-posta ile gönderir."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        owner = article.owner
        if not owner or not owner.email:
            return False
        checked = result.get('checked') or 0
        supported = result.get('supported') or 0
        score = result.get('score')
        unsupported = result.get('unsupported') or []
        lines = [
            f'"{article.title}" makaleniz için atıf–kaynak doğrulaması yapıldı.\n',
            f"Desteklenen atıf: {supported}/{checked}"
            + (f" (skor {score}/100)" if score is not None else "") + "\n",
        ]
        if unsupported:
            lines.append("Kaynakta AÇIKÇA bulunamayan iddialar (gözden geçirin):\n")
            for i, it in enumerate(unsupported[:15], 1):
                nums = ", ".join(str(n) for n in it['nums'])
                lines.append(f"{i}. [{nums}] {it['claim']}\n   → {it['note']}\n")
        else:
            lines.append("Tüm doğrulanabilir atıflar kaynaklarca destekleniyor görünüyor.\n")
        cr = result.get('crossref') or {}
        if cr.get('message'):
            lines.append(f"\nCrossRef kaynak doğrulaması: {cr['message']}\n")
        lines.append("\nNot: Kaynak metni alınamayan atıflar 'doğrulanamadı' sayıldı; "
                     "bu, iddianın yanlış olduğu anlamına gelmez.\n\nAI Blog Ekibi")
        subject = f"Atıf Doğrulama: {article.title or 'Makale'}"
        from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')
        send_mail(subject, "".join(lines), from_email, [owner.email], fail_silently=True)
        return True
    except Exception:
        return False
