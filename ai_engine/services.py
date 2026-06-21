"""
ai_engine.services — Genel amaçlı yapay zeka motoru.

Tüm site bu modülü import ederek AI çağrısı yapar.

Mimari:
  Provider (sağlayıcı) → API anahtarı havuzu (model'den bağımsız)
                       → birden çok Model (gemini-2.5-flash, ...)

Ana giriş noktaları:
  generate_with_pool(prompt, service_name=..., model_name=...)  -> (str, key)
      Sağlayıcının anahtar havuzunu 'en az kullanılan önce' dener; biri
      hata verirse (429/kota) diğerine geçer. model_name verilmezse
      sağlayıcının ilk aktif modeli kullanılır.

  generate_json_with_pool(...) -> (dict, key)
      Yanıtı JSON olarak ayrıştırır.

Örnek (bio-tool, model sabit):
    from ai_engine.services import generate_with_pool
    text, key = generate_with_pool("Özetle...", service_name="Google Gemini",
                                   model_name="gemini-2.5-flash")

Örnek (makale, kullanıcı modeli seçti):
    text, key = generate_with_pool(prompt, service_name="Google Gemini",
                                   model_name=secilen_model)
"""
import json
import re

try:
    import google.generativeai as genai
except Exception:
    genai = None
try:
    import openai
except Exception:
    openai = None
try:
    import anthropic
except Exception:
    anthropic = None


DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.7


def _call_service(service_name, model_name, api_key, prompt,
                  system_prompt=None, max_tokens=DEFAULT_MAX_TOKENS,
                  temperature=DEFAULT_TEMPERATURE, safety_settings=None):
    """Tek bir servise ham istek gönderir, düz metin döndürür."""
    if service_name == 'Google Gemini':
        if genai is None:
            raise RuntimeError("google.generativeai kurulu değil.")
        genai.configure(api_key=api_key)
        generation_config = {"temperature": temperature, "max_output_tokens": max_tokens}
        model = genai.GenerativeModel(model_name=model_name,
                                      generation_config=generation_config)
        full = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if safety_settings:
            response = model.generate_content(full, safety_settings=safety_settings)
        else:
            response = model.generate_content(full)
        return response.text

    elif service_name == 'OpenAI':
        if openai is None:
            raise RuntimeError("openai kurulu değil.")
        client = openai.OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model_name, messages=messages, max_tokens=max_tokens,
            temperature=temperature)
        return response.choices[0].message.content

    elif service_name == 'Anthropic':
        if anthropic is None:
            raise RuntimeError("anthropic kurulu değil.")
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = {"model": model_name, "max_tokens": max_tokens,
                  "temperature": temperature,
                  "messages": [{"role": "user", "content": prompt}]}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text

    raise ValueError(f"Bilinmeyen servis: {service_name}")


def _resolve_model_name(provider, model_name=None):
    """
    model_name verilmemişse sağlayıcının ilk aktif modelini seçer.
    Verilmişse aynen döndürür (kodda sabit kullanım için).
    """
    if model_name:
        return model_name
    first = provider.ai_models.filter(is_active=True).order_by('id').first()
    if not first:
        raise ValueError(
            f"'{provider.service_name}' için aktif bir model tanımı yok. "
            "Admin panelinden model ekleyin.")
    return first.model_name


def generate_with_pool(prompt, service_name="Google Gemini", model_name=None,
                       system_prompt=None, max_tokens=DEFAULT_MAX_TOKENS,
                       temperature=DEFAULT_TEMPERATURE, safety_settings=None):
    """
    Havuz/fallback ile üretir.

    İlgili sağlayıcının aktif anahtarlarını 'en az kullanılan önce' sırasıyla
    dener. Bir anahtar hata verirse (kota/429) sıradakine geçer. Başarılı
    olanın usage_count'u artırılır.

    model_name verilmezse sağlayıcının ilk aktif modeli kullanılır.

    Döner: (text, used_key)
    """
    from django.utils import timezone
    from ai_engine.models import Provider

    try:
        provider = Provider.objects.get(service_name=service_name, is_active=True)
    except Provider.DoesNotExist:
        raise ValueError(f"'{service_name}' adlı aktif bir sağlayıcı yok.")

    resolved_model = _resolve_model_name(provider, model_name)

    keys = list(provider.api_keys.filter(is_active=True).order_by('usage_count', 'id'))
    if not keys:
        raise ValueError(f"'{service_name}' sağlayıcısında hiç aktif anahtar yok.")

    last_error = None
    for key_obj in keys:
        try:
            text = _call_service(
                service_name, resolved_model, key_obj.key,
                prompt, system_prompt, max_tokens, temperature, safety_settings)
            key_obj.usage_count = (key_obj.usage_count or 0) + 1
            key_obj.last_used = timezone.now()
            key_obj.save(update_fields=['usage_count', 'last_used'])
            return text, key_obj
        except Exception as e:
            last_error = e
            print(f"[ai_engine] {service_name}/{resolved_model} "
                  f"anahtar #{key_obj.id} başarısız: {e}")
            continue

    raise RuntimeError(
        f"Havuzdaki {len(keys)} anahtarın tümü başarısız oldu. Son hata: {last_error}")


def _parse_json(text):
    """```json fence'lerini temizleyip ilk geçerli JSON nesnesini döndürür."""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?', '', cleaned).strip()
    cleaned = re.sub(r'```$', '', cleaned).strip()
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def generate_json_with_pool(prompt, service_name="Google Gemini", model_name=None, **kwargs):
    """generate_with_pool() çağırır, (dict, key) döndürür."""
    text, key_obj = generate_with_pool(
        prompt, service_name=service_name, model_name=model_name, **kwargs)
    return _parse_json(text), key_obj


def get_fallback_models(preferred_service=None, preferred_model=None, cross_provider=False):
    """
    Fallback için denenecek (service_name, model_name) listesini döndürür.

    cross_provider=False (varsayılan): SADECE seçilen sağlayıcının modelleri denenir.
        Kullanıcı bir sağlayıcı seçtiyse (örn. 'Anthropic'), o seçime sadık kalınır.
    cross_provider=True: Seçilen sağlayıcı önce, sonra DİĞER aktif sağlayıcılar da
        denenir. Sistem-içi otomatik çağrılar (kota dolunca devam etmesi gereken
        keyword/yorum üretimi vb.) için kullanılır.

    Döner: [(service_name, model_name), ...] sıralı liste.
    """
    ordered = []

    # 1. Seçilen sağlayıcı + model en başta
    if preferred_service and preferred_model:
        ordered.append((preferred_service, preferred_model))

    try:
        from ai_engine.models import AIModel
        actives = (AIModel.objects
                   .filter(is_active=True, provider__is_active=True)
                   .select_related('provider'))

        # 2. Seçilen sağlayıcının diğer aktif modelleri
        if preferred_service:
            for m in actives:
                if m.provider.service_name == preferred_service:
                    pair = (m.provider.service_name, m.model_name)
                    if pair not in ordered:
                        ordered.append(pair)

        # 3. cross_provider=True ise DİĞER sağlayıcıların modelleri (son çare)
        if cross_provider:
            for m in actives:
                pair = (m.provider.service_name, m.model_name)
                if pair not in ordered:
                    ordered.append(pair)
    except Exception:
        pass

    # Hiçbir şey bulunamadıysa en azından seçileni dene
    if not ordered and preferred_service:
        ordered.append((preferred_service, preferred_model))

    return ordered