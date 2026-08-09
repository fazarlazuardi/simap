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

        # 1. Backup Dokumen Arsip
        archives_to_backup = Archive.objects.filter(drive_backed_up=False)
        if not archives_to_backup.exists():
            archives_to_backup = Archive.objects.all().order_by('-created_at')[:10]

        for archive in archives_to_backup:
            if archive.file_path and hasattr(archive.file_path, 'path') and os.path.exists(archive.file_path.path):
                file_name = f"ARSIP_{archive.archive_number or archive.id}_{os.path.basename(archive.file_path.name)}"
                drive_res = gdrive.upload_file(archive.file_path.path, custom_filename=file_name)
                drive_id = drive_res.get('id') if isinstance(drive_res, dict) else (str(drive_res) if drive_res else None)
                
                if drive_id:
                    archive.drive_backed_up = True
                    archive.drive_file_id = drive_id
                    archive.save(update_fields=['drive_backed_up', 'drive_file_id'])
                    total_backed_up += 1
                    backed_up_details.append({
                        'type': 'ARSIP',
                        'title': archive.title,
                        'drive_id': drive_id
                    })
                    self.stdout.write(self.style.SUCCESS(f"[OK] Arsip '{archive.title}' berhasil diunggah ke GDrive. (ID: {drive_id})"))

        # 2. Backup Berkas Laporan Hasil
        reports_to_backup = Report.objects.filter(file__isnull=False).order_by('-created_at')[:5]
        for report in reports_to_backup:
            if report.file and hasattr(report.file, 'path') and os.path.exists(report.file.path):
                file_name = f"LAPORAN_{report.report_number}_{os.path.basename(report.file.name)}"
                drive_res = gdrive.upload_file(report.file.path, custom_filename=file_name)
                drive_id = drive_res.get('id') if isinstance(drive_res, dict) else (str(drive_res) if drive_res else None)
                if drive_id:
                    total_backed_up += 1
                    backed_up_details.append({
                        'type': 'LAPORAN',
                        'title': report.title,
                        'drive_id': drive_id
                    })
                    self.stdout.write(self.style.SUCCESS(f"[OK] Laporan '{report.title}' berhasil diunggah ke GDrive. (ID: {drive_id})"))

        # 2.5 Sinkronisasi Data Rekap ke Google Sheets Target
        try:
            now = timezone.now()
            all_archives = Archive.objects.all().order_by('-created_at')[:50]
            rows = []
            for arc in all_archives:
                rows.append([
                    arc.archive_number or 'DRAFT',
                    arc.title,
                    arc.get_archive_type_display(),
                    arc.category.name if arc.category else '-',
                    arc.letter_date.strftime('%d/%m/%Y') if arc.letter_date else '-',
                    arc.sender or '-',
                    arc.description or '-',
                    arc.activity_name,
                    arc.latest_dispo.disposition_number if arc.latest_dispo else '-',
                    arc.current_assignee_names,
                    '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-',
                    f'https://drive.google.com/file/d/{arc.drive_file_id}/view' if arc.drive_file_id else '-',
                    f'http://localhost:8000/archives/{arc.pk}/'
                ])
            sp_id, sp_url, err = gdrive.create_monthly_backup(now.month, now.year, rows)
            if sp_id:
                self.stdout.write(self.style.SUCCESS(f"[OK] Data rekap berhasil disinkronkan ke Google Sheet ({sp_url})."))
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
            self.stdout.write(self.style.SUCCESS(f"[OK] Laporan email backup berhasil dikirim ke {getattr(settings, 'BACKUP_EMAIL_RECIPIENT', 'simap.baznas@gmail.com')}."))
        else:
            self.stdout.write(self.style.WARNING("Info: Email backup terkirim atau tercatat di log (fail_silently)."))

        # Clean up dump file
        if dump_path and os.path.exists(dump_path):
            try:
                os.remove(dump_path)
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS("=== Selesai Backup SIMAP ke Google Drive & Email ==="))
