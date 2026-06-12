from django.db import migrations


def create_default_prices(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    defaults = [
        ('makale_uretim', 'Makale Üretimi', 10),
        ('bio_sequence_analyzer', 'Sekans Analizi', 5),
        ('bio_sequence_alignment', 'Sekans Hizalama', 5),
        ('bio_molecule_viewer', 'Molekül Görüntüleyici', 5),
        ('bio_mutation_predictor', 'Mutasyon Tahmini', 5),
        ('bio_bacterial_designer', 'Bakteri Tasarımı', 5),
        ('bio_pipeline_designer', 'Pipeline Tasarımı', 5),
        ('bio_federated', 'Federated Learning', 5),
        ('bio_pharmacogenomics', 'Farmakogenomik', 5),
        ('bio_variant', 'Varyant Önceliklendirme', 5),
    ]
    for key, label, cost in defaults:
        ServicePrice.objects.get_or_create(
            service_key=key, defaults={'label': label, 'cost': cost, 'is_active': True})


def remove_default_prices(apps, schema_editor):
    ServicePrice = apps.get_model('billing', 'ServicePrice')
    ServicePrice.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_prices, remove_default_prices),
    ]
