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
                f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
                f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
                f"Berikut adalah pemberitahuan rekap disposisi Pimpinan yang memerlukan tindak lanjut Anda:\n\n"
                f"• *No. Arsip:* {archive.archive_number or '—'}\n"
                f"• *Perihal:* {archive.title}\n"
                f"• *Penerima:* {penerima_names}\n"
                f"• *Prioritas:* {dispo.get_priority_display()}\n"
                f"• *Arahan Pimpinan:* {dispo.note or '—'}\n"
                f"• *Instruksi:* {instruksi}\n\n"
                f"Silakan login ke sistem SIMAP BAZNAS untuk melihat detail dan memproses dokumen tersebut.\n\n"
                f"Atas perhatian dan kerja samanya, kami ucapkan terima kasih.\n"
                f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
            )

            forwarded_emps = list(dispo.forwarded_to.all())
            user_map = {u.employee_id: u for u in User.objects.filter(employee__in=forwarded_emps)}
            for emp in forwarded_emps:
                user = user_map.get(emp.pk)
                WhatsAppService.send_notification(user=user, message=msg, employee=emp, category='disposition', title="Disposisi Pimpinan")
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
            f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
            f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
            f"Pemberitahuan bahwa Surat Tugas & SPPD Perjalanan Dinas telah resmi diterbitkan:\n\n"
            f"• *No. SPPD:* {sppd_obj.sppd_number}\n"
            f"• *Kegiatan:* {archive.title if archive else 'Perjalanan Dinas'}\n"
            f"• *Tujuan:* {sppd_obj.destination}\n"
            f"• *Tanggal Keberangkatan:* {dep_date}\n"
            f"• *Tanggal Kepulangan:* {ret_date}\n"
            f"• *Transportasi:* {sppd_obj.transportation}\n\n"
            f"Mohon untuk melaksanakan tugas dengan sebaik-baiknya serta mengunggah Laporan SPPD setelah kegiatan selesai melalui aplikasi SIMAP.\n\n"
            f"Terima kasih atas dedikasi dan kerja samanya.\n"
            f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
        )

        import threading

        def _bg_send():
            from django.db import connections
            connections.close_all()
            try:
                for emp in employees:
                    user = user_map.get(emp.pk)
                    WhatsAppService.send_notification(user=user, message=msg, employee=emp, category='sppd', title="Penugasan SPPD")
                    if user:
                        Notification.objects.create(
                            user=user,
                            notification_type='whatsapp',
                            message=f"SPPD Terbit: {sppd_obj.sppd_number}",
                            status='sent'
                        )
            except Exception:
                pass
            finally:
                connections.close_all()

        threading.Thread(target=_bg_send, daemon=True).start()
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

            should_send_h1 = (timing == 'h_minus_1' and not is_today and agenda.notification_sent_at is None)
            time_diff = (agenda.scheduled_at - now).total_seconds()
            should_send_1h = (timing == 'h_minus_1_hour' and is_today and 0 <= time_diff <= 3600 and agenda.notification_sent_at is None)

            if should_send_h1 or should_send_1h or (timing == 'instant' and agenda.notification_sent_at is None):
                timing_str = "HARI INI (1 Jam Lagi)" if should_send_1h else ("BESOK (H-1)" if should_send_h1 else "")
                
                msg = (
                    f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
                    f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
                    f"Pengingat agenda kegiatan dinas BAZNAS {timing_str}:\n\n"
                    f"• *Agenda:* {agenda.title}\n"
                    f"• *Waktu:* {agenda.scheduled_at.strftime('%d/%m/%Y jam %H:%M WIB')}\n"
                    f"• *Keterangan:* {agenda.description or '—'}\n\n"
                    f"Mohon untuk dapat bersiap dan menghadiri kegiatan tepat waktu.\n\n"
                    f"Terima kasih.\n"
                    f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
                )

                users = list(agenda.assigned_to.all())
                emp_list = list(agenda.assigned_employees.all())
                user_map = {u.employee_id: u for u in User.objects.filter(employee__in=emp_list)}

                for emp in emp_list:
                    user = user_map.get(emp.pk)
                    WhatsAppService.send_notification(user=user, message=msg, employee=emp, category='agenda', title="Pengingat Agenda")
                    sent_count += 1

                for user in users:
                    emp = getattr(user, 'employee', None)
                    if emp not in emp_list:
                        WhatsAppService.send_notification(user=user, message=msg, employee=emp, category='agenda', title="Pengingat Agenda")
                        sent_count += 1

                agenda.notification_sent_at = now
                agenda.save(update_fields=['notification_sent_at'])

        return sent_count

    @classmethod
    def notify_bidang2_for_bantuan_document(cls, archive, dispo=None):
        """
        Kirim notifikasi web dashboard otomatis ke Waka II & Kabid II secara ASYNC thread-safe.
        """
        if not archive:
            return
        
        archive_id = archive.pk
        dispo_id = dispo.pk if dispo else None

        import threading

        def _bg_notify():
            from django.db import connections
            connections.close_all()
            try:
                from archives.models import Archive
                from dispositions.models import Disposition
                from services.workflows.workflow_engine import WorkflowEngine
                from users.models import User
                from django.db.models import Q

                arc = Archive.objects.filter(pk=archive_id).first()
                dsp = Disposition.objects.filter(pk=dispo_id).first() if dispo_id else None
                if not arc:
                    return
                
                is_bantuan = WorkflowEngine.is_bantuan(arc)
                is_forwarded_to_bidang2 = False
                
                if dsp:
                    for emp in list(dsp.forwarded_to.all()) + list(dsp.waka_forwarded_to.all()):
                        dept_name = emp.dept_relation.name.lower() if emp and emp.dept_relation else ''
                        pos_name = emp.position.lower() if emp and emp.position else ''
                        if any(kw in dept_name or kw in pos_name for kw in ['pendistribusian', 'bidang 2', 'bidang ii', 'waka 2', 'kabid 2']):
                            is_forwarded_to_bidang2 = True
                            break
                
                if is_bantuan or is_forwarded_to_bidang2:
                    bidang2_users = User.objects.filter(
                        Q(username__icontains='waka2') |
                        Q(username__icontains='kabid2') |
                        Q(role='waka_2') |
                        Q(role='kabid_2') |
                        Q(employee__leadership_type='waka_2') |
                        Q(employee__dept_relation__name__icontains='pendistribusian') |
                        Q(employee__dept_relation__name__icontains='bidang 2') |
                        Q(employee__dept_relation__name__icontains='bidang ii')
                    ).distinct()
                    
                    link_target = f"/dispositions/{dsp.pk}/" if dsp else f"/archives/{arc.pk}/"
                    
                    for b_user in bidang2_users:
                        if not Notification.objects.filter(user=b_user, link_url=link_target, status='unread').exists():
                            Notification.create_system_notif(
                                user=b_user,
                                title="🤝 Disposisi Dokumen Bantuan (Bidang II)",
                                message=f"Dokumen bantuan '{arc.title}' memerlukan tindakan & tindak lanjut oleh Waka II / Kabid II.",
                                link_url=link_target,
                                category="disposition"
                            )
            except Exception:
                pass
            finally:
                connections.close_all()

        threading.Thread(target=_bg_notify, daemon=True).start()

    @classmethod
    def send_disposition_system_notifications(cls, dispo, stage='ketua', actor=None):
        """
        Mengirim notifikasi sistem (lonceng / web dashboard) ke Waka dan Kabid dari Bidang yang menerima disposisi.
        Misal: Ketua / Waka IV mendisposisikan ke Bidang II, maka notifikasi lonceng muncul di akun Waka II & Kabid II.
        Sama halnya untuk Bidang I, III, IV.
        HANYA notifikasi sistem (dashboard lonceng), BUKAN WhatsApp Gateway.
        """
        if not dispo or not dispo.pk:
            return

        dispo_id = dispo.pk

        import threading

        def _bg_notify():
            from django.db import connections
            connections.close_all()
            try:
                from dispositions.models import Disposition
                from users.models import User
                from notifications.models import Notification
                from django.db.models import Q

                d = Disposition.objects.filter(pk=dispo_id).select_related('archive', 'sender').first()
                if not d or not d.archive:
                    return

                if stage == 'waka_iv' or d.is_stage_waka:
                    target_emps = list(d.waka_forwarded_to.all())
                    sender_title = d.sender_label or "Wakil Ketua IV"
                    if not target_emps:
                        target_emps = list(d.forwarded_to.all())
                else:
                    target_emps = list(d.forwarded_to.all())
                    sender_title = d.sender_label or "Ketua BAZNAS"

                if not target_emps:
                    return

                target_bidangs = set()
                recipient_user_ids = set()

                for emp in target_emps:
                    if hasattr(emp, 'user_account') and emp.user_account:
                        recipient_user_ids.add(emp.user_account.pk)

                    pos_dept = f"{emp.position or ''} {emp.dept_relation.name if emp.dept_relation else ''} {emp.leadership_type or ''}".lower()

                    if any(k in pos_dept for k in ['1', 'i', 'pengumpulan']):
                        target_bidangs.add('1')
                    if any(k in pos_dept for k in ['2', 'ii', 'pendistribusian', 'pendayagunaan', 'bantuan']):
                        target_bidangs.add('2')
                    if any(k in pos_dept for k in ['3', 'iii', 'perencanaan', 'keuangan']):
                        target_bidangs.add('3')
                    if any(k in pos_dept for k in ['4', 'iv', 'administrasi', 'sdm', 'umum']):
                        target_bidangs.add('4')

                for b_num in target_bidangs:
                    if b_num == '1':
                        q_bidang = Q(username__icontains='waka1') | Q(username__icontains='kabid1') | Q(employee__leadership_type='waka_1') | Q(employee__dept_relation__name__icontains='pengumpulan') | Q(employee__dept_relation__name__icontains='bidang 1') | Q(employee__dept_relation__name__icontains='bidang i')
                    elif b_num == '2':
                        q_bidang = Q(username__icontains='waka2') | Q(username__icontains='kabid2') | Q(role='waka_2') | Q(role='kabid_2') | Q(employee__leadership_type='waka_2') | Q(employee__dept_relation__name__icontains='pendistribusian') | Q(employee__dept_relation__name__icontains='bidang 2') | Q(employee__dept_relation__name__icontains='bidang ii')
                    elif b_num == '3':
                        q_bidang = Q(username__icontains='waka3') | Q(username__icontains='kabid3') | Q(employee__leadership_type='waka_3') | Q(employee__dept_relation__name__icontains='perencanaan') | Q(employee__dept_relation__name__icontains='keuangan') | Q(employee__dept_relation__name__icontains='bidang 3') | Q(employee__dept_relation__name__icontains='bidang iii')
                    elif b_num == '4':
                        q_bidang = Q(username__icontains='waka4') | Q(username__icontains='kabid4') | Q(role='waka_4') | Q(role='kabid_4') | Q(employee__leadership_type='waka_4') | Q(employee__dept_relation__name__icontains='administrasi') | Q(employee__dept_relation__name__icontains='sdm') | Q(employee__dept_relation__name__icontains='bidang 4') | Q(employee__dept_relation__name__icontains='bidang iv')
                    else:
                        continue

                    users_in_bidang = User.objects.filter(q_bidang).filter(is_active_account=True)
                    for u in users_in_bidang:
                        recipient_user_ids.add(u.pk)

                actor_id = actor.pk if actor else None
                link_target = f"/dispositions/{d.pk}/"

                for uid in recipient_user_ids:
                    if actor_id and uid == actor_id:
                        continue
                    u_obj = User.objects.filter(pk=uid).first()
                    if not u_obj:
                        continue

                    if not Notification.objects.filter(user=u_obj, link_url=link_target, status='unread').exists():
                        Notification.create_system_notif(
                            user=u_obj,
                            title=f"📋 Disposisi Baru dari {sender_title}",
                            message=f"Dokumen '{d.archive.title}' didisposisikan ke Bidang Anda. Arahan: {(d.note or d.waka_note or 'Mohon ditindaklanjuti.')[:150]}",
                            link_url=link_target,
                            category="disposition"
                        )
            except Exception as ex:
                import logging
                logging.getLogger(__name__).warning(f"Error in dispo system notification: {ex}")
            finally:
                connections.close_all()

        threading.Thread(target=_bg_notify, daemon=True).start()
