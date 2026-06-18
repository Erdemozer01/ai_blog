from django.db import migrations


def add_makale_kontrol_price(apps, schema_editor):
    AIServicePrice = apps.get_model('billing', 'AIServicePrice')
    AIServicePrice.objects.get_or_create(
        service_key='makale_kontrol',
        defaults={'label': 'Makale Kontrol (AI)', 'cost': 5, 'is_active': True})


def remove_makale_kontrol_price(apps, schema_editor):
    AIServicePrice = apps.get_model('billing', 'AIServicePrice')
    AIServicePrice.objects.filter(service_key='makale_kontrol').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_alter_aiserviceprice_id'),
    ]

    operations = [
        migrations.RunPython(add_makale_kontrol_price, remove_makale_kontrol_price),
    ]