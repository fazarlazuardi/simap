from django.apps import AppConfig
import os

class ArchivesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'archives'

    def ready(self):
        try:
            from archives.models import Category
            if Category.objects.count() == 0:
                bantuan_cats = [
                    "Bantuan Rutilahu",
                    "Bantuan Kesehatan",
                    "Bantuan Gharimin",
                    "Bantuan Pendidikan",
                    "Pembangunan Peribadatan",
                    "Bantuan Meubelair",
                    "Bantuan UMKM",
                    "Bantuan Musafir",
                    "Bantuan Muallaf",
                    "Santunan Sembako",
                    "Bantuan Lainnya",
                ]
                umum_cats = [
                    "Audiensi",
                    "Undangan",
                    "Kerjasama",
                    "Permohonan Umum",
                    "Laporan UPZ",
                    "Dokumen Internal",
                ]
                for name in bantuan_cats + umum_cats:
                    Category.objects.get_or_create(name=name)
        except Exception:
            pass
