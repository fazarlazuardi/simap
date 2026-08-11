import os
import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def format_archive_row(index, archive):
    """
    Helper function untuk menguraikan data dari object Archive / Disposition
    menjadi 1 baris array yang berisi TEPAT 23 item data sesuai format SIMAP BAZNAS.
    """
    if isinstance(archive, list):
        if len(archive) == 23:
            # Pastikan item index 3 (Perihal) BUKAN ceklis '✓' atau '-'
            if archive[3] not in ['✓', '-', 'V', 'v']:
                archive[0] = index
                return archive

    disposition = getattr(archive, 'disposition', None) or getattr(archive, 'disposisi', None) or getattr(archive, 'latest_dispo', None)

    reg_number = getattr(archive, 'archive_number', None) or (f"REG-{archive.pk:04d}" if hasattr(archive, 'pk') else '-')
    sender = getattr(archive, 'sender', None) or getattr(archive, 'receiver', None) or getattr(archive, 'agency_origin', '-')
    subject = getattr(archive, 'title', None) or getattr(archive, 'subject', '-')
    
    received_date = getattr(archive, 'received_date', None) or getattr(archive, 'letter_date', None) or getattr(archive, 'created_at', None)
    if received_date and hasattr(received_date, 'strftime'):
        received_date_str = received_date.strftime('%d/%m/%Y')
    else:
        received_date_str = str(received_date) if received_date else '-'

    doc_type = archive.get_archive_type_display() if hasattr(archive, 'get_archive_type_display') else getattr(archive, 'archive_type', '-')
    
    category = '-'
    if hasattr(archive, 'category') and archive.category:
        category = archive.category.name if hasattr(archive.category, 'name') else str(archive.category)
    
    pj_list = '-'
    if hasattr(archive, 'current_assignee_names') and archive.current_assignee_names:
        pj_list = archive.current_assignee_names
    elif disposition:
        pj_list = getattr(disposition, 'person_in_charge', None) or getattr(disposition, 'pic', '-')

    # Status Ceklis 8 Tahapan Disposisi Vertikal (100% EMPIRIS BERDASARKAN RECORD SPPD, ST, & AUDIT LOG)
    st = getattr(archive, 'status', '')
    has_dispo = disposition is not None
    reg_no = getattr(archive, 'archive_number', '') or (f"REG-{archive.pk}" if hasattr(archive, 'pk') else '')

    dispos_list = list(archive.dispositions.all()) if hasattr(archive, 'dispositions') else []
    
    # Kumpulkan SPPD & Surat Tugas terkait dokumen ini
    sppd_purposes = []
    st_count = 0
    try:
        from django.db.models import Q
        from sppd_service.models import SPPD
        from surat_tugas.models import SuratTugas
        sts = list(SuratTugas.objects.filter(disposition__archive=archive))
        st_count = len(sts)
        sppds = list(SPPD.objects.filter(Q(disposition__archive=archive) | Q(surat_tugas__disposition__archive=archive)).distinct())
        sppd_purposes = [sp.purpose.lower() for sp in sppds if sp.purpose]
    except Exception:
        pass

    log_actions = []
    if reg_no:
        try:
            from audit_logs.models import AuditLog
            logs = AuditLog.objects.filter(action__icontains=reg_no)
            log_actions = [l.action.lower() for l in logs]
        except Exception:
            pass

    # 1. Verifikasi Kabid IV
    v_kabid = "✓" if (st in ['verifikasi_kabid', 'disposisi_pimpinan', 'terverifikasi', 'didisposisikan', 'proses', 'sudah_ditugaskan', 'menghadiri_undangan', 'dalam_survei', 'telah_disalurkan', 'selesai'] 
                     or any('verifikasi' in a or 'kabid' in a for a in log_actions)) else "-"

    # 2. Disposisi Ketua
    v_ketua = "✓" if (st in ['disposisi_pimpinan', 'terverifikasi', 'didisposisikan', 'proses', 'sudah_ditugaskan', 'menghadiri_undangan', 'dalam_survei', 'telah_disalurkan', 'selesai'] 
                     or len(dispos_list) > 0 or any('disposisi' in a for a in log_actions)) else "-"

    # 3. Disposisi Waka IV
    v_waka4 = "✓" if (st in ['terverifikasi', 'didisposisikan', 'proses', 'sudah_ditugaskan', 'menghadiri_undangan', 'dalam_survei', 'telah_disalurkan', 'selesai'] 
                     or any(getattr(d, 'waka_note', None) for d in dispos_list) or any('waka' in a for a in log_actions)) else "-"

    # 4. Proses Bidang/Unit
    v_unit = "✓" if (st in ['proses', 'sudah_ditugaskan', 'menghadiri_undangan', 'dalam_survei', 'telah_disalurkan', 'selesai'] 
                    or st_count > 0 or len(sppd_purposes) > 0 or any('proses' in a or 'tugas' in a for a in log_actions)) else "-"

    # 5. Survei: MURNI HANYA JIKA MEMILIKI SPPD/ST SURVEI, STATUS DALAM SURVEI, ATAU LOG SURVEI RIIL
    has_survei_sppd = any('survei' in p or 'mustahik' in p or 'lapangan' in p for p in sppd_purposes)
    has_survei_log = any('survei' in a or 'verifikasi lapangan' in a for a in log_actions)
    v_survey = "✓" if (st == 'dalam_survei' or has_survei_sppd or has_survei_log) else "-"

    # 6. Penyaluran: MURNI HANYA JIKA MEMILIKI SPPD/ST PENYALURAN, STATUS TELAH DISALURKAN, ATAU LOG PENYALURAN RIIL
    has_dist_sppd = any('penyaluran' in p or 'pentasyarufan' in p or 'disalurkan' in p for p in sppd_purposes)
    has_dist_log = any('penyaluran' in a or 'pentasyarufan' in a or 'disalurkan' in a for a in log_actions)
    v_dist = "✓" if (st == 'telah_disalurkan' or has_dist_sppd or has_dist_log) else "-"

    # 7. Laporan: MURNI HANYA JIKA MEMILIKI BERKAS LAPORAN HASIL (LHP / REPORT) ATAU LOG LAPORAN
    v_report = "✓" if (getattr(archive, 'latest_report', None) is not None or any('laporan' in a or 'lhp' in a for a in log_actions)) else "-"

    # 8. Selesai: Ceklis ✓ jika status akhir dokumen selesai
    v_done = "✓" if st == 'selesai' else "-"

    progress = getattr(archive, 'activity_name', None) or (archive.get_status_display() if hasattr(archive, 'get_status_display') else 'Sedang Diproses')
    
    st_obj = getattr(archive, 'latest_st', None)
    task_letter = st_obj.nomor_surat if st_obj else '-'

    sppd_obj = getattr(archive, 'latest_sppd', None)
    sppd_no = sppd_obj.sppd_number if sppd_obj else '-'
    
    agenda_date_str = '-'
    if hasattr(archive, 'latest_agenda_date') and archive.latest_agenda_date:
        agenda_date_str = archive.latest_agenda_date.strftime('%d/%m/%Y')

    report_obj = getattr(archive, 'latest_report', None)
    report_no = report_obj.report_number if report_obj else '-'

    pk_val = getattr(archive, 'pk', 1)
    file_path = getattr(archive, 'file_path', None)
    if file_path and hasattr(file_path, 'url'):
        dok_link = f'=HYPERLINK("http://localhost:8000{file_path.url}", "Buka Berkas SIMAP")'
    else:
        dok_link = '-'

    detail_link = f'=HYPERLINK("http://localhost:8000/archives/{pk_val}/", "Lihat Detail Sistem")'

    # Return Array TEPAT 23 Item Sesuai Format User
    return [
        index,              # 1. No
        reg_number,         # 2. No. Reg. Dokumen
        sender,             # 3. Pengirim / Asal Instansi
        subject,            # 4. Perihal
        received_date_str,  # 5. Tanggal Diterima
        doc_type,           # 6. Jenis Dokumen
        category,           # 7. Kategori Arsip
        pj_list,            # 8. Penanggung Jawab
        v_kabid,            # 9. Verifikasi Kabid 4
        v_ketua,            # 10. Disposisi Ketua
        v_waka4,            # 11. Disposisi Waka 4
        v_unit,             # 12. Proses Bidang
        v_survey,           # 13. Survei Lapangan
        v_dist,             # 14. Penyaluran
        v_report,           # 15. Laporan Hasil
        v_done,             # 16. Selesai & Terekap
        progress,           # 17. Progres
        task_letter,        # 18. No. Surat Tugas
        sppd_no,            # 19. No. SPPD
        agenda_date_str,    # 20. Tanggal Agenda
        report_no,          # 21. No. Laporan
        dok_link,           # 22. Link Dokumen
        detail_link         # 23. Link Detail
    ]


