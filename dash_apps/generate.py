import re, json
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import Input, Output, State, no_update, html
from dash_apps.i18n_helper import t
from datetime import date

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
app = DjangoDash('GenerateArticleApp', external_stylesheets=external_stylesheets)


def validate_topic_rules(text, lang='en'):
    """
    Hızlı kural bazlı konu ön kontrolü (bedava, anında).
    (bool gecerli, str sebep) döner.
    """
    txt = text.strip().lower()

    if len(txt) < 10:
        return False, t('gen_val_short', lang)

    words = txt.split()
    if len(words) < 2:
        return False, t('gen_val_words', lang)

    # Selamlaşma / sohbet kalıpları
    chat_patterns = [
        'merhaba', 'selam', 'nasılsın', 'naber', 'günaydın', 'iyi misin',
        'teşekkür', 'sağol', 'görüşürüz', 'hoşçakal', 'kimsin', 'adın ne',
        'şiir yaz', 'fıkra', 'şaka yap', 'hikaye anlat', 'masal anlat',
        'hello', 'how are you', 'thanks', 'tell me a joke', 'write a poem',
    ]
    for p in chat_patterns:
        if p in txt:
            return False, t('gen_val_chat', lang)

    # Anlamsız tekrar (asdasd, aaaaa)
    if re.match(r'^(.)\1{4,}$', txt.replace(' ', '')):
        return False, t('gen_val_gibberish', lang)

    # Tek-iki harflik kelime grupları (asdf qwer)
    if all(len(w) <= 2 for w in words) and len(words) < 5:
        return False, t('gen_val_meaningful', lang)

    # Argo / müstehcen / küfür içeren konular
    import re as _re

    # 1) Normalleştirme: leetspeak ve ayırıcıları temizle
    leet = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's'})
    normalized = txt.translate(leet)
    collapsed = _re.sub(r'[\s.\-_*]+', '', normalized)

    hard_roots = [
        'amcık', 'amcik', 'amcığ', 'amcig', 'yarrak', 'yarrağ', 'orospu',
        'sikiş', 'sikis', 'siktir', 'pezevenk', 'gavat', 'kahpe',
        'penis', 'vajina', 'porno', 'pussy', 'fuck', 'porn', 'whore', 'bitch',
    ]
    for root in hard_roots:
        root_norm = root.translate(leet)
        if root_norm in collapsed:
            return False, t('gen_val_inappropriate', lang)

    word_bound = [
        'sik', 'piç', 'pic', 'göt', 'got', 'meme', 'seks', 'sex', 'dick', 'shit',
    ]
    for p in word_bound:
        if _re.search(r'(^|[\s.,;:!?\-])' + _re.escape(p) + r'($|[\s.,;:!?\-])', normalized):
            return False, t('gen_val_inappropriate', lang)

    return True, ""


def validate_topic_ai(text, lang='en'):
    """
    AI ile konu doğrulama: 'bu geçerli akademik/bilgi konusu mu?'
    (bool gecerli, str sebep) döner. Hata olursa geçerli kabul eder (engellemez).
    """
    try:
        from ai_engine.services import generate_with_pool, get_fallback_models
        prompt = (
            "Aşağıdaki metin, akademik/bilgilendirici bir makale için GEÇERLİ bir KONU mu? "
            "Şu durumlar GEÇERSİZDİR: sohbet, selamlaşma, şaka, anlamsız metin, kişisel istek, "
            "makale konusu olmayan şeyler, VE müstehcen/cinsel/argo/küfür içeren veya "
            "uygunsuz çağrışım yapan ifadeler. Sadece tek kelimeyle cevap ver: "
            "'GECERLI' veya 'GECERSIZ'.\n\n"
            f"Metin: \"{text}\""
        )
        result = None
        for svc, mdl in get_fallback_models("Google Gemini", "gemini-2.5-flash", cross_provider=True):
            try:
                result, _key = generate_with_pool(
                    prompt, service_name=svc, model_name=mdl,
                    max_tokens=10, temperature=0.4)
                if result:
                    break
            except Exception:
                continue
        answer = (result or "").strip().upper()
        if "GECERSIZ" in answer or "GEÇERSIZ" in answer or "INVALID" in answer:
            return False, t('gen_val_ai_invalid', lang)
        return True, ""
    except Exception:
        # AI doğrulanamazsa engelleme (kullanıcıyı mağdur etme)
        return True, ""


