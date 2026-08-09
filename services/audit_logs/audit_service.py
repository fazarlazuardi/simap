from django.db import models
from django.conf import settings
from audit_logs.models import AuditLog

class AuditService:
    @staticmethod
    def log_action(user, action, request=None):
        ip = None
        ua = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            ua = request.META.get('HTTP_USER_AGENT')
            
        AuditLog.objects.create(
            user=user,
            action=action,
            ip_address=ip,
            user_agent=ua
        )
