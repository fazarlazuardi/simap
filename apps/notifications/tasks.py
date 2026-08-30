import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.apps import apps
from config.celery import app


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    autoretry_for=(requests.RequestException, ConnectionError)
)
def task_send_wa_notification(self, recipient_phone, message_text, outbox_id=None):
    """
    Shared Celery task for sending WhatsApp notification via WA Gateway microservice (http://localhost:3000/send-message).
    Logs HTTP responses and updates outbox Notification status in database if outbox_id is provided.
    """
    if not recipient_phone:
        return {'status': 'skipped', 'reason': 'no_phone'}

    gateway_url = getattr(settings, 'WA_GATEWAY_URL', '') or 'http://localhost:3000'
    endpoint = gateway_url.rstrip('/') + '/send-message'

    payload = {
        'to': recipient_phone,
        'number': recipient_phone,
        'message': message_text,
    }

    Notification = apps.get_model('notifications', 'Notification')
    notif_obj = None
    if outbox_id:
        notif_obj = Notification.objects.filter(pk=outbox_id).first()

    try:
        resp = requests.post(endpoint, json=payload, timeout=5.0)
        if resp.status_code == 200:
            if notif_obj:
                notif_obj.status = 'sent'
                notif_obj.sent_at = timezone.now()
                notif_obj.error_log = None
                notif_obj.save(update_fields=['status', 'sent_at', 'error_log'])
            return {'status': 'sent', 'recipient': recipient_phone, 'http_code': resp.status_code}
        else:
            err_msg = f"HTTP Error {resp.status_code}: {resp.text[:200]}"
            if notif_obj:
                notif_obj.status = 'failed'
                notif_obj.retry_count += 1
                notif_obj.error_log = err_msg
                notif_obj.save(update_fields=['status', 'retry_count', 'error_log'])
            return {'status': 'failed', 'code': resp.status_code, 'error': err_msg}

    except (requests.RequestException, ConnectionError) as exc:
        err_msg = f"WA Gateway Connection Error: {str(exc)}"
        if notif_obj:
            notif_obj.status = 'failed'
            notif_obj.retry_count += 1
            notif_obj.error_log = err_msg
            notif_obj.save(update_fields=['status', 'retry_count', 'error_log'])
        raise exc


@app.task(bind=True)
def send_wa_message(self, to_number, message, metadata=None):
    """Legacy wrapper task for sending WhatsApp message."""
    return task_send_wa_notification(to_number, message, outbox_id=(metadata or {}).get('outbox_id'))


@shared_task(bind=True)
def task_trigger_disposisi_notifications(self, disposisi_id):
    """
    Celery task to handle Disposisi notification triggers asynchronously.
    """
    Disposition = apps.get_model('dispositions', 'Disposition')
    Notification = apps.get_model('notifications', 'Notification')
    WANotificationSetting = apps.get_model('notifications', 'WANotificationSetting')

    dispo = Disposition.objects.filter(pk=disposisi_id).select_related('archive', 'sender').first()
    if not dispo or not dispo.archive:
        return {'status': 'not_found'}

    if WANotificationSetting.is_disabled_for_category('disposition'):
        return {'status': 'disabled'}

    archive = dispo.archive
    stage = dispo.disposition_stage or 'ketua'
    
    if stage == 'waka_iv' or dispo.is_stage_waka:
        target_emps = list(dispo.waka_forwarded_to.all())
        sender_label = dispo.sender_label or "Wakil Ketua IV"
        if not target_emps:
            target_emps = list(dispo.forwarded_to.all())
    else:
        target_emps = list(dispo.forwarded_to.all())
        sender_label = dispo.sender_label or "Ketua BAZNAS"

    if not target_emps:
        return {'status': 'no_recipients'}

    inst_list = []
    if dispo.inst_selesaikan: inst_list.append("✅ Selesaikan / Jawab")
    if dispo.inst_untuk_diketahui: inst_list.append("📋 Untuk diketahui / simpan")
    if dispo.inst_laporkan_hasilnya: inst_list.append("📊 Laporkan hasilnya")
    if dispo.inst_koordinasikan: inst_list.append("🤝 Koordinasikan")
    instruksi = "\n".join(inst_list) if inst_list else "—"

    penerima_names = ', '.join(e.full_name for e in target_emps)

    msg = (
        f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
        f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
        f"Pemberitahuan disposisi baru dari Pimpinan BAZNAS ({sender_label}):\n\n"
        f"• *No. Disposisi:* {dispo.disposition_number or '—'}\n"
        f"• *Perihal:* {archive.title}\n"
        f"• *Penerima:* {penerima_names}\n"
        f"• *Arahan:* {(dispo.waka_note if stage == 'waka_iv' else dispo.note) or '—'}\n"
        f"• *Instruksi:* {instruksi}\n\n"
        f"Silakan login ke sistem SIMAP BAZNAS untuk menindaklanjuti arahan Pimpinan.\n\n"
        f"Terima kasih.\n"
        f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
    )

    sent_count = 0
    for emp in target_emps:
        phone = emp.phone
        if phone:
            user_acc = getattr(emp, 'user_account', None)
            notif = Notification.objects.create(
                user=user_acc,
                employee=emp,
                notification_type='whatsapp',
                category='disposition',
                title=f"Disposisi {sender_label}",
                message=msg,
                recipient_phone=phone,
                link_url=f"/dispositions/{dispo.pk}/",
                status='pending'
            )
            task_send_wa_notification.delay(phone, msg, outbox_id=notif.pk)
            sent_count += 1

    return {'status': 'dispatched', 'count': sent_count}


