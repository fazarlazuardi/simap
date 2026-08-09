from django.urls import path

app_name = 'audit_logs'

from . import views

urlpatterns = [
    path('', views.audit_log_list, name='list'),
]
