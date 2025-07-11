import os
import json
from .models import GeneratedArticle, APIKey
import google.generativeai as genai


def generate_academic_article_task(article_id):
    """
    Verilen bir makale isteği ID'si için arka planda Gemini API'si ile içerik üretir.
    API Anahtarını veritabanından dinamik olarak okur.
    """
    article_request = None  # Hata durumunda bile erişebilmek için başta tanımlıyoruz
    try:
        # 1. İlgili makale isteğini veritabanından bul ve durumunu güncelle
        article_request = GeneratedArticle.objects.get(id=article_id)
        article_request.status = 'isleniyor'
        article_request.save()

        # 2. API anahtarını .env yerine veritabanından çek
        try:
            api_key_object = APIKey.objects.get(service_name='Google Gemini', is_active=True)
            api_key = api_key_object.key
        except APIKey.DoesNotExist:
            raise ValueError(
                "Veritabanında aktif bir 'Google Gemini' API anahtarı bulunamadı. Lütfen admin panelinden ekleyin.")

        genai.configure(api_key=api_key)

        # 3. Gemini modelini ve üretim ayarlarını yapılandır
        generation_config = {
            "temperature": 0.8,
            "top_p": 1,
            "max_output_tokens": 8192,  # Daha uzun makaleler için artırıldı
        }
        # İstediğiniz gibi en güncel modeli kullanıyoruz
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
        )

        # 4. AI için detaylı bir "Prompt" (talimat) oluştur
        prompt = f"""
        Bir akademik araştırmacı ve uzman bir yazar rolünü üstlen. Aşağıdaki konu hakkında, istenen JSON formatında, iyi yapılandırılmış bir makale taslağı oluştur:

        İstek Konusu: "{article_request.user_request}"

        Oluşturacağın JSON objesi şu anahtarlara sahip olmalı: "title", "abstract", "content", "bibliography".

        - "title": Konuyla ilgili, ilgi çekici ve akademik bir başlık.
        - "abstract": Makalenin amacını, temel yaklaşımını ve ana sonuçlarını özetleyen, yaklaşık 150 kelimelik bir özet (abstract).
        - "content": "1. Giriş", "2. Ana Tartışma" ve "3. Sonuç" gibi alt başlıklar içeren, en az 600 kelimelik, paragraflara bölünmüş, akıcı ve tutarlı bir makale metni.
        - "bibliography": Makalede kullanılmış gibi görünen, konuyla ilgili ve gerçekçi formatta 3-5 adet kaynakça maddesi.

        Cevabın SADECE ve SADECE istenen formatta, geçerli bir JSON objesi olmalı. Öncesinde veya sonrasında kesinlikle başka hiçbir metin veya açıklama ekleme.
        """

        # 5. Gemini API'sini çağır
        print(f"ID {article_id}: Gemini 1.5 Pro API'sine istek gönderiliyor...")
        response = model.generate_content(prompt)
        print(f"ID {article_id}: Gemini API'sinden yanıt alındı.")

        # 6. Gelen JSON formatındaki yanıtı temizle ve işle
        # AI bazen yanıtı ```json ... ``` bloğu içine koyabilir, bunu temizliyoruz.
        cleaned_json_string = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned_json_string)

        # 7. Veritabanındaki kaydı AI'dan gelen verilerle güncelle
        article_request.title = data.get("title", "Başlık Üretilemedi")
        article_request.abstract = data.get("abstract", "Özet üretilemedi.")
        article_request.full_content = data.get("content", "İçerik üretilemedi.")
        article_request.bibliography = data.get("bibliography", "Kaynakça üretilemedi.")
        article_request.status = 'tamamlandi'
        article_request.save()
        print(f"ID {article_id}: Makale başarıyla üretildi ve veritabanına kaydedildi.")

    except Exception as e:
        # Herhangi bir hata durumunda (API, JSON parse, DB vb.) görevi sonlandır ve durumu güncelle
        error_message = f"Hata oluştu (ID: {article_id}): {e}"
        print(error_message)
        if article_request:
            article_request.status = 'hata'
            # Hata mesajını da kaydedebiliriz (modele bir alan ekleyerek)
            # article_request.error_message = error_message
            article_request.save()