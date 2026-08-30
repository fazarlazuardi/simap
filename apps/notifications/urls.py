from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<int:pk>/read/', views.read_and_redirect, name='read_and_redirect'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('clear-all/', views.clear_all, name='clear_all'),
    
    # WA Gateway Centralized Outbox & Matrix Control Console
    path('wa-outbox/', views.wa_outbox_list, name='wa_outbox'),
    path('wa-outbox/<int:pk>/resend/', views.resend_wa_notification, name='resend_wa'),
    path('wa-outbox/<int:pk>/delete/', views.delete_wa_notification, name='delete_wa'),

    # WA Gateway Microservice Proxy API Endpoints (Real-time Status, QR, Logs & 1-Click Control)
    path('wa-gateway/status/', views.wa_gateway_status, name='wa_gateway_status'),
    path('wa-gateway/restart/', views.wa_gateway_restart, name='wa_gateway_restart'),
    path('wa-gateway/disconnect/', views.wa_gateway_disconnect, name='wa_gateway_disconnect'),
    path('wa-gateway/logs/', views.wa_gateway_logs, name='wa_gateway_logs'),



    # Interactive Amil Direct Messaging & Chat Room
    path('chat/', views.chat_inbox, name='chat_inbox'),
    path('chat/<int:recipient_id>/', views.chat_inbox, name='chat_inbox_user'),
    path('chat/send/', views.send_direct_message, name='send_direct_message'),
    path('chat/message/<int:pk>/delete/', views.delete_direct_message, name='delete_direct_message'),
    path('chat/<int:recipient_id>/clear/', views.clear_chat_thread, name='clear_chat_thread'),
    path('chat/<int:recipient_id>/poll/', views.poll_chat_messages, name='poll_chat_messages'),
    path('chat/presence-status/', views.presence_status_json, name='presence_status'),
]
