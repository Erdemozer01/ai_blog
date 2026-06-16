from django.db import migrations


def add_plasmid_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.get_or_create(
        service_key='bio_plasmid_map',
        defaults={'label': 'Plazmit Harita Görselleştirici', 'cost': 5, 'is_active': True})


def remove_plasmid_price(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.filter(service_key='bio_plasmid_map').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_restriction_price'),
    ]

    operations = [
        migrations.RunPython(add_plasmid_price, remove_plasmid_price),
    ]