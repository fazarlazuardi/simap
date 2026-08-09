from django.utils import timezone
from datetime import timedelta
from dispositions.models import Disposition
from sppd_service.models import SPPD
from agendas.models import Agenda
from notifications.models import Notification
from services.integrations.gateway_service import WhatsAppService
from users.models import User

class NotificationService:
    """
    SIMAP Smart Notification Manager
    - Disposisi: Batch notification minimal 10 dokumen (pilihan tombol) untuk cegah spam.
    - Surat Tugas & SPPD: Notifikasi Otomatis Langsung.
    - Agenda Kerja: Notifikasi H-1 / H-3 dan Pas Hari H.
    """

    BATCH_THRESHOLD = 10

    @classmethod
    def get_pending_disposition_count(cls) -> int:
        """
        Menghitung disposisi terverifikasi/terisi yang belum dikirim notifikasi batch.
        """
        return Disposition.objects.filter(status__in=['terisi', 'terverifikasi']).count()

    @classmethod
    def is_batch_ready(cls) -> bool:
        """
        Apakah antrian disposisi sudah mencapai minimal 10 untuk tombol batch.
        """
        return cls.get_pending_disposition_count() >= cls.BATCH_THRESHOLD

    @classmethod
    def send_batch_disposition_notifications(cls, sender_user) -> dict:
        """
        Mengirimkan notifikasi batch ke seluruh penerima disposisi.
        """
        pending_dispos = Disposition.objects.filter(status='terverifikasi').prefetch_related('forwarded_to', 'archive')
        count = 0

        for dispo in pending_dispos:
            if not hasattr(dispo, 'archive') or not dispo.archive:
                continue
            archive = dispo.archive

            inst_list = []
            if dispo.inst_selesaikan: inst_list.append("✅ Selesaikan / Jawab")
            if dispo.inst_untuk_diketahui: inst_list.append("📋 Untuk diketahui / simpan")
            if dispo.inst_laporkan_hasilnya: inst_list.append("📊 Laporkan hasilnya")
            if dispo.inst_koordinasikan: inst_list.append("🤝 Koordinasikan")
            instruksi = "\n".join(inst_list) if inst_list else "—"

            penerima_names = ', '.join(emp.full_name for emp in dispo.forwarded_to.all()) or "—"
            
            msg = (
                f"📄 *REKAP DISPOSISI PIMPIMAN BAZNAS*\n\n"
                f"*No. Arsip:* {archive.archive_number or '—'}\n"
                f"*Perihal:* {archive.title}\n"
                f"*Penerima:* {penerima_names}\n"
                f"*Prioritas:* {dispo.get_priority_display().upper()}\n"
                f"*Arahan:* {dispo.note or '—'}\n\n"
                f"*Instruksi:*\n{instruksi}\n\n"
                f"Silakan login ke SIMAP BAZNAS untuk menindaklanjuti."
            )

            forwarded_emps = list(dispo.forwarded_to.all())
            user_map = {u.employee_id: u for u in User.objects.filter(employee__in=forwarded_emps)}
            for emp in forwarded_emps:
                user = user_map.get(emp.pk)
                WhatsAppService.send_notification(user=user, message=msg, employee=emp)
                Notification.objects.create(
                    user=user if user else sender_user,
                    notification_type='whatsapp',
                    message=f"Batch Disposisi: {archive.title}",
                    status='sent'
                )
                count += 1

        return {'status': 'success', 'sent_count': count}

    @classmethod
    def send_sppd_notification_auto_by_id(cls, sppd_id: int) -> bool:
        """
        Thread-safe background notification handler for SPPD.
        """
        from django.db import connections
        connections.close_all()
        try:
            sppd_obj = SPPD.objects.filter(pk=sppd_id).first()
            if not sppd_obj:
                return False
            return cls.send_sppd_notification_auto(sppd_obj)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Error in async SPPD notification: %s", e)
            return False
        finally:
            connections.close_all()

    @classmethod
    def send_sppd_notification_auto(cls, sppd_obj) -> bool:
        """
        Pengiriman Notifikasi WhatsApp Otomatis untuk SPPD & Surat Tugas.
        """

        if not sppd_obj:
            return False

        dispo = sppd_obj.disposition
        archive = dispo.archive if dispo else None

        employees = list(sppd_obj.assigned_employees.all())
        user_map = {u.employee_id: u for u in User.objects.filter(employee__in=employees)}

        dep_date = sppd_obj.departure_date.strftime('%d/%m/%Y') if hasattr(sppd_obj.departure_date, 'strftime') else (str(sppd_obj.departure_date) if sppd_obj.departure_date else "—")
        ret_date = sppd_obj.return_date.strftime('%d/%m/%Y') if hasattr(sppd_obj.return_date, 'strftime') else (str(sppd_obj.return_date) if sppd_obj.return_date else "—")

        msg = (
            f"🚗 *SURAT TUGAS & SPPD TERBIT*\n\n"
            f"*No. SPPD:* {sppd_obj.sppd_number}\n"
            f"*Kegiatan:* {archive.title if archive else 'Perjalanan Dinas'}\n"
            f"*Tujuan:* {sppd_obj.destination}\n"
            f"*Tgl Berangkat:* {dep_date}\n"
            f"*Tgl Kembali:* {ret_date}\n"
            f"*Transportasi:* {sppd_obj.transportation}\n\n"
            f"Harap melaksanakan tugas dengan penuh tanggung jawab dan mengunggah Laporan SPPD setelah selesai."
        )


        try:
            for emp in employees:
                user = user_map.get(emp.pk)
                WhatsAppService.send_notification(user=user, message=msg, employee=emp)
                if user:
                    Notification.objects.create(
                        user=user,
                        notification_type='whatsapp',
                        message=f"SPPD Terbit: {sppd_obj.sppd_number}",
                        status='sent'
                    )
        except Exception:
            pass

        return True


    @classmethod
    def process_agenda_reminders(cls) -> int:
        """
        Memproses Notifikasi Reminder Agenda berdasarkan wa_notification_timing (Langsung, H-1, Hari H-1 Jam).
        """
        now = timezone.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        agendas = Agenda.objects.filter(
            scheduled_at__date__in=[today, tomorrow],
            is_completed=False,
            status='terjadwal'
        ).prefetch_related('assigned_to', 'assigned_employees')

        sent_count = 0
        for agenda in agendas:
            agenda_date = agenda.scheduled_at.date()
            is_today = (agenda_date == today)
            timing = getattr(agenda, 'wa_notification_timing', 'instant')

            # H-1 Reminder Condition
            should_send_h1 = (timing == 'h_minus_1' and not is_today and agenda.notification_sent_at is None)

            # Hari H (1 Jam Sebelum) Reminder Condition
            time_diff = (agenda.scheduled_at - now).total_seconds()
            should_send_1h = (timing == 'h_minus_1_hour' and is_today and 0 <= time_diff <= 3600 and agenda.notification_sent_at is None)

            if should_send_h1 or should_send_1h or (timing == 'instant' and agenda.notification_sent_at is None):
                prefix = "🔔 *REMINDER AGENDA HARI INI (1 Jam Lagi)*" if should_send_1h else ("⏰ *REMINDER AGENDA BESOK (H-1)*" if should_send_h1 else "📅 *REMINDER AGENDA KERJA*")
                
                msg = (
                    f"{prefix}\n\n"
                    f"*Agenda:* {agenda.title}\n"
                    f"*Waktu:* {agenda.scheduled_at.strftime('%d/%m/%Y jam %H:%M WIB')}\n"
                    f"*Keterangan:* {agenda.description or '—'}\n\n"
                    f"Mohon bersiap dan hadir tepat waktu."
                )

                users = list(agenda.assigned_to.all())
                emp_list = list(agenda.assigned_employees.all())
                user_map = {u.employee_id: u for u in User.objects.filter(employee__in=emp_list)}

                for emp in emp_list:
                    user = user_map.get(emp.pk)
                    WhatsAppService.send_notification(user=user, message=msg, employee=emp)
                    sent_count += 1

                for user in users:
                    emp = getattr(user, 'employee', None)
                    if emp not in emp_list:
                        WhatsAppService.send_notification(user=user, message=msg, employee=emp)
                        sent_count += 1

                agenda.notification_sent_at = now
                agenda.save(update_fields=['notification_sent_at'])

        return sent_count

