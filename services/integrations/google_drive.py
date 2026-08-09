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
        self.sheet_id = self._get_sheet_id_from_db()
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
        val = getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm')
        return val if val and val != 'your_folder_id_here' else '10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm'

    def _get_sheet_id_from_db(self):
        try:
            from users.models import SystemSetting
            setting = SystemSetting.objects.filter(key='GOOGLE_SHEET_ID').first()
            if setting and setting.value and setting.value != 'your_spreadsheet_id_here':
                return setting.value
        except Exception:
            pass
        return getattr(settings, 'GOOGLE_SHEET_ID', '1WX3-UvF4okkXKRuui9oiTzF6TZFgsdtSyoQR89QyiTc')

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
            scopes = [
                'https://www.googleapis.com/auth/drive.file',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            try:
                import json
                with open(creds_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)

                if 'type' in content and content['type'] == 'service_account':
                    from google.oauth2.service_account import Credentials
                    return Credentials.from_service_account_file(creds_path, scopes=scopes)
                elif 'installed' in content or 'web' in content:
                    logger.info(f"File kredensial OAuth2 Client Secret terdeteksi pada {creds_path}")
                    token_file = os.path.join(os.path.dirname(creds_path), 'token.json')
                    if os.path.exists(token_file):
                        from google.oauth2.credentials import Credentials as OAuthCredentials
                        return OAuthCredentials.from_authorized_user_file(token_file, scopes)
                    else:
                        logger.info("Informasi OAuth2 Client Secret berhasil dimuat dari credentials.json.")
            except Exception as e:
                logger.error(f"Gagal memuat kredensial dari file {creds_path}: {e}")

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
        Membuat spreadsheet Google Sheets rapi dengan Kop BAZNAS di folder 10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm.
        """
        try:
            creds = self._get_credentials()
            if not creds:
                return None, None, "Credentials/Token OAuth Google Drive tidak ditemukan."

            from googleapiclient.discovery import build
            drive = build('drive', 'v3', credentials=creds)
            sheets = build('sheets', 'v4', credentials=creds)

            target_folder = self.folder_id or '10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm'
            month_names = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            month_str = month_names[month] if 1 <= month <= 12 else str(month)
            title = f"REKAP_SIMAP_BAZNAS_{month_str}_{year}"

            # 1. Cari apakah spreadsheet rekap di folder target sudah ada
            spreadsheet_id = None
            try:
                q = f"name='{title}' and mimeType='application/vnd.google-apps.spreadsheet' and '{target_folder}' in parents and trashed=false"
                res = drive.files().list(q=q, fields='files(id, name)').execute()
                files = res.get('files', [])
                if files:
                    spreadsheet_id = files[0].get('id')
            except Exception:
                pass

            # 2. Jika belum ada, buat spreadsheet baru di folder target 10vXmaQ7IkJBUZuwEKt1ZRZabatspjEmm
            if not spreadsheet_id:
                file_metadata = {
                    'name': title,
                    'mimeType': 'application/vnd.google-apps.spreadsheet',
                    'parents': [target_folder]
                }
                created_file = drive.files().create(body=file_metadata, fields='id').execute()
                spreadsheet_id = created_file.get('id')

            # 3. Formati Kop BAZNAS & Header Tabel
            kop_header = [
                ['BADAN AMIL ZAKAT NASIONAL (BAZNAS) KABUPATEN TANGERANG'],
                [f'REKAPITULASI DOKUMEN ARSIP & MONITORING PROSES SYSTEM SIMAP - {month_str.upper()} {year}'],
                ['Jl. H. Somawinata No. 1, Kadu Agung, Tigaraksa, Kabupaten Tangerang | Website: simap.baznas.or.id'],
                ['']  # Separator
            ]

            headers = [
                'No. Agenda/Reg', 'Judul / Perihal Dokumen', 'Jenis Arsip', 'Kategori',
                'Tanggal Surat', 'Pengirim / Pemohon', 'Deskripsi / Sinopsis',
                'Status Dokumen', 'No. Disposisi', 'Penanggung Jawab',
                'Pengirim Disposisi', 'Prioritas', 'Status Disposisi',
                'Catatan / Arahan', 'Tgl Pelaksanaan', 'Selesaikan', 'Diketahui',
                'Laporkan', 'Koordinasikan', 'Tgl Agenda', 'No. SPPD',
                'No. Laporan', 'Link File SIMAP', 'Link Detail System'
            ]

            values = kop_header + [headers] + rows

            body = {
                'values': values
            }
            sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            # 4. Terapkan Formatting Kop & Header Tabel (Warna Hijau BAZNAS #00583b)
            try:
                sheet_metadata = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                first_sheet_id = sheet_metadata['sheets'][0]['properties']['sheetId']

                requests = [
                    # Merge Kop Row 1 (A1:X1)
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 1,
                                'startColumnIndex': 0, 'endColumnIndex': 24
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Merge Kop Row 2 (A2:X2)
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 1, 'endRowIndex': 2,
                                'startColumnIndex': 0, 'endColumnIndex': 24
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Merge Kop Row 3 (A3:X3)
                    {
                        'mergeCells': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 2, 'endRowIndex': 3,
                                'startColumnIndex': 0, 'endColumnIndex': 24
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    },
                    # Style Kop Headers (Hijau BAZNAS #00583b, Teks Putih, Centered)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 0, 'endRowIndex': 3,
                                'startColumnIndex': 0, 'endColumnIndex': 24
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {'red': 0.0, 'green': 0.345, 'blue': 0.231},
                                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}},
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Style Tabel Headers Row 5 (Hijau Pekat #004129, Teks Putih, Bold, Centered)
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': 5,
                                'startColumnIndex': 0, 'endColumnIndex': 25
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {'red': 0.004, 'green': 0.255, 'blue': 0.161},
                                    'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}},
                                    'horizontalAlignment': 'CENTER',
                                    'verticalAlignment': 'MIDDLE'
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
                        }
                    },
                    # Bingkai Garis Tabel Seluruh Data (Full Borders Thin Solid)
                    {
                        'updateBorders': {
                            'range': {
                                'sheetId': first_sheet_id,
                                'startRowIndex': 4, 'endRowIndex': max(5, 5 + len(rows)),
                                'startColumnIndex': 0, 'endColumnIndex': 25
                            },
                            'top': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.6, 'green': 0.6, 'blue': 0.6}},
                            'bottom': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.6, 'green': 0.6, 'blue': 0.6}},
                            'left': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.6, 'green': 0.6, 'blue': 0.6}},
                            'right': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.6, 'green': 0.6, 'blue': 0.6}},
                            'innerHorizontal': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}},
                            'innerVertical': {'style': 'SOLID', 'width': 1, 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}}
                        }
                    }
                ]

                sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': requests}
                ).execute()
            except Exception as format_err:
                logger.warning(f"Formatting Google Sheets: {format_err}")

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