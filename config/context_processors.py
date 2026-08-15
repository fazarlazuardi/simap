from notifications.models import Notification
from users.models import AppConfig
from archives.models import Archive

def notification_context(request):
    config = AppConfig.get_config()
    context = {
        'app_config': config,
    }
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, status='unread').order_by('-created_at')
        
        active_pov = request.session.get('active_pov')
        is_kabid_4_active = active_pov in ['kabid_4', 'sdm'] or (not active_pov and (getattr(request.user, 'is_kabid_4', False) or getattr(request.user, 'is_waka_4', False)))
        
        unverified_count = 0
        if is_kabid_4_active or (request.user.is_superadmin and not active_pov):
            unverified_count = Archive.objects.filter(
                verified_by_kabid=False
            ).exclude(status__in=['selesai', 'ditolak']).count()

        context.update({
            'global_notifications': unread_notifications[:5],
            'global_notif_count': unread_notifications.count(),
            'is_kabid_4_active': is_kabid_4_active,
            'unverified_count': unverified_count,
        })
    return context
