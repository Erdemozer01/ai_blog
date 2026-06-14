from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, GeneratedArticle
from django.core.cache import cache


@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    profile, new = Profile.objects.get_or_create(user=instance)

    # Kullanıcının adı veya soyadı değiştiyse, profile da yansıt
    if profile.first_name != instance.first_name or profile.last_name != instance.last_name:
        profile.first_name = instance.first_name
        profile.last_name = instance.last_name
        profile.save()

    # --- Yeni üyeye SADECE kendi makalesini yönetme yetkisi ver ---
    # Üye admin paneline girer ama yalnızca "Makale" modülünü görür ve
    # (admin.py'deki yetki kuralları sayesinde) sadece kendi makalesini düzenler.
    if created and not instance.is_superuser:
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        try:
            # Makale izinleri
            ct_article = ContentType.objects.get(app_label='blog', model='generatedarticle')
            perms = list(Permission.objects.filter(
                content_type=ct_article,
                codename__in=['add_generatedarticle', 'change_generatedarticle',
                              'delete_generatedarticle', 'view_generatedarticle']))
            # Profil izinleri (makale üretimi için Ad/Soyad doldurması gerekiyor)
            ct_profile = ContentType.objects.get(app_label='blog', model='profile')
            perms += list(Permission.objects.filter(
                content_type=ct_profile,
                codename__in=['change_profile', 'view_profile']))
            # Admin paneline girebilmesi için staff yap
            if not instance.is_staff:
                instance.is_staff = True
                post_save.disconnect(handle_user_save, sender=User)
                instance.save(update_fields=['is_staff'])
                post_save.connect(handle_user_save, sender=User)
            instance.user_permissions.add(*perms)
        except ContentType.DoesNotExist:
            pass


@receiver(post_save, sender=Profile)
def update_user_from_profile(sender, instance, **kwargs):
    """Profile kaydedildiğinde, User'ı günceller."""
    user = instance.user

    changed = False
    if user.email != instance.email:
        user.email = instance.email
        changed = True
    if user.first_name != instance.first_name:
        user.first_name = instance.first_name
        changed = True
    if user.last_name != instance.last_name:
        user.last_name = instance.last_name
        changed = True

    if changed:
        # Sonsuz döngüyü önle
        post_save.disconnect(handle_user_save, sender=User)
        user.save(update_fields=['email', 'first_name', 'last_name'])
        post_save.connect(handle_user_save, sender=User)



@receiver([post_save, post_delete], sender=GeneratedArticle)
def invalidate_homepage_stats_cache(sender, instance, **kwargs):
    """
    GeneratedArticle modeli kaydedildiğinde veya silindiğinde
    anasayfa istatistikleri cache'ini temizler.
    Özellikle yeni bir makale 'tamamlandi' durumuna geçtiğinde önemlidir.
    """
    print("Signal received: Invalidating 'homepage_stats' cache...")
    cache.delete('homepage_stats')