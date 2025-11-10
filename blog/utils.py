# blog/utils.py

from django.utils.text import slugify as django_slugify
import re

# Slug'da yer almasını istemediğimiz gereksiz kelimeler (bu liste aynı kalabilir)
stop_words = [
    've', 'ile', 'ama', 'fakat', 'lakin', 'ancak', 'ya', 'veya', 'da', 'de',
    'bir', 'bu', 'şu', 'o', 'için', 'gibi', 'mi', 'mı', 'mu', 'mü',
    'acaba', 'aslında', 'hem', 'her', 'hiç', 'ise', 'kez', 'ki', 'ne',
    'sonra', 'önce', 'şey', 'çok', 'en', 'hep', 'pek', 'zaten', 'yani',
    'üzerine'
]


def custom_slugify(value):
    """
    Gereksiz kelimeleri ('stop words') çıkaran ve Türkçe karakterleri
    koruyarak slug oluşturan GÜNCELLENMİŞ ve SAĞLAM bir fonksiyon.
    """
    # --- YENİ: Ön İşleme Adımları ---

    # 1. Özel tire karakterlerini standart tireye dönüştür
    value = value.replace('–', '-')

    # 2. İki nokta ve virgül gibi noktalama işaretlerini boşlukla değiştir
    value = value.replace(':', ' ').replace(',', ' ')

    # 3. Birden fazla olan boşlukları tek boşluğa indir
    value = re.sub(r'\s+', ' ', value).strip()

    # --- Eski Kodun Devamı ---

    # 4. Değeri küçük harfe çevir ve kelimelere ayır
    words = value.lower().split()

    # 5. Gereksiz kelimeleri listeden çıkar
    cleaned_words = [word for word in words if word not in stop_words]

    # 6. Temizlenmiş kelimeleri tekrar birleştir
    new_value = " ".join(cleaned_words)

    # 7. Son olarak, Django'nun slugify fonksiyonunu çağır
    return django_slugify(new_value, allow_unicode=True)