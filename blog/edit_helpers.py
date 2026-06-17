"""
Makale Düzenleme Yardımcıları.

Sorun: full_content içinde _||_STRUCTURED_DATA_N_||_ ve _||_SECTION_BREAK_||_
gibi yer tutucular var. Kullanıcı bunları görmemeli/bozmamalı, ama grafikler
korunmalı.

Çözüm: İçeriği yer tutucuların ETRAFINDAN parçalara böl. Kullanıcı yalnızca
metin parçalarını düzenler; yer tutucular kilitli/gizli tutulur ve kaydederken
aynen geri yerleştirilir.

Ayrıca: kullanıcının gerçekten düzenleme yapıp yapmadığını anlamak için
içerik imzası (hash) karşılaştırması.
"""
import re
import hashlib


PLACEHOLDER_PATTERN = r'(_\|\|_[A-Z_]+\d*_\|\|_)'


def split_content_for_editing(full_content):
    """
    İçeriği yer tutucuların etrafından böler.
    Döner: parçalar listesi.
      - {'type': 'text', 'value': '...'}
      - {'type': 'placeholder', 'token': '_||_..._||_', 'label': '📊 Grafik 1'}
    """
    if not full_content:
        return [{'type': 'text', 'value': ''}]

    parts = re.split(PLACEHOLDER_PATTERN, full_content)
    result = []
    graph_counter = 0

    for part in parts:
        if not part:
            continue
        if re.fullmatch(PLACEHOLDER_PATTERN, part):
            if 'STRUCTURED_DATA' in part:
                graph_counter += 1
                label = f"📊 Grafik / Tablo {graph_counter}"
            elif 'SECTION_BREAK' in part:
                label = "✂️ Bölüm Ayracı"
            else:
                label = "🔒 Özel Alan"
            result.append({'type': 'placeholder', 'token': part, 'label': label})
        else:
            result.append({'type': 'text', 'value': part})

    return result


def get_editable_text_parts(full_content):
    """
    Yalnızca düzenlenebilir metin parçalarını sıralı döndürür (template için).
    Her biri {'index': i, 'value': '...'} — index orijinal parça sırasındaki yeri.
    """
    parts = split_content_for_editing(full_content)
    editable = []
    for i, p in enumerate(parts):
        if p['type'] == 'text':
            editable.append({'index': i, 'value': p['value']})
    return editable, parts


def rebuild_content(original_parts, edited_texts):
    """
    Düzenlenmiş metin parçalarını orijinal yapıyla birleştirir.
    original_parts: split_content_for_editing çıktısı (yapı + token'lar)
    edited_texts: {index: yeni_metin} sözlüğü (sadece text parçaları)

    Yer tutucular original_parts'tan aynen alınır — kullanıcı onlara dokunamaz.
    """
    pieces = []
    for i, p in enumerate(original_parts):
        if p['type'] == 'text':
            # Kullanıcının düzenlediği metni kullan; yoksa orijinali
            pieces.append(edited_texts.get(i, p['value']))
        else:
            # Yer tutucu — orijinalden aynen
            pieces.append(p['token'])
    return ''.join(pieces)


def content_signature(full_content):
    """İçeriğin imzasını (hash) üretir — değişiklik tespiti için."""
    if not full_content:
        return ''
    normalized = re.sub(r'\s+', ' ', full_content).strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def has_meaningful_change(old_content, new_content):
    """
    İçerik anlamlı şekilde değişmiş mi? (Sadece boşluk farkı değişiklik sayılmaz.)
    Döner: bool
    """
    return content_signature(old_content) != content_signature(new_content)