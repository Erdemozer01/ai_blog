<div align="center">

# 🧬 AI Blog — Yapay Zekâ Destekli Akademik Yayın ve Biyoinformatik Platformu

**AI-Powered Academic Publishing & Bioinformatics Platform**

*Gerçek literatüre dayalı, uydurma kaynak içermeyen akademik makale üretimi ve entegre biyoinformatik analiz araçları*

[![Django](https://img.shields.io/badge/Django-5.2.7-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Plotly Dash](https://img.shields.io/badge/Plotly_Dash-2.5-3F4F75?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC_BY--NC_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

🌐 **Canlı Demo / Live Demo:** [aiblog.pythonanywhere.com](https://aiblog.pythonanywhere.com)

[Türkçe](#-türkçe) · [English](#-english)

</div>

---

## 🇹🇷 Türkçe

### 📖 Proje Hakkında

**AI Blog**, yapay zekâ ile akademik makale üretimini biyoinformatik analiz araçlarıyla birleştiren bütünleşik bir platformdur. Projenin temel ayırt edici özelliği, ürettiği makalelerin **gerçek, doğrulanabilir akademik kaynaklara** dayanmasıdır — yapay zekâ dil modellerinin yaygın bir sorunu olan **sahte kaynak/DOI uydurma** problemi, CrossRef API entegrasyonuyla çözülmüştür.

Bu proje, doktora çalışmalarım sırasında başlatılmış ve halen aktif olarak geliştirilmektedir. Hem akademik bir araştırma çalışması hem de işlevsel bir web ürünü olarak tasarlanmıştır.

### ✨ Öne Çıkan Özellikler

#### 📝 Gerçek Kaynaklı Akademik Makale Üretimi
- Kullanıcının verdiği konu, önce **CrossRef API** üzerinden taranır; özeti (abstract) bulunan, son yıllara ait, atıf almış **gerçek kaynaklar** toplanır.
- Makale, bu gerçek kaynaklar **temel alınarak** yazılır — yani önce kaynak bulunur, sonra içerik üretilir. Bu yaklaşım, dil modellerinin kaynak uydurma sorununu ortadan kaldırır.
- Türkçe makale üretirken arama **uluslararası (İngilizce) literatürde** yapılır; böylece dünya çapındaki bilimsel yayınlardan beslenir.
- Tablo ve grafikler **yalnızca kaynaklardaki gerçek sayısal verilerle** oluşturulur; uydurma veri kullanımı engellenir.

#### 🔬 Biyoinformatik Araç Seti (14+ araç)
Tarayıcı üzerinden, kurulum gerektirmeden çalışan biyoinformatik analiz araçları:
- **Sekans Analizi** — DNA/RNA/protein dizisi karakterizasyonu (GC içeriği, uzunluk, çeviri vb.)
- **Sekans Hizalama** — dizi karşılaştırma ve hizalama
- **Mutasyon Tahmini** — varyant etki analizi
- **Primer Tasarımı** — PCR primer tasarımı
- **Restriksiyon Analizi** — kesim bölgesi tespiti
- **Plazmit Haritası** — klonlama vektörü görselleştirme
- **FASTQ Analizi** — dizileme kalite kontrolü
- **Farmakogenomik**, **Varyant Önceliklendirme**, **Multi-Omik Analiz**, **Moleküler Görselleştirme** ve daha fazlası.

#### 🧪 Biyoinformatik Sonuçtan Makaleye (Özgün Özellik)
Platformun en özgün özelliği: bir biyoinformatik analiz sonucunu (örn. sekans analizi) **tek tıkla akademik makaleye dönüştürme**. Akış şöyle işler:
1. Kullanıcı bir analiz çalıştırır (örn. bir gen dizisini analiz eder).
2. "Sonuçları Yayına Dönüştür" butonuna tıklar.
3. Yapay zekâ sonucu **biyolojik olarak yorumlar** ve bir konu üretir.
4. Bu konuyla CrossRef'te **gerçek literatür** taranır.
5. Kullanıcının **gerçek analiz sonucu**, bulunan literatürle **bağdaştırılarak** bir makale yazılır.

Bu, "analiz yapan ama makale yazmayan" biyoinformatik araçlar ile "makale yazan ama analiz yapmayan" yazım araçları arasındaki boşluğu dolduran özgün bir kesişimdir.

#### 🤖 Çoklu AI Sağlayıcı ve Otomatik Yedekleme
- **Google Gemini**, **OpenAI** ve **Anthropic Claude** desteği.
- Bir model/sağlayıcı kota dolduğunda (örn. 429 hatası), sistem **otomatik olarak diğer kayıtlı modellere geçer**. Sistem-içi otomatik çağrılarda sağlayıcılar arası geçiş; kullanıcının seçtiği sağlayıcıda ise seçime sadık kalma mantığı uygulanır.

#### 💳 Kredi Tabanlı Kullanım Sistemi
- Her işlem (makale üretimi, biyoinformatik araç kullanımı) için kredi tüketen iki katmanlı bir faturalandırma sistemi.
- Yönetici panelinden hizmet bazında fiyat tanımlama.

#### 🌍 Çift Dilli Arayüz
- Türkçe ve İngilizce arayüz desteği.

### 🛠️ Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| **Backend** | Django 5.2.7, Python 3.13 |
| **İnteraktif Arayüz** | Plotly Dash, django-plotly-dash 2.5 |
| **Biyoinformatik** | BioPython 1.85, primer3-py |
| **Yapay Zekâ** | Google Gemini, OpenAI, Anthropic Claude API |
| **Literatür** | CrossRef REST API |
| **Veritabanı** | MySQL (prod) / SQLite (geliştirme) |
| **PDF Üretimi** | WeasyPrint |
| **Dağıtım** | PythonAnywhere |

### 🏗️ Proje Yapısı

```
ai_blog/
├── ai_blog/          # Proje ayarları (settings, urls)
├── ai_engine/        # AI sağlayıcı havuzu, model yedekleme mantığı
├── blog/             # Makaleler, kaynak doğrulama, bildirimler, AI inceleme
├── billing/          # Kredi sistemi, faturalandırma, fiyatlandırma
├── bio_tools/        # Biyoinformatik araç URL yönlendirmeleri
├── dash_apps/        # 20+ Dash uygulaması (bio araçları + makale üretimi)
├── programs/         # Yardımcı uygulamalar
├── templates/        # HTML şablonları
└── static/           # CSS, JS, fontlar, görseller
```

### 🚀 Kurulum (Geliştirme Ortamı)

```bash
# 1. Depoyu klonlayın
git clone https://github.com/Erdemozer01/ai_blog.git
cd ai_blog

# 2. Sanal ortam oluşturun
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Ortam değişkenlerini ayarlayın (.env dosyası)
#    AI API anahtarları yönetici panelinden de eklenebilir.

# 5. Veritabanı geçişlerini uygulayın
python manage.py migrate

# 6. Statik dosyaları toplayın
python manage.py collectstatic --noinput

# 7. Sunucuyu başlatın
python manage.py runserver
```

> **Not:** AI sağlayıcı API anahtarları, yönetici panelindeki **AI Modelleri** bölümünden eklenir. Yedekleme (fallback) mekanizmasının çalışması için **birden fazla aktif model** tanımlanması önerilir.

### 📜 Lisans

Bu proje **Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0)** lisansı altında sunulmaktadır. Eğitim ve akademik amaçlarla, **atıf vermek koşuluyla** incelenebilir ve kullanılabilir; **ticari kullanım için yazarın izni gereklidir**. Ayrıntılar için [LICENSE](LICENSE) dosyasına bakınız.

### 👤 Yazar

**Mehmet Erdem Özer**
📧 ozer246@gmail.com
🔗 [github.com/Erdemozer01](https://github.com/Erdemozer01)

*Doktora çalışmaları sırasında başlatılmış, aktif olarak geliştirilmektedir.*

---

## 🇬🇧 English

### 📖 About

**AI Blog** is an integrated platform that combines AI-powered academic article generation with bioinformatics analysis tools. Its key distinguishing feature is that generated articles are grounded in **real, verifiable academic sources** — the common LLM problem of **fabricating fake references/DOIs** is solved through CrossRef API integration.

This project was started during my doctoral studies and is under active development. It is designed both as an academic research effort and a functional web product.

### ✨ Key Features

#### 📝 Real-Source Academic Article Generation
- The user's topic is first searched via the **CrossRef API**; **real sources** with abstracts, recent and well-cited, are collected.
- The article is then written **based on these real sources** — sources are found first, content is generated second. This eliminates the LLM hallucination problem of inventing references.
- When writing Turkish articles, the search is performed against **international (English) literature**, drawing on worldwide scientific publications.
- Tables and charts are built **only from real numerical data found in the sources**; fabricated data is prevented.

#### 🔬 Bioinformatics Toolkit (14+ tools)
Browser-based bioinformatics tools requiring no installation:
- **Sequence Analysis** — DNA/RNA/protein characterization (GC content, length, translation, etc.)
- **Sequence Alignment**, **Mutation Prediction**, **Primer Design**, **Restriction Analysis**
- **Plasmid Map**, **FASTQ Analysis**, **Pharmacogenomics**, **Variant Prioritization**
- **Multi-Omics Analysis**, **Molecular Visualization**, and more.

#### 🧪 From Bioinformatics Result to Article (Original Feature)
The platform's most original feature: converting a bioinformatics analysis result into an academic article with **one click**:
1. The user runs an analysis (e.g. analyzes a gene sequence).
2. Clicks "Convert Results to Publication".
3. AI **biologically interprets** the result and generates a topic.
4. **Real literature** is searched on CrossRef for that topic.
5. The user's **real analysis result** is woven together with the found literature into an article.

This fills the gap between bioinformatics tools that "analyze but don't write" and writing tools that "write but don't analyze."

#### 🤖 Multi-Provider AI with Automatic Fallback
- Support for **Google Gemini**, **OpenAI**, and **Anthropic Claude**.
- When a model/provider hits its quota (e.g. 429 error), the system **automatically falls back to other registered models**. Cross-provider fallback applies to internal automated calls, while user-selected providers are respected.

#### 💳 Credit-Based Usage System
- A two-tier billing system that consumes credits per operation (article generation, bioinformatics tool usage).
- Per-service pricing configurable from the admin panel.

#### 🌍 Bilingual Interface
- Turkish and English UI support.

### 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Django 5.2.7, Python 3.13 |
| **Interactive UI** | Plotly Dash, django-plotly-dash 2.5 |
| **Bioinformatics** | BioPython 1.85, primer3-py |
| **AI** | Google Gemini, OpenAI, Anthropic Claude API |
| **Literature** | CrossRef REST API |
| **Database** | MySQL (prod) / SQLite (development) |
| **PDF** | WeasyPrint |
| **Deployment** | PythonAnywhere |

### 🚀 Installation (Development)

```bash
# 1. Clone the repository
git clone https://github.com/Erdemozer01/ai_blog.git
cd ai_blog

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (.env file)
#    AI API keys can also be added via the admin panel.

# 5. Apply database migrations
python manage.py migrate

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Run the server
python manage.py runserver
```

> **Note:** AI provider API keys are added via the **AI Models** section in the admin panel. Defining **multiple active models** is recommended for the fallback mechanism to work.

### 📜 License

This project is licensed under **Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0)**. It may be studied and used for educational and academic purposes **with attribution**; **commercial use requires the author's permission**. See the [LICENSE](LICENSE) file for details.

### 👤 Author

**Mehmet Erdem Özer**
📧 ozer246@gmail.com
🔗 [github.com/Erdemozer01](https://github.com/Erdemozer01)

*Started during doctoral studies, under active development.*

---

<div align="center">

⭐ Bu proje işinize yaradıysa yıldız vermeyi unutmayın! / If you find this project useful, consider giving it a star!

</div>