def get_base_prompt(user_request_text, word_count=1500, real_sources=None):
    """Tüm modeller için ortak olan prompt metnini oluşturur.

    real_sources: CrossRef'ten çekilmiş gerçek kaynaklar listesi (varsa).
    Verilirse AI bu kaynaklara dayanarak yazar, kendi kaynak uydurmaz.
    """
    current_year = date.today().year
    # Kelime sayısına göre ara başlık ve kaynakça sayısını ölçekle
    if word_count <= 500:
        sections_hint = "1-2 ara başlık ve kısa bir sonuç"
        ref_count = "5-7"
    elif word_count <= 1500:
        sections_hint = "3-4 ara başlık ve bir sonuç bölümü"
        ref_count = "10-15"
    elif word_count <= 2500:
        sections_hint = "4-6 ara başlık ve detaylı bir sonuç bölümü"
        ref_count = "15-20"
    else:
        sections_hint = "6-8 ara başlık, alt başlıklar ve kapsamlı bir sonuç bölümü"
        ref_count = "20-30"

    # Gerçek kaynaklar verildiyse: kaynakça SADECE metinde [N] ile atıf yapılanları
    # içermeli. Atıfsız/alakasız kaynağı listeye doldurmamalı (öksüz kaynak olmasın).
    if real_sources:
        ref_count = f"en çok {len(real_sources)} (yalnızca metinde gerçekten kullandıkların)"

    # Gerçek kaynaklar verildiyse, prompt'a kaynak listesi + özet/tam metin eklenir
    sources_block = ""
    if real_sources:
        lines = []
        has_fulltext = False
        for i, s in enumerate(real_sources, start=1):
            # Tam metin varsa (PMC açık erişim, ticari-uygun lisans) onu kullan;
            # yoksa özete düş. Tam metin token bütçesi için kırpılır.
            fulltext = s.get('fulltext')
            if fulltext:
                has_fulltext = True
                body = fulltext[:2500]
                kind = "TAM METİN"
            else:
                body = (s.get('abstract') or '')[:400]
                kind = "ÖZET"
            # Atıf izlenebilirliği: PMID/DOI varsa numaranın yanında göster
            tag = ""
            if s.get('pmid'):
                tag += f" PMID:{s['pmid']}"
            if s.get('doi'):
                tag += f" DOI:{s['doi']}"
            lines.append(
                f"[{i}] {s['citation']}{tag}\n"
                f"     {kind}: {body}"
            )
        ft_note = (
            "Bazı kaynaklar TAM METİN olarak verildi; bunların bulgularını daha "
            "ayrıntılı kullanabilirsin. ANCAK tam metni KELİMESİ KELİMESİNE KOPYALAMA — "
            "sayıları/bulguları aynen koru ama cümleleri kendi ifadenle yeniden yaz. "
            if has_fulltext else ""
        )
        sources_block = (
            "\n\n=== KULLANILACAK GERÇEK KAYNAKLAR (PubMed/CrossRef'ten doğrulanmış) ===\n"
            "Aşağıda, bu konuda GERÇEKTEN VAR OLAN akademik kaynaklar ve içerikleri var. "
            "Makaleyi YALNIZCA bu kaynaklara dayanarak yaz. Her kaynağı içeriğindeki "
            "bilgiye uygun bir cümlede [N] numarasıyla kullan. Bu listenin DIŞINDA "
            "kaynak UYDURMA. "
            "ÖNEMLİ: Bu listedeki TÜM kaynakları kullanmak ZORUNDA DEĞİLSİN. Konuyla "
            "doğrudan ilgili olanları seç ve kullan; konuyla alakasız (örn. farklı bir "
            "hastalık, ilgisiz bir model/tür, konu dışı bir bulgu) kaynağı metinde "
            "KULLANMA ve kaynakçaya da KOYMA. Kaynakça SADECE metinde [N] ile gerçekten "
            "atıf yaptığın kaynaklardan oluşur — sayıyı doldurmak için alakasız kaynak EKLEME. "
            + ft_note +
            "\n\n"
            + "\n\n".join(lines) +
            "\n=== GERÇEK KAYNAKLAR SONU ===\n"
        )

    return f"""
    İstek Konusu: "{user_request_text}"{sources_block}
    Makalenin bölümlerini aşağıdaki 8 bölümden oluşacak şekilde ve her birinin arasına `_||_SECTION_BREAK_||_` ayıracını koyarak oluştur.
    Oluşturulacak Bölümlerin Sırası:
    1.  Başlık: Spesifik, analitik ve akademik bir başlık.
    2.  İngilizce Özet (Abstract): Yaklaşık 150 kelimelik, makaleyi özetleyen İngilizce bir abstract.
    3.  Türkçe Özet: İngilizce özetin anlam olarak aynısı olan, akıcı bir Türkçe çevirisi.
    4.  Kategori Adı: Konuyu en iyi özetleyen 1-2 kelimelik kategori adı.
    5.  Anahtar Kelimeler: Virgülle ayrılmış 5-6 anahtar kelime.
    6.  Tam İçerik: Markdown formatında, yaklaşık {word_count} kelime uzunluğunda (en az {int(word_count * 0.85)} kelime). Metin, son 5 yıla ({current_year - 5}-{current_year}) odaklanan güncel bir literatür taramasıyla başlamalıdır. Konuyu analiz eden {sections_hint} ekle. Metin içinde [1], [2] gibi atıflar olsun. ÇOK ÖNEMLİ: Metnin içinde, verilerin görselleştirileceği uygun yerlere `_||_STRUCTURED_DATA_1_||_`, `_||_STRUCTURED_DATA_2_||_` gibi placeholder'lar yerleştir. ANCAK placeholder'ı SADECE, o yere koyacağın tablo/grafik için kaynaklarda GERÇEK sayısal veri varsa ekle. Uydurma veriyle dolduracağın placeholder KOYMA — gerçek veri yoksa hiç placeholder ekleme.
    7.  Kaynakça (ZORUNLU - ASLA ATLAMA): Makalenin SONUNDA, metindeki atıflara karşılık gelen,
        numaralı kaynakça maddelerini yaz. Kaynakça {ref_count} madde olmalı. Makale içeriğini
        kaynakça için yer kalacak şekilde planla; içeriği uzatıp kaynakçayı yarıda BIRAKMA.
        Kaynakça bölümü eksik veya kesik OLAMAZ.
        KAYNAK DOĞRULUĞU KURALLARI (ÇOK ÖNEMLİ):
        - EN ÖNEMLİ KURAL: Kaynakça, SADECE metin içinde [N] ile GERÇEKTEN atıf yaptığın
          kaynaklardan oluşur. Metinde kullanmadığın bir kaynağı, sırf sayıyı tamamlamak
          için kaynakçaya EKLEME. Atıfsız kaynak = ÖKSÜZ KAYNAK = YASAK.
        - Belirli bir sayıya ulaşmak için konuyla ALAKASIZ kaynak kullanma. 6 alakalı kaynak,
          10 kaynağın 4'ü alakasız olmasından İYİDİR.
        - Yukarıda "GERÇEK KAYNAKLAR" listesi verildiyse: SADECE o kaynakları kullan,
          verilen numaralarla ve aynen yaz. Liste dışında HİÇBİR kaynak ekleme/uydurma.
        - Liste verilmediyse: ASLA var olmayan, uydurma kaynak, yazar veya makale üretme.
        - Gelecek tarihli ({current_year}'dan sonraki) veya henüz yayınlanmamış kaynak verme.
        - Yalnızca gerçekten var olduğundan emin olduğun, doğrulanabilir kaynakları kullan.
        - Eğer bir iddia için gerçek bir kaynak bilmiyorsan, o iddiaya atıf koyma.
        - Az ama gerçek kaynak, çok ama uydurma kaynaktan iyidir.
        - Kaynakçadaki HER kaynak, metinde en az bir [N] atfıyla kullanılmalı; metinde
          atıf yapılmayan kaynağı kaynakçaya koyma.
    8.  Yapısal Veri (JSON): Makale içindeki placeholder'larla eşleşen, anahtar-değer yapısında GEÇERLİ bir JSON nesnesi oluştur. Anahtarlar metindeki placeholder'daki sayılar olmalı (örn: "1", "2"). Sadece JSON nesnesini ver, başına veya sonuna "```json" gibi kod blokları ekleme.
        ⚠️ KRİTİK VERİ DOĞRULUĞU KURALI (UYDURMA YASAK):
        - Tablo ve grafiklerdeki TÜM sayılar/değerler, YALNIZCA yukarıda verilen GERÇEK KAYNAKLARIN
          özetlerinde (abstract) AÇIKÇA geçen verilerden alınmalıdır. Kaynakta olmayan hiçbir sayı,
          yüzde, istatistik veya değer UYDURMA.
        - "Kavramsal", "örnek", "temsili" veya "tahmini" sayılarla tablo/grafik OLUŞTURMA. Uydurma
          sayı bilimsel değer taşımaz ve YASAKTIR.
        - Bir tablo/grafik için kaynaklarda gerçek, sayısal veri YOKSA: o placeholder için veri üretme,
          JSON'da o anahtarı ATLA. Hiç uygun gerçek veri yoksa `{{}}` (boş nesne) döndür.
        - 'source' alanı, verinin alındığı GERÇEK kaynağı belirtmeli ve bu kaynak MUTLAKA
          yukarıdaki "GERÇEK KAYNAKLAR" listesinde/kaynakçada olmalı (örn. "Yau et al., 2025 [3]").
          Listede OLMAYAN bir kuruluş/rapor/veri tabanı adını (örn. "IDF 2024", "WHO",
          "DSÖ raporu") source olarak YAZMA — bu izlenemez ve YASAKTIR. Uygun kaynak yoksa
          o tabloyu/grafiği hiç oluşturma.
        - Veriye en uygun grafik türünü ('bar', 'line', 'pie', 'scatter') seç.
        - Tablo formatı: `{{"1": {{"type": "table", "title": "...", "description": "...", "source": "Yazar, Yıl", "columns": ["..."], "data": [["..."]]}}}}`
        - Grafik formatı: `{{"2": {{"type": "chart", "chart_type": "bar", "title": "...", "description": "...", "source": "Yazar, Yıl", "data": {{"x": ["..."], "y": [...]}}}}}}`
        - Eğer uygun GERÇEK veri yoksa, `{{}}` şeklinde boş bir nesne döndür.
    Cevabında başka hiçbir açıklama veya metin olmasın. Sadece bu 8 bölümü, aralarında belirtilen ayraçla birlikte ver.
    """


