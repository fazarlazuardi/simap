from django.urls import path
from . import views

app_name = 'dispositions'

urlpatterns = [
    path('', views.disposition_list, name='list'),
    path('<int:pk>/', views.disposition_detail, name='detail'),
    path('<int:archive_pk>/create/', views.disposition_create, name='create'),
    path('<int:pk>/edit/', views.disposition_edit, name='edit'),
    path('<int:pk>/waka-edit/', views.disposition_waka_edit, name='waka_edit'),
    path('<int:pk>/verify/', views.disposition_verify, name='verify'),
    path('<int:pk>/delete/', views.disposition_delete, name='delete'),
    path('<int:pk>/followup/', views.disposition_staff_followup, name='staff_followup'),
    path('print/', views.disposition_print, name='print'),
    path('batch-notify/', views.disposition_batch_notify, name='batch_notify'),
]