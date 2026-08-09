from django.apps import AppConfig
import os

class SuratTugasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'surat_tugas'
    path = os.path.dirname(os.path.abspath(__file__))
