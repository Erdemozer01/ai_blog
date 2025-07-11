import re, json

import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update
from datetime import date

import google.generativeai as genai

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('GenerateArticleApp', external_stylesheets=external_stylesheets)


def run_gemini_sync(user_request_text):
    """
    Doğrudan Gemini API'sini çağırır ve metin içine gömülecek şekilde
    yapısal veri (grafik/tablo) üretir.
    """
    from blog.models import APIKey

    try:
        api_key_object = APIKey.objects.get(service_name='Google Gemini', is_active=True)
    except APIKey.DoesNotExist:
        raise ValueError("Veritabanında aktif bir 'Google Gemini' API anahtarı bulunamadı.")

    genai.configure(api_key=api_key_object.key)
    generation_config = {"temperature": 0.7, "max_output_tokens": 8192}
    model = genai.GenerativeModel(model_name="gemini-2.5-pro", generation_config=generation_config)
    current_year = date.today().year

    # === EN GELİŞMİŞ PROMPT ===
    prompt = f"""
    Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, yayınlanmaya hazır bir makale taslağı oluşturmak.

    İstek Konusu: "{user_request_text}"

    Makalenin bölümlerini aşağıdaki 8 bölümden oluşacak şekilde ve her birinin arasına `_||_SECTION_BREAK_||_` ayıracını koyarak oluştur.

    Oluşturulacak Bölümlerin Sırası:
    1.  Başlık: Spesifik, analitik ve akademik bir başlık.
    2.  İngilizce Özet (Abstract): Yaklaşık 150 kelimelik, makaleyi özetleyen İngilizce bir abstract.
    3.  Türkçe Özet: İngilizce özetin anlam olarak aynısı olan, akıcı bir Türkçe çevirisi.
    4.  Kategori Adı: Konuyu en iyi özetleyen 1-2 kelimelik kategori adı.
    5.  Anahtar Kelimeler: Virgülle ayrılmış 5-6 anahtar kelime.
    6.  Tam İçerik: Markdown formatında, en az 1500 kelime uzunluğunda. Metin, son 5 yıla ({current_year - 5}-{current_year}) odaklanan güncel bir literatür taramasıyla başlamalıdır. Konuyu analiz eden 3-4 ara başlık ve bir sonuç bölümü ekle. Metin içinde [1], [2] gibi atıflar olsun. ÇOK ÖNEMLİ: Metnin içinde, verilerin görselleştirileceği uygun yerlere `_||_STRUCTURED_DATA_1_||_`, `_||_STRUCTURED_DATA_2_||_` gibi placeholder'lar yerleştir.
    7.  Kaynakça: Metindeki atıflara karşılık gelen, numaralı, 10-15 kaynakça maddesi.
    8.  Yapısal Veri (JSON): Makale içindeki placeholder'larla eşleşen, anahtar-değer yapısında GEÇERLİ bir JSON nesnesi oluştur. Anahtarlar metindeki placeholder'daki sayılar olmalı (örn: "1", "2"). Sadece JSON nesnesini ver, başına veya sonuna "```json" gibi kod blokları ekleme.
        - Bir tablo için: `{{"1": {{"type": "table", "title": "Tablo Başlığı", "columns": ["Sütun 1", "Sütun 2"], "data": [["Değer 1A", "Değer 1B"]]}}}}`
        - Bir çubuk grafik için: `{{"2": {{"type": "chart", "chart_type": "bar", "title": "Grafik Başlığı", "data": {{"x": ["Kategori A"], "y": [10]}}}}}}`
        - Eğer uygun veri yoksa, `{{}}` şeklinde boş bir nesne döndür.

    Cevabında başka hiçbir açıklama veya metin olmasın. Sadece bu 8 bölümü, aralarında belirtilen ayraçla birlikte ver.
    """

    print("Gelişmiş prompt ile Gemini API'sine istek gönderiliyor...")
    response = model.generate_content(prompt)
    print("Gemini API'sinden yanıt alındı.")

    response_text = response.text
    parts = response_text.split('_||_SECTION_BREAK_||_')

    structured_data_json = None
    if len(parts) > 7:
        try:
            json_string = parts[7].strip().replace("```json", "").replace("```", "").strip()
            if json_string:
                structured_data_json = json.loads(json_string)
        except json.JSONDecodeError:
            print("HATA: AI tarafından üretilen yapısal veri geçerli bir JSON değil.")
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

    # Temizleme işlemleri aynı kalacak
    ai_data['title'] = ai_data.get('title', '').replace('**', '').strip()
    ai_data['english_abstract'] = re.sub(r'^\s*(\*\*abstract:\*\*|abstract:)\s*', '',
                                         ai_data.get('english_abstract', ''), flags=re.IGNORECASE).strip()
    ai_data['turkish_abstract'] = re.sub(r'^\s*(\*\*özet:\*\*|özet:)\s*', '', ai_data.get('turkish_abstract', ''),
                                         flags=re.IGNORECASE).strip()

    return ai_data


@app.callback(
    Output('form-feedback-message', 'children'),
    Output('url', 'href', allow_duplicate=True),
    Input('submit-request-button', 'n_clicks'),
    State('request-textarea', 'value'),
    State('user-session-store', 'data'),
    prevent_initial_call=True
)
def handle_form_submission(n_clicks, request_text, user_data):
    from blog.models import GeneratedArticle, Category
    from django.contrib.auth.models import User

    if not user_data or 'user_id' not in user_data:
        return dbc.Alert("Kullanıcı oturum bilgisi bulunamadı. Lütfen tekrar giriş yapın.", color="danger"), no_update
    if not request_text or len(request_text.strip()) < 10:
        return dbc.Alert("Lütfen en az 10 karakterlik bir konu girin.", color="warning"), no_update

    try:
        user = User.objects.get(id=user_data['user_id'])
        ai_data = run_gemini_sync(request_text)

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise TypeError("Yapay zekadan beklenen formatta bir yanıt alınamadı.")

        category_name = ai_data.get("category_name", "Genel").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=category_name)

        # === VERİTABANINA KAYDETME (GÜNCELLENDİ) ===
        GeneratedArticle.objects.create(
            owner=user,
            user_request=request_text,
            title=ai_data.get("title"),
            category=category_obj,
            keywords=ai_data.get("keywords", ""),
            english_abstract=ai_data.get("english_abstract"),
            turkish_abstract=ai_data.get("turkish_abstract"),
            full_content=ai_data.get("content"),
            bibliography=ai_data.get("bibliography"),
            structured_data=ai_data.get("structured_data"), # YENİ ALAN
            status='tamamlandi'
        )

        success_message = dbc.Alert("Makale metni ve yapısal veriler başarıyla üretildi!", color="success")
        return success_message, "/"

    except User.DoesNotExist:
        return dbc.Alert("Geçersiz kullanıcı kimliği.", color="danger"), no_update
    except Exception as e:
        import traceback
        traceback.print_exc() # Hatanın detayını terminalde görmek için
        return dbc.Alert(f"Beklenmedik bir hata oluştu: {e}", color="danger"), no_update



@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    """
    Kullanıcı hamburger menü butonuna bastığında, menünün
    açık/kapalı durumunu tersine çevirir.
    """
    if n_clicks:
        return not is_open
    return is_open