@shared_task(bind=True)
def task_trigger_surat_tugas_notifications(self, surat_tugas_id):
    """
    Celery task to handle Surat Tugas notification triggers asynchronously.
    """
    SuratTugas = apps.get_model('surat_tugas', 'SuratTugas')
    Notification = apps.get_model('notifications', 'Notification')
    WANotificationSetting = apps.get_model('notifications', 'WANotificationSetting')

    st = SuratTugas.objects.filter(pk=surat_tugas_id).prefetch_related('pegawai_ditugaskan').first()
    if not st:
        return {'status': 'not_found'}

    if WANotificationSetting.is_disabled_for_category('sppd'):
        return {'status': 'disabled'}

    tgl_mulai = st.tanggal_mulai.strftime('%d/%m/%Y') if st.tanggal_mulai else '—'
    tgl_selesai = st.tanggal_selesai.strftime('%d/%m/%Y') if st.tanggal_selesai else tgl_mulai
    tgl_str = tgl_mulai if tgl_mulai == tgl_selesai else f"{tgl_mulai} s/d {tgl_selesai}"

    msg = (
        f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
        f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
        f"Pemberitahuan Penugasan Surat Tugas Resmi:\n\n"
        f"• *No. Surat:* {st.nomor_surat or '—'}\n"
        f"• *Tentang:* {st.tentang or '—'}\n"
        f"• *Lokasi Tujuan:* {st.lokasi_tujuan or '—'}\n"
        f"• *Tanggal:* {tgl_str}\n\n"
        f"Mohon untuk melaksanakan tugas dengan sebaik-baiknya.\n\n"
        f"Terima kasih atas dedikasi dan kerja samanya.\n"
        f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
    )

    employees = list(st.pegawai_ditugaskan.all())
    sent_count = 0
    for emp in employees:
        phone = emp.phone
        if phone:
            user_acc = getattr(emp, 'user_account', None)
            notif = Notification.objects.create(
                user=user_acc,
                employee=emp,
                notification_type='whatsapp',
                category='sppd',
                title="Penugasan Surat Tugas",
                message=msg,
                recipient_phone=phone,
                link_url=f"/surat-tugas/{st.pk}/",
                status='pending'
            )
            task_send_wa_notification.delay(phone, msg, outbox_id=notif.pk)
            sent_count += 1

    return {'status': 'dispatched', 'count': sent_count}


@shared_task(bind=True)
def task_trigger_sppd_notifications(self, sppd_id):
    """
    Celery task to handle SPPD notification triggers asynchronously.
    """
    SPPD = apps.get_model('sppd_service', 'SPPD')
    Notification = apps.get_model('notifications', 'Notification')
    WANotificationSetting = apps.get_model('notifications', 'WANotificationSetting')

    sppd_obj = SPPD.objects.filter(pk=sppd_id).select_related('disposition__archive').prefetch_related('assigned_employees', 'followers').first()
    if not sppd_obj:
        return {'status': 'not_found'}

    if WANotificationSetting.is_disabled_for_category('sppd'):
        return {'status': 'disabled'}

    dispo = sppd_obj.disposition
    archive = dispo.archive if dispo else None

    dep_date = sppd_obj.departure_date.strftime('%d/%m/%Y') if hasattr(sppd_obj.departure_date, 'strftime') else (str(sppd_obj.departure_date) if sppd_obj.departure_date else "—")
    ret_date = sppd_obj.return_date.strftime('%d/%m/%Y') if hasattr(sppd_obj.return_date, 'strftime') else (str(sppd_obj.return_date) if sppd_obj.return_date else "—")

    msg = (
        f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
        f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
        f"Pemberitahuan bahwa SPPD Perjalanan Dinas telah resmi diterbitkan:\n\n"
        f"• *No. SPPD:* {sppd_obj.sppd_number}\n"
        f"• *Maksud/Kegiatan:* {sppd_obj.purpose or (archive.title if archive else 'Perjalanan Dinas')}\n"
        f"• *Tujuan:* {sppd_obj.destination}\n"
        f"• *Keberangkatan:* {dep_date}\n"
        f"• *Kepulangan:* {ret_date}\n"
        f"• *Transportasi:* {sppd_obj.transportation}\n\n"
        f"Mohon untuk melaksanakan tugas dengan sebaik-baiknya serta mengunggah Laporan SPPD setelah kegiatan selesai melalui SIMAP.\n\n"
        f"Terima kasih atas dedikasi dan kerja samanya.\n"
        f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
    )

    recipients = list(set(list(sppd_obj.assigned_employees.all()) + list(sppd_obj.followers.all())))
    sent_count = 0
    for emp in recipients:
        phone = emp.phone
        if phone:
            user_acc = getattr(emp, 'user_account', None)
            notif = Notification.objects.create(
                user=user_acc,
                employee=emp,
                notification_type='whatsapp',
                category='sppd',
                title="Penugasan SPPD",
                message=msg,
                recipient_phone=phone,
                link_url=f"/sppd/{sppd_obj.pk}/",
                status='pending'
            )
            task_send_wa_notification.delay(phone, msg, outbox_id=notif.pk)
            sent_count += 1

    return {'status': 'dispatched', 'count': sent_count}


