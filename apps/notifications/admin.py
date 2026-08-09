from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'message', 'status', 'created_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('user__username', 'message')
    ordering = ('-created_at',)
