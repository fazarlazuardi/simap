import logging
import re
import urllib.parse
import requests
from django.conf import settings
from django.utils import timezone
from notifications.models import Notification, WANotificationSetting

logger = logging.getLogger(__name__)

class WhatsAppService:

    @staticmethod
    def format_phone_number(phone):
        """Menyelaraskan format nomor HP menjadi format internasional WhatsApp (62xxx)."""
        if not phone:
            return None
        clean_number = re.sub(r'\D', '', str(phone))
        if clean_number.startswith('0'):
            clean_number = '62' + clean_number[1:]
        return clean_number

    @staticmethod
    def check_health():
        gateway_url = getattr(settings, 'WA_GATEWAY_URL', None)
        if not gateway_url:
            return {'status': 'not_configured', 'ready': False, 'message': 'URL Gateway tidak dikonfigurasi'}
        try:
            resp = requests.get(f"{gateway_url.rstrip('/')}/health", timeout=1.0)
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
    def send_notification(user=None, message='', phone_number=None, employee=None, category='general', title=None, force_mode=None):
        """
        Sentralisasi Pengiriman Notifikasi WhatsApp.
        Memeriksa Mode Matriks Pengaturan (Otomatis vs Manual vs Nonaktif).
        Jika Nonaktif, langsung bypass secara instan (0ms) tanpa eksekusi jaringan atau log DB.
        """
        # Cek Mode Pengiriman Matriks Pertama Kali (Fast-Path Bypass)
        mode = force_mode or WANotificationSetting.get_mode_for_category(category)
        if mode == 'disabled' or WANotificationSetting.is_disabled_for_category(category):
            logger.info(f"[WA DISABLED] Pengiriman notifikasi WA untuk kategori '{category}' dinonaktifkan.")
            return {'status': 'disabled', 'message': 'Kategori notifikasi ini dinonaktifkan di pengaturan'}

        import threading

        # Tentukan Pegawai/Penerima
        target_emp = employee
        if not target_emp and user and hasattr(user, 'employee'):
            target_emp = user.employee

        # Tentukan Nomor WA
        phone = phone_number
        if not phone and target_emp:
            phone = getattr(target_emp, 'phone_number', None) or getattr(target_emp, 'phone', None)

        phone = WhatsAppService.format_phone_number(phone)
        if not phone:
            logger.warning(f"Nomor WhatsApp tidak tersedia untuk penerima: User={user}, Employee={target_emp}")
            return {'status': 'failed', 'message': 'Nomor HP tidak valid'}

        notif_title = title or "Notifikasi WhatsApp"

        # MODE MANUAL: Buat Record Draft & Generasi Direct WA Link
        if mode == 'manual':
            notif = Notification.objects.create(
                user=user,
                employee=target_emp,
                notification_type='whatsapp',
                dispatch_mode='manual',
                category=category,
                title=notif_title,
                message=message,
                recipient_phone=phone,
                status='draft_manual'
            )
            logger.info(f"[WA MANUAL DRAFT] Draf notifikasi manual dibuat ID={notif.id} untuk {phone}")
            return {
                'status': 'manual',
                'message': 'Draf Notifikasi WA Manual Berhasil Dibuat',
                'wa_link': notif.wa_direct_link,
                'notif_id': notif.id
            }

        # MODE OTOMATIS: Kirim Async (Non-Blocking) ke Gateway API
        gateway_url = getattr(settings, 'WA_GATEWAY_URL', None)
        notif = Notification.objects.create(
            user=user,
            employee=target_emp,
            notification_type='whatsapp',
            dispatch_mode='auto',
            category=category,
            title=notif_title,
            message=message,
            recipient_phone=phone,
            status='pending'
        )

        if not gateway_url:
            notif.status = 'failed'
            notif.error_log = "WA_GATEWAY_URL tidak dikonfigurasi"
            notif.save()
            return {'status': 'failed', 'message': 'Gateway WA belum dikonfigurasi', 'wa_link': notif.wa_direct_link, 'notif_id': notif.id}

        notif_id_val = notif.id

        def _dispatch_async():
            from django.db import connections
            connections.close_all()
            try:
                payload = {'number': phone, 'message': message}
                resp = requests.post(
                    f"{gateway_url.rstrip('/')}/send-message",
                    json=payload,
                    timeout=1.5
                )
                n = Notification.objects.filter(pk=notif_id_val).first()
                if n:
                    if resp.status_code == 200 and (resp.headers.get('content-type', '').startswith('application/json') and resp.json().get('success', True)):
                        n.status = 'sent'
                        n.sent_at = timezone.now()
                    elif resp.status_code == 200:
                        n.status = 'sent'
                        n.sent_at = timezone.now()
                    else:
                        n.status = 'failed'
                        n.error_log = f"HTTP {resp.status_code}"
                    n.save(update_fields=['status', 'sent_at', 'error_log'])
            except Exception as ex:
                n = Notification.objects.filter(pk=notif_id_val).first()
                if n:
                    n.status = 'failed'
                    n.error_log = f"Gateway offline: {str(ex)}"
                    n.save(update_fields=['status', 'error_log'])
            finally:
                connections.close_all()

        try:
            from django.db import transaction
            transaction.on_commit(lambda: threading.Thread(target=_dispatch_async, daemon=True).start())
        except Exception:
            threading.Thread(target=_dispatch_async, daemon=True).start()

        return {'status': 'sent', 'message': 'Notifikasi WA dikirim di latar belakang', 'notif_id': notif.id}

    @staticmethod
    def resend_outbox(notif_id):
        """Mencoba mengirim ulang pesan WA dari outbox log."""
        try:
            notif = Notification.objects.get(pk=notif_id, notification_type='whatsapp')
            notif.retry_count += 1
            gateway_url = getattr(settings, 'WA_GATEWAY_URL', None)
            if not gateway_url:
                notif.error_log = "WA_GATEWAY_URL tidak dikonfigurasi"
                notif.save()
                return False, "Gateway URL belum dikonfigurasi"

            payload = {'number': notif.recipient_phone, 'message': notif.message}
            resp = requests.post(
                f"{gateway_url.rstrip('/')}/send-message",
                json=payload,
                timeout=1.5
            )
            if resp.status_code == 200:
                notif.status = 'sent'
                notif.sent_at = timezone.now()
                notif.error_log = None
                notif.save()
                return True, "Pesan WA berhasil dikirim ulang!"
            else:
                notif.status = 'failed'
                notif.error_log = f"Retry HTTP {resp.status_code}"
                notif.save()
                return False, f"Gagal kirim ulang (HTTP {resp.status_code})"
        except Exception as e:
            return False, str(e)


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