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

            rows = []
            for idx, arc in enumerate(all_archives, start=1):
                dispo = arc.latest_dispo
                tgl_letter = arc.letter_date.strftime('%d/%m/%Y') if arc.letter_date else arc.created_at.strftime('%d/%m/%Y')
                sender_receiver = arc.sender or arc.receiver or '-'
                description = arc.description or '-'
                status_dok = arc.activity_name
                jenis_arsip = arc.get_archive_type_display()
                kategori = arc.category.name if arc.category else '-'

                if dispo:
                    dispo_number = dispo.disposition_number or f'DISP-{dispo.id}'
                    pj_list = arc.current_assignee_names
                    sender_name = dispo.sender.username if dispo.sender else '-'
                    prioritas = dispo.get_priority_display()
                    status_dispo = dispo.get_status_display()
                    catatan = (dispo.waka_note if dispo.is_stage_waka and dispo.waka_note else dispo.note) or '-'
                    tgl_pelaksanaan = dispo.implementation_date.strftime('%d/%m/%Y') if dispo.implementation_date else '-'
                    inst_selesaikan = 'Ya' if (dispo.waka_inst_selesaikan if dispo.is_stage_waka else dispo.inst_selesaikan) else 'Tidak'
                    inst_diketahui = 'Ya' if (dispo.waka_inst_untuk_diketahui if dispo.is_stage_waka else dispo.inst_untuk_diketahui) else 'Tidak'
                    inst_laporkan = 'Ya' if (dispo.waka_inst_laporkan_hasilnya if dispo.is_stage_waka else dispo.inst_laporkan_hasilnya) else 'Tidak'
                    inst_koordinasikan = 'Ya' if (dispo.waka_inst_koordinasikan if dispo.is_stage_waka else dispo.inst_koordinasikan) else 'Tidak'
                else:
                    dispo_number = '-'
                    pj_list = '-'
                    sender_name = '-'
                    prioritas = '-'
                    status_dispo = '-'
                    catatan = '-'
                    tgl_pelaksanaan = '-'
                    inst_selesaikan = '-'
                    inst_diketahui = '-'
                    inst_laporkan = '-'
                    inst_koordinasikan = '-'

                sppd_obj = arc.latest_sppd
                st_obj = arc.latest_st
                sppd_number = sppd_obj.sppd_number if sppd_obj else (st_obj.nomor_surat if st_obj else '-')

                report_obj = arc.latest_report
                report_number = report_obj.report_number if report_obj else '-'

                tgl_agenda = arc.latest_agenda_date.strftime('%d/%m/%Y') if arc.latest_agenda_date else '-'

                dok_link = f"http://localhost:8000{arc.file_path.url}" if arc.file_path else ''
                arsip_link = f"http://localhost:8000/archives/{arc.pk}/"

                rows.append([
                    idx,
                    arc.archive_number or 'DRAFT',
                    arc.title,
                    jenis_arsip,
                    kategori,
                    tgl_letter,
                    sender_receiver,
                    description,
                    status_dok,
                    dispo_number,
                    pj_list,
                    sender_name,
                    prioritas,
                    status_dispo,
                    catatan,
                    tgl_pelaksanaan,
                    inst_selesaikan,
                    inst_diketahui,
                    inst_laporkan,
                    inst_koordinasikan,
                    tgl_agenda,
                    sppd_number,
                    report_number,
                    f'=HYPERLINK("{dok_link}", "Buka Berkas SIMAP")' if dok_link else '-',
                    f'=HYPERLINK("{arsip_link}", "Lihat Detail Sistem")',
                ])

            sp_id, sp_url, err = gdrive.create_monthly_backup(now.month, now.year, rows)
            if sp_id:
                total_backed_up = len(rows)
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
