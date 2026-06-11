"""
Otomatik makale üretimi — komut satırından veya zamanlanmış görevle çalışır.

API Anahtarı Havuzu: Belirtilen servisin tüm aktif anahtarlarını "en az
kullanılan önce" sırasıyla dener. Bir anahtar kota/hata verirse otomatik
olarak havuzdaki sıradaki anahtara geçer. Üretim, bir anahtar başarılı
olana kadar devam eder.

Kullanım:
    # Rastgele konu, Gemini havuzundan üret
    python manage.py generate_article

    # Belirli konu
    python manage.py generate_article --topic "Kuantum bilgisayarların geleceği"

    # Uzunluk belirterek
    python manage.py generate_article --length 2500

    # Farklı servis havuzu (OpenAI / Anthropic)
    python manage.py generate_article --service OpenAI

    # Sahibi belirterek (varsayılan: ilk superuser)
    python manage.py generate_article --owner admin
"""
import random

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from blog.models import GeneratedArticle, Category
from dash_apps.generate import run_ai_generation_with_pool


DEFAULT_TOPICS = [
    "Yapay zekanın sağlık sektöründeki dönüştürücü etkileri",
    "Kuantum bilgisayarların kriptografi üzerindeki etkisi",
    "CRISPR gen düzenleme teknolojisinin etik boyutları",
    "Sürdürülebilir enerji teknolojilerinde son gelişmeler",
    "Büyük dil modellerinin bilimsel araştırmadaki rolü",
    "Mikrobiyom araştırmalarının kişiselleştirilmiş tıbba katkısı",
    "Nöromorfik hesaplama ve beyin-bilgisayar arayüzleri",
    "İklim değişikliğiyle mücadelede biyoteknolojik çözümler",
    "Otonom sistemlerde güvenlik ve doğrulama yöntemleri",
    "Sentetik biyoloji ve geleceğin ilaç üretimi",
]


class Command(BaseCommand):
    help = "AI anahtarı havuzu ile otomatik makale üretir ve kaydeder."

    def add_arguments(self, parser):
        parser.add_argument('--topic', type=str, default=None,
                            help='Makale konusu (boşsa havuzdan rastgele seçilir)')
        parser.add_argument('--length', type=int, default=1500,
                            help='Makale uzunluğu (kelime). Varsayılan 1500')
        parser.add_argument('--owner', type=str, default=None,
                            help='Makale sahibi kullanıcı adı (boşsa ilk superuser)')
        parser.add_argument('--service', type=str, default='Google Gemini',
                            help='Kullanılacak servis havuzu (varsayılan: Google Gemini)')
        parser.add_argument('--model', type=str, default=None,
                            help='Model adı (boşsa sağlayıcının ilk aktif modeli)')

    def handle(self, *args, **options):
        # 1. Konu
        topic = options['topic'] or random.choice(DEFAULT_TOPICS)
        self.stdout.write(f"Konu: {topic}")

        # 2. Sahip
        owner_name = options['owner']
        if owner_name:
            owner = User.objects.filter(username=owner_name).first()
            if not owner:
                raise CommandError(f"'{owner_name}' kullanıcısı bulunamadı.")
        else:
            owner = User.objects.filter(is_superuser=True).order_by('id').first()
            if not owner:
                raise CommandError("Hiç superuser yok. Önce createsuperuser çalıştırın.")
        self.stdout.write(f"Sahip: {owner.username}")

        # 3. Üretim — API havuzu ile (fallback)
        length = options['length']
        service = options['service']
        model = options['model']
        self.stdout.write(f"Üretiliyor ({length} kelime, {service} havuzu)... "
                          "bu biraz sürebilir.")
        try:
            ai_data, used_key = run_ai_generation_with_pool(
                topic, word_count=length, service_name=service, model_name=model)
        except Exception as e:
            raise CommandError(f"AI üretim hatası: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"✓ Üretim başarılı — anahtar #{used_key.id}"))

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise CommandError("AI'dan beklenen formatta yanıt alınamadı.")

        # 4. Kategori
        category_name = ai_data.get("category_name", "Genel").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=category_name)

        # 5. Kayıt
        article = GeneratedArticle.objects.create(
            owner=owner,
            user_request=topic,
            title=ai_data.get("title"),
            category=category_obj,
            keywords=ai_data.get("keywords", ""),
            english_abstract=ai_data.get("english_abstract"),
            turkish_abstract=ai_data.get("turkish_abstract"),
            full_content=ai_data.get("content"),
            bibliography=ai_data.get("bibliography"),
            structured_data=ai_data.get("structured_data"),
            status='tamamlandi',
        )

        self.stdout.write(self.style.SUCCESS(
            f"✓ Makale üretildi: '{article.title}' "
            f"(id={article.id}, kategori={category_name})"
        ))
