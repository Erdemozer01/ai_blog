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


def _norm_doi(doi):
    return (doi or "").strip().lower().rstrip('.')


# --------------------------------------------------------------------------- #
# OTOMATİK DÜZELTME: desteklenmeyen cümleyi kaynağa SADIK şekilde yeniden yaz
# --------------------------------------------------------------------------- #
def _norm_txt(s):
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()


def _ai_rewrite(claim, source_text):
    """Desteklenmeyen bir cümleyi, KAYNAK METNİ'ne sadık kalacak şekilde yeniden
    yazar. Yalnız düzeltilmiş cümleyi (atıf işareti olmadan) döndürür; başarısızsa None.
    """
    if not source_text:
        return None
    try:
        from ai_engine.services import generate_with_fallback
        prompt = (
            "Bir CUMLE, atif yaptigi KAYNAK METNI tarafindan desteklenmiyor. "
            "Gorevin: cumleyi, SADECE kaynak metninde gercekten yer alan bilgiye "
            "sadik kalacak sekilde yeniden yazmak. Kaynakta olmayan bir iddiayi "
            "cikar ya da kaynagin soyledigiyle sinirli, olculu bir ifadeye cevir. "
            "Kendi genel bilgini EKLEME. Ayni dilde yaz. Koseli parantezli atif "
            "numarasi (ornegin [1]) EKLEME. SADECE duzeltilmis tek cumleyi dondur, "
            "baska aciklama yazma.\n\n"
            f'CUMLE: "{claim}"\n\n'
            f"KAYNAK METNI:\n{source_text[:SOURCE_TEXT_LIMIT]}\n"
        )
        text, _k = generate_with_fallback(
            prompt, service_name="Google Gemini", model_name="gemini-3.5-flash",
            max_tokens=400, temperature=0.2)
        if not text:
            return None
        out = text.strip().strip('"').strip()
        out = out.split('\n')[0].strip().strip('"').strip()
        out = re.sub(r'\s*\[[\d\s,]+\]', '', out).strip()   # atıf işaretlerini at
        return out or None
    except Exception:
        return None


def _rewrite_in_content(content, claim, nums, new_sentence):
    """full_content içinde 'claim' cümlesini bulup 'new_sentence' + atıf ile değiştirir.

    Atıf işaretleri korunur (cümlenin sonuna [n1, n2] olarak yeniden eklenir).
    Bulunamazsa (content, False) döner; asla bozmaz.
    """
    core = (claim or '').strip().rstrip(' .!?;:')
    words = re.findall(r'\S+', core)
    if not words:
        return content, False
    sep = r'(?:\s|\[[\d\s,]+\])+'                 # kelimeler arası boşluk/atıf
    pattern = sep.join(re.escape(w) for w in words)
    tail = r'(?:\s|\[[\d\s,]+\])*[.!?]?'          # sondaki atıf + noktalama
    try:
        rx = re.compile(pattern + tail)
    except re.error:
        return content, False
    cite = '[' + ', '.join(str(n) for n in nums) + ']'
    new_clean = (new_sentence or '').strip().rstrip('.!?').strip()
    if not new_clean:
        return content, False
    replacement = f"{new_clean} {cite}."
    new_content, n = rx.subn(lambda m: replacement, content, count=1)
    return new_content, (n > 0)


def _apply_corrections(article, candidates):
    """candidates: [(claim, nums, source_text), ...].

    Her aday için AI'dan sadık bir yeniden-yazım alır, full_content içinde yerine
    koyar ve makaleyi kaydeder. Düzeltilenlerin listesini döndürür:
      [{'nums','before','after'}, ...]
    """
    content = article.full_content or ""
    if not content or not candidates:
        return []
    fixed = []
    for claim, nums, src in candidates:
        new_sentence = _ai_rewrite(claim, src)
        if not new_sentence or _norm_txt(new_sentence) == _norm_txt(claim):
            continue
        new_content, ok = _rewrite_in_content(content, claim, nums, new_sentence)
        if ok:
            content = new_content
            fixed.append({
                'nums': nums,
                'before': claim[:300],
                'after': new_sentence[:300],
            })
    if fixed:
        try:
            article.full_content = content
            article.save(update_fields=['full_content'])
        except Exception as e:
            logger.warning(
                f"Otomatik düzeltme kaydedilemedi (article {getattr(article,'id','?')}): {e}")
            return []
    return fixed


