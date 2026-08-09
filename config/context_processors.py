from notifications.models import Notification
from users.models import AppConfig

def notification_context(request):
    config = AppConfig.get_config()
    context = {
        'app_config': config,
    }
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, status='unread').order_by('-created_at')
        context.update({
            'global_notifications': unread_notifications[:5],
            'global_notif_count': unread_notifications.count()
        })
    return context
