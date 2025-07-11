from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile


@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    profile, new = Profile.objects.get_or_create(user=instance)

    # Kullanıcının adı veya soyadı değiştiyse, profile da yansıt
    if profile.first_name != instance.first_name or profile.last_name != instance.last_name:
        profile.first_name = instance.first_name
        profile.last_name = instance.last_name
        profile.save()


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