def generate_topic_from_bio_result(bio_tool, bio_results, lang='tr'):
    """
    Biyoinformatik araç sonucunu AI ile yorumlar ve makale için
    bir konu/başlık + arama bağlamı üretir.

    bio_tool: aracın adı (örn. 'Sekans Analizi')
    bio_results: araç çıktısı dict (örn. {'type': 'DNA', 'gc_content': '58%', ...})
    Döner: (topic_text, interpretation) — topic_text CrossRef aramasında kullanılır,
           interpretation makale promptuna bağlam olarak eklenir.
    """
    from ai_engine.services import generate_with_pool

    # Sonuçları okunabilir metne çevir
    lines = []
    multi_records = (bio_results or {}).get('all_records')
    for k, v in (bio_results or {}).items():
        if k == 'all_records':
            continue  # çoklu diziler aşağıda ayrıca özetlenir
        if k in ('sequence', 'transcribed_rna', 'complement', 'reverse_complement',
                 'back_transcribed_dna', 'protein_translation'):
            # Uzun ham diziler: sadece uzunluk/özet
            if isinstance(v, str) and len(v) > 120:
                lines.append(f"- {k}: ({len(v)} karakter, ham dizi)")
                continue
        if isinstance(v, dict):
            v = ", ".join(f"{ik}: {iv}" for ik, iv in list(v.items())[:10])
        lines.append(f"- {k}: {v}")

    # Çoklu dizi varsa: hepsinin özetini konu üretimine ekle
    if multi_records and len(multi_records) > 1:
        valid = [r for r in multi_records if 'error' not in r]
        lines.append(f"\n- TOPLAM DİZİ SAYISI: {len(valid)} (çoklu dizi analizi)")
        descs = []
        for r in valid[:10]:
            descs.append(f"{r.get('id','?')} ({r.get('length','?')}bp, GC {r.get('gc_content','-')})")
        lines.append("- Diziler: " + "; ".join(descs))

    results_text = "\n".join(lines)

    prompt = f"""Bir biyoinformatik analiz aracı ('{bio_tool}') aşağıdaki sonuçları üretti:

{results_text}

GÖREV: Bu analiz sonucundan yola çıkarak BİYOLOJİK/TIBBİ bir makale konusu üret.

ÇOK ÖNEMLİ KURALLAR:
- Konu, dizinin BİYOLOJİK KİMLİĞİNE odaklanmalı: hangi gen/protein, hangi organizma,
  hangi biyolojik işlev, hangi hastalık/süreçle ilişkili.
- Eğer dizi kimliği (id/description) bilinen bir geni gösteriyorsa (örn. 'INS'=insülin,
  'TP53'=tümör baskılayıcı, 'BRCA1'=meme kanseri geni), KONUYU O GENİN BİYOLOJİSİNE göre
  belirle (örn. 'İnsülin geninin yapısı, ekspresyonu ve diyabetteki rolü').
- ASLA 'sekans analiz yöntemleri', 'biyoinformatik araçlar', 'genomik veri işleme',
  'hesaplamalı yöntemler' gibi ARAÇ/YÖNTEM odaklı bir konu üretme. Konu, biyolojik
  içerik hakkında olmalı — analizi yapan yazılımlar hakkında DEĞİL.
- GC içeriği, uzunluk gibi özellikler biyolojik bağlamda yorumlanmalı (gen düzenlenmesi,
  protein işlevi, evrim, hastalık), araç tanıtımına dönüşmemeli.

Önce sonuçları 2-3 cümleyle BİYOLOJİK olarak yorumla, sonra konuyu öner.

Yanıtını TAM olarak şu formatta ver (başka hiçbir şey ekleme):
YORUM: <biyolojik yorum>
KONU: <biyolojik/tıbbi makale konusu - Türkçe, 1 cümle başlık>"""

    # Model fallback ile dene (kota dolarsa diğer kayıtlı modele geç)
    from ai_engine.services import get_fallback_models
    text = None
    for svc, mdl in get_fallback_models("Google Gemini", "gemini-2.5-flash", cross_provider=True):
        try:
            text, _key = generate_with_pool(
                prompt, service_name=svc, model_name=mdl,
                max_tokens=500, temperature=0.5)
            if text:
                break
        except Exception:
            continue
    if not text:
        # AI tamamen başarısızsa, sonuçlardan basit bir konu üret
        seq_type = (bio_results or {}).get('type', 'biyolojik dizi')
        return f"{seq_type} dizi analizi ve biyolojik önemi", ""

    interpretation = ""
    topic = ""
    for line in (text or "").splitlines():
        line = line.strip()
        if line.upper().startswith("YORUM:"):
            interpretation = line.split(":", 1)[1].strip()
        elif line.upper().startswith("KONU:"):
            topic = line.split(":", 1)[1].strip()

    if not topic:
        seq_type = (bio_results or {}).get('type', 'biyolojik dizi')
        topic = f"{seq_type} dizi analizi ve biyolojik önemi"

    return topic, interpretation


