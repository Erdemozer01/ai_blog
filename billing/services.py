"""
billing.services — Kredi kontrol ve düşme mantığı.

Tüm site bu modülü kullanarak kredi kontrol eder ve düşer.

Ana fonksiyonlar:
  can_use(user, service_key)      -> (bool, mesaj)   # kullanabilir mi?
  charge(user, service_key, ...)  -> kalan bakiye    # krediyi düş
  get_balance(user)               -> int             # bakiye

Kural:
  - superuser her zaman kullanabilir, kredi düşmez (sınırsız)
  - diğer kullanıcılar: yeterli kredisi varsa kullanır, işlem kredisini düşer
"""
from .models import UserCredit, ServicePrice, AIServicePrice


# AI servis anahtarları — bunlar AIServicePrice'tan, diğerleri ServicePrice'tan okunur
AI_SERVICE_KEYS = {'makale_uretim', 'bio_tool_ai', 'makale_kontrol'}


def _price_model(service_key):
    """service_key'e göre doğru fiyat modelini döndürür (AI mı analiz mi)."""
    return AIServicePrice if service_key in AI_SERVICE_KEYS else ServicePrice


def get_balance(user):
    """Kullanıcının kredi bakiyesi."""
    if not user or not user.is_authenticated:
        return 0
    return UserCredit.get_balance(user)


def get_cost(service_key, default=1):
    """Bir servisin kredi maliyeti (AI ise AIServicePrice, değilse ServicePrice)."""
    return _price_model(service_key).get_cost(service_key, default=default)


def can_use(user, service_key, default_cost=1):
    """
    Kullanıcı bu servisi kullanabilir mi?
    Döner: (izin_var_mı: bool, mesaj: str)
    """
    if not user or not user.is_authenticated:
        return False, "Bu işlem için giriş yapmalısınız."

    # Superuser sınırsız
    if user.is_superuser:
        return True, ""

    cost = _price_model(service_key).get_cost(service_key, default=default_cost)
    balance = UserCredit.get_balance(user)
    if balance < cost:
        return False, (f"Yetersiz kredi. Bu işlem {cost} kredi gerektiriyor, "
                       f"bakiyeniz {balance} kredi. Lütfen kredi yükleyin.")
    return True, ""


def charge(user, service_key, default_cost=1, description=None):
    """
    Kullanıcıdan ilgili servisin kredisini düşer.

    - Superuser ise düşmez, sadece 'sınırsız' döner.
    - Yetersiz kredi varsa ValueError fırlatır.

    Döner: kalan bakiye (superuser için None)
    """
    if not user or not user.is_authenticated:
        raise ValueError("Giriş yapılmamış kullanıcıdan kredi düşülemez.")

    # Superuser sınırsız — düşme yok
    if user.is_superuser:
        return None

    model = _price_model(service_key)
    cost = model.get_cost(service_key, default=default_cost)
    price_obj = model.objects.filter(service_key=service_key).first()
    label = price_obj.label if price_obj else service_key
    desc = description or f"{label} kullanımı"

    # UserCredit kaydı yoksa oluştur (bakiye 0)
    credit, _ = UserCredit.objects.get_or_create(user=user)
    return credit.spend(cost, description=desc, transaction_type='usage')


def add_credit(user, amount, description="Kredi yükleme", transaction_type="topup"):
    """Kullanıcıya kredi ekler (ödeme veya admin tarafından)."""
    credit, _ = UserCredit.objects.get_or_create(user=user)
    return credit.add(amount, description=description, transaction_type=transaction_type)