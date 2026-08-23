from django.urls import path
from . import views

app_name = 'internal_meetings'

urlpatterns = [
    path('', views.meeting_list, name='list'),
    path('create/', views.meeting_create, name='create'),
    path('action-plans/', views.action_plan_list, name='action_plan_list'),
    path('action-plans/print/', views.action_plan_print, name='action_plan_print'),
    path('action-plans/<int:item_id>/upload-proof/', views.action_plan_upload_proof, name='action_plan_upload_proof'),
    path('<int:pk>/', views.meeting_detail, name='detail'),
    path('<int:pk>/edit/', views.meeting_edit, name='edit'),
    path('<int:pk>/notulensi/', views.meeting_notulensi, name='notulensi'),
    path('<int:pk>/action-items/<int:item_id>/toggle/', views.toggle_action_item_status, name='toggle_action_item_status'),
    path('<int:pk>/print/', views.meeting_print_notulensi, name='print'),
    path('<int:pk>/print-notulensi/', views.meeting_print_notulensi, name='print_notulensi'),
    path('<int:pk>/notify/', views.meeting_notify, name='notify'),
    path('<int:pk>/update-attendance/', views.meeting_update_attendance, name='update_attendance'),
    path('<int:pk>/cancel/', views.meeting_cancel, name='cancel'),
    path('<int:pk>/delete/', views.meeting_delete, name='delete'),
    path('attachments/<int:attachment_id>/delete/', views.delete_notulensi_attachment, name='delete_attachment'),
]


