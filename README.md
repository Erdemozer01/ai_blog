# Django & Dash ile Gelişmiş İçerik Platformu

Bu proje, Django ve Plotly Dash kullanılarak geliştirilmiş, çeşitli konularda otomatik olarak akademik düzeyde makale taslakları üreten bir web platformudur.

## Özellikler

- **Otomatik Makale Üretimi:** Kullanıcı tarafından girilen bir konuya göre başlık, özet, anahtar kelimeler, dinamik alt başlıklar içeren ana metin ve kaynakça üreten bir sistem.
- **Dinamik Kategori Sistemi:** Üretilen her makale için en uygun kategori otomatik olarak belirlenir ve sisteme yeni bir kategori olarak eklenebilir.
- **İnteraktif Anasayfa:** Üretilen tüm makalelerin listelendiği, arama ve kategoriye göre anında (sayfa yenilenmeden) filtrelenebilen bir anasayfa.
- **Detaylı Makale Sayfası:** Her makale için özel, SEO uyumlu, akademik formatta bir sunum sayfası.
- **Kullanıcı Etkileşimi:** Makaleler için "Faydalı / Faydasız" geri bildirim sistemi ve sosyal medya paylaşım butonları.
- **Kullanıcı Yönetimi:** Django'nun yerleşik kimlik doğrulama sistemi ile kullanıcı girişi, çıkışı ve yetkilendirme (içerik üretimi sadece süper kullanıcılara özel).
- **Özel Yönetici Paneli:** Sitenin genel istatistiklerini (toplam makale, kullanıcı sayısı vb.) ve zamanla üretilen makale grafiğini gösteren özel bir Dash paneli.
- **İletişim Formu:** Ziyaretçilerin mesaj gönderebileceği, Dash ile oluşturulmuş interaktif bir iletişim sayfası.

## Kullanılan Teknolojiler

- **Backend:** Django
- **Arayüz & Dashboard:** Plotly Dash, Dash Bootstrap Components
- **Veritabanı:** Django ORM (varsayılan: SQLite)
- **Veri İşleme:** Pandas

## Kurulum ve Çalıştırma

1.  **Depoyu Klonlayın:**
    ```bash
    git clone [repo_adresi]
    cd ai_blog
    ```

2.  **Sanal Ortam Oluşturun ve Aktifleştirin:**
    ```bash
    python -m venv venv
    # Windows için:
    venv\Scripts\activate
    # macOS/Linux için:
    source venv/bin/activate
    ```

3.  **Gereksinimleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ortam Değişkenlerini Ayarlayın:**
    Proje ana dizininde `.env` adında bir dosya oluşturun ve içine gerekli API anahtarınızı ekleyin:
    ```
    API_KEY="buraya_gerekli_api_anahtarini_yapistirin"
    ```

5.  **Veritabanını Hazırlayın:**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

6.  **Süper Kullanıcı Oluşturun:**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Admin Panelinden Ayarları Yapın:**
    Siteyi çalıştırıp `/admin` adresine gidin.
    - "API Anahtarları" bölümüne, ilgili servis için API anahtarınızı ekleyin.
    - "Siteler" bölümüne, `example.com` veya `localhost:8000` için bir site kaydı oluşturun.

8.  **Sunucuyu Çalıştırın:**
    ```bash
    python manage.py runserver
    ```

## Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakın.