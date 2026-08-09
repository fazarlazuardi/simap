import logging
import re
import requests
from django.conf import settings
from django.utils import timezone
from notifications.models import Notification

logger = logging.getLogger(__name__)


class WhatsAppService:

    @staticmethod
    def format_phone_number(phone):
        """Menyelaraskan format nomor HP menjadi format internasional WhatsApp (62xxx)."""
        if not phone:
            return None
        
        # Hapus karakter non-digit
        clean_number = re.sub(r'\D', '', str(phone))

        # Konversi awalan 08xxx menjadi 628xxx
        if clean_number.startswith('0'):
            clean_number = '62' + clean_number[1:]
        
        return clean_number

    @staticmethod
    def check_health():
        gateway_url = getattr(settings, 'WA_GATEWAY_URL', None)
        if not gateway_url:
            return {'status': 'not_configured', 'ready': False, 'message': 'URL Gateway tidak dikonfigurasi'}
        try:
            resp = requests.get(f"{gateway_url.rstrip('/')}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'status': 'connected' if data.get('status') == 'connected' else 'disconnected',
                    'ready': data.get('ready', False),
                    'message': 'Terhubung' if data.get('status') == 'connected' else 'Gateway tidak siap',
                }
            return {'status': 'error', 'ready': False, 'message': f'HTTP {resp.status_code}'}
        except requests.exceptions.ConnectionError:
            return {'status': 'offline', 'ready': False, 'message': 'Gateway tidak dapat dijangkau'}
        except requests.exceptions.Timeout:
            return {'status': 'timeout', 'ready': False, 'message': 'Gateway tidak merespon'}
        except Exception as e:
            return {'status': 'error', 'ready': False, 'message': str(e)}

    @staticmethod
    def send_notification(user=None, message='', phone_number=None, employee=None, category='general', title=None):
        # Tentukan Pegawai/Penerima
        target_emp = employee
        if not target_emp and user and hasattr(user, 'employee'):
            target_emp = user.employee

        # Tentukan Nomor WA
        phone = phone_number
        if not phone and target_emp:
            phone = target_emp.phone_number

        # Format & Normalisasi Nomor HP
        phone = WhatsAppService.format_phone_number(phone)

        if not phone:
            logger.warning(f"Nomor WhatsApp tidak tersedia untuk penerima: User={user}, Employee={target_emp}")
            return False

        gateway_url = getattr(settings, 'WA_GATEWAY_URL', None)
        if not gateway_url:
            logger.warning("WA_GATEWAY_URL tidak dikonfigurasi dalam settings.py")
            return False

        # Kirim HTTP Request langsung tanpa mengantre jika offline
        try:
            payload = {'number': phone, 'message': message}
            resp = requests.post(
                f"{gateway_url.rstrip('/')}/send-message",
                json=payload,
                timeout=1.5
            )

            if resp.status_code == 200:
                res_data = resp.json() if resp.text else {}
                if res_data.get('success', True):
                    # Hanya buat record database saat benar-benar terkirim (ONLINE)
                    Notification.objects.create(
                        user=user,
                        employee=target_emp,
                        notification_type='whatsapp',
                        category=category,
                        title=title or "Notifikasi WhatsApp",
                        message=message,
                        status='sent',
                        sent_at=timezone.now()
                    )
                    return True
            return False

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # WA Gateway Offline -> LANGSUNG DISKIP (Tanpa menyimpan di database)
            logger.info(f"[SKIP WA] WA Gateway offline, notifikasi ke {phone} langsung dilewati.")
            return False
        except Exception:
            return False
            logger.warning(f"Request ke WA Gateway mengalami timeout saat mengirim ke {phone}")
            return False
        except Exception as e:
            notif.status = 'failed'
            notif.error_log = str(e)
            notif.save()
            logger.exception(f"Terjadi kesalahan sistem pada WA Gateway: {e}")
            return False


class GoogleIntegrationService:

    @staticmethod
    def sync_to_drive(archive):
        try:
            from services.integrations.google_drive import GoogleDriveService
            drive_service = GoogleDriveService()
            result = drive_service.upload_archive(archive)
            if result:
                logger.info(f"Arsip {archive.archive_number} berhasil disinkronkan ke Drive: {result.get('webViewLink')}")
            return result
        except Exception as e:
            logger.exception(f"Gagal melakukan sinkronisasi Google Drive: {e}")
            return None

    @staticmethod
    def log_to_spreadsheet(archive):
        logger.info(f"Fitur registrasi Spreadsheet belum diimplementasikan untuk arsip {archive.archive_number}")
        pass