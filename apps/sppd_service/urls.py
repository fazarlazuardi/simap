from django.urls import path
from . import views

app_name = 'sppd_service'

urlpatterns = [
    path('', views.sppd_list, name='list'),
    path('create/<int:dispo_pk>/', views.sppd_create, name='create'),
    path('create/st/<int:surat_tugas_pk>/', views.sppd_create_with_st, name='create_with_st'),
    path('<int:pk>/', views.sppd_detail, name='detail'),
    path('<int:pk>/edit/', views.sppd_edit, name='edit'),
    path('<int:pk>/delete/', views.sppd_delete, name='delete'),
    path('<int:pk>/cancel/', views.sppd_cancel, name='cancel'),
    path('print/', views.sppd_print, name='print'),
    path('<int:pk>/complete/', views.sppd_complete, name='complete'),
]