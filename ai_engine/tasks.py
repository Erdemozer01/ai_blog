import logging
import threading
from datetime import date
import re
import json

from django.contrib.auth.models import User
from django.db import transaction

from blog.models import GeneratedArticle, Category
from blog.pubmed_sources import collect_pubmed_sources_for_topic
from blog.reference_check import collect_real_sources_for_topic, remove_orphan_references, clean_article_references
from blog.models import create_notification
from billing.services import charge
from ai_engine.services import generate_with_pool, generate_json_with_pool, get_fallback_models, get_base_prompt

logger = logging.getLogger(__name__)

def _normalize_json_article(data, real_sources=None):
    """
    AI'dan gelen JSON makale nesnesini, kaydetme akışının beklediği ai_data
    şekline çevirir ve izlenebilirlik doğrulaması yapar:
      - structured_data dict değilse boşaltılır.
      - Bir tablo/grafiğin 'source' alanı kaynakçadaki [N]'e bağlanamıyorsa
        (geçersiz [N]'e işaret ediyorsa) o tablo/grafik DÜŞÜRÜLÜR — izlenemez
        veri yayınlanmaz (örn. 'IDF 2024' gibi kaynakçada olmayan atıf).
    """
    def _s(v):
        return v.strip() if isinstance(v, str) else (v or "")

    biblio = _s(data.get('bibliography'))
    valid_nums = set(int(n) for n in re.findall(r'^\s*\[?(\d+)[\].\)]', biblio, re.MULTILINE))

    sd = data.get('structured_data')
    if not isinstance(sd, dict):
        sd = {}
    cleaned_sd = {}
    for k, v in sd.items():
        if not isinstance(v, dict):
            continue
        src = str(v.get('source', ''))
        ref_nums = [int(n) for n in re.findall(r'\[(\d+)\]', src)]
        if ref_nums:
            # source bir [N] içeriyor → N kaynakçada GERÇEKTEN varsa kabul, yoksa düşür
            if any(n in valid_nums for n in ref_nums):
                cleaned_sd[k] = v
            # geçersiz [N] → izlenemez, atılır
        else:
            # source'ta [N] yok:
            #   - kaynakça varsa → izlenemez kabul edilir, DÜŞÜRÜLÜR (örn. "IDF 2024")
            #   - kaynakça hiç yoksa → filtreleme yapma (lenient)
            if not valid_nums:
                cleaned_sd[k] = v

    return {
        "title": _s(data.get('title')) or "Başlık Üretilemedi",
        "english_abstract": _s(data.get('english_abstract')),
        "turkish_abstract": _s(data.get('turkish_abstract')),
        "category_name": _s(data.get('category_name')) or "Genel",
        "keywords": _s(data.get('keywords')),
        "content": _s(data.get('content')),
        "bibliography": biblio,
        "structured_data": cleaned_sd,
    }


def _parse_article_response(response_text):
    """AI'dan gelen 8 bölümlü metni ayrıştırıp temizlenmiş dict döndürür."""
    parts = response_text.split('_||_SECTION_BREAK_||_')

    structured_data_json = None
    if len(parts) > 7:
        try:
            json_string = parts[7].strip().replace("```json", "").replace("```", "").strip()
            if json_string:
                structured_data_json = json.loads(json_string)
        except json.JSONDecodeError:
            structured_data_json = {}

    ai_data = {
        "title": parts[0].strip() if len(parts) > 0 else "Başlık Üretilemedi",
        "english_abstract": parts[1].strip() if len(parts) > 1 else "",
        "turkish_abstract": parts[2].strip() if len(parts) > 2 else "",
        "category_name": parts[3].strip() if len(parts) > 3 else "Genel",
        "keywords": parts[4].strip() if len(parts) > 4 else "",
        "content": parts[5].strip() if len(parts) > 5 else "",
        "bibliography": parts[6].strip() if len(parts) > 6 else "",
        "structured_data": structured_data_json or {}
    }

    # Temizleme işlemleri
    title_raw = ai_data.get('title', '')
    title_clean = re.sub(r'^\s*\d+\.\s*başlık:\s*', '', title_raw, flags=re.IGNORECASE)
    ai_data['title'] = title_clean.replace('**', '').strip()
    abstract_raw = ai_data.get('english_abstract', '')
    abstract_clean = re.sub(r'^\s*(\d+\.\s*)?((ingilizce\s*)?özet|abstract)(\s*\(abstract\))?:\s*', '', abstract_raw,
                            flags=re.IGNORECASE)
    ai_data['english_abstract'] = abstract_clean.strip()
    tr_abstract_raw = ai_data.get('turkish_abstract', '')
    tr_abstract_clean = re.sub(r'^\s*(\d+\.\s*)?(türkçe\s*)?özet:\s*', '', tr_abstract_raw, flags=re.IGNORECASE)
    ai_data['turkish_abstract'] = tr_abstract_clean.strip()
    content_raw = ai_data.get('content', '')
    content_clean = re.sub(r'^\s*giriş:\s*', '', content_raw, flags=re.IGNORECASE)
    ai_data['content'] = content_clean.strip()
    biblio_raw = ai_data.get('bibliography', '')
    biblio_clean = re.sub(r'^\s*(\d+\.\s*)?kaynakça:\s*', '', biblio_raw, flags=re.IGNORECASE)
    ai_data['bibliography'] = biblio_clean.strip()

    return ai_data


