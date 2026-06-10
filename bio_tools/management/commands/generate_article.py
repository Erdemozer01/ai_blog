"""
Otomatik makale üretimi — komut satırından veya zamanlanmış görevle (PythonAnywhere Tasks) çalışır.

Kullanım:
    # Rastgele konu, varsayılan API ve uzunluk
    python manage.py generate_article

    # Belirli konu
    python manage.py generate_article --topic "Kuantum bilgisayarların geleceği"

    # API ve uzunluk belirterek
    python manage.py generate_article --api-id 1 --length 2500

    # Sahibi belirterek (varsayılan: ilk superuser)
    python manage.py generate_article --owner admin
"""
import random

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from blog.models import GeneratedArticle, Category, APIKey
from dash_apps.generate import run_ai_generation


# Otomatik üretimde rastgele seçilecek konu havuzu
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
    help = "AI ile otomatik makale üretir ve veritabanına kaydeder."

    def add_arguments(self, parser):
        parser.add_argument('--topic', type=str, default=None,
                            help='Makale konusu (boşsa havuzdan rastgele seçilir)')
        parser.add_argument('--api-id', type=int, default=None,
                            help='Kullanılacak APIKey ID (boşsa ilk aktif anahtar)')
        parser.add_argument('--length', type=int, default=1500,
                            help='Makale uzunluğu (kelime). Varsayılan 1500')
        parser.add_argument('--owner', type=str, default=None,
                            help='Makale sahibi kullanıcı adı (boşsa ilk superuser)')

    def handle(self, *args, **options):
        # 1. Konu
        topic = options['topic'] or random.choice(DEFAULT_TOPICS)
        self.stdout.write(f"Konu: {topic}")

        # 2. API anahtarı
        api_id = options['api_id']
        if api_id:
            api_obj = APIKey.objects.filter(id=api_id, is_active=True).first()
        else:
            api_obj = APIKey.objects.filter(is_active=True).first()
        if not api_obj:
            raise CommandError("Aktif bir API anahtarı bulunamadı. "
                               "Admin panelinden bir APIKey ekleyin.")
        self.stdout.write(f"API: {api_obj.service_name} (id={api_obj.id})")

        # 3. Sahip
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

        # 4. Üretim
        length = options['length']
        self.stdout.write(f"Üretiliyor ({length} kelime)... bu biraz sürebilir.")
        try:
            ai_data = run_ai_generation(topic, api_obj.id, length)
        except Exception as e:
            raise CommandError(f"AI üretim hatası: {e}")

        if not isinstance(ai_data, dict) or "content" not in ai_data:
            raise CommandError("AI'dan beklenen formatta yanıt alınamadı.")

        # 5. Kategori
        category_name = ai_data.get("category_name", "Genel").strip().title()
        category_obj, _ = Category.objects.get_or_create(name=category_name)

        # 6. Kayıt
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
            f"✓ Makale üretildi: '{article.title}' (id={article.id}, kategori={category_name})"
        ))