"""
ai_engine.services — Genel amaçlı yapay zeka motoru.

Tüm site bu modülü import ederek AI çağrısı yapar.

Ana giriş noktaları:
  generate(prompt, service_name=...)             -> str
  generate_with_pool(prompt, service_name=...)   -> (str, key, provider)
  generate_json(prompt, ...)                      -> dict
  generate_json_with_pool(prompt, ...)           -> (dict, key, provider)

Örnek:
    from ai_engine.services import generate_with_pool
    text, key, prov = generate_with_pool("Kısa bir şiir yaz",
                                         service_name="Google Gemini")
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


def generate(prompt, service_name="Google Gemini", system_prompt=None,
             max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE,
             api_key=None, model_name=None):
    """
    Ham prompt çalıştırır, düz metin döndürür (havuzsuz, tek anahtar).

    api_key + model_name verilirse doğrudan kullanır; verilmezse DB'den
    ilgili servisin aktif bir anahtarını çeker.
    """
    if not api_key or not model_name:
        from ai_engine.models import APIKey
        key_obj = APIKey.get_active_key(service_name)
        if not key_obj:
            raise RuntimeError(
                f"'{service_name}' için aktif bir API anahtarı bulunamadı.")
        api_key = key_obj.key
        model_name = key_obj.provider.model_name
    return _call_service(service_name, model_name, api_key, prompt,
                         system_prompt, max_tokens, temperature)


def generate_with_pool(prompt, service_name="Google Gemini", system_prompt=None,
                       max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE,
                       safety_settings=None):
    """
    Havuz/fallback ile üretir. İlgili servisin aktif Provider'larını ve
    her birinin aktif anahtarlarını 'en az kullanılan önce' sırasıyla dener.
    Bir anahtar hata verirse (kota/429) sıradakine geçer. Başarılı olanın
    usage_count'u artırılır.

    Döner: (text, used_key, used_provider)
    """
    from django.utils import timezone
    from ai_engine.models import Provider

    providers = list(Provider.objects.filter(
        service_name=service_name, is_active=True))
    if not providers:
        raise ValueError(
            f"'{service_name}' için aktif bir sağlayıcı/model tanımı yok.")

    last_error = None
    tried = 0
    for provider in providers:
        keys = list(provider.api_keys.filter(is_active=True).order_by('usage_count', 'id'))
        for key_obj in keys:
            tried += 1
            try:
                text = _call_service(
                    provider.service_name, provider.model_name, key_obj.key,
                    prompt, system_prompt, max_tokens, temperature, safety_settings)
                key_obj.usage_count = (key_obj.usage_count or 0) + 1
                key_obj.last_used = timezone.now()
                key_obj.save(update_fields=['usage_count', 'last_used'])
                return text, key_obj, provider
            except Exception as e:
                last_error = e
                print(f"[ai_engine] {provider.service_name}/{provider.model_name} "
                      f"anahtar #{key_obj.id} başarısız: {e}")
                continue

    if tried == 0:
        raise ValueError(f"'{service_name}' sağlayıcısında hiç aktif anahtar yok.")
    raise RuntimeError(
        f"Havuzdaki {tried} anahtarın tümü başarısız oldu. Son hata: {last_error}")


def _parse_json(text):
    """```json fence'lerini temizleyip ilk geçerli JSON nesnesini döndürür."""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?', '', cleaned).strip()
    cleaned = re.sub(r'```$', '', cleaned).strip()
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def generate_json(prompt, service_name="Google Gemini", **kwargs):
    """generate() çağırır, yanıtı JSON dict olarak döndürür."""
    text = generate(prompt, service_name=service_name, **kwargs)
    return _parse_json(text)


def generate_json_with_pool(prompt, service_name="Google Gemini", **kwargs):
    """generate_with_pool() çağırır, (dict, key, provider) döndürür."""
    text, key_obj, provider = generate_with_pool(
        prompt, service_name=service_name, **kwargs)
    return _parse_json(text), key_obj, provider