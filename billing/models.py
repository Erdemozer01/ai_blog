from django.db import models
from django.contrib.auth.models import User


class ServicePrice(models.Model):
    """
    Her AI işleminin kredi maliyeti. Admin panelinden ayarlanır.
    service_key, kodda kredi düşülürken kullanılan benzersiz anahtardır.
    """
    service_key = models.CharField(max_length=100, unique=True, verbose_name="Servis Anahtarı",
                                   help_text="Kodda kullanılan benzersiz ad (örn: makale_uretim, sequence_analyzer)")
    label = models.CharField(max_length=150, verbose_name="Görünen Ad",
                             help_text="Örn: Makale Üretimi")
    cost = models.PositiveIntegerField(default=1, verbose_name="Kredi Maliyeti",
                                       help_text="Bu işlem kaç kredi düşsün")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")

    def __str__(self):
        return f"{self.label} ({self.cost} kredi)"

    class Meta:
        verbose_name = "Servis Fiyatı"
        verbose_name_plural = "Servis Fiyatları"
        ordering = ['label']

    @classmethod
    def get_cost(cls, service_key, default=1):
        """Bir servisin kredi maliyetini döndürür. Tanımsızsa default."""
        obj = cls.objects.filter(service_key=service_key, is_active=True).first()
        return obj.cost if obj else default


class AIServicePrice(models.Model):
    """
    AI işlemlerinin (makale üretimi, bio-tool AI yorumları) kredi maliyeti.
    Analiz işlemlerinden AYRI yönetilir (ServicePrice analiz, bu AI).
    service_key, kodda kredi düşülürken kullanılan benzersiz anahtardır.
    """
    service_key = models.CharField(max_length=100, unique=True, verbose_name="Servis Anahtarı",
                                   help_text="Kodda kullanılan benzersiz ad (örn: makale_uretim, bio_tool_ai)")
    label = models.CharField(max_length=150, verbose_name="Görünen Ad",
                             help_text="Örn: Makale AI, Bio-Tool AI")
    cost = models.PositiveIntegerField(default=1, verbose_name="Kredi Maliyeti",
                                       help_text="Bu AI işlemi kaç kredi düşsün")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")

    def __str__(self):
        return f"{self.label} ({self.cost} kredi)"

    class Meta:
        verbose_name = "AI Servis Fiyatı"
        verbose_name_plural = "AI Servis Fiyatları"
        ordering = ['label']

    @classmethod
    def get_cost(cls, service_key, default=1):
        """Bir AI servisinin kredi maliyetini döndürür. Tanımsızsa default."""
        obj = cls.objects.filter(service_key=service_key, is_active=True).first()
        return obj.cost if obj else default


class UserCredit(models.Model):
    """Kullanıcının kredi bakiyesi."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='credit', verbose_name="Kullanıcı")
    balance = models.PositiveIntegerField(default=0, verbose_name="Kredi Bakiyesi")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {self.balance} kredi"

    class Meta:
        verbose_name = "Kullanıcı Kredisi"
        verbose_name_plural = "Kullanıcı Kredileri"
        ordering = ['-balance']

    @classmethod
    def get_balance(cls, user):
        """Kullanıcının bakiyesini döndürür (kaydı yoksa 0)."""
        obj = cls.objects.filter(user=user).first()
        return obj.balance if obj else 0

    def add(self, amount, description="Kredi yükleme", transaction_type="topup"):
        """Bakiyeye kredi ekler ve işlem kaydı oluşturur (atomik)."""
        from django.db import transaction
        from django.db.models import F
        if amount < 0:
            raise ValueError("Eklenecek miktar negatif olamaz.")
        with transaction.atomic():
            UserCredit.objects.filter(pk=self.pk).update(
                balance=F('balance') + amount)
            CreditTransaction.objects.create(
                user=self.user, amount=amount,
                transaction_type=transaction_type, description=description)
        self.refresh_from_db(fields=['balance'])
        return self.balance

    def spend(self, amount, description="Kullanım", transaction_type="usage"):
        """
        Bakiyeden kredi düşer. Yetersizse ValueError fırlatır.
        Eşzamanlı isteklere karşı ATOMİK: yalnızca bakiye >= amount ise düşer,
        böylece yarış durumunda bakiye eksiye düşemez (koşullu F() update).
        İşlem kaydı oluşturur (amount negatif yazılır).
        """
        from django.db import transaction
        from django.db.models import F
        if amount < 0:
            raise ValueError("Harcama miktarı negatif olamaz.")
        with transaction.atomic():
            # Tek atomik SQL UPDATE: SADECE yeterli bakiye varsa düşer.
            updated = UserCredit.objects.filter(
                pk=self.pk, balance__gte=amount
            ).update(balance=F('balance') - amount)
            if not updated:
                current = (UserCredit.objects
                           .filter(pk=self.pk)
                           .values_list('balance', flat=True).first()) or 0
                raise ValueError(
                    f"Yetersiz kredi. Gerekli: {amount}, mevcut: {current}")
            CreditTransaction.objects.create(
                user=self.user, amount=-amount,
                transaction_type=transaction_type, description=description)
        self.refresh_from_db(fields=['balance'])
        return self.balance


class CreditTransaction(models.Model):
    """Kredi hareketleri geçmişi (yükleme + harcama)."""
    TYPE_CHOICES = (
        ('topup', 'Kredi Yükleme'),
        ('usage', 'Kullanım'),
        ('refund', 'İade'),
        ('bonus', 'Bonus'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='credit_transactions', verbose_name="Kullanıcı")
    amount = models.IntegerField(verbose_name="Miktar",
                                 help_text="Pozitif: yükleme, Negatif: harcama")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES,
                                        default='usage', verbose_name="İşlem Tipi")
    description = models.CharField(max_length=255, blank=True, verbose_name="Açıklama")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user.username}: {sign}{self.amount} ({self.get_transaction_type_display()})"

    class Meta:
        verbose_name = "Kredi Hareketi"
        verbose_name_plural = "Kredi Hareketleri"
        ordering = ['-created_at']