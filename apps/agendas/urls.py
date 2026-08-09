from django.urls import path
from . import views

app_name = 'agendas'

urlpatterns = [
    path('', views.agenda_list, name='list'),
    path('create/', views.agenda_create, name='create'),
    path('events/', views.agenda_events, name='events'),
    path('<int:pk>/complete/', views.agenda_complete, name='complete'),
    path('<int:pk>/cancel/', views.agenda_cancel, name='cancel'),
    path('<int:pk>/edit/', views.agenda_edit, name='edit'),
    path('<int:pk>/delete/', views.agenda_delete, name='delete'),
    path('<int:pk>/notify/', views.agenda_notify, name='notify'),
    path('<int:pk>/generate-sppd/', views.agenda_generate_sppd, name='generate_sppd'),
    path('<int:pk>/upload-notulensi/', views.agenda_upload_notulensi, name='upload_notulensi'),
]