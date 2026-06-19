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


def _clean_abstract(raw):
    """CrossRef abstract'ı JATS/XML etiketlerinden temizler."""
    if not raw:
        return None
    text = re.sub(r'<[^>]+>', ' ', raw)  # XML etiketlerini kaldır
    text = re.sub(r'\s+', ' ', text).strip()
    return text or None


def verify_single_reference(ref_text, timeout=10):
    """
    Tek bir kaynağı CrossRef'te doğrular.
    Döner: dict {
        'status': 'verified' | 'not_found' | 'unreachable',
        'doi': str|None,
        'matched_title': str|None,
        'abstract': str|None,   # atıf-içerik kontrolü için
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
            abstract = _clean_abstract(msg.get('abstract'))
            return {'status': 'verified', 'doi': doi, 'matched_title': title,
                    'abstract': abstract}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass  # DOI bulunamadı, başlıkla aramaya devam et
            else:
                return {'status': 'unreachable', 'doi': None, 'matched_title': None,
                        'abstract': None}
        except Exception:
            return {'status': 'unreachable', 'doi': None, 'matched_title': None,
                    'abstract': None}

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
            return {'status': 'not_found', 'doi': None, 'matched_title': None,
                    'abstract': None}

        # En iyi eşleşme — CrossRef relevance'a göre sıralı döner
        top = items[0]
        found_title = (top.get('title') or ['?'])[0]
        found_doi = top.get('DOI')
        found_abstract = _clean_abstract(top.get('abstract'))

        # Basit benzerlik: aranan başlık kelimelerinin ne kadarı eşleşmede var
        score = _title_similarity(query, found_title)
        if score >= 0.4:  # makul eşleşme eşiği
            return {'status': 'verified', 'doi': found_doi, 'matched_title': found_title,
                    'abstract': found_abstract}
        else:
            return {'status': 'not_found', 'doi': None, 'matched_title': found_title,
                    'abstract': None}

    except Exception:
        return {'status': 'unreachable', 'doi': None, 'matched_title': None,
                'abstract': None}


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


def _remove_fake_references(full_content, bibliography, suspicious_nums):
    """
    Şüpheli (uydurma) kaynakları kaynakçadan siler ve metindeki atıf İŞARETLERİNİ
    (örn. [3]) kaldırır. CÜMLELER KORUNUR — yalnızca [N] işareti silinir, cümlenin
    kelimelerine dokunulmaz (AI'ın ürettiği bilgi yerinde kalır). Kalan kaynaklar
    yeniden numaralandırılır.

    full_content içindeki _||_..._||_ placeholder'ları KORUNUR (regex sadece [N] yakalar).

    Döner: (yeni_content, yeni_bibliography, rapor_dict)
    """
    suspicious = set(int(n) for n in suspicious_nums)

    # Kaynakçayı ayrıştır (sıralı)
    lines = [ln.strip() for ln in (bibliography or '').split('\n') if ln.strip()]
    refs = {}
    order = []
    num_re = re.compile(r'^\[?(\d+)[\].\)]\s*(.*)')
    for ln in lines:
        m = num_re.match(ln)
        if m:
            n = int(m.group(1))
            refs[n] = m.group(2)
            order.append(n)

    # Eski→yeni numara haritası (şüpheliler atlanır)
    remap = {}
    new_n = 1
    for old_n in order:
        if old_n not in suspicious:
            remap[old_n] = new_n
            new_n += 1

    # Yeni kaynakça
    new_biblio_lines = []
    for old_n in order:
        if old_n in remap:
            new_biblio_lines.append(f"{remap[old_n]}. {refs[old_n]}")
    new_bibliography = '\n'.join(new_biblio_lines)

    # Metindeki atıfları işle ([N] → sil veya yeni numara). Placeholder'lar etkilenmez.
    def _replace_citation(match):
        n = int(match.group(1))
        if n in suspicious:
            return ''
        if n in remap:
            return f'[{remap[n]}]'
        return match.group(0)

    new_content = re.sub(r'\[(\d+)\]', _replace_citation, full_content or '')
    # Atıf silinince oluşan fazla boşluk/noktalama düzeltmesi
    new_content = re.sub(r'  +', ' ', new_content)
    new_content = re.sub(r'\s+([.,;:])', r'\1', new_content)
    new_content = re.sub(r'\(\s*\)', '', new_content)  # boş parantez kaldıysa

    rapor = {
        'silinen': sorted(suspicious & set(order)),
        'kalan': len(remap),
        'toplam': len(order),
    }
    return new_content, new_bibliography, rapor


def clean_superuser_article_references(article):
    """
    SADECE superuser'a ait makaleler için: önce kaynakları doğrular, sonra
    uydurma (bulunamayan) kaynakları siler ve metni/kaynakçayı günceller.

    (ok: bool, mesaj: str) döner.
    """
    from django.utils import timezone

    # Güvenlik: yalnızca superuser makalesi
    owner = getattr(article, 'owner', None) or getattr(article, 'author', None)
    if not owner or not getattr(owner, 'is_superuser', False):
        return False, "Bu işlem yalnızca superuser'a ait makalelerde yapılır."

    if not article.bibliography:
        return False, "Makalede kaynakça bulunamadı."

    # Önce doğrula
    result = verify_bibliography(article.bibliography)
    if not result['reachable']:
        return False, ("CrossRef API'sine ulaşılamadı. api.crossref.org'un "
                       "whitelist'te olduğundan emin olun.")

    # Şüpheli (not_found) kaynak numaralarını topla
    suspicious_nums = [int(r['num']) for r in result['results']
                       if r['status'] == 'not_found' and str(r['num']).isdigit()]

    if not suspicious_nums:
        # Sonucu yine kaydet (hepsi temiz)
        article.reference_check_result = result
        article.reference_checked_at = timezone.now()
        article.save(update_fields=['reference_check_result', 'reference_checked_at'])
        return True, f"Tüm kaynaklar doğrulandı ({result['verified']}/{result['total']}). Silinecek uydurma kaynak yok."

    # Uydurmaları temizle
    new_content, new_biblio, rapor = _remove_fake_references(
        article.full_content, article.bibliography, suspicious_nums)

    article.full_content = new_content
    article.bibliography = new_biblio
    # Doğrulama sonucunu da güncelle (artık temizlenmiş)
    article.reference_check_result = {
        'cleaned': True,
        'removed': rapor['silinen'],
        'remaining': rapor['kalan'],
        'original_total': rapor['toplam'],
    }
    article.reference_checked_at = timezone.now()
    article.save(update_fields=['full_content', 'bibliography',
                                'reference_check_result', 'reference_checked_at'])

    return True, (f"{len(rapor['silinen'])} uydurma kaynak silindi "
                  f"(numaralar: {rapor['silinen']}). Cümleler korundu, yalnızca "
                  f"sahte atıf işaretleri kaldırıldı. {rapor['kalan']} gerçek kaynak "
                  f"kaldı ve yeniden numaralandı.")


def _extract_citation_context(full_content, citation_num):
    """
    Metinde [N] atfının geçtiği cümleyi bulur (AI içerik kontrolü için).
    Placeholder'lar temizlenir.
    """
    if not full_content:
        return None
    text = re.sub(r'_\|\|_[A-Z_]+\d*_\|\|_', ' ', full_content)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    target = f'[{citation_num}]'
    for sent in sentences:
        if target in sent:
            clean = re.sub(r'\[\d+\]', '', sent).strip()
            return clean[:500]  # uzunsa kırp
    return None


def check_citation_relevance_ai(sentence, abstract, lang='tr'):
    """
    AI'a sorar: bu cümle, bu kaynağın abstract'ıyla içerik olarak ilgili mi?
    Türkçe cümle + İngilizce abstract sorununu AI çözer.

    Döner: dict {'relevance': 'relevant'|'unrelated'|'uncertain', 'note': str}
    """
    if not sentence or not abstract:
        return {'relevance': 'uncertain', 'note': 'Abstract bulunamadı.'}

    prompt = (
        "Aşağıda bir akademik makaleden bir CÜMLE ve bu cümlede atıf yapılan "
        "kaynağın ÖZETİ (abstract) var. Görevin: bu kaynağın özeti, cümledeki "
        "iddiayı/konuyu destekliyor mu yoksa alakasız mı belirlemek.\n\n"
        f"CÜMLE: {sentence}\n\n"
        f"KAYNAK ÖZETİ: {abstract[:1500]}\n\n"
        "Yalnızca şu üç kelimeden biriyle yanıt ver (başka açıklama yapma):\n"
        "- ILGILI (özet cümleyle konu/iddia olarak örtüşüyor)\n"
        "- ALAKASIZ (özet tamamen farklı bir konuda, cümleyle ilgisiz)\n"
        "- BELIRSIZ (karar verilemiyor)\n"
    )

    try:
        from ai_engine.services import generate_with_pool
        answer, _key = generate_with_pool(
            prompt, service_name='Google Gemini', model_name='gemini-2.5-flash'
        )
        if not answer:
            return {'relevance': 'uncertain', 'note': 'AI yanıt vermedi.'}
        ans = answer.strip().upper()
        if 'ALAKASIZ' in ans:
            return {'relevance': 'unrelated', 'note': 'Kaynak özeti cümleyle alakasız görünüyor.'}
        elif 'ILGILI' in ans or 'İLGİLİ' in ans:
            return {'relevance': 'relevant', 'note': 'Kaynak konuyla ilgili görünüyor.'}
        else:
            return {'relevance': 'uncertain', 'note': 'İlgi durumu belirsiz.'}
    except Exception as e:
        return {'relevance': 'uncertain', 'note': f'AI kontrolü yapılamadı: {e}'}


def check_article_references_with_content(article, max_ai_checks=8):
    """
    Kaynakları doğrular VE (abstract varsa) AI ile atıf-içerik ilgisini kontrol eder.
    AI çağrısı maliyetli olduğu için en fazla max_ai_checks kaynak kontrol edilir.

    Sonucu modele kaydeder. (ok, mesaj) döner.
    """
    from django.utils import timezone

    if not article.bibliography:
        return False, "Makalede kaynakça bulunamadı."

    result = verify_bibliography(article.bibliography)
    if not result['reachable']:
        return False, ("CrossRef API'sine ulaşılamadı. api.crossref.org'un "
                       "whitelist'te olduğundan emin olun.")

    # Doğrulanan + abstract'ı olan kaynaklar için AI içerik kontrolü
    ai_checks = 0
    relevant_count = 0
    unrelated_count = 0
    for ref in result['results']:
        if ref['status'] != 'verified':
            continue
        if ai_checks >= max_ai_checks:
            ref['content_relevance'] = 'skipped'
            continue
        abstract = ref.get('abstract')
        if not abstract:
            ref['content_relevance'] = 'no_abstract'
            continue
        sentence = _extract_citation_context(article.full_content, ref['num'])
        if not sentence:
            ref['content_relevance'] = 'no_context'
            continue
        check = check_citation_relevance_ai(sentence, abstract)
        ref['content_relevance'] = check['relevance']
        ref['content_note'] = check['note']
        ai_checks += 1
        if check['relevance'] == 'relevant':
            relevant_count += 1
        elif check['relevance'] == 'unrelated':
            unrelated_count += 1

    result['content_checked'] = True
    result['content_relevant'] = relevant_count
    result['content_unrelated'] = unrelated_count

    article.reference_check_result = result
    article.reference_checked_at = timezone.now()
    article.save(update_fields=['reference_check_result', 'reference_checked_at'])

    msg = (f"{result['verified']}/{result['total']} kaynak doğrulandı. "
           f"İçerik kontrolü: {relevant_count} ilgili, {unrelated_count} alakasız "
           f"(şüpheli atıf).")
    return True, msg


def clean_article_references(article, max_ai_checks=10):
    """
    SADE TEK AKIŞ — "Makaleyi Kontrol Et":
      1. CrossRef'e bakar; bulunmayan (doğrulanmayan) kaynakları kaynakçadan ÇIKARIR
         ve metindeki [N] atıf işaretini de kaldırır (kaynak sahte olduğu için).
      2. Kalan doğrulanmış kaynaklar için AI ile içerik uyuşmasını kontrol eder;
         içerik UYUŞMAYAN kaynağı kaynakçadan ÇIKARIR ama metinde [N] atfı KALIR
         (bilgi yerinde dursun, sadece kaynak listeden çıkar).
      3. Kaynakçayı yeniden numaralandırır.

    (ok: bool, mesaj: str) döner.
    """
    from django.utils import timezone

    if not article.bibliography:
        return False, "Makalede kaynakça bulunamadı."

    # --- 1. CrossRef doğrulama ---
    result = verify_bibliography(article.bibliography)
    if not result['reachable']:
        return False, ("CrossRef API'sine ulaşılamadı. api.crossref.org'un "
                       "whitelist'te olduğundan emin olun.")

    # Bulunamayan (sahte) kaynak numaraları
    not_found_nums = set(int(r['num']) for r in result['results']
                         if r['status'] == 'not_found' and str(r['num']).isdigit())

    # --- 1b. Sahte kaynaklar için CrossRef'te GERÇEK değiştirme ara ---
    # Atıf cümlesinin konusuyla ilgili gerçek bir makale bulunursa, sahte kaynağı
    # onunla DEĞİŞTİR (kaynakçada kalır, atıf korunur). Bulunamazsa silinir.
    replaced_refs = {}      # num -> yeni gerçek kaynak metni
    replaced_count = 0
    search_budget = 10      # en fazla 10 sahte kaynak için arama (maliyet/süre)
    for num in sorted(not_found_nums):
        if search_budget <= 0:
            break
        sentence = _extract_citation_context(article.full_content, num)
        if not sentence:
            continue
        found = find_real_reference_for_sentence(sentence)
        search_budget -= 1
        if found and found.get('citation'):
            replaced_refs[num] = found['citation']
            replaced_count += 1

    # Değiştirilenler artık "sahte" değil; silinecekler listesinden çıkar
    not_found_nums = not_found_nums - set(replaced_refs.keys())

    # --- 2. Doğrulananlar için AI içerik kontrolü ---
    unrelated_nums = set()  # içerik uyuşmayan → kaynakçadan çıkar, atıf kalır
    ai_checks = 0
    for ref in result['results']:
        if ref['status'] != 'verified':
            continue
        if ai_checks >= max_ai_checks:
            break
        abstract = ref.get('abstract')
        if not abstract:
            continue
        try:
            num = int(ref['num'])
        except (ValueError, KeyError, TypeError):
            continue
        sentence = _extract_citation_context(article.full_content, num)
        if not sentence:
            continue
        check = check_citation_relevance_ai(sentence, abstract)
        ai_checks += 1
        if check['relevance'] == 'unrelated':
            unrelated_nums.add(num)

    # --- 3. Kaynakçayı yeniden kur ---
    lines = [ln.strip() for ln in (article.bibliography or '').split('\n') if ln.strip()]
    refs = {}
    order = []
    num_re = re.compile(r'^\[?(\d+)[\].\)]\s*(.*)')
    for ln in lines:
        m = num_re.match(ln)
        if m:
            n = int(m.group(1))
            refs[n] = replaced_refs.get(n, m.group(2))  # değiştirildiyse gerçek kaynak
            order.append(n)

    # Kaynakçadan çıkarılacaklar: bulunamayanlar + içerik uyuşmayanlar
    removed_from_biblio = not_found_nums | unrelated_nums

    # Eski→yeni numara haritası (kaynakçada KALANLAR için)
    remap = {}
    new_n = 1
    for old_n in order:
        if old_n not in removed_from_biblio:
            remap[old_n] = new_n
            new_n += 1

    # Yeni kaynakça
    new_biblio_lines = []
    for old_n in order:
        if old_n in remap:
            new_biblio_lines.append(f"{remap[old_n]}. {refs[old_n]}")
    new_bibliography = '\n'.join(new_biblio_lines)

    # Metindeki atıfları işle:
    #   - not_found (sahte) → atıf işareti SİLİNİR
    #   - unrelated → atıf KALIR (ama numarası... kaynakçada yok artık)
    #   - kalan → yeni numaraya çevrilir
    # Sorun: unrelated atıf kalırsa numarası kaynakçayla uyuşmaz. Çözüm: unrelated
    # atıfları olduğu gibi bırak (eski numarayla) ama köşeli parantezi koru.
    def _replace_citation(match):
        n = int(match.group(1))
        if n in not_found_nums:
            return ''  # sahte → atıf işareti silinir
        if n in unrelated_nums:
            return ''  # içerik uyuşmaz → kaynakçadan çıktı, atıf işareti de silinir (cümle kalır)
        if n in remap:
            return f'[{remap[n]}]'  # kalan → yeni numara
        return ''  # kaynakçada karşılığı kalmayan diğer atıflar da temizlenir

    new_content = re.sub(r'\[(\d+)\]', _replace_citation, article.full_content or '')
    new_content = re.sub(r'  +', ' ', new_content)
    new_content = re.sub(r'\s+([.,;:])', r'\1', new_content)

    # Kaydet
    article.full_content = new_content
    article.bibliography = new_bibliography
    article.reference_check_result = {
        'cleaned': True,
        'replaced': replaced_count,
        'not_found_removed': sorted(not_found_nums & set(order)),
        'unrelated_removed': sorted(unrelated_nums & set(order)),
        'remaining': len(remap),
        'original_total': len(order),
    }
    article.reference_checked_at = timezone.now()
    article.save(update_fields=['full_content', 'bibliography',
                                'reference_check_result', 'reference_checked_at'])

    n_fake = len(not_found_nums & set(order))
    n_unrel = len(unrelated_nums & set(order))
    return True, (
        f"Kontrol tamamlandı. {replaced_count} sahte kaynak, konuyla ilgili GERÇEK "
        f"kaynakla değiştirildi. {n_fake} kaynak için gerçek bulunamadı, silindi "
        f"(atıfları da kaldırıldı). {n_unrel} içerik-uyuşmayan kaynak kaynakçadan "
        f"çıkarıldı (metindeki bilgi korundu). {len(remap)} kaynak kaynakçada kaldı."
    )

def _ai_extract_search_terms(sentence, lang='tr'):
    """
    Türkçe cümleden, CrossRef'te aranabilecek İngilizce anahtar arama
    terimleri üretir (AI ile). Türkçe→İngilizce konu çevirisi.
    """
    if not sentence:
        return None
    prompt = (
        "Aşağıdaki Türkçe akademik cümlenin ANA KONUSUNU İngilizce 3-6 kelimelik "
        "bir akademik arama sorgusuna çevir. Sadece arama terimlerini ver, "
        "açıklama veya noktalama ekleme.\n\n"
        f"CÜMLE: {sentence}\n\n"
        "İngilizce arama terimleri:"
    )
    try:
        from ai_engine.services import generate_with_pool
        answer, _ = generate_with_pool(prompt, service_name='Google Gemini',
                                       model_name='gemini-2.5-flash')
        if answer:
            terms = answer.strip().strip('"').strip()
            # İlk satırı al, kısalt
            terms = terms.split('\n')[0][:120]
            return terms or None
    except Exception:
        pass
    return None


def find_real_reference_for_sentence(sentence, timeout=10, lang='tr'):
    """
    Bir cümlenin konusuyla ilgili CrossRef'te GERÇEK bir makale arar.
    Bulursa APA benzeri bir kaynak string'i + DOI döner, bulamazsa None.

    Döner: dict {'citation': '...', 'doi': '...', 'title': '...'} | None
    """
    terms = _ai_extract_search_terms(sentence, lang=lang)
    if not terms:
        return None
    try:
        params = urllib.parse.urlencode({'query.bibliographic': terms, 'rows': 3})
        url = f"{CROSSREF_API}?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        items = data.get('message', {}).get('items', [])
        if not items:
            return None
        top = items[0]
        title = (top.get('title') or ['?'])[0]
        doi = top.get('DOI', '')

        # Yazarlar
        authors = top.get('author', [])
        if authors:
            first = authors[0]
            author_str = first.get('family', '')
            if len(authors) > 1:
                author_str += ' et al.'
        else:
            author_str = (top.get('publisher') or 'Unknown')

        # Yıl
        year = ''
        for k in ('published-print', 'published-online', 'created'):
            dp = top.get(k, {}).get('date-parts', [[None]])
            if dp and dp[0] and dp[0][0]:
                year = str(dp[0][0])
                break

        # Dergi
        container = (top.get('container-title') or [''])[0]

        citation = f"{author_str} ({year}). {title}."
        if container:
            citation += f" {container}."
        if doi:
            citation += f" https://doi.org/{doi}"

        return {'citation': citation, 'doi': doi, 'title': title}
    except Exception:
        return None