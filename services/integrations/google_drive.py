import os
import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """
    SIMAP Google Drive & Google Sheets Backup Integration Service
    Menyimpan cadangan dokumen PDF/Gambar dan menyinkronkan data rekap ke Google Drive & Sheets.
    """
    def __init__(self):
        self.creds_path = self._get_creds_path_from_db()
        self.folder_id = self._get_folder_id_from_db()
        self._service = None
        self._sheets_service = None
        self._oauth_token = None

    def _get_creds_path_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_DRIVE_CREDENTIALS').first()
            if setting and setting.value:
                return setting.value
        except Exception:
            pass
        return getattr(settings, 'GOOGLE_DRIVE_CREDENTIALS', None)

    def _get_folder_id_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_DRIVE_ID').first()
            if setting and setting.value and setting.value != 'your_folder_id_here':
                return setting.value
        except Exception:
            pass
        return getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm')

    def _get_oauth_token(self):
        if self._oauth_token:
            return self._oauth_token
        try:
            from reports.models import GoogleOAuthToken
            token = GoogleOAuthToken.objects.first()
            if token and token.refresh_token:
                token.refresh_if_expired()
                self._oauth_token = token
                return token
        except Exception:
            pass
        return None

    def _get_credentials(self):
        token = self._get_oauth_token()
        if token:
            try:
                creds = token.get_credentials()
                if creds:
                    return creds
            except Exception as e:
                logger.error(f"Gagal memuat kredensial dari token DB: {e}")
        
        creds_path = self.creds_path
        if creds_path and os.path.exists(creds_path):
            try:
                from google.oauth2.service_account import Credentials
                scopes = [
                    'https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
                return Credentials.from_service_account_file(creds_path, scopes=scopes)
            except Exception as e:
                logger.error(f"Gagal memuat kredensial Service Account dari file {creds_path}: {e}")

        return None

    def _save_token_after_request(self, creds):
        """Menyimpan pembaruan token akses ke database setelah API call."""
        try:
            if hasattr(creds, 'token') and creds.token:
                from reports.models import GoogleOAuthToken
                token = GoogleOAuthToken.objects.first()
                if token:
                    token.access_token = creds.token
                    if hasattr(creds, 'expiry') and creds.expiry:
                        token.token_expiry = creds.expiry
                    token.save()
        except Exception as e:
            logger.error(f"Gagal memperbarui token OAuth di database: {e}")

    def get_service(self):
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            if creds:
                self._service = build('drive', 'v3', credentials=creds)
                return self._service
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
                # Diselaraskan ke 'v4' (bukan '4')
                self._sheets_service = build('sheets', 'v4', credentials=creds)
                return self._sheets_service
        except Exception as e:
            logger.error(f"Gagal membuat layanan Google Sheets API: {e}")
        return None

    def upload_file(self, file_path, custom_filename=None, folder_id=None):
        service = self.get_service()
        if not service:
            logger.warning("Layanan Google Drive API belum siap/terkonfigurasi.")
            return None

        if not os.path.exists(file_path):
            logger.error(f"File tidak ditemukan: {file_path}")
            return None

        target_folder = folder_id or self.folder_id
        filename = custom_filename or os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        try:
            from googleapiclient.http import MediaFileUpload
            file_metadata = {'name': filename}
            if target_folder:
                file_metadata['parents'] = [target_folder]

            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            uploaded_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()

            logger.info(f"File {filename} berhasil diunggah ke Google Drive ID: {uploaded_file.get('id')}")
            return uploaded_file
        except Exception as e:
            logger.error(f"Gagal mengunggah file ke Google Drive: {e}")
            return None

    def upload_archive(self, archive):
        # Diselaraskan dengan model Archive (file_path bukan file_attachment)
        if not archive.file_path:
            return None
        file_path = archive.file_path.path
        if not os.path.exists(file_path):
            return None
        
        ext = os.path.splitext(file_path)[1]
        custom_name = f"{archive.archive_number or archive.pk}_{archive.archive_type}{ext}"
        res = self.upload_file(file_path, custom_filename=custom_name)
        if res and res.get('id'):
            archive.drive_file_id = res.get('id')
            archive.drive_backed_up = True
            archive.save(update_fields=['drive_file_id', 'drive_backed_up'])
        return res

    def create_monthly_backup(self, month, year, rows):
        """
        Membuat spreadsheet Google Sheets baru untuk backup bulanan
        yang dipanggil oleh reports.views.drive_backup_monthly.
        """
        try:
            creds = self._get_credentials()
            if not creds:
                return None, None, "Credentials/Token OAuth Google Drive tidak ditemukan."

            from googleapiclient.discovery import build
            drive = build('drive', 'v3', credentials=creds)
            sheets = build('sheets', 'v4', credentials=creds)

            headers = [
                'No. Dokumen', 'Nama Dokumen', 'Jenis Arsip', 'Kategori',
                'Tanggal Surat', 'Pengirim/Penerima', 'Deskripsi/Sinopsis',
                'Status Dokumen', 'No. Disposisi', 'Penanggung Jawab',
                'Pengirim Disposisi', 'Prioritas', 'Status Disposisi',
                'Catatan/Arahan', 'Tgl Pelaksanaan', 'Selesaikan', 'Diketahui',
                'Laporkan', 'Koordinasikan', 'Tgl Agenda', 'No. SPPD',
                'No. Laporan', 'Link File Drive', 'Link Detail System'
            ]

            values = [headers] + rows
            month_names = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_str = month_names[month] if 1 <= month <= 12 else str(month)
            title = f"Backup_Laporan_BAZNAS_{month_str}_{year}"

            file_metadata = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.spreadsheet',
            }
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]

            created_file = drive.files().create(body=file_metadata, fields='id').execute()
            spreadsheet_id = created_file.get('id')

            body = {
                'values': values
            }
            sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Sheet1!A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

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