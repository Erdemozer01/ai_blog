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
    Tarayıcı diline göre 'tr' veya 'en' döndürür.
    Accept-Language başlığında 'tr' geçiyorsa Türkçe, yoksa İngilizce.
    """
    if request is None:
        return DEFAULT_LANG
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '').lower()
    # Türkçe tarayıcı tespiti
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
}


def t(key, lang='en'):
    """Anahtara karşılık gelen metni döndürür. Anahtar yoksa anahtarın kendisi döner."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get(DEFAULT_LANG, key))