def run_ai_generation_with_pool(user_request_text, word_count=1500,
                                service_name="Google Gemini", model_name=None,
                                bio_context=None):
    """
    Makale üretimini ai_engine havuzu ile çalıştırır.

    bio_context: (opsiyonel) biyoinformatik araç yorumu. Verilirse makale,
    kullanıcının gerçek analiz sonucunu literatürle bağdaştıracak şekilde yazılır.

    ai_engine.services.generate_with_pool kullanır: seçilen sağlayıcının
    anahtar havuzunu 'en az kullanılan önce' dener, biri hata verirse
    (429/kota) diğerine geçer. model_name verilirse o model kullanılır,
    verilmezse sağlayıcının ilk aktif modeli.

    Döner: (ai_data dict, used_key)
    """
    from ai_engine.services import generate_with_pool

    # Üretimden önce konuya göre gerçek kaynakları topla (abstract'lı + varsa tam metin).
    # Önce PubMed/PMC (özet kapsamı geniş, açık erişimde tam metin); ulaşılamaz veya
    # boşsa CrossRef'e düş. Her ikisi de aynı kaynak şeklini döndürür.
    # Kaynak sayısı makale uzunluğuna göre ölçeklenir (uzun makale = geniş kaynakça).
    if word_count <= 500:
        src_count = 8
    elif word_count <= 1500:
        src_count = 15
    elif word_count <= 2500:
        src_count = 20
    else:
        src_count = 25

    real_sources = None
    try:
        from blog.pubmed_sources import collect_pubmed_sources_for_topic
        real_sources = collect_pubmed_sources_for_topic(user_request_text, target_count=src_count)
        if not real_sources:
            real_sources = None
    except Exception:
        real_sources = None

    if not real_sources:
        try:
            from blog.reference_check import collect_real_sources_for_topic
            real_sources = collect_real_sources_for_topic(user_request_text, target_count=src_count)
            if not real_sources:
                real_sources = None
        except Exception:
            real_sources = None

    base_prompt = get_base_prompt(user_request_text, word_count, real_sources=real_sources)

    # Bio-analiz bağlamı varsa prompt'a ekle: makale gerçek sonucu literatürle bağdaştırsın
    if bio_context:
        base_prompt = (
            f"=== KULLANICININ GERÇEK ANALİZ SONUCU ===\n{bio_context}\n\n"
            f"ÖNEMLİ: Bu makale, yukarıdaki GERÇEK biyoinformatik analiz sonucunu temel almalı "
            f"ve bu sonucu aşağıda toplanan literatürle BAĞDAŞTIRMALIDIR. Kullanıcının elde ettiği "
            f"bu somut bulguyu bilimsel literatür ışığında yorumlamalı, benzer çalışmalarla "
            f"karşılaştırmalıdır.\n\n"
            f"⚠️ ODAK KURALI: Makale, dizinin BİYOLOJİK İÇERİĞİNE odaklanmalı (hangi gen/protein, "
            f"işlevi, ilişkili hastalık/süreç). Analizi yapan YAZILIM ARAÇLARINI (SciPy, IQ-TREE, "
            f"DIAMOND, ColabFold vb.) makalenin konusu HALİNE GETİRME — bunlar sadece yöntem, "
            f"konu değil. Konuyla alakasız araç/yöntem/teknoloji tanıtımına SAPMA.\n\n"
            f"⚠️ TABLO/GRAFİK KURALI: Bu makalede tablo/grafik SADECE şunları gösterebilir: "
            f"(a) kullanıcının yukarıdaki gerçek analiz sonucu (örn. GC içeriği, uzunluk gibi), "
            f"(b) toplanan kaynakların özetlerinde AÇIKÇA geçen gerçek sayısal veriler. "
            f"Yazılım kütüphanesi istatistiği (GitHub yıldızı, indirme sayısı, katkıcı sayısı vb.) "
            f"gibi konuyla ALAKASIZ veya UYDURMA grafikler KESİNLİKLE OLUŞTURMA. Uygun gerçek "
            f"veri yoksa tablo/grafik koyma.\n\n"
            + base_prompt
        )
    system_prompt = ("Sen, konusuna son derece hakim, kıdemli bir akademik yazarsın. "
                     "Görevin, verilen konu hakkında, literatüre derinlemesine bir giriş "
                     "yapan, orijinal argümanlar sunan, zengin kaynakçaya sahip ve içinde "
                     "konuyla ilgili veri görselleştirmeleri (tablo/grafik) barındıran, "
                     "yayınlanmaya hazır bir makale taslağı oluşturmak. "
                     "AKADEMİK DÜRÜSTLÜK: Asla var olmayan kaynak, yazar, makale veya DOI "
                     "uydurma. Emin olmadığın bilgiyi gerçekmiş gibi sunma. Gerçek olmayan "
                     "bir kaynağa atıf yapmaktansa o iddiayı atıfsız bırak. "
                     "Cevabını, istenen "
                     "8 bölümün arasına `_||_SECTION_BREAK_||_` ayıracı koyarak, başka "
                     "hiçbir açıklama olmadan sunmalısın.")
    # Token bütçesi: içerik + kaynakça (15 kaynak ~2000 token) için bol yer bırak.
    # Kaynakça yarıda kesilmesin diye cömert tutulur.
    max_tokens = min(int(word_count * 2.8) + 4000, 32768)

    # Model fallback: seçilen modeli ve aynı sağlayıcının diğer aktif modellerini
    # sırayla dener (biri kota dolarsa diğerine geçer).
    from ai_engine.services import get_fallback_models
    # Bio-makale (bio_context) veya model seçilmemişse: otomatik çağrı sayılır,
    # kota dolunca diğer sağlayıcılara da geçer. Kullanıcı model seçtiyse ona sadık kal.
    cross = bool(bio_context) or (model_name is None)
    model_chain = get_fallback_models(preferred_service=service_name,
                                      preferred_model=model_name,
                                      cross_provider=cross)
    if not model_chain:
        model_chain = [(service_name, model_name)]

    response_text = None
    used_key = None
    last_error = None
    for svc, mdl in model_chain:
        try:
            response_text, used_key = generate_with_pool(
                base_prompt, service_name=svc, model_name=mdl,
                system_prompt=system_prompt, max_tokens=max_tokens, temperature=0.7)
            if response_text:
                break
        except Exception as e:
            last_error = e
            continue
    if not response_text:
        raise RuntimeError(f"Tüm modeller başarısız oldu. Son hata: {last_error}")

    ai_data = _parse_article_response(response_text)
    return ai_data, used_key


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


