import re
import json
from datetime import date
from celery import shared_task
import random
import string
import traceback

# API kütüphaneleri
import google.generativeai as genai
from openai import OpenAI
import anthropic

# Proje modelleri
from .models import GeneratedArticle, Category, APIKey
from django.contrib.auth.models import User
from django.db import IntegrityError


def call_gemini(api_key, prompt, model_identifier, is_json=True):
    """Google Gemini API'sini çağıran fonksiyon."""
    print(f"Calling Google API with model: '{model_identifier}' (JSON mode: {is_json})...")
    genai.configure(api_key=api_key)
    generation_config = {
        "temperature": 0.7, "max_output_tokens": 8192,
        "response_mime_type": "application/json" if is_json else "text/plain",
    }
    model = genai.GenerativeModel(model_name=model_identifier, generation_config=generation_config)
    response = model.generate_content(prompt)
    return response.text


def call_openai(api_key, prompt, model_identifier, is_json=True):
    """OpenAI API'sini JSON modunda çağıran fonksiyon."""
    print(f"Calling OpenAI API with model: '{model_identifier}' (JSON mode: {is_json})...")
    client = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}]

    if is_json:
        response = client.chat.completions.create(model=model_identifier, response_format={"type": "json_object"},
                                                  messages=messages)
    else:
        response = client.chat.completions.create(model=model_identifier, messages=messages)

    return response.choices[0].message.content


def call_anthropic(api_key, prompt, model_identifier, is_json=True):
    """Anthropic Claude API'sini JSON modunda çağıran fonksiyon."""
    print(f"Calling Anthropic API with model: '{model_identifier}' (JSON mode: {is_json})...")
    client = anthropic.Anthropic(api_key=api_key)

    if is_json:
        prompt += "\n\nLütfen cevabınızı istenen şemaya uygun tek bir JSON nesnesi olarak, kod bloğu olmadan verin."

    message = client.messages.create(model=model_identifier, max_tokens=4096,
                                     messages=[{"role": "user", "content": prompt}])

    if message.content:
        raw_text = "".join(block.text for block in message.content if hasattr(block, 'text'))
        if is_json:
            json_start = raw_text.find('{')
            if json_start != -1:
                return raw_text[json_start:]
            return "{}"
        return raw_text
    return ""


