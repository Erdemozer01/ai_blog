from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ServicePrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_key', models.CharField(help_text='Kodda kullanılan benzersiz ad (örn: makale_uretim, sequence_analyzer)', max_length=100, unique=True, verbose_name='Servis Anahtarı')),
                ('label', models.CharField(help_text='Örn: Makale Üretimi', max_length=150, verbose_name='Görünen Ad')),
                ('cost', models.PositiveIntegerField(default=1, help_text='Bu işlem kaç kredi düşsün', verbose_name='Kredi Maliyeti')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktif mi?')),
            ],
            options={
                'verbose_name': 'Servis Fiyatı',
                'verbose_name_plural': 'Servis Fiyatları',
                'ordering': ['label'],
            },
        ),
        migrations.CreateModel(
            name='UserCredit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.PositiveIntegerField(default=0, verbose_name='Kredi Bakiyesi')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credit', to=settings.AUTH_USER_MODEL, verbose_name='Kullanıcı')),
            ],
            options={
                'verbose_name': 'Kullanıcı Kredisi',
                'verbose_name_plural': 'Kullanıcı Kredileri',
                'ordering': ['-balance'],
            },
        ),
        migrations.CreateModel(
            name='CreditTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField(help_text='Pozitif: yükleme, Negatif: harcama', verbose_name='Miktar')),
                ('transaction_type', models.CharField(choices=[('topup', 'Kredi Yükleme'), ('usage', 'Kullanım'), ('refund', 'İade'), ('bonus', 'Bonus')], default='usage', max_length=20, verbose_name='İşlem Tipi')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Açıklama')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_transactions', to=settings.AUTH_USER_MODEL, verbose_name='Kullanıcı')),
            ],
            options={
                'verbose_name': 'Kredi Hareketi',
                'verbose_name_plural': 'Kredi Hareketleri',
                'ordering': ['-created_at'],
            },
        ),
    ]
