from django.db import migrations


def add_restriction_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.get_or_create(
        service_key='bio_restriction',
        defaults={'label': 'Restriksiyon Enzim Analizi', 'cost': 5, 'is_active': True})


def remove_restriction_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.filter(service_key='bio_restriction').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_primer_price'),
    ]

    operations = [
        migrations.RunPython(add_restriction_price, remove_restriction_price),
    ]