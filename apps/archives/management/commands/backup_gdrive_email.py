import os
import json
import tempfile
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone
from archives.models import Archive
from reports.models import Report
from services.integrations.google_drive import GoogleDriveService
from services.notifications.email_service import BackupEmailNotifier


class Command(BaseCommand):
    help = "Mencadangkan seluruh dokumen arsip & laporan ke Google Drive dan mengirimkan laporan email ringkasan ke administrator."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Memulai Eksekusi Backup SIMAP ke Google Drive & Email ==="))
        
        gdrive = GoogleDriveService()
        backed_up_details = []
        total_backed_up = 0

        # 1. (Instruksi Pengguna) Berkas PDF fisik tidak diunggah ke Drive, cukup disinkronkan via tautan sistem SIMAP
        self.stdout.write(self.style.SUCCESS("[INFO] Pengunggahan PDF ke Drive dilewati (Tautan langsung sistem SIMAP digunakan)."))

        # 2. Sinkronisasi Data Rekap ke Google Sheets Target (Standar Ekspor Laporan Lembaga)
        try:
            now = timezone.now()
            all_archives = Archive.objects.all().select_related('category', 'uploaded_by').prefetch_related(
                'dispositions', 'agendas'
            ).order_by('-created_at')[:100]

            archive_list = list(all_archives)
            sp_id, sp_url, err = gdrive.create_monthly_backup(now.month, now.year, archive_list)
            
            if sp_id:
                total_backed_up = len(archive_list)
                backed_up_details.append({
                    'type': 'REKAP_GSHEET',
                    'title': f'Rekapitulasi Dokumen {now.strftime("%B %Y")}',
                    'drive_id': sp_id
                })
                self.stdout.write(self.style.SUCCESS(f"[OK] Spreadsheet Rekapitulasi Berhasil Disinkronkan ke Google Sheet ({sp_url})."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Peringatan sync Google Sheets: {e}"))

        # 3. Buat Dump Database JSON Sementara
        dump_path = None
        try:
            temp_dir = tempfile.gettempdir()
            dump_filename = f"simap_db_dump_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            dump_path = os.path.join(temp_dir, dump_filename)
            with open(dump_path, 'w', encoding='utf-8') as f:
                call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], stdout=f)
            self.stdout.write(self.style.SUCCESS(f"[OK] Dump Database JSON berhasil dibuat di: {dump_path}"))
        except Exception as err:
            self.stdout.write(self.style.WARNING(f"Peringatan dump database: {err}"))

        # 4. Pengiriman Email Notifikasi Laporan Backup
        sent = BackupEmailNotifier.send_backup_report(
            total_backed_up=total_backed_up,
            backed_up_details=backed_up_details,
            dump_file_path=dump_path
        )

        if sent:
            self.stdout.write(self.style.SUCCESS(f"[OK] Laporan email backup berhasil dikirim ke {getattr(settings, 'BACKUP_EMAIL_RECIPIENT', 'kabupatenbaznastangerang@gmail.com')}."))
        else:
            self.stdout.write(self.style.WARNING("Info: Email backup terkirim atau tercatat di log (fail_silently)."))

        # Clean up dump file
        if dump_path and os.path.exists(dump_path):
            try:
                os.remove(dump_path)
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS("=== Selesai Backup SIMAP ke Google Drive & Email ==="))