def resolve_category(ai_category_name, title="", abstract=""):
    """Makaleye kategori atar.

    1) AI'in onerdigi ad mevcut bir kategoriyle (buyuk/kucuk harf duyarsiz) eslesirse onu kullanir.
    2) Eslesmezse, TUM mevcut kategorileri AI'a gosterip en uygununu sectirir.
    3) AI hicbiri uymuyor derse yeni bir kategori olusturur.
    Hata/AI yoksa guvenli sekilde isimle eslestirir veya olusturur.
    """
    ai_name = (ai_category_name or "").strip()

    # 1) Hizli yol: dogrudan isim eslesmesi
    if ai_name:
        obj = Category.objects.filter(name__iexact=ai_name).first()
        if obj:
            return obj

    existing = list(Category.objects.order_by("name").values_list("id", "name"))

    # 2) AI ile anlamsal eslestirme (mevcut kategoriler arasindan)
    if existing:
        try:
            cat_lines = "\n".join(f"{cid}: {cname}" for cid, cname in existing)
            prompt = (
                "Bir makale icin en uygun kategoriyi sececeksin.\n"
                f"Makale basligi: {title}\n"
                f"Makale ozeti: {(abstract or '')[:400]}\n"
                f"AI'in onerdigi kategori: {ai_name or '(yok)'}\n\n"
                "MEVCUT KATEGORILER (id: ad):\n"
                f"{cat_lines}\n\n"
                "Makale konu olarak yukaridaki kategorilerden birine uyuyorsa SADECE o "
                "kategorinin id numarasini yaz (ornek: 5). Hicbiri uymuyorsa 1-2 kelimelik "
                "yeni bir kategori adini su bicimde yaz: YENI: <kategori adi>. "
                "Baska hicbir aciklama ekleme."
            )
            result = None
            for svc, mdl in get_fallback_models("Google Gemini", "gemini-2.5-flash", cross_provider=True):
                try:
                    result, _key = generate_with_pool(
                        prompt, service_name=svc, model_name=mdl,
                        max_tokens=20, temperature=0.2)
                    if result:
                        break
                except Exception:
                    continue
            answer = (result or "").strip()
            if answer:
                valid_ids = {cid for cid, _ in existing}
                # Yeni kategori istendi mi?
                new_match = re.search(r"YEN[İI]\s*:\s*(.+)", answer, re.IGNORECASE)
                if new_match:
                    new_name = new_match.group(1).strip().strip('"').strip().title()
                    if new_name:
                        return (Category.objects.filter(name__iexact=new_name).first()
                                or Category.objects.create(name=new_name))
                # Mevcut kategori id'si mi?
                id_match = re.search(r"\d+", answer)
                if id_match:
                    cid = int(id_match.group())
                    if cid in valid_ids:
                        obj = Category.objects.filter(id=cid).first()
                        if obj:
                            return obj
        except Exception:
            pass

    # 3) Fallback: AI'in onerdigi (yoksa 'Genel') ile eslestir/olustur
    name = (ai_name or "Genel").title()
    return (Category.objects.filter(name__iexact=name).first()
            or Category.objects.create(name=name))


