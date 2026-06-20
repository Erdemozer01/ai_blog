from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('blog', '0005_last_edited_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('makale_hatasi', 'Makale Oluşturma Hatası'), ('ai_inceleme_hatasi', 'AI İnceleme Hatası'), ('kaynak_hatasi', 'Kaynak Kontrol Hatası'), ('iletisim', 'İletişim Mesajı'), ('sistem', 'Sistem Bildirimi'), ('diger', 'Diğer')], default='diger', max_length=30, verbose_name='Kategori')),
                ('title', models.CharField(max_length=200, verbose_name='Başlık')),
                ('message', models.TextField(blank=True, verbose_name='Mesaj / Detay')),
                ('technical_detail', models.TextField(blank=True, verbose_name='Teknik Detay (ham hata)')),
                ('is_read', models.BooleanField(default=False, verbose_name='Okundu')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma')),
                ('related_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to=settings.AUTH_USER_MODEL, verbose_name='İlgili Kullanıcı')),
            ],
            options={
                'verbose_name': 'Bildirim',
                'verbose_name_plural': 'Bildirimler',
                'ordering': ['-created_at'],
            },
        ),
    ]