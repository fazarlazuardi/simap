from django.urls import path
from . import views

app_name = 'internal_meetings'

urlpatterns = [
    path('', views.meeting_list, name='list'),
    path('create/', views.meeting_create, name='create'),
    path('<int:pk>/', views.meeting_detail, name='detail'),
    path('<int:pk>/edit/', views.meeting_edit, name='edit'),
    path('<int:pk>/notulensi/', views.meeting_notulensi, name='notulensi'),
    path('<int:pk>/action-items/<int:item_id>/toggle/', views.toggle_action_item_status, name='toggle_action_item_status'),
    path('<int:pk>/print/', views.meeting_print_notulensi, name='print'),
    path('<int:pk>/delete/', views.meeting_delete, name='delete'),
]

