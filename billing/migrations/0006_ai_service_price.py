from django.db import migrations, models


def setup_ai_prices(apps, schema_editor):
    AIServicePrice = apps.get_model('billing', 'AIServicePrice')
    ServicePrice = apps.get_model('billing', 'ServicePrice')

    # Eski makale_uretim fiyatını al (varsa), AI tablosuna taşı
    makale = ServicePrice.objects.filter(service_key='makale_uretim').first()
    makale_cost = makale.cost if makale else 10

    # AI Servis Fiyatları (2 satır)
    AIServicePrice.objects.get_or_create(
        service_key='makale_uretim',
        defaults={'label': 'Makale AI', 'cost': makale_cost, 'is_active': True})
    AIServicePrice.objects.get_or_create(
        service_key='bio_tool_ai',
        defaults={'label': 'Bio-Tool AI', 'cost': 5, 'is_active': True})

    # makale_uretim artık AI tablosunda — analiz (ServicePrice) tablosundan kaldır
    ServicePrice.objects.filter(service_key='makale_uretim').delete()


def reverse_ai_prices(apps, schema_editor):
    AIServicePrice = apps.get_model('billing', 'AIServicePrice')
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    # makale_uretim'i analiz tablosuna geri koy
    ai_makale = AIServicePrice.objects.filter(service_key='makale_uretim').first()
    cost = ai_makale.cost if ai_makale else 10
    ServicePrice.objects.get_or_create(
        service_key='makale_uretim',
        defaults={'label': 'Makale Üretimi', 'cost': cost, 'is_active': True})
    AIServicePrice.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_plasmid_price'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIServicePrice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_key', models.CharField(help_text='Kodda kullanılan benzersiz ad (örn: makale_uretim, bio_tool_ai)', max_length=100, unique=True, verbose_name='Servis Anahtarı')),
                ('label', models.CharField(help_text='Örn: Makale AI, Bio-Tool AI', max_length=150, verbose_name='Görünen Ad')),
                ('cost', models.PositiveIntegerField(default=1, help_text='Bu AI işlemi kaç kredi düşsün', verbose_name='Kredi Maliyeti')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktif mi?')),
            ],
            options={
                'verbose_name': 'AI Servis Fiyatı',
                'verbose_name_plural': 'AI Servis Fiyatları',
                'ordering': ['label'],
            },
        ),
        migrations.RunPython(setup_ai_prices, reverse_ai_prices),
    ]