class GoogleDriveService:
    """
    SIMAP Google Drive & Google Sheets Backup Integration Service
    Menyimpan cadangan dokumen PDF/Gambar dan menyinkronkan data rekap ke Google Drive & Sheets.
    """
    def __init__(self):
        self.creds_path = self._get_creds_path_from_db()
        self.folder_id = self._get_folder_id_from_db()
        self.sheet_id = self._get_sheet_id_from_db()
        self._oauth_token = None
        self._drive_service = None
        self._sheets_service = None

    def _get_creds_path_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_CREDENTIALS_JSON').first()
            if setting and setting.value and os.path.exists(setting.value):
                return setting.value
        except Exception:
            pass
        default_path = os.path.join(settings.BASE_DIR, 'credentials.json')
        return default_path

    def _get_folder_id_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_DRIVE_FOLDER_ID').first()
            if setting and setting.value:
                return setting.value
        except Exception:
            pass
        return getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm')

    def _get_sheet_id_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_SHEET_ID').first()
            if setting is not None:
                return setting.value if setting.value else None
        except Exception:
            pass
        val = getattr(settings, 'GOOGLE_SHEET_ID', None)
        return val if val else None

    def _get_oauth_token(self):
        if self._oauth_token:
            return self._oauth_token

        try:
            from reports.models import GoogleOAuthToken
            token_obj = GoogleOAuthToken.objects.order_by('-updated_at').first()
            if token_obj and token_obj.refresh_token:
                creds = token_obj.get_credentials()
                if creds:
                    self._oauth_token = creds
                    return creds
        except Exception as e:
            logger.warning(f"Tidak dapat memuat OAuth token dari DB: {e}")

        return None

    def _save_token_after_request(self, creds):
        if not creds:
            return
        try:
            from reports.models import GoogleOAuthToken
            token_obj = GoogleOAuthToken.objects.order_by('-updated_at').first()
            if token_obj and getattr(creds, 'token', None) and creds.token != token_obj.access_token:
                token_obj.access_token = creds.token
                if hasattr(creds, 'expiry') and creds.expiry:
                    token_obj.token_expiry = creds.expiry
                token_obj.save()
        except Exception as e:
            logger.warning(f"Gagal memperbarui token ke DB: {e}")

    def _get_credentials(self):
        creds = self._get_oauth_token()
        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                self._save_token_after_request(creds)
                return creds
            except Exception as e:
                logger.error(f"Gagal me-refresh token OAuth Google: {e}")

        creds_file = self.creds_path
        if not os.path.exists(creds_file):
            logger.error(f"File kredensial Google OAuth tidak ditemukan di: {creds_file}")
            raise ValueError("Kredensial Google OAuth (credentials.json) tidak ditemukan. Silakan atur kredensial Google di Pengaturan Aplikasi.")

        # Cek apakah file JSON kredensial merupakan Service Account JSON
        try:
            import json
            with open(creds_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('type') == 'service_account':
                from google.oauth2.service_account import Credentials
                SCOPES = [
                    'https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
                return Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"Pemeriksaan Service Account JSON: {e}")

        # Jangan panggil flow.run_local_server() dalam konteks aplikasi web karena akan membekukan server
        raise ValueError("Akun Google OAuth belum terhubung atau otorisasi kadaluarsa. Silakan buka Pengaturan Aplikasi -> klik 'Login dengan Google' untuk menghubungkan akun Google Drive BAZNAS.")

    def get_service(self):
        if self._drive_service:
            return self._drive_service
        try:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            if creds:
                self._drive_service = build('drive', 'v3', credentials=creds)
                return self._drive_service
        except Exception as e:
            logger.error(f"Gagal membuat layanan Google Drive API: {e}")
        return None

    def get_sheets_service(self):
        if self._sheets_service:
            return self._sheets_service
        try:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            if creds:
                self._sheets_service = build('sheets', 'v4', credentials=creds)
                return self._sheets_service
        except Exception as e:
            logger.error(f"Gagal membuat layanan Google Sheets API: {e}")
        return None

    def _get_or_upload_logo_url(self, drive_service, folder_id):
        try:
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_baznas.png')
            if not os.path.exists(logo_path):
                return None

            query = f"name = 'logo_baznas.png' and '{folder_id}' in parents and trashed = false"
            results = drive_service.files().list(q=query, fields="files(id, webViewLink, webContentLink)").execute()
            files = results.get('files', [])

            if files:
                file_id = files[0]['id']
            else:
                from googleapiclient.http import MediaFileUpload
                file_metadata = {
                    'name': 'logo_baznas.png',
                    'parents': [folder_id]
                }
                media = MediaFileUpload(logo_path, mimetype='image/png', resumable=True)
                uploaded_file = drive_service.files().create(
                    body=file_metadata, media_body=media, fields='id'
                ).execute()
                file_id = uploaded_file.get('id')

                drive_service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()

            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except Exception as e:
            logger.warning(f"Gagal mengunggah logo BAZNAS ke Drive untuk formula IMAGE: {e}")
            return None

    def create_monthly_backup(self, month, year, rows):
        """
        Membuat spreadsheet Google Sheets rapi dengan Kop BAZNAS, Logo Resmi, dan Auto-Fit Column di folder target.
        Diselaraskan persis dengan format SIMAP (23 Kolom dengan 8 Header Tahapan Vertikal di Samping Penanggung Jawab).
        """
        try:
            creds = self._get_credentials()
            drive = self.get_service()
            sheets = self.get_sheets_service()

            if not drive or not sheets:
                return None, None, "Gagal mendapatkan akses ke Google Services."

            target_folder = self.folder_id
            month_names = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_str = month_names[int(month)] if 1 <= int(month) <= 12 else str(month)
            title = f"SIMAP_REKAP_DOKUMEN_BAZNAS_{month_str.upper()}_{year}"

            spreadsheet_id = self.sheet_id

            if not spreadsheet_id:
                query = f"name = '{title}' and '{target_folder}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
                results = drive.files().list(q=query, fields="files(id, webViewLink)").execute()
                files = results.get('files', [])

                if files:
                    spreadsheet_id = files[0]['id']

            if not spreadsheet_id:
                file_metadata = {
                    'name': title,
                    'mimeType': 'application/vnd.google-apps.spreadsheet',
                    'parents': [target_folder]
                }
                created_file = drive.files().create(body=file_metadata, fields='id').execute()
                spreadsheet_id = created_file.get('id')

            logo_url = self._get_or_upload_logo_url(drive, target_folder)
            logo_formula = f'=IMAGE("{logo_url}")' if logo_url else 'BAZNAS'

            kop_header = [
                [logo_formula, '', 'BADAN AMIL ZAKAT NASIONAL (BAZNAS) KABUPATEN TANGERANG'],
                ['', '', f'REKAPITULASI DOKUMEN ARSIP & MONITORING PROSES DISPOSISI SYSTEM SIMAP - {month_str.upper()} {year}'],
                ['', '', 'Gedung Islamic Center Kabupaten Tangerang, Jl. Islamic Center No.1, Citra Raya, Ciakar, Kecamatan Panongan, Kabupaten Tangerang, Banten'],
                ['']  # Separator
            ]

            # Baris 5: Header Utama (23 Kolom, I5:P5 untuk 8 Tahapan Progres Dokumen)
            header_row1 = [
                'No', 'No. Reg. Dokumen', 'Pengirim / Asal Instansi', 'Perihal', 'Tanggal Diterima',
                'Jenis Dokumen', 'Kategori Arsip', 'Penanggung Jawab',
                'Progres Dokumen', '', '', '', '', '', '', '',
                'Progres', 'No. Surat Tugas', 'No. SPPD', 'Tanggal Agenda', 'No. Laporan', 'Link Dokumen', 'Link Detail'
            ]

            # Baris 6: Sub-Header 8 Kolom Vertikal Tahapan Progres Dokumen (I6:P6)
            header_row2 = [
                '', '', '', '', '', '', '', '',
                'Verifikasi Kabid IV', 'Disposisi Ketua', 'Disposisi Waka IV', 'Proses Bidang/Unit',
                'Survei', 'Penyaluran', 'Laporan', 'Selesai',
                '', '', '', '', '', '', ''
            ]

            processed_rows = []
            for i, row in enumerate(rows, start=1):
                processed_rows.append(format_archive_row(i, row))

            values = kop_header + [header_row1, header_row2] + processed_rows

            body = {'values': values}
            try:
                # Bersihkan isi lembar kerja lama agar data yang sudah dihapus di SIMAP tidak tersisa
                try:
                    sheets.spreadsheets().values().clear(
                        spreadsheetId=spreadsheet_id,
                        range='A:Z',
                        body={}
                    ).execute()
                except Exception as clear_err:
                    logger.warning(f"Gagal membersihkan sel lama: {clear_err}")

                sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range='A1',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
            except Exception as update_err:
                if '404' in str(update_err) or 'not found' in str(update_err).lower():
                    logger.warning(f"Spreadsheet ID {spreadsheet_id} tidak ditemukan (404). Membuat spreadsheet baru...")
                    file_metadata = {
                        'name': title,
                        'mimeType': 'application/vnd.google-apps.spreadsheet',
                        'parents': [target_folder]
                    }
                    created_file = drive.files().create(body=file_metadata, fields='id').execute()
                    spreadsheet_id = created_file.get('id')
                    try:
                        from users.models import SystemSetting
                        SystemSetting.objects.update_or_create(key='GOOGLE_SHEET_ID', defaults={'value': spreadsheet_id})
                    except Exception:
                        pass
                    
                    try:
                        sheets.spreadsheets().values().clear(
                            spreadsheetId=spreadsheet_id,
                            range='A:Z',
                            body={}
                        ).execute()
                    except Exception:
                        pass

                    sheets.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range='A1',
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
                else:
                    raise update_err

            # Formatting Kop, Logo, Vertical Headers & Borders
            try:
                sheet_metadata = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                first_sheet = sheet_metadata['sheets'][0]
                first_sheet_id = first_sheet['properties']['sheetId']

                unmerge_requests = [{'unmergeCells': {'range': m}} for m in first_sheet.get('merges', [])]
                if unmerge_requests:
                    try:
                        sheets.spreadsheets().batchUpdate(
                            spreadsheetId=spreadsheet_id,
                            body={'requests': unmerge_requests}
                        ).execute()
                    except Exception:
                        pass

                # Pemetaan Warna Khusus 8 Kolom Vertikal (I6:P6 / Index Col 8-15)
                col_colors = [
                    {'bg': {'red': 0.122, 'green': 0.306, 'blue': 0.471}, 'fg': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}, # 1. Biru Tua
                    {'bg': {'red': 0.706, 'green': 0.776, 'blue': 0.906}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}, # 2. Biru Muda
                    {'bg': {'red': 0.706, 'green': 0.776, 'blue': 0.906}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}, # 3. Biru Muda
                    {'bg': {'red': 0.957, 'green': 0.694, 'blue': 0.514}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}, # 4. Oranye
                    {'bg': {'red': 1.0, 'green': 0.85, 'blue': 0.4}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},      # 5. Kuning
                    {'bg': {'red': 1.0, 'green': 0.85, 'blue': 0.4}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},      # 6. Kuning
                    {'bg': {'red': 0.663, 'green': 0.816, 'blue': 0.557}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}, # 7. Hijau
                    {'bg': {'red': 0.663, 'green': 0.816, 'blue': 0.557}, 'fg': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}  # 8. Hijau
                ]

                stage_col_styles = []
                for c_idx, color_def in enumerate(col_colors, start=8):
                    stage_col_styles.append({
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 5, 'endRowIndex': 6,
                                'startColumnIndex': c_idx, 'endColumnIndex': c_idx + 1
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': color_def['bg'],
                                    'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': color_def['fg']},
                                    'textRotation': {'angle': 90},
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat,textRotation,horizontalAlignment,verticalAlignment)'
                        }
                    })

                requests = [
                    # Merge Logo A1:B3
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 3,
                                'startColumnIndex': 0, 'endColumnIndex': 2
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Merge Kop Title C1:W1, C2:W2, C3:W3
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 1,
                                'startColumnIndex': 2, 'endColumnIndex': 23
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 1, 'endRowIndex': 2,
                                'startColumnIndex': 2, 'endColumnIndex': 23
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 2, 'endRowIndex': 3,
                                'startColumnIndex': 2, 'endColumnIndex': 23
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Style Kop Headers C1:W3 (Hijau BAZNAS #006633, Teks Putih Bold, Rata Kiri, Middle)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 3,
                                'startColumnIndex': 2, 'endColumnIndex': 23
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {'red': 0.0, 'green': 0.4, 'blue': 0.2},
                                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}},
                                    'horizontalAlignment': 'LEFT',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Style Logo Cell A1:B3 (Latar Putih)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 3,
                                'startColumnIndex': 0, 'endColumnIndex': 2
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Border sekeliling Kop (A1:W3)
                    {
                        'updateBorders': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 3,
                                'startColumnIndex': 0, 'endColumnIndex': 23
                            },
                            'top': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.3, 'blue': 0.1}},
                            'bottom': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.3, 'blue': 0.1}},
                            'left': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.3, 'blue': 0.1}},
                            'right': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.3, 'blue': 0.1}}
                        }
                    },
                    # Merge Vertikal 2 Baris untuk Kolom Utama Non-Progres (A5:H6 & Q5:W6)
                    *[
                        {
                            'mergeCells': {
                                'range': {
                                    'sheetId': first_sheet_id,
                                    'startRowIndex': 4, 'endRowIndex': 6,
                                    'startColumnIndex': c, 'endColumnIndex': c + 1
                                },
                                'mergeType': 'MERGE_ALL'
                            }
                        } for c in list(range(0, 8)) + list(range(16, 23))
                    ],
                    # Style Header Utama Non-Progres (A5:H6 & Q5:W6) - Background Kuning #FFD966, Teks Hitam Bold
                    *[
                        {
                            'repeatCell': {
                                'range': {
                                    'sheetId': first_sheet_id,
                                    'startRowIndex': 4, 'endRowIndex': 6,
                                    'startColumnIndex': c, 'endColumnIndex': c + 1
                                },
                                'cell': {
                                    'userEnteredFormat': {
                                        'backgroundColor': {'red': 1.0, 'green': 0.85, 'blue': 0.4},
                                        'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                                        'horizontalAlignment': 'CENTER',
                                        'verticalAlignment': 'MIDDLE'
                                    }
                                },
                                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
                            }
                        } for c in list(range(0, 8)) + list(range(16, 23))
                    ],
                    # Merge Horizontal untuk Header "Progres Dokumen" (I5:P5)
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': 5,
                                'startColumnIndex': 8, 'endColumnIndex': 16
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Style Header "Progres Dokumen" (I5:P5) - Background Abu-abu Terang #EFEFEF, Teks Hitam Bold
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': 5,
                                'startColumnIndex': 8, 'endColumnIndex': 16
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {'red': 0.938, 'green': 0.938, 'blue': 0.938},
                                    'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Bingkai Biru Tebal di Sekeliling "Progres Dokumen" (I5:P5)
                    {
                        'updateBorders': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': 5,
                                'startColumnIndex': 8, 'endColumnIndex': 16
                            },
                            'top': {'style': 'SOLID_MEDIUM', 'width': 2, 'color': {'red': 0.122, 'green': 0.306, 'blue': 0.471}},
                            'bottom': {'style': 'SOLID_MEDIUM', 'width': 2, 'color': {'red': 0.122, 'green': 0.306, 'blue': 0.471}},
                            'left': {'style': 'SOLID_MEDIUM', 'width': 2, 'color': {'red': 0.122, 'green': 0.306, 'blue': 0.471}},
                            'right': {'style': 'SOLID_MEDIUM', 'width': 2, 'color': {'red': 0.122, 'green': 0.306, 'blue': 0.471}}
                        }
                    },
                    # Style 8 Sub-Header Vertikal Warna-Warni
                    *stage_col_styles,
                    # Atur Tinggi Baris Header 6 (Pixel Size 120 agar teks vertikal muat rapi)
                    {
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'dimension': 'ROWS',
                                'startIndex': 5,
                                'endIndex': 6
                            },
                            'properties': {'pixelSize': 120},
                            'fields': 'pixelSize'
                        }
                    },
                    # AUTO WRAP & Middle Alignment untuk Sel Data (Baris 7 dst)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 6, 'endRowIndex': max(7, 6 + len(processed_rows)),
                                'startColumnIndex': 0, 'endColumnIndex': 23
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'wrapStrategy': 'WRAP',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
                        }
                    },
                    # Center Alignment khusus untuk Kolom Ceklis Tahapan (I-P / Col 8-15)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 6, 'endRowIndex': max(7, 6 + len(processed_rows)),
                                'startColumnIndex': 8, 'endColumnIndex': 16
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Full All Borders (Hitam Tegas & Jelas) untuk seluruh tabel (Baris 5 sd Selesai)
                    {
                        'updateBorders': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': max(6, 6 + len(processed_rows)),
                                'startColumnIndex': 0, 'endColumnIndex': 23
                            },
                            'top': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                            'bottom': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                            'left': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                            'right': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                            'innerHorizontal': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}},
                            'innerVertical': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}
                        }
                    },
                    # Atur Ukuran Lebar Kolom Cerdas & Pas (Smart Pixel Widths) A s.d W
                    *[
                        {
                            'updateDimensionProperties': {
                                'range': {
                                    'sheetId': first_sheet_id,
                                    'dimension': 'COLUMNS',
                                    'startIndex': c_idx,
                                    'endIndex': c_idx + 1
                                },
                                'properties': {'pixelSize': width},
                                'fields': 'pixelSize'
                            }
                        } for c_idx, width in enumerate([
                            45,   # 1. No (A)
                            180,  # 2. No. Reg. Dokumen (B)
                            160,  # 3. Pengirim / Asal Instansi (C) - SMART & PAS!
                            250,  # 4. Perihal (D)
                            110,  # 5. Tanggal Diterima (E)
                            110,  # 6. Jenis Dokumen (F)
                            130,  # 7. Kategori Arsip (G)
                            160,  # 8. Penanggung Jawab (H)
                            45,   # 9. Verifikasi Kabid IV (I)
                            45,   # 10. Disposisi Ketua (J)
                            45,   # 11. Disposisi Waka IV (K)
                            45,   # 12. Proses Bidang/Unit (L)
                            45,   # 13. Survei (M)
                            45,   # 14. Penyaluran (N)
                            45,   # 15. Laporan (O)
                            45,   # 16. Selesai (P)
                            160,  # 17. Progres (Q)
                            160,  # 18. No. Surat Tugas (R)
                            160,  # 19. No. SPPD (S)
                            110,  # 20. Tanggal Agenda (T)
                            160,  # 21. No. Laporan (U)
                            140,  # 22. Link Dokumen (V)
                            130   # 23. Link Detail (W)
                        ])
                    ]
                ]

                sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': requests}
                ).execute()

            except Exception as ex_fmt:
                logger.warning(f"Gagal menerapkan formatting Google Sheets: {ex_fmt}")

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            self._save_token_after_request(creds)

            return spreadsheet_id, spreadsheet_url, None

        except Exception as e:
            logger.error(f"Gagal membuat backup bulanan di Google Sheets: {e}")
            return None, None, str(e)

    def check_connection(self):
        service = self.get_service()
        if not service:
            return {
                'connected': False,
                'status': 'error',
                'message': 'Layanan Google Drive tidak terhubung. Periksa Kredensial OAuth.'
            }
        try:
            about = service.about().get(fields="user").execute()
            user_info = about.get('user', {})
            return {
                'connected': True,
                'status': 'connected',
                'message': f"Terhubung sebagai {user_info.get('displayName', 'Google User')} ({user_info.get('emailAddress', '')})"
            }
        except Exception as e:
            return {
                'connected': False,
                'status': 'error',
                'message': str(e)
            }