def generate_article_task(
    user_id, request_text, interpreted_topic, word_count,
    selected_service, selected_model, lang
):
    """
    Makale üretimini arka planda gerçekleştiren görev.
    """
    try:
        user = User.objects.get(id=user_id)
        
        # 1. Kaynakları topla
        src_count = 8
        if word_count <= 500:
            src_count = 8
        elif word_count <= 1500:
            src_count = 15
        elif word_count <= 2500:
            src_count = 20
        else:
            src_count = 25

        real_sources = None
        ft_limit = max(4, min(src_count // 2, 8))
        try:
            real_sources = collect_pubmed_sources_for_topic(
                interpreted_topic, target_count=src_count, fulltext_limit=ft_limit)
            if not real_sources:
                real_sources = None
        except Exception as e:
            logger.warning(f"PubMed kaynak toplama hatası: {e}")
            real_sources = None

        if not real_sources:
            try:
                real_sources = collect_real_sources_for_topic(interpreted_topic, target_count=src_count)
                if not real_sources:
                    real_sources = None
            except Exception as e:
                logger.warning(f"CrossRef kaynak toplama hatası: {e}")
                real_sources = None

        # 2. AI ile makale üretimi
        bio_context = None 

        json_prompt = get_base_prompt(
            interpreted_topic, word_count, real_sources=real_sources, output_format='json')
        section_prompt = get_base_prompt(
            interpreted_topic, word_count, real_sources=real_sources, output_format='sections')

        base_system = ("Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. "
                       "Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş "
                       "yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde "
                       "konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, "
                       "yayınlanmaya hazır bir makale taslağı oluşturmak. "
                       "AKADEMİK DÜRÜSTLÜK: Asla var olmayan kaynak, yazar, makale veya DOI "
                       "uydurma. Emin olmadığın bilgiyi gerçekmiş gibi sunma. Gerçek olmayan "
                       "bir kaynağa atıf yapmaktansa o iddiayı atıfsız bırak. ")
        json_system = base_system + ("Cevabını, başka hiçbir açıklama olmadan, TEK bir geçerli "
                                     "JSON nesnesi olarak ver.")
        section_system = base_system + ("Cevabını, istenen 8 bölümün arasına "
                                        "`_||_SECTION_BREAK_||_` ayıracı koyarak, başka hiçbir "
                                        "açıklama olmadan sunmalısın.")

        max_tokens = min(int(word_count * 2.8) + 4000, 32768)

        model_chain = get_fallback_models(preferred_service=selected_service,
                                          preferred_model=selected_model,
                                          cross_provider=False)

        used_key = None
        last_error = None
        ai_data = None

        # --- 1) ÖNCE JSON dene ---
        for svc, mdl in model_chain:
            try:
                data, used_key = generate_json_with_pool(
                    json_prompt, service_name=svc, model_name=mdl,
                    system_prompt=json_system, max_tokens=max_tokens, temperature=0.7)
                if isinstance(data, dict) and (data.get('content') or '').strip():
                    ai_data = _normalize_json_article(data, real_sources)
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"JSON üretim hatası ({svc}/{mdl}): {e}")
                continue

        # --- 2) JSON başarısızsa: 8-bölüm formatına düş ---
        if not ai_data:
            response_text = None
            for svc, mdl in model_chain:
                try:
                    response_text, used_key = generate_with_pool(
                        section_prompt, service_name=svc, model_name=mdl,
                        system_prompt=section_system, max_tokens=max_tokens, temperature=0.7)
                    if response_text:
                        ai_data = _parse_article_response(response_text)
                        break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Section üretim hatası ({svc}/{mdl}): {e}")
                    continue
            if not ai_data:
                raise RuntimeError(f"Tüm modeller başarısız oldu. Son hata: {last_error}")

        # 3. Makaleyi kaydet
        with transaction.atomic():
            category_obj = resolve_category(
                ai_data.get("category_name"),
                title=ai_data.get("title", "") or "",
                abstract=(ai_data.get("turkish_abstract") or ai_data.get("english_abstract") or ""),
            )

            new_article = GeneratedArticle.objects.create(
                owner=user,
                user_request=request_text,
                title=ai_data.get("title"),
                category=category_obj,
                keywords=ai_data.get("keywords", ""),
                english_abstract=ai_data.get("english_abstract"),
                turkish_abstract=ai_data.get("turkish_abstract"),
                full_content=ai_data.get("content"),
                bibliography=ai_data.get("bibliography"),
                structured_data=ai_data.get("structured_data"),
                status='tamamlandi',
                is_published=bool(user.is_superuser),
            )

            # --- 1) DETERMİNİSTİK öksüz kaynak temizliği ---
            try:
                remove_orphan_references(new_article)
                new_article.refresh_from_db()
            except Exception as e:
                logger.warning(f"Öksüz kaynak temizleme hatası: {e}")

            # --- 2) ZORUNLU CrossRef DOĞRULAMASI ---
            try:
                ok_verify, _msg = clean_article_references(new_article)
                new_article.refresh_from_db()
                if not ok_verify:
                    logger.warning(f"CrossRef doğrulama hatası: {_msg}")
            except Exception as e:
                logger.warning(f"CrossRef doğrulama hatası: {e}")

            # --- Kredi düş ---
            if not user.is_superuser:
                try:
                    charge(user, 'makale_uretim', default_cost=15,
                           description=f"Makale üretimi: {ai_data.get('title', '')[:50]}")
                except Exception as e:
                    logger.error(f"Kredi düşme hatası (user_id: {user_id}): {e}")

        logger.info(f"Makale başarıyla üretildi: {new_article.title} (ID: {new_article.id})")

        # Kullaniciya basari bildirimi (makale hazir + link)
        try:
            create_notification(
                category='sistem',
                title=f"Makaleniz hazir: {new_article.title[:60]}",
                message=f"'{new_article.title}' makaleniz olusturuldu. Goruntulemek icin: {new_article.get_absolute_url()}",
                related_user=user,
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Makale üretim görevinde hata oluştu (user_id: {user_id}, request: {request_text}): {e}", exc_info=True)
        # Hata durumunda bildirim oluştur
        create_notification(
            category='makale_hatasi',
            title=f"Makale oluşturma hatası: {str(request_text)[:60]}",
            message=f"Konu: {request_text}",
            technical_detail=str(e),
            related_user=User.objects.get(id=user_id),
        )
    finally:
        # Arka plan thread'inin DB baglantisini kapat (baglanti sizintisini onler)
        try:
            from django.db import connection
            connection.close()
        except Exception:
            pass
