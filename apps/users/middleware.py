from django.core.cache import cache
from django.utils import timezone
from users.models import User

class ActiveUserMiddleware:
    """
    Middleware untuk mencatat aktivitas & status Online/Offline pengguna secara real-time.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            cache_key = f'user_last_seen_{request.user.pk}'
            # Cache status aktif presisi 60 detik (1 menit)
            cache.set(cache_key, now, 60)

            # Simpan ke Database setiap 30 detik sekali agar akurat
            last_seen_db = getattr(request.user, 'last_seen', None)
            if not last_seen_db or (now - last_seen_db).total_seconds() > 30:
                User.objects.filter(pk=request.user.pk).update(last_seen=now)

        response = self.get_response(request)
        return response
