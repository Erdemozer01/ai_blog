import re, json
import dash_bootstrap_components as dbc
import openai
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update, html
from datetime import date
import google.generativeai as genai
import anthropic

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
app = DjangoDash('GenerateArticleApp', external_stylesheets=external_stylesheets)


def get_base_prompt(user_request_text):
    """Tüm modeller için ortak olan prompt metnini oluşturur."""
    current_year = date.today().year
    # Not: JSON içeriği için `client.chat.completions.create`'e `response_format={ "type": "json_object" }` eklenebilir
    # ama bu, metinle JSON'u bir arada isteme senaryomuzu karmaşıklaştırır. Bu yüzden metin içinde JSON istiyoruz.
    return f"""
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
        - Veriye en uygun grafik türünü ('bar', 'line', 'pie', 'scatter') kendin seç.
        - Bir tablo için: `{{"1": {{"type": "table", "title": "Tablo Başlığı", "description": "Bu tablo neyi gösteriyor, kısa bir açıklama.", "source": "Veri Kaynağı (örn: Dünya Bankası, 2024)", "columns": ["Sütun 1"], "data": [["Değer 1A"]]}}}}`
        - Bir grafik için: `{{"2": {{"type": "chart", "chart_type": "bar", "title": "Grafik Başlığı", "description": "Bu grafik neyi analiz ediyor, kısa bir açıklama.", "source": "Veri Kaynağı (örn: TUIK, 2025)", "data": {{"x": ["Kategori A"], "y": [10]}}}}}}`
        - Eğer uygun veri yoksa, `{{}}` şeklinde boş bir nesne döndür.
    Cevabında başka hiçbir açıklama veya metin olmasın. Sadece bu 8 bölümü, aralarında belirtilen ayraçla birlikte ver.
    """


def run_ai_generation(user_request_text, api_key_id):
    """Seçilen AI servisine göre makale üretimini çalıştırır."""
    from blog.models import APIKey
    try:
        api_key_object = APIKey.objects.get(id=api_key_id, is_active=True)
    except APIKey.DoesNotExist:
        raise ValueError("Seçilen API anahtarı bulunamadı veya aktif değil.")

    response_text = ""
    base_prompt = get_base_prompt(user_request_text)

    if api_key_object.service_name == 'Google Gemini':
        genai.configure(api_key=api_key_object.key)
        generation_config = {"temperature": 0.7, "max_output_tokens": 8192}
        model = genai.GenerativeModel(model_name=api_key_object.model_name, generation_config=generation_config)

        system_prompt = "Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, yayınlanmaya hazır bir makale taslağı oluşturmak."
        full_prompt = f"{system_prompt}\n\n{base_prompt}"

        response = model.generate_content(full_prompt)
        response_text = response.text

    elif api_key_object.service_name == 'OpenAI':
        client = openai.OpenAI(api_key=api_key_object.key)
        messages = [
            {
                "role": "system",
                "content": "Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, yayınlanmaya hazır bir makale taslağı oluşturmak. Cevabını, istenen 8 bölümün arasına `_||_SECTION_BREAK_||_` ayıracı koyarak, başka hiçbir açıklama olmadan sunmalısın."
            },
            {
                "role": "user",
                "content": base_prompt
            }
        ]
        response = client.chat.completions.create(
            model=api_key_object.model_name,
            messages=messages,
        )
        response_text = response.choices[0].message.content

    elif api_key_object.service_name == 'Anthropic':
        client = anthropic.Anthropic(api_key=api_key_object.key)
        system_prompt = "Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, yayınlanmaya hazır bir makale taslağı oluşturmak. Cevabını, istenen 8 bölümün arasına `_||_SECTION_BREAK_||_` ayıracı koyarak, başka hiçbir açıklama olmadan sunmalısın."

        response = client.messages.create(
            model=api_key_object.model_name,
            system=system_prompt,
            messages=[
                {"role": "user", "content": base_prompt}
            ],
            max_tokens=8192,
        )

        response_text = response.content[0].text

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


@app.callback(
    Output('form-feedback-message', 'children'),
    Output('url', 'href', allow_duplicate=True),
    Input('submit-request-button', 'n_clicks'),
    State('request-textarea', 'value'),
    State('user-session-store', 'data'),
    State('ai-service-dropdown', 'value'),  # YENİ: Dropdown'dan seçilen değeri al
    prevent_initial_call=True
)
def handle_form_submission(n_clicks, request_text, user_data, selected_api_id):  # YENİ: Parametre eklendi
    from blog.models import GeneratedArticle, Category
    from django.contrib.auth.models import User
    if not user_data or 'user_id' not in user_data:
        return dbc.Alert("Kullanıcı oturum bilgisi bulunamadı. Lütfen tekrar giriş yapın.", color="danger"), no_update
    if not request_text or len(request_text.strip()) < 10:
        return dbc.Alert("Lütfen en az 10 karakterlik bir konu girin.", color="warning"), no_update

    # YENİ: AI servisi seçilip seçilmediğini kontrol et
    if not selected_api_id:
        return dbc.Alert("Lütfen bir yapay zeka servisi seçin.", color="warning"), no_update

    try:
        user = User.objects.get(id=user_data['user_id'])

        # Güncellenmiş fonksiyonu çağır
        ai_data = run_ai_generation(request_text, selected_api_id)

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise TypeError("Yapay zekadan beklenen formatta bir yanıt alınamadı.")

        category_name = ai_data.get("category_name", "Genel").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=category_name)

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
            status='tamamlandi'
        )
        success_message = dbc.Alert(
            ["Makale başarıyla üretildi! ",
             html.A("Görüntülemek için tıklayın.", href=new_article.get_absolute_url(), className="alert-link")],
            color="success"
        )
        return success_message, no_update
    except User.DoesNotExist:
        return dbc.Alert("Geçersiz kullanıcı kimliği.", color="danger"), no_update
    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"Beklenmedik bir hata oluştu: {e}", color="danger"), no_update


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open