from django.urls import path
from . import views
from . import report_views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index, name='index'),
    path('create/<int:dispo_pk>/', views.report_create, name='create'),
    path('<int:pk>/', report_views.report_detail, name='detail'),
    path('<int:pk>/edit/', views.report_edit, name='edit'),
    path('drive-backup/<int:pk>/', views.drive_backup, name='drive_backup'),
    path('drive-backup-batch/', views.drive_backup_batch, name='drive_backup_batch'),
    path('oauth/login/', views.oauth_login, name='oauth_login'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('backup-test-connection/', views.backup_test_connection, name='backup_test_connection'),
    path('backup-count-documents/', views.backup_count_documents, name='backup_count_documents'),
    path('drive-backup-monthly/', views.drive_backup_monthly, name='drive_backup_monthly'),
    path('rekap-sppd/', views.rekap_sppd_view, name='rekap_sppd'),
    path('rekap-bantuan/', views.rekap_bantuan_view, name='rekap_bantuan'),
    path('kalender-kerja/', views.calendar_work_view, name='calendar_work'),
]
