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
]
