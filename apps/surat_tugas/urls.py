from django.urls import path
from . import views

app_name = 'surat_tugas' 

urlpatterns = [
    path('', views.surat_list, name='list'),
    path('create/', views.surat_create, name='create'),
    path('create/archive/<int:pk>/', views.surat_create_from_archive, name='create_from_archive'),
    path('create/<int:disposition_id>/', views.surat_create_from_disposition, name='create_from_disposition'),
    path('create-from-disposition/<int:disposition_id>/', views.surat_create_from_disposition, name='create_from_disposition_alias'),
    path('<int:pk>/', views.surat_detail, name='detail'),
    path('<int:pk>/edit/', views.surat_update, name='update'),
    path('<int:pk>/print/', views.surat_print, name='print'),
    path('<int:pk>/delete/', views.surat_delete, name='delete'),
]