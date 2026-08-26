from django.urls import path
from . import views

app_name = 'archives'

urlpatterns = [
    path('', views.archive_list, name='list'),
    path('upload/', views.archive_upload, name='upload'),
    path('batch-verify/', views.batch_verify_view, name='batch_verify'),
    path('<int:pk>/', views.archive_detail, name='detail'),
    path('<int:pk>/quick-detail/', views.archive_quick_detail, name='quick_detail'),
    path('<int:pk>/receipt/', views.archive_receipt, name='receipt'),
    path('<int:pk>/edit/', views.archive_edit, name='edit'),
    path('<int:pk>/verify/', views.archive_verify, name='verify'),
    path('<int:pk>/forward-to-ketua/', views.forward_to_ketua, name='forward_to_ketua'),
    path('<int:pk>/reject/', views.archive_reject, name='reject'),
    path('<int:pk>/print-disposition/', views.archive_print_disposition, name='print_disposition'),
    path('<int:pk>/create-surat-tugas/', views.create_surat_tugas_view, name='create_surat_tugas'),
    path('<int:pk>/create-sppd/', views.create_sppd_view, name='create_sppd'),
    path('<int:pk>/upload-report/', views.upload_report_view, name='upload_report'),
    path('track/<int:pk>/', views.archive_public_track, name='public_track'),
    path('scan-document-ocr/', views.scan_document_ocr, name='scan_document_ocr'),
    path('reset-all-documents/', views.reset_all_documents, name='reset_all_documents'),
    path('backup-gdrive-email/', views.trigger_backup_gdrive_email, name='backup_gdrive_email'),
]