# --------------------------------------------------------------------------- #
# Üretim anında: ELDEKİ kaynak JSON'u ile doğrulama (yeniden çekmeden)
# --------------------------------------------------------------------------- #
def verify_with_sources(article, real_sources, max_claims=MAX_CLAIMS,
                        send_email=False, auto_fix=True):
    """Makale üretimi biter bitmez, ZATEN toplanmış real_sources (JSON) ile
    atıf sadakatini doğrular. Kaynak metnini yeniden ÇEKMEZ.

    real_sources: [{'citation','doi','pmid','abstract','fulltext',...}, ...]
    Sonucu article.reference_check_result['faithfulness'] altına yazar (CrossRef
    varlık doğrulaması ayrı; onu ezmez). Döner: (ok, mesaj).
    """
    from django.utils import timezone
    if not real_sources:
        return False, "kaynak JSON'u yok"

    # DOI/PMID -> kaynak metni (tam metin + özet); ayrıca sıra (1-based) yedeği
    by_doi, by_pmid, ordered = {}, {}, []
    for s in real_sources:
        txt = "\n\n".join(t for t in (s.get('fulltext'), s.get('abstract')) if t)
        ordered.append(txt)
        d = _norm_doi(s.get('doi'))
        if d:
            by_doi[d] = txt
        p = str(s.get('pmid') or '').strip()
        if p:
            by_pmid[p] = txt

    biblio = _parse_bibliography(article.bibliography)   # num -> {'text','doi'}
    claims = _collect_claims(article.full_content)
    if max_claims:
        claims = claims[:max_claims]

    def _src_for(num):
        entry = biblio.get(num) or {}
        d = _norm_doi(entry.get('doi'))
        if d and d in by_doi:
            return by_doi[d]
        if 1 <= num <= len(ordered):     # numaralama korunduysa sıra yedeği
            return ordered[num - 1]
        return None

    checked = supported = unverifiable = 0
    unsupported_items = []
    fix_candidates = []
    for claim, nums in claims:
        verdicts, note_any, src_parts = [], "", []
        for n in nums:
            src_text = _src_for(n)
            if src_text:
                src_parts.append(src_text)
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
                'claim': claim[:300], 'nums': nums,
                'note': note_any or "Kaynakta bu iddia açıkça bulunamadı.",
            })
            combined = "\n\n".join(src_parts)
            if combined:
                fix_candidates.append((claim, nums, combined))

    # OTOMATİK DÜZELTME: desteklenmeyen cümleleri kaynağa sadık şekilde yeniden yaz
    fixed = _apply_corrections(article, fix_candidates) if auto_fix else []
    fixed_by_claim = {f['before']: f for f in fixed}
    for it in unsupported_items:
        f = fixed_by_claim.get(it['claim'])
        if f:
            it['fixed'] = True
            it['after'] = f['after']

    total = checked
    score = int(round(100 * supported / total)) if total else None
    faithfulness = {
        'checked': checked, 'supported': supported, 'unverifiable': unverifiable,
        'score': score, 'unsupported': unsupported_items,
        'auto_fixed_count': len(fixed),
        'auto_fixed': fixed,
        'note': ("Üretim anında, toplanan kaynak JSON'una göre doğrulandı."
                 + (f" {len(fixed)} cümle kaynağa sadık şekilde otomatik düzeltildi."
                    if fixed else "")),
    }
    try:
        existing = article.reference_check_result
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged['faithfulness'] = faithfulness
        article.reference_check_result = merged
        article.reference_checked_at = timezone.now()
        article.save(update_fields=['reference_check_result', 'reference_checked_at'])
    except Exception as e:
        logger.warning(f"Sadakat sonucu kaydedilemedi (article {getattr(article,'id','?')}): {e}")

    if send_email:
        _send_citation_email(article, faithfulness)

    if total == 0:
        return True, f"Doğrulanabilir atıf yok (doğrulanamayan: {unverifiable})."
    return True, (f"Sadakat: {supported}/{total} (skor {score}); "
                  f"sorunlu: {len(unsupported_items)}, doğrulanamayan: {unverifiable}.")


# --------------------------------------------------------------------------- #
# Ana giriş noktası
# --------------------------------------------------------------------------- #
def verify_article_citations(article, max_claims=MAX_CLAIMS, auto_fix=True):
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
    fix_candidates = []

    for claim, nums in claims:
        # Bir cümle birden çok kaynağa atıf yapabilir; HERHANGI biri destekliyorsa OK.
        verdicts = []
        note_any = ""
        src_parts = []
        for n in nums:
            abstract, fulltext = _src(n)
            src_text = "\n\n".join(t for t in (fulltext, abstract) if t)
            if src_text:
                src_parts.append(src_text)
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
            combined = "\n\n".join(src_parts)
            if combined:
                fix_candidates.append((claim, nums, combined))

    # CrossRef varlık doğrulaması (kaynak gerçekten var mı) — mevcut altyapı
    crossref_summary = None
    try:
        from blog.reference_check import clean_article_references
        ok_cr, msg_cr = clean_article_references(article)
        crossref_summary = {'ok': bool(ok_cr), 'message': str(msg_cr)}
        article.refresh_from_db()
    except Exception as e:
        crossref_summary = {'ok': None, 'message': f"CrossRef çalıştırılamadı: {e}"}

    # OTOMATİK DÜZELTME — CrossRef refresh_from_db'DEN SONRA (içeriği ezmesin diye)
    fixed = _apply_corrections(article, fix_candidates) if auto_fix else []
    fixed_by_claim = {f['before']: f for f in fixed}
    for it in unsupported_items:
        f = fixed_by_claim.get(it['claim'])
        if f:
            it['fixed'] = True
            it['after'] = f['after']

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
        'auto_fixed_count': len(fixed),
        'auto_fixed': fixed,
        'crossref': crossref_summary,
        'note': (
            "Kaynak metni alınamayan atıflar 'doğrulanamadı' sayıldı (paralı makale / "
            "PMID yok / NCBI erişimi yok olabilir)."
            + (f" {len(fixed)} cümle kaynağa sadık şekilde otomatik düzeltildi."
               if fixed else "")
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
        auto_fixed = result.get('auto_fixed_count') or 0
        if auto_fixed:
            lines.append(
                f"Otomatik düzeltme: {auto_fixed} cümle, kaynağına sadık kalacak "
                "şekilde AI tarafından yeniden yazıldı.\n")
        if unsupported:
            lines.append("Kaynakta AÇIKÇA bulunamayan iddialar (gözden geçirin):\n")
            for i, it in enumerate(unsupported[:15], 1):
                nums = ", ".join(str(n) for n in it['nums'])
                tag = " [düzeltildi]" if it.get('fixed') else ""
                lines.append(f"{i}.{tag} [{nums}] {it['claim']}\n   → {it['note']}\n")
                if it.get('fixed') and it.get('after'):
                    lines.append(f"   ✓ Yeni: {it['after']}\n")
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
