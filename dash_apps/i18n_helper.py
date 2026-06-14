"""
i18n_helper — Hafif çoklu dil desteği (Dash uygulamaları için).

Kullanım:
    from dash_apps.i18n_helper import get_lang, t

    lang = get_lang(request)          # 'tr' veya 'en'
    metin = t('primer_title', lang)   # o dildeki metin

Dil tespiti: tarayıcının Accept-Language başlığına göre otomatik.
Türkçe tarayıcı -> 'tr', diğerleri -> 'en'.
"""

SUPPORTED = ('tr', 'en')
DEFAULT_LANG = 'en'


def get_lang(request):
    """
    Dil tercihini belirler:
    1. Kullanıcı cookie'de dil seçmişse onu kullan (dropdown seçimi)
    2. Yoksa tarayıcı diline göre otomatik (tr/en)
    """
    if request is None:
        return DEFAULT_LANG
    # 1. Kullanıcının açık seçimi (cookie)
    cookie_lang = request.COOKIES.get('site_lang')
    if cookie_lang in SUPPORTED:
        return cookie_lang
    # 2. Tarayıcı dili
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '').lower()
    if accept.startswith('tr') or ',tr' in accept or 'tr-' in accept:
        return 'tr'
    return 'en'


# ---- Çeviri sözlüğü ----
# Her anahtar için tr/en karşılığı. Bio-tool'lar bu sözlükten metin çeker.
TRANSLATIONS = {
    # ---- Genel / ortak ----
    'input': {'tr': 'Giriş', 'en': 'Input'},
    'results': {'tr': 'Sonuçlar', 'en': 'Results'},
    'loading': {'tr': 'Yükleniyor...', 'en': 'Loading...'},
    'error': {'tr': 'Hata', 'en': 'Error'},
    'submit': {'tr': 'Gönder', 'en': 'Submit'},
    'analyze': {'tr': 'Analiz Et', 'en': 'Analyze'},
    'download': {'tr': 'İndir', 'en': 'Download'},
    'credits_required': {'tr': 'kredi', 'en': 'credits'},

    # ---- Primer Tasarım Aracı ----
    'primer_title': {'tr': 'Primer Tasarım Aracı', 'en': 'Primer Design Tool'},
    'primer_subtitle': {
        'tr': 'PCR primer tasarımı (Primer3 motoru). DNA dizinizi yapıştırın veya gen accession numarası girin.',
        'en': 'PCR primer design (Primer3 engine). Paste your DNA sequence or enter a gene accession number.'},
    'primer_seq_label': {'tr': 'DNA Dizisi (yapıştır)', 'en': 'DNA Sequence (paste)'},
    'primer_seq_placeholder': {
        'tr': "5'-ATGC... dizinizi buraya yapıştırın (FASTA da olur)",
        'en': "5'-ATGC... paste your sequence here (FASTA accepted)"},
    'primer_or': {'tr': '— veya —', 'en': '— or —'},
    'primer_acc_label': {'tr': 'Gen Accession / ID (EBI ENA)', 'en': 'Gene Accession / ID (EBI ENA)'},
    'primer_fetch_btn': {'tr': 'Diziyi Çek', 'en': 'Fetch Sequence'},
    'primer_prod_min': {'tr': 'Ürün boyu (min)', 'en': 'Product size (min)'},
    'primer_prod_max': {'tr': 'Ürün boyu (max)', 'en': 'Product size (max)'},
    'primer_len_min': {'tr': 'Primer uzunluğu (min)', 'en': 'Primer length (min)'},
    'primer_len_max': {'tr': 'Primer uzunluğu (max)', 'en': 'Primer length (max)'},
    'primer_design_btn': {'tr': 'Primer Tasarla', 'en': 'Design Primers'},
    'primer_no': {'tr': 'No', 'en': 'No'},
    'primer_fwd': {'tr': 'Forward (5→3)', 'en': 'Forward (5→3)'},
    'primer_fwd_len': {'tr': 'Fwd Uzunluk (nt)', 'en': 'Fwd Length (nt)'},
    'primer_fwd_tm': {'tr': 'Fwd Tm (°C)', 'en': 'Fwd Tm (°C)'},
    'primer_fwd_gc': {'tr': 'Fwd GC%', 'en': 'Fwd GC%'},
    'primer_rev': {'tr': 'Reverse (5→3)', 'en': 'Reverse (5→3)'},
    'primer_rev_len': {'tr': 'Rev Uzunluk (nt)', 'en': 'Rev Length (nt)'},
    'primer_rev_tm': {'tr': 'Rev Tm (°C)', 'en': 'Rev Tm (°C)'},
    'primer_rev_gc': {'tr': 'Rev GC%', 'en': 'Rev GC%'},
    'primer_product': {'tr': 'Ürün Boyu (bp)', 'en': 'Product Size (bp)'},
    'primer_found': {'tr': 'primer çifti bulundu', 'en': 'primer pairs found'},
    'primer_seq_len': {'tr': 'dizi', 'en': 'sequence'},
    'primer_no_seq': {'tr': 'Lütfen bir DNA dizisi girin veya çekin.',
                      'en': 'Please enter or fetch a DNA sequence.'},
    'primer_too_short': {'tr': 'Dizi çok kısa. En az 50 baz gerekli.',
                         'en': 'Sequence too short. At least 50 bases required.'},
    'primer_too_long': {'tr': 'Dizi çok uzun (maks. 10.000 baz). Daha kısa bir bölge seçin.',
                        'en': 'Sequence too long (max 10,000 bases). Please select a shorter region.'},
    'primer_not_found': {'tr': 'Uygun primer bulunamadı. Ürün boyu aralığını genişletmeyi deneyin.',
                         'en': 'No suitable primers found. Try widening the product size range.'},
    'primer_not_installed': {'tr': 'Primer3 kütüphanesi sunucuda kurulu değil.',
                             'en': 'Primer3 library is not installed on the server.'},
    'primer_ai_prompt': {
        'tr': 'Primer sonuçlarını yapay zeka ile yorumlatmak ister misiniz? (spesifiklik, dimer riski, öneriler)',
        'en': 'Would you like AI to interpret the primer results? (specificity, dimer risk, recommendations)'},
    'primer_ai_btn': {'tr': 'AI ile Yorumla', 'en': 'Interpret with AI'},
    'primer_ai_title': {'tr': 'AI Değerlendirmesi', 'en': 'AI Assessment'},
    'primer_ai_failed': {'tr': 'AI yorumu alınamadı', 'en': 'AI interpretation failed'},
    'primer_acc_empty': {'tr': 'Lütfen bir accession/ID girin.', 'en': 'Please enter an accession/ID.'},
    'primer_fetched': {'tr': 'Dizi çekildi', 'en': 'Sequence fetched'},
    'primer_fetch_then': {'tr': "baz). Şimdi 'Primer Tasarla'ya basın.",
                          'en': "bases). Now click 'Design Primers'."},

    # ---- Sekans Analiz Aracı ----
    'sa_title': {'tr': 'Sekans Analiz Aracı', 'en': 'Sequence Analysis Tool'},
    'sa_subtitle': {'tr': 'DNA, RNA veya Protein sekansınızı dosya yükleyerek veya yapıştırarak analiz edin.',
                    'en': 'Analyze your DNA, RNA or Protein sequence by uploading a file or pasting it.'},
    'sa_control_panel': {'tr': 'Kontrol Paneli', 'en': 'Control Panel'},
    'sa_file_format': {'tr': 'Dosya Formatı:', 'en': 'File Format:'},
    'sa_seq_type': {'tr': 'Sekans Tipi:', 'en': 'Sequence Type:'},
    'sa_dna': {'tr': 'DNA', 'en': 'DNA'},
    'sa_rna': {'tr': 'RNA', 'en': 'RNA'},
    'sa_protein': {'tr': 'Protein', 'en': 'Protein'},
    'sa_drag_drop': {'tr': 'Sürükleyip Bırakın veya ', 'en': 'Drag and Drop or '},
    'sa_select_file': {'tr': 'Dosya Seçin', 'en': 'Select File'},
    'sa_seq_data_label': {'tr': 'Sekans Verisi (veya dosyadan okunan içerik):',
                          'en': 'Sequence Data (or content read from file):'},
    'sa_seq_placeholder': {'tr': 'Dosya yükleyin veya sekansı buraya yapıştırın...',
                           'en': 'Upload a file or paste the sequence here...'},
    'sa_analyze_btn': {'tr': 'Analiz Et', 'en': 'Analyze'},
    'sa_results_title': {'tr': 'Analiz Sonuçları', 'en': 'Analysis Results'},
    'sa_results_placeholder': {'tr': 'Lütfen soldaki menüden bir sekans girip analizi başlatın.',
                               'en': 'Please enter a sequence from the left menu and start the analysis.'},
    'sa_no_input': {'tr': 'Lütfen analiz için bir dosya yükleyin veya sekans girin.',
                    'en': 'Please upload a file or enter a sequence for analysis.'},
    'sa_file_error': {'tr': 'Dosya okunurken bir hata oluştu',
                      'en': 'An error occurred while reading the file'},
    'sa_file_format_hint': {'tr': 'Lütfen dosya formatını doğru seçtiğinizden emin olun.',
                            'en': 'Please make sure you selected the correct file format.'},
    'sa_no_valid_seq': {'tr': 'Dosya içinde geçerli bir sekans bulunamadı.',
                        'en': 'No valid sequence found in the file.'},
    'sa_no_uracil': {'tr': "Protein sekansında 'U' (Urasil) bulunamaz.",
                     'en': "'U' (Uracil) cannot be present in a protein sequence."},
    'sa_analysis_error': {'tr': 'Analiz sırasında bir hata oluştu',
                          'en': 'An error occurred during analysis'},
    'sa_file_id': {'tr': 'Dosya ID:', 'en': 'File ID:'},
    'sa_description': {'tr': 'Açıklama:', 'en': 'Description:'},
    'sa_analyzed_type': {'tr': 'Analiz Edilen Sekans Tipi:', 'en': 'Analyzed Sequence Type:'},
    'sa_length': {'tr': 'Uzunluk:', 'en': 'Length:'},
    'sa_length_unit': {'tr': 'baz/amino asit', 'en': 'bases/amino acids'},
    'sa_mol_weight': {'tr': 'Moleküler Ağırlık:', 'en': 'Molecular Weight:'},
    'sa_transcription': {'tr': 'Transkripsiyon (DNA → RNA):', 'en': 'Transcription (DNA → RNA):'},
    'sa_complement': {'tr': 'Tamamlayıcı (Complement) DNA:', 'en': 'Complement DNA:'},
    'sa_rev_complement': {'tr': 'Ters-Tamamlayıcı (Reverse Complement) DNA:',
                          'en': 'Reverse Complement DNA:'},
    'sa_rev_transcription': {'tr': 'Ters Transkripsiyon (RNA → DNA):',
                             'en': 'Reverse Transcription (RNA → DNA):'},
    'sa_translation': {'tr': 'Translasyon (RNA → Protein):', 'en': 'Translation (RNA → Protein):'},
    'sa_amino_acid': {'tr': 'Amino Asit', 'en': 'Amino Acid'},
    'sa_percent': {'tr': 'Yüzde', 'en': 'Percentage'},
    'sa_gc_content': {'tr': 'GC İçeriği', 'en': 'GC Content'},
    'sa_base_dist': {'tr': 'Baz Dağılımı', 'en': 'Base Distribution'},
    'sa_aa_dist': {'tr': 'Amino Asit Dağılımı', 'en': 'Amino Acid Distribution'},

    # ---- Navbar ----
    'nav_blog': {'tr': 'Blog', 'en': 'Blog'},
    'nav_article_search': {'tr': 'Makale Arama', 'en': 'Article Search'},
    'nav_biotools': {'tr': 'Biyoinformatik Araçları', 'en': 'Bioinformatics Tools'},
    'nav_basic_tools': {'tr': 'Temel Araçlar', 'en': 'Basic Tools'},
    'nav_precision_med': {'tr': 'Hassas Tıp', 'en': 'Precision Medicine'},
    'nav_seq_analyzer': {'tr': 'Sekans Analiz Aracı', 'en': 'Sequence Analysis Tool'},
    'nav_seq_alignment': {'tr': 'Sekans Hizalama Aracı', 'en': 'Sequence Alignment Tool'},
    'nav_molecule_viewer': {'tr': '3D Molekül Görüntüleyici', 'en': '3D Molecule Viewer'},
    'nav_mutation': {'tr': 'Mutasyon Etki Tahmincisi', 'en': 'Mutation Effect Predictor'},
    'nav_bacterial': {'tr': 'Bakteri Tasarımcısı', 'en': 'Bacteria Designer'},
    'nav_pipeline': {'tr': 'Pipeline Tasarımcısı', 'en': 'Pipeline Designer'},
    'nav_primer': {'tr': 'Primer Tasarımı', 'en': 'Primer Design'},
    'nav_fastq': {'tr': 'FASTQ Analizi', 'en': 'FASTQ Analysis'},
    'nav_pharma': {'tr': 'Farmakogenomik Analiz', 'en': 'Pharmacogenomic Analysis'},
    'nav_variant': {'tr': 'Varyant Önceliklendirme', 'en': 'Variant Prioritization'},
    'nav_federated': {'tr': 'Birleşik Öğrenme (FL)', 'en': 'Federated Learning (FL)'},
    'nav_generate': {'tr': 'Yeni Makale Üret', 'en': 'Generate New Article'},
    'nav_admin_dash': {'tr': 'Admin Dashboard', 'en': 'Admin Dashboard'},
    'nav_django_admin': {'tr': 'Django Admin', 'en': 'Django Admin'},
    'nav_profile': {'tr': 'Profil / Özgeçmiş', 'en': 'Profile / Resume'},
    'nav_credits': {'tr': 'Kredilerim', 'en': 'My Credits'},
    'nav_logout': {'tr': 'Çıkış Yap', 'en': 'Log Out'},
    'nav_login': {'tr': 'Giriş Yap', 'en': 'Log In'},
    'nav_register': {'tr': 'Kayıt Ol', 'en': 'Sign Up'},
    'nav_contact': {'tr': 'İletişim', 'en': 'Contact'},
    'nav_account': {'tr': 'Hesabım', 'en': 'My Account'},

    # ---- Footer ----
    'footer_quick_access': {'tr': 'Hızlı Erişim', 'en': 'Quick Access'},
    'footer_home': {'tr': 'Anasayfa', 'en': 'Home'},
    'footer_login': {'tr': 'Giriş Yap', 'en': 'Log In'},
    'footer_contact': {'tr': 'İletişim', 'en': 'Contact'},
    'footer_generate': {'tr': 'Makale Üret', 'en': 'Generate Article'},
    'footer_follow': {'tr': 'Bizi Takip Edin', 'en': 'Follow Us'},
    'footer_rights': {'tr': 'Tüm hakları saklıdır.', 'en': 'All rights reserved.'},
}


def t(key, lang='en'):
    """Anahtara karşılık gelen metni döndürür. Anahtar yoksa anahtarın kendisi döner."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get(DEFAULT_LANG, key))