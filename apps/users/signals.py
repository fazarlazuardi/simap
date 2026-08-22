from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    """
    Seketika saat akun amil logout (Keluar):
    Hapus cache aktif & set status DB menjadi Offline (0 detik delay).
    """
    if user and user.pk:
        cache.delete(f'user_last_seen_{user.pk}')
        try:
            from users.models import User
            User.objects.filter(pk=user.pk).update(last_seen=None)
        except Exception:
            pass