@shared_task(bind=True)
def task_trigger_meeting_invitations(self, meeting_id):
    """
    Celery task to handle Internal Meeting invitation notifications asynchronously.
    """
    InternalMeeting = apps.get_model('internal_meetings', 'InternalMeeting')
    Notification = apps.get_model('notifications', 'Notification')
    WANotificationSetting = apps.get_model('notifications', 'WANotificationSetting')

    meeting = InternalMeeting.objects.filter(pk=meeting_id).select_related('leader', 'notulis').prefetch_related('leaders', 'participants').first()
    if not meeting:
        return {'status': 'not_found'}

    if WANotificationSetting.is_disabled_for_category('internal_meeting'):
        return {'status': 'disabled'}

    recipients = set()
    if meeting.leader:
        recipients.add(meeting.leader)
    for l in meeting.leaders.all():
        recipients.add(l)
    for p in meeting.participants.all():
        recipients.add(p)

    msg = (
        f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
        f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
        f"Undangan Rapat Internal BAZNAS Kabupaten Tangerang:\n\n"
        f"• *Judul Rapat:* {meeting.title}\n"
        f"• *No. Risalah:* {meeting.meeting_number or '-'}\n"
        f"• *Waktu:* {meeting.scheduled_at.strftime('%d/%m/%Y %H:%M')} WIB\n"
        f"• *Tempat:* {meeting.location}\n"
        f"• *Pimpinan Rapat:* {meeting.leader_names_display}\n\n"
        f"• *Agenda Pembahasan:*\n{meeting.agenda_topics or '-'}\n\n"
        f"Mohon untuk dapat bersiap dan menghadiri rapat tepat waktu.\n\n"
        f"Atas perhatian dan kehadirannya, kami ucapkan terima kasih.\n"
        f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
    )

    sent_count = 0
    for emp in recipients:
        phone = emp.phone
        if phone:
            user_acc = getattr(emp, 'user_account', None)
            notif = Notification.objects.create(
                user=user_acc,
                employee=emp,
                notification_type='whatsapp',
                category='internal_meeting',
                title="Undangan Rapat Internal",
                message=msg,
                recipient_phone=phone,
                link_url=f"/internal-meetings/{meeting.pk}/",
                status='pending'
            )
            task_send_wa_notification.delay(phone, msg, outbox_id=notif.pk)
            sent_count += 1

    return {'status': 'dispatched', 'count': sent_count}


@app.task(bind=True)
def create_calendar_event(self, source_type, source_id, title, start_dt, end_dt=None, location=None, attendees=None):
    """Create or update an internal CalendarEvent record."""
    AgendaApp = apps.get_model('agendas', 'CalendarEvent')
    now = timezone.now()
    key = f"{source_type}:{source_id}"
    try:
        defaults = {
            'title': title,
            'start': start_dt,
            'end': end_dt,
            'location': location,
            'updated_at': now,
        }
        if source_type == 'sppd':
            defaults['sppd_id'] = source_id
        elif source_type == 'surat_tugas':
            defaults['surat_tugas_id'] = source_id
        elif source_type == 'agenda':
            defaults['agenda_id'] = source_id
        elif source_type == 'archive':
            defaults['archive_id'] = source_id

        ev, created = AgendaApp.objects.update_or_create(
            source_key=key,
            defaults=defaults,
        )
        return {'created': created, 'id': ev.pk}
    except Exception as e:
        print('Failed to create calendar event:', e)
        raise
