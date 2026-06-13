from django.db import migrations


def add_primer_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.get_or_create(
        service_key='bio_primer_design',
        defaults={'label': 'Primer Tasarımı', 'cost': 5, 'is_active': True})


def remove_primer_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.filter(service_key='bio_primer_design').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_default_prices'),
    ]

    operations = [
        migrations.RunPython(add_primer_price, remove_primer_price),
    ]
