from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ArticleFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vote', models.CharField(choices=[('like', 'Faydalı'), ('dislike', 'Faydasız')], max_length=10, verbose_name='Oy')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feedbacks',
                    to='blog.generatedarticle',
                    verbose_name='Makale',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Kullanıcı',
                )),
            ],
            options={
                'verbose_name': 'Makale Geri Bildirimi',
                'verbose_name_plural': 'Makale Geri Bildirimleri',
                'unique_together': {('article', 'user')},
            },
        ),
    ]