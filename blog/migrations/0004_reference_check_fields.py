from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_generatedarticle_ai_review_notes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedarticle',
            name='reference_check_result',
            field=models.JSONField(
                blank=True, null=True,
                help_text='CrossRef ile kaynakların varlık doğrulaması (özet + her kaynağın durumu).',
                verbose_name='Kaynak Doğrulama Sonucu',
            ),
        ),
        migrations.AddField(
            model_name='generatedarticle',
            name='reference_checked_at',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Kaynak Doğrulama Tarihi',
            ),
        ),
    ]