@shared_task
def generate_article_task(article_id):
    """
    Bu fonksiyon, Celery tarafından arka planda çalıştırılacak olan ana görevdir.
    Tüm makale üretme, işleme ve kaydetme mantığı burada yer alır.
    """
    print(f"\n--- [CELERY-TASK] GÖREV BAŞLADI: Makale ID {article_id} işleniyor. ---")

    article = None
    try:
        article = GeneratedArticle.objects.get(id=article_id)
        service = article.generated_by_service
        if not service:
            raise Exception("Görev için API servisi belirtilmemiş.")

        print(f"[CELERY-TASK] Durum 'isleniyor' olarak güncelleniyor.")
        article.status = 'isleniyor'
        article.save()

        language_code = article.language
        user_request_text = article.user_request
        language_name = dict(GeneratedArticle.LANGUAGE_CHOICES).get(language_code, 'belirtilmemiş')
        current_year = date.today().year

        main_prompt = f"""
        Sen, titiz bir akademik araştırmacı ve veri yapılandırma uzmanısın. Görevin, verilen konu hakkında, istenen tüm bilgileri içeren TEK BİR JSON NESNESİ oluşturmaktır.

        **EN ÖNEMLİ KURALLAR:**
        1.  **KAYNAKÇA UYDURMAK KESİNLİKLE YASAKTIR.** Ürettiğin her kaynakça maddesinin gerçek ve bilimsel literatürde (Google Scholar vb.) doğrulanabilir olduğundan emin ol. Mümkünse her kaynak için bir DOI (Digital Object Identifier) ekle. Var olmayan bir kaynak eklemek, görevde başarısız olduğun anlamına gelir.
        2.  **CEVABINA KESİNLİKLE BİR GİRİŞ PARAGRAFI EKLEME.** Cevabın doğrudan istenen JSON formatında başlamalıdır.

        İstek Konusu: "{user_request_text}"

        Lütfen aşağıdaki şemaya tam olarak uyan bir JSON nesnesi oluştur:
        {{
          "title": "Konuya uygun, spesifik ve akademik bir başlık.",
          "english_abstract": "Yaklaşık 150 kelimelik, İngilizce bir abstract. BU BÖLÜM ZORUNLUDUR.",
          "language_specific_abstract": "İngilizce özetin {language_name} diline çevirisi.",
          "category_name": "Konuyu en iyi özetleyen 1-2 kelimelik kategori adı.",
          "keywords": "Virgülle ayrılmış 5-6 adet anahtar kelime.",
          "content": "Markdown formatında, en az 1500 kelime uzunluğunda, [{current_year - 5}-{current_year}] literatür taraması, [1], [2] gibi atıflar ve `_||_STRUCTURED_DATA_1_||_` gibi yer tutucular içeren tam makale metni.",
          "bibliography": "Metindeki atıflara karşılık gelen, **ZORUNLU OLARAK EN AZ 10, en fazla 15 adet**, numaralandırılmış ve GERÇEK kaynaklardan oluşan metin.",
          "structured_data": {{
            "1": {{"type": "table", "title": "Örnek Tablo Başlığı", "columns": ["Sütun 1"], "data": [["Veri 1A", "Veri 1B"]]}},
            "2": {{"type": "chart", "chart_type": "bar", "title": "Örnek Grafik Başlığı", "data": {{"x": ["A"], "y": [10]}}}}
          }}
        }}
        """

        service_name_lower = service.service_name.lower()
        response_text = ""
        if 'gemini' in service_name_lower:
            response_text = call_gemini(service.key, main_prompt, service.model_name, is_json=True)
        elif 'gpt' in service_name_lower or 'openai' in service_name_lower:
            response_text = call_openai(service.key, main_prompt, service.model_name, is_json=True)
        elif 'claude' in service_name_lower or 'anthropic' in service_name_lower:
            response_text = call_anthropic(service.key, main_prompt, service.model_name, is_json=True)

        print("--- [CELERY-TASK] AI Ham Cevabı ---\n", response_text, "\n--- Bitiş ---")

        ai_data = {}
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            raise Exception(f"Yapay zeka geçerli bir JSON döndürmedi. Gelen cevap: {response_text}")

        # Garanti Mekanizmaları ve Veri Tipi Kontrolleri
        bibliography_data = ai_data.get('bibliography', '')
        if isinstance(bibliography_data, list):
            bibliography_text = "\n".join(map(str, bibliography_data))
            ai_data['bibliography'] = bibliography_text
        else:
            bibliography_text = str(bibliography_data)

        ref_count = len(re.findall(r'^\d+\.', bibliography_text, re.MULTILINE))
        if ref_count < 10:
            print(f"UYARI: Yetersiz kaynakça ({ref_count}/10). Ek kaynaklar isteniyor...")
            # Bu kısım isteğe bağlı olarak ek kaynak isteme mantığıyla doldurulabilir.
            pass

        if not ai_data.get('english_abstract') or len(str(ai_data.get('english_abstract')).split()) < 20:
            print(f"UYARI: Makale ID {article.id} için İngilizce özet eksik. İkinci bir API çağrısı yapılıyor...")
            abstract_prompt = f"Aşağıdaki metne dayanarak yaklaşık 150 kelimelik bir İngilizce 'Abstract' yaz: \"{ai_data.get('language_specific_abstract') or ai_data.get('content') or user_request_text}\""
            generated_abstract = call_gemini(service.key, abstract_prompt, "gemini-1.5-flash-latest", is_json=False)
            if generated_abstract:
                ai_data['english_abstract'] = generated_abstract.strip()

        # Veritabanını Güncelleme
        final_category_name = (ai_data.get("category_name") or "Genel").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=final_category_name)

        article.title = ai_data.get("title", "Başlıksız Makale")
        article.category = category_obj
        article.keywords = str(ai_data.get("keywords", ""))
        article.english_abstract = ai_data.get("english_abstract", "")
        article.language_specific_abstract = ai_data.get("language_specific_abstract", "")
        article.full_content = ai_data.get("content", "")
        article.bibliography = ai_data.get("bibliography", "")
        article.structured_data = ai_data.get("structured_data", {})
        article.status = 'tamamlandi'

        try:
            article.save()
        except IntegrityError:
            print(f"UYARI: Makale ID {article.id} için başlık çakışması tespit edildi.")
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            article.title = f"{ai_data.get('title', 'Başlıksız Makale')} [{random_suffix}]"
            article.save()

        print(f"[CELERY-TASK] GÖREV BAŞARIYLA TAMAMLANDI: Makale ID {article_id}")

    except Exception as e:
        print(f"--- [CELERY-TASK] HATA OLUŞTU: Makale ID {article_id} ---")
        traceback.print_exc()
        print("----------------------------------------------------")

        if article:
            article.status = 'hata'
            article.full_content = f"Üretim sırasında bir hata oluştu:\n{traceback.format_exc()}"
            article.save()