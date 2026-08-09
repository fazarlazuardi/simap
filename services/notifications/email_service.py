import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

class PimpinanEmailNotifier:
    """
    Layanan Notifikasi Email Resmi Pimpinan SIMAP & BAZNAS
    Mengirimkan email alert ke Ketua, Para Waka, dan Kabid saat ada disposisi baru.
    """

    @classmethod
    def send_disposition_alert(cls, disposition):
        if not disposition or not disposition.archive:
            return False

        archive = disposition.archive
        is_bantuan = 'BANTUAN MUSTAHIK' if archive.category and 'bantuan' in archive.category.name.lower() else 'SURAT / PROPOSAL UMUM'
        
        subject = f"[DISPOSISI PIMPINAN] {archive.title or archive.number or 'Dokumen Masuk Baru'}"
        
        from users.models import User
        pimpinan_emails = list(User.objects.filter(role__in=['ketua', 'waka_1', 'waka_2', 'waka_3', 'waka_4', 'kabid'], is_active=True).values_list('email', flat=True))
        
        recipient_list = [e for e in pimpinan_emails if e and '@' in e]
        if not recipient_list:
            recipient_list = ['pimpinan@baznas-kabtangerang.or.id']

        message_plain = f"""
🏛️ BAZNAS KABUPATEN TANGERANG - SISTEM SIMAP
==================================================
Yth. Pimpinan BAZNAS Kabupaten Tangerang,

Terdapat dokumen baru yang membutuhkan petunjuk & disposisi Anda.

📌 RINCIAN DOKUMEN:
• No. Agenda/Reg  : {archive.number or '-'}
• Sifat Dokumen   : [{is_bantuan}]
• Jenis Berkas    : {archive.get_archive_type_display()}
• Pengirim/Pemohon: {archive.sender_receiver or '-'}
• Perihal         : {archive.title or '-'}

💬 CATATAN VERIFIKASI KABID:
"{archive.description or 'Berkas telah diverifikasi dan siap didisposisikan.'}"

🔗 AKSES SISTEM SIMAP:
http://127.0.0.1:8000/archives/{archive.id}/

--------------------------------------------------
Email otomatis dari SIMAP BAZNAS Kabupaten Tangerang.
"""

        try:
            send_mail(
                subject=subject,
                message=message_plain,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'simap@baznas-kabtangerang.or.id'),
                recipient_list=recipient_list,
                fail_silently=True
            )
            logger.info(f"[EMAIL-ALERT] Success sending disposition alert for Archive ID {archive.id}")
            return True
        except Exception as e:
            logger.error(f"[EMAIL-ALERT] Failed sending email: {e}")
            return False