@app.callback(
    Output('form-feedback-message', 'children'),
    Output('url', 'href', allow_duplicate=True),
    Input('gen-modal-confirm', 'n_clicks'),
    State('request-textarea', 'value'),
    State('user-session-store', 'data'),
    State('ai-service-dropdown', 'value'),  # YENİ: Dropdown'dan seçilen değeri al
    State('article-length-dropdown', 'value'),  # YENİ: Makale uzunluğu
    State('gen-lang-store', 'data'),
    prevent_initial_call=True
)
def handle_form_submission(n_clicks, request_text, user_data, selected_value, article_length, lang):
    from blog.models import GeneratedArticle, Category
    from django.contrib.auth.models import User
    lang = lang or 'en'
    if not user_data or 'user_id' not in user_data:
        return dbc.Alert(t('gen_no_session', lang), color="danger"), no_update
    if not request_text or len(request_text.strip()) < 10:
        return dbc.Alert(t('gen_min_chars', lang), color="warning"), no_update

    if not selected_value:
        return dbc.Alert(t('gen_select_model', lang), color="warning"), no_update

    # --- KONU DOĞRULAMA (kural + AI) — saçma/sohbet konuları engelle ---
    valid, reason = validate_topic_rules(request_text, lang)
    if not valid:
        return dbc.Alert(reason, color="warning"), no_update
    valid_ai, reason_ai = validate_topic_ai(request_text, lang)
    if not valid_ai:
        return dbc.Alert(reason_ai, color="warning"), no_update

    # Dropdown değeri "service_name|model_name" formatında
    if '|' in selected_value:
        selected_service, selected_model = selected_value.split('|', 1)
    else:
        selected_service, selected_model = selected_value, None

    try:
        user = User.objects.get(id=user_data['user_id'])

        # Havuz ile üret — seçilen modelin sağlayıcı anahtarlarını sırayla dener
        ai_data, used_key = run_ai_generation_with_pool(
            request_text, word_count=article_length or 1500,
            service_name=selected_service, model_name=selected_model)

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
            status='tamamlandi',
            # Superuser üretirse otomatik yayında; normal kullanıcı onay bekler
            is_published=bool(user.is_superuser),
        )

        # --- ZORUNLU CrossRef DOĞRULAMASI (otomatik) ---
        # Kaynakçadaki her kaynağı CrossRef'te doğrula: bulunmayanı (sahteyi)
        # gerçek kaynakla değiştir ya da sil, içerik-uyuşmayanı kaynakçadan çıkar,
        # yeniden numaralandır. clean_article_references makaleyi kendi kaydeder.
        # CrossRef erişilemezse (PythonAnywhere whitelist vb.) makale mağdur
        # edilmez; doğrulama atlanır, kaynaklar zaten PubMed'den gerçektir.
        verify_note = ""
        try:
            from blog.reference_check import clean_article_references
            ok_verify, _msg = clean_article_references(new_article)
            new_article.refresh_from_db()
            if not ok_verify:
                verify_note = ""  # erişilemedi → sessiz geç
        except Exception:
            pass

        # --- Makale başarıyla üretildi → şimdi krediyi düş ---
        # (Sayfa girişinde değil, ÜRETİM başarılı olunca. Superuser muaf.)
        remaining_note = ""
        if not user.is_superuser:
            try:
                from billing.services import charge
                remaining = charge(user, 'makale_uretim', default_cost=15,
                                   description=t('gen_charge_desc', lang).format(title=ai_data.get('title', '')[:50]))
                if remaining is not None:
                    remaining_note = t('gen_remaining', lang).format(n=remaining)
            except Exception:
                pass

        success_message = dbc.Alert(
            [t('gen_success', lang) + remaining_note + " ",
             html.A(t('gen_view_click', lang), href=new_article.get_absolute_url(), className="alert-link")],
            color="success"
        )
        return success_message, no_update
    except User.DoesNotExist:
        return dbc.Alert(t('gen_invalid_user', lang), color="danger"), no_update
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()

        # Hatayı bildirim olarak kaydet (ham detay sadece superuser admin'de görünür)
        try:
            from blog.models import create_notification
            uid = user_data.get('user_id') if isinstance(user_data, dict) else None
            ruser = None
            if uid:
                try:
                    ruser = User.objects.get(id=uid)
                except Exception:
                    ruser = None
            create_notification(
                category='makale_hatasi',
                title=f"Makale oluşturma hatası: {str(request_text)[:60]}",
                message=f"Konu: {request_text}",
                technical_detail=tb,
                related_user=ruser,
            )
        except Exception:
            pass

        # Kullanıcıya nazik, teknik olmayan mesaj + geri bildirim butonu
        friendly = dbc.Alert([
            html.Div([
                html.I(className="fas fa-exclamation-circle me-2"),
                html.Strong(t('gen_system_busy', lang)),
            ]),
            html.P(t('gen_busy_retry', lang), className="mb-2 mt-2"),
            dbc.Button(t('gen_feedback_btn', lang), id="gen-feedback-btn",
                       color="link", size="sm", className="p-0"),
            html.Div(id="gen-feedback-result", className="mt-2 text-success"),
        ], color="warning")
        return friendly, no_update


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@app.callback(
    Output("gen-feedback-result", "children"),
    Input("gen-feedback-btn", "n_clicks"),
    State('gen-lang-store', 'data'),
    prevent_initial_call=True,
)
def gen_feedback_thanks(n_clicks, lang):
    """Geri bildirim butonuna tıklanınca teşekkür mesajı (hata zaten kaydedildi)."""
    if not n_clicks:
        return no_update
    return t('gen_feedback_thanks', lang or 'en')


# --- Kredi onay modalı: Üretimi Başlat butonu onay sorar ---
@app.callback(
    Output('gen-modal', 'is_open'),
    Output('gen-modal-body', 'children'),
    Output('gen-modal-confirm', 'disabled'),
    Input('submit-request-button', 'n_clicks'),
    Input('gen-modal-cancel', 'n_clicks'),
    Input('gen-modal-confirm', 'n_clicks'),
    State('request-textarea', 'value'),
    State('gen-lang-store', 'data'),
    prevent_initial_call=True
)
def toggle_gen_modal(open_click, cancel_click, confirm_click, request_text, lang, **kwargs):
    import dash
    from billing.dash_helpers import confirm_modal_body
    lang = lang or 'en'
    triggered = dash.callback_context.triggered
    trig_id = triggered[0]['prop_id'].split('.')[0] if triggered else ''
    if trig_id == 'submit-request-button' and open_click:
        if not request_text or not request_text.strip():
            return True, dbc.Alert(t('gen_enter_topic', lang), color="warning",
                                   className="mb-0"), True
        body, can_proceed = confirm_modal_body(kwargs, 'makale_uretim', cost=15, lang=lang)
        return True, body, (not can_proceed)
    return False, no_update, no_update