from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import re
import json

from .forms import InternalMeetingForm, NotulensiForm
from .models import InternalMeeting, MeetingActionItem, MeetingNotulensiAttachment
from users.models import Employee
from services.audit_logs.audit_service import AuditService


def resolve_employee_bidang(emp):
    if not emp:
        return 'other'
    pos = (emp.position or '').lower()
    dept = (emp.dept_relation.name if emp.dept_relation else '').lower()
    text = f"{pos} {dept}"

    if re.search(r'\bbidang\s*(4|iv)\b', text) or re.search(r'\b(waka|kabid)\s*(4|iv)\b', text) or 'administrasi' in text or 'sdm' in text:
        return 'bidang_4'
    if re.search(r'\bbidang\s*(3|iii)\b', text) or re.search(r'\b(waka|kabid)\s*(3|iii)\b', text) or 'perencanaan' in text or 'pelaporan' in text:
        return 'bidang_3'
    if re.search(r'\bbidang\s*(2|ii)\b', text) or re.search(r'\b(waka|kabid)\s*(2|ii)\b', text) or 'pendistribusian' in text or 'pendayagunaan' in text:
        return 'bidang_2'
    if re.search(r'\bbidang\s*(1|i)\b', text) or re.search(r'\b(waka|kabid)\s*(1|i)\b', text) or 'pengumpulan' in text:
        return 'bidang_1'

    return 'other'


def resolve_user_bidang(request):
    active_pov = request.session.get('active_pov')
    if active_pov:
        if active_pov in ['waka_1', 'kabid_1']: return 'bidang_1'
        if active_pov in ['waka_2', 'kabid_2']: return 'bidang_2'
        if active_pov in ['waka_3', 'kabid_3']: return 'bidang_3'
        if active_pov in ['waka_4', 'kabid_4', 'sdm', 'front_office']: return 'bidang_4'
        if active_pov == 'admin': return 'all'

    user = request.user
    if getattr(user, 'is_superadmin', False) and not active_pov:
        return 'all'

    emp = getattr(user, 'employee', None)
    if emp:
        b = resolve_employee_bidang(emp)
        if b != 'other':
            return b

    if getattr(user, 'is_waka_2', False) or getattr(user, 'is_kabid_2', False): return 'bidang_2'
    if getattr(user, 'is_waka_4', False) or getattr(user, 'is_kabid_4', False) or getattr(user, 'is_sdm', False): return 'bidang_4'

    return 'all'



def send_meeting_wa_notifications(meeting, is_notulensi=False, custom_message=None, custom_phones=None):
    """
    Kirim Notifikasi WA Gateway islami & humanis tanpa garis ke Pimpinan & Peserta Rapat.
    """
    try:
        if custom_phones is not None:
            phones = list(set([p for p in custom_phones if p]))
        else:
            recipients = set()
            if meeting.leader:
                recipients.add(meeting.leader)
            for l in meeting.leaders.all():
                recipients.add(l)
            for p in meeting.participants.all():
                recipients.add(p)
            phones = [r.phone for r in recipients if r.phone]

        if not phones:
            return

        note_str = f"\n\n• *Catatan Tambahan:*\n{custom_message}" if custom_message else ""

        if not is_notulensi:
            msg = (
                f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
                f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
                f"Undangan Rapat Internal BAZNAS Kabupaten Tangerang:\n\n"
                f"• *Judul Rapat:* {meeting.title}\n"
                f"• *No. Risalah:* {meeting.meeting_number or '-'}\n"
                f"• *Waktu:* {meeting.scheduled_at.strftime('%d/%m/%Y %H:%M')} WIB\n"
                f"• *Tempat:* {meeting.location}\n"
                f"• *Pimpinan Rapat:* {meeting.leader_names_display}\n\n"
                f"• *Agenda Pembahasan:*\n{meeting.agenda_topics or '-'}"
                f"{note_str}\n\n"
                f"Mohon untuk dapat bersiap dan menghadiri rapat tepat waktu.\n\n"
                f"Atas perhatian dan kehadirannya, kami ucapkan terima kasih.\n"
                f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
            )
        else:
            msg = (
                f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
                f"Yth. Bapak/Ibu Amil BAZNAS Kabupaten Tangerang,\n\n"
                f"Pemberitahuan bahwa Notulensi/Risalah Rapat Internal telah diselesaikan:\n\n"
                f"• *Judul Rapat:* {meeting.title}\n"
                f"• *No. Risalah:* {meeting.meeting_number or '-'}\n"
                f"• *Notulis:* {meeting.notulis_name_display}\n\n"
                f"• *Kesimpulan & Keputusan Rapat:*\n{meeting.notulensi_decision or meeting.notulensi_summary or '-'}"
                f"{note_str}\n\n"
                f"Dokumen risalah notulensi lengkap serta lampiran dapat diakses melalui sistem SIMAP BAZNAS.\n\n"
                f"Terima kasih atas perhatian dan tindak lanjutnya.\n"
                f"Wassalamu'alaikum Warahmatullahi Wabarakatuh."
            )

        from django.conf import settings
        import requests
        wa_url = getattr(settings, 'WA_GATEWAY_URL', '')

        import threading

        def _async_fallback_wa(target_phones, message_text, target_url, meeting_pk):
            for phone in target_phones:
                try:
                    requests.post(target_url, json={'to': phone, 'message': message_text, 'metadata': {'meeting_id': meeting_pk}}, timeout=3)
                except Exception as err_req:
                    print("WA gateway request error:", err_req)

        try:
            from notifications.tasks import send_wa_message
            for phone in phones:
                try:
                    send_wa_message.delay(phone, msg, metadata={'meeting_id': meeting.pk})
                except Exception:
                    if wa_url:
                        threading.Thread(target=_async_fallback_wa, args=([phone], msg, wa_url, meeting.pk), daemon=True).start()
        except Exception:
            if wa_url:
                threading.Thread(target=_async_fallback_wa, args=(phones, msg, wa_url, meeting.pk), daemon=True).start()
    except Exception as err:
        print("Error in send_meeting_wa_notifications:", err)


def sync_meeting_to_agenda(meeting):
    """
    Menyelaraskan agenda rapat internal ke modul Agenda Kerja secara otomatis.
    Jika Agenda belum ada, sistem akan membuat Agenda Kerja baru.
    Jika Agenda sudah ada, sistem akan memperbarui waktu, tempat, peserta, dan statusnya.
    """
    try:
        from agendas.models import Agenda
        agenda_title = f"[RAPAT INTERNAL] {meeting.title}"
        marker = f"InternalMeetingID:{meeting.pk}"
        
        agenda = Agenda.objects.filter(description__icontains=marker).first()
        
        desc_text = (
            f"{marker}\n\n"
            f"📌 Nomor Risalah: {meeting.meeting_number or '-'}\n"
            f"📌 Jenis Rapat: {meeting.get_meeting_type_display()}\n"
            f"👤 Pimpinan Rapat: {meeting.leader_names_display}\n\n"
            f"*Agenda Pembahasan*:\n{meeting.agenda_topics}"
        )

        is_finished = (meeting.status == 'selesai' or meeting.is_notulensi_completed)
        status_val = 'selesai' if is_finished else 'terjadwal'

        if not agenda:
            agenda = Agenda.objects.create(
                title=agenda_title,
                location=meeting.location or 'Ruang Rapat Utama BAZNAS',
                description=desc_text,
                scheduled_at=meeting.scheduled_at,
                created_by=meeting.created_by,
                status=status_val,
                is_completed=is_finished
            )
        else:
            agenda.title = agenda_title
            agenda.location = meeting.location or 'Ruang Rapat Utama BAZNAS'
            agenda.description = desc_text
            agenda.scheduled_at = meeting.scheduled_at
            agenda.status = status_val
            agenda.is_completed = is_finished
            
        if meeting.notulensi_summary:
            notes = f"Hasil Notulensi:\n{meeting.notulensi_summary}"
            if meeting.notulensi_decision:
                notes += f"\n\nKeputusan:\n{meeting.notulensi_decision}"
            agenda.completed_notes = notes
            
        if meeting.notulensi_file:
            agenda.completed_file = meeting.notulensi_file

        if meeting.attachment and not agenda.attachment:
            agenda.attachment = meeting.attachment

        agenda.save()

        # Link dua arah ke meeting
        if hasattr(meeting, 'agenda_id') and not meeting.agenda_id:
            meeting.agenda_id = agenda.pk
            meeting.save(update_fields=['agenda'])

        # Sync pegawai yang ditugaskan ke agenda (Hanya PIC Notulis / Pimpinan Utama)
        pic_set = set()
        if meeting.notulis:
            pic_set.add(meeting.notulis)
        elif meeting.leader:
            pic_set.add(meeting.leader)
        
        if pic_set:
            agenda.assigned_employees.set(list(pic_set))
        else:
            agenda.assigned_employees.clear()

        return agenda
    except Exception as err:
        print("Error in sync_meeting_to_agenda:", err)
        return None


@login_required
def meeting_list(request):
    """
    Dashboard & Daftar Rapat Internal SIMAP BAZNAS.
    Tab 1: Agenda Rapat Terjadwal & Berlangsung
    Tab 2: Riwayat Notulensi Rapat Selesai
    """
    all_meetings = InternalMeeting.objects.select_related('leader', 'notulis', 'created_by').prefetch_related('leaders', 'participants').order_by('-scheduled_at')

    scheduled_meetings = all_meetings.filter(status__in=['terjadwal', 'berlangsung'])
    completed_meetings = all_meetings.filter(status='selesai')
    other_meetings = all_meetings.filter(status='dibatalkan')

    # Stats Summary
    now = timezone.now()
    total_meetings = all_meetings.count()
    this_month_count = all_meetings.filter(scheduled_at__month=now.month, scheduled_at__year=now.year).count()
    upcoming_count = scheduled_meetings.count()
    completed_count = completed_meetings.count()

    employees = Employee.objects.filter(is_active=True).order_by('full_name')

    return render(request, 'internal_meetings/list.html', {
        'scheduled_meetings': scheduled_meetings,
        'completed_meetings': completed_meetings,
        'other_meetings': other_meetings,
        'total_meetings': total_meetings,
        'this_month_count': this_month_count,
        'upcoming_count': upcoming_count,
        'completed_count': completed_count,
        'employees': employees,
    })


@login_required
def meeting_create(request):
    """
    Form Pembuatan Agenda Rapat Internal Baru.
    """
    if request.method == 'POST':
        form = InternalMeetingForm(request.POST, request.FILES)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_by = request.user
            selected_leaders = list(form.cleaned_data.get('leaders') or [])
            if selected_leaders:
                meeting.leader = selected_leaders[0]
            meeting.save()
            form.save_m2m()
            if selected_leaders:
                meeting.leaders.set(selected_leaders)

            sync_meeting_to_agenda(meeting)
            send_meeting_wa_notifications(meeting, is_notulensi=False)

            AuditService.log_action(request.user, f"Buat Agenda Rapat Internal: {meeting.title}", request)
            messages.success(request, f"Agenda Rapat Internal '{meeting.title}' berhasil dibuat & tercatat di Agenda Kerja.")
            return redirect('internal_meetings:detail', pk=meeting.pk)
    else:
        form = InternalMeetingForm()

    all_employees = Employee.objects.filter(is_active=True).order_by('full_name')
    from agendas.models import Agenda
    agendas = Agenda.objects.all().order_by('-scheduled_at')[:50]
    emp_bidang_map = {str(e.id): resolve_employee_bidang(e) for e in all_employees}
    employee_bidang_json = json.dumps(emp_bidang_map)
    user_bidang = resolve_user_bidang(request)

    return render(request, 'internal_meetings/create.html', {
        'form': form,
        'is_edit': False,
        'employees': all_employees,
        'agendas': agendas,
        'user_bidang': user_bidang,
        'emp_bidang_map': emp_bidang_map,
        'employee_bidang_json': employee_bidang_json,
    })


@login_required
def meeting_detail(request, pk):
    """
    Detail Agenda Rapat Internal & Hasil Notulensi.
    """
    meeting = get_object_or_404(
        InternalMeeting.objects.select_related('leader', 'notulis', 'created_by').prefetch_related('leaders', 'participants'),
        pk=pk
    )
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    notulensi_form = NotulensiForm(instance=meeting)
    action_items = meeting.action_items.select_related('pic', 'completed_by').all()
    action_stats = meeting.action_plan_stats

    emp_bidang_map = {str(e.id): resolve_employee_bidang(e) for e in employees}
    employee_bidang_json = json.dumps(emp_bidang_map)
    user_bidang = resolve_user_bidang(request)

    return render(request, 'internal_meetings/detail.html', {
        'meeting': meeting,
        'employees': employees,
        'notulensi_form': notulensi_form,
        'action_items': action_items,
        'action_stats': action_stats,
        'user_bidang': user_bidang,
        'emp_bidang_map': emp_bidang_map,
        'employee_bidang_json': employee_bidang_json,
    })


@login_required
def meeting_edit(request, pk):
    """
    Edit Agenda Rapat Internal.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)

    if request.method == 'POST':
        form = InternalMeetingForm(request.POST, request.FILES, instance=meeting)
        if form.is_valid():
            meeting = form.save(commit=False)
            selected_leaders = list(form.cleaned_data.get('leaders') or [])
            if selected_leaders:
                meeting.leader = selected_leaders[0]
            meeting.save()
            form.save_m2m()
            if selected_leaders:
                meeting.leaders.set(selected_leaders)

            sync_meeting_to_agenda(meeting)
            AuditService.log_action(request.user, f"Edit Agenda Rapat Internal: {meeting.title}", request)
            messages.success(request, f"Agenda Rapat Internal '{meeting.title}' berhasil diperbarui.")
            return redirect('internal_meetings:detail', pk=meeting.pk)
    else:
        form = InternalMeetingForm(instance=meeting)

    all_employees = Employee.objects.filter(is_active=True).order_by('full_name')
    from agendas.models import Agenda
    agendas = Agenda.objects.all().order_by('-scheduled_at')[:50]
    emp_bidang_map = {str(e.id): resolve_employee_bidang(e) for e in all_employees}
    employee_bidang_json = json.dumps(emp_bidang_map)
    user_bidang = resolve_user_bidang(request)

    return render(request, 'internal_meetings/create.html', {
        'form': form,
        'meeting': meeting,
        'is_edit': True,
        'employees': all_employees,
        'agendas': agendas,
        'user_bidang': user_bidang,
        'emp_bidang_map': emp_bidang_map,
        'employee_bidang_json': employee_bidang_json,
    })


@login_required
def meeting_notulensi(request, pk):
    """
    Input / Perbarui Notulensi Rapat Internal & Terbitkan Hasil Notulensi beserta Action Items.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)

    if request.method == 'POST':
        form = NotulensiForm(request.POST, request.FILES, instance=meeting)
        if form.is_valid():
            meeting_obj = form.save(commit=False)
            meeting_obj.notulensi_created_at = timezone.now()
            if meeting_obj.status != 'dibatalkan':
                meeting_obj.status = 'selesai'
            meeting_obj.save()
            form.save_m2m()

            # Process Multiple Notulensi Attachment Files
            uploaded_files = request.FILES.getlist('notulensi_files')
            single_file = request.FILES.get('notulensi_file')
            if single_file:
                uploaded_files.append(single_file)

            uploaded_labels = request.POST.getlist('notulensi_file_labels[]')

            for idx, f in enumerate(uploaded_files):
                label_val = uploaded_labels[idx].strip() if idx < len(uploaded_labels) and uploaded_labels[idx].strip() else f.name
                MeetingNotulensiAttachment.objects.create(
                    meeting=meeting_obj,
                    file=f,
                    file_name=label_val
                )

            # Process Dynamic Action Plan Items
            action_titles = request.POST.getlist('action_title[]')
            action_pics = request.POST.getlist('action_pic[]')
            action_due_dates = request.POST.getlist('action_due_date[]')
            action_ids = request.POST.getlist('action_id[]')

            processed_ids = []
            for i, title in enumerate(action_titles):
                title_str = title.strip()
                if not title_str:
                    continue

                item_id = action_ids[i] if i < len(action_ids) else None
                pic_id = action_pics[i] if i < len(action_pics) and action_pics[i] else None
                due_date_val = action_due_dates[i] if i < len(action_due_dates) and action_due_dates[i] else None
                
                # Checkbox check: is_tracked checkbox per row
                is_tracked_val = request.POST.get(f'action_is_tracked_{i}') == 'on' or request.POST.get(f'action_is_tracked_existing_{item_id}') == 'on'
                # If checkbox not sent or default, default to True if user filled in action item
                if f'action_is_tracked_{i}' not in request.POST and f'action_is_tracked_existing_{item_id}' not in request.POST:
                    is_tracked_val = True

                pic_obj = Employee.objects.filter(pk=pic_id).first() if pic_id else None

                if item_id and item_id.isdigit():
                    item = MeetingActionItem.objects.filter(pk=int(item_id), meeting=meeting_obj).first()
                    if item:
                        item.title = title_str
                        item.pic = pic_obj
                        if due_date_val:
                            item.due_date = due_date_val
                        item.is_tracked = is_tracked_val
                        item.save()
                        processed_ids.append(item.pk)
                        continue

                new_item = MeetingActionItem.objects.create(
                    meeting=meeting_obj,
                    title=title_str,
                    pic=pic_obj,
                    due_date=due_date_val if due_date_val else None,
                    is_tracked=is_tracked_val
                )
                processed_ids.append(new_item.pk)

            # Option: Delete items explicitly removed by user in form if action_titles array was provided
            if 'has_action_items_form' in request.POST:
                meeting_obj.action_items.exclude(pk__in=processed_ids).delete()

            sync_meeting_to_agenda(meeting_obj)
            send_meeting_wa_notifications(meeting_obj, is_notulensi=True)

            AuditService.log_action(request.user, f"Input Notulensi Rapat: {meeting.title}", request)
            messages.success(request, f"Notulensi Rapat '{meeting.title}' berhasil disimpan & diterbitkan di Agenda Kerja.")

            referer = request.META.get('HTTP_REFERER', '')
            if 'agendas' in referer:
                return redirect('agendas:list')
            return redirect('internal_meetings:detail', pk=meeting.pk)
        else:
            messages.error(request, "Terjadi kesalahan saat menyimpan Notulensi Rapat.")

    return redirect('internal_meetings:detail', pk=pk)


@login_required
@require_POST
def delete_notulensi_attachment(request, attachment_id):
    """
    Hapus berkas lampiran notulensi rapat tertentu.
    """
    attachment = get_object_or_404(MeetingNotulensiAttachment, pk=attachment_id)
    meeting_pk = attachment.meeting.pk
    file_name = attachment.file_name or attachment.file.name
    attachment.delete()
    AuditService.log_action(request.user, f"Hapus Berkas Notulensi: {file_name}", request)
    messages.success(request, f"Berkas lampiran '{file_name}' berhasil dihapus.")
    return redirect('internal_meetings:detail', pk=meeting_pk)


@login_required
@require_POST
def toggle_action_item_status(request, pk, item_id):
    """
    AJAX endpoint untuk mengubah status Action Item (Checklist) & Catatan Realisasi secara interaktif.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)
    action_item = get_object_or_404(MeetingActionItem, pk=item_id, meeting=meeting)

    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')

    valid_statuses = ['pending', 'in_progress', 'completed', 'overdue']
    if new_status in valid_statuses:
        action_item.status = new_status
        if new_status == 'completed':
            action_item.completed_at = timezone.now()
            action_item.completed_by = request.user
        else:
            action_item.completed_at = None
            action_item.completed_by = None

        if notes != '':
            action_item.notes = notes

        action_item.save()

        stats = meeting.action_plan_stats
        completed_by_name = (action_item.completed_by.get_full_name() or action_item.completed_by.username) if action_item.completed_by else '-'
        completed_at_str = action_item.completed_at.strftime('%d/%m/%Y %H:%M WIB') if action_item.completed_at else '-'

        return JsonResponse({
            'status': 'success',
            'item_id': action_item.id,
            'item_status': action_item.status,
            'item_status_display': action_item.get_status_display(),
            'notes': action_item.notes or '',
            'completed_at': completed_at_str,
            'completed_by': completed_by_name,
            'stats': stats,
        })

    return JsonResponse({'status': 'error', 'message': 'Status tidak valid'}, status=400)



@login_required
def meeting_print_notulensi(request, pk):
    """
    Format Cetak Risalah Notulensi Rapat Internal / Audiensi Resmi BAZNAS Kabupaten Tangerang.
    """
    meeting = get_object_or_404(
        InternalMeeting.objects.select_related('leader', 'notulis', 'created_by').prefetch_related('leaders', 'participants'),
        pk=pk
    )

    # Auto-fill fallback jika leader/leaders belum terisi
    if not meeting.ordered_leaders:
        from agendas.models import Agenda
        agenda = Agenda.objects.filter(description__icontains=f"InternalMeetingID:{meeting.pk}").first()
        if agenda and agenda.assigned_employees.exists():
            meeting.leaders.set(agenda.assigned_employees.all())
        elif meeting.notulis:
            meeting.leader = meeting.notulis

    title_lower = (meeting.title or '').lower()
    is_audiensi = (
        meeting.meeting_type == 'audiensi' or
        any(kw in title_lower for kw in ['audiensi', 'tamu', 'kerja sama', 'kerjasama', 'permohonan', 'kunjungan', 'penerimaan'])
    )

    return render(request, 'internal_meetings/print_notulensi.html', {
        'meeting': meeting,
        'is_audiensi': is_audiensi,
    })


@login_required
def meeting_notify(request, pk):
    """
    Kirim / Kirim Ulang Notifikasi WA Undangan Rapat Internal via Modal.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)
    if request.method == 'POST':
        recipient_type = request.POST.get('recipient_type', 'participants')
        custom_message = request.POST.get('custom_message', '').strip()
        
        custom_phones = None
        recipient_label = "Pimpinan & Peserta Rapat"
        
        if recipient_type == 'specific':
            selected_emp_ids = request.POST.getlist('specific_employees')
            emps = Employee.objects.filter(id__in=selected_emp_ids)
            custom_phones = [e.phone for e in emps if e.phone]
            recipient_label = f"{len(custom_phones)} Pegawai Pilihan"
        elif recipient_type == 'all':
            emps = Employee.objects.filter(is_active=True)
            custom_phones = [e.phone for e in emps if e.phone]
            recipient_label = "Seluruh Pegawai BAZNAS"

        send_meeting_wa_notifications(
            meeting, 
            is_notulensi=False, 
            custom_message=custom_message if custom_message else None,
            custom_phones=custom_phones
        )
        
        AuditService.log_action(request.user, f"Kirim WA Notifikasi Rapat ({recipient_label}): {meeting.title}", request)
        messages.success(request, f"✅ Notifikasi WA Undangan Rapat '{meeting.title}' berhasil dikirimkan ke {recipient_label}.")
    return redirect('internal_meetings:detail', pk=pk)


@login_required
def meeting_update_attendance(request, pk):
    """
    Penyesuaian Pimpinan Rapat & Peserta Hadir setelah Jadwal Rapat Diterbitkan.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)
    if request.method == 'POST':
        leader_ids = request.POST.getlist('leaders')
        participant_ids = request.POST.getlist('participants')
        
        leaders = Employee.objects.filter(id__in=leader_ids)
        participants = Employee.objects.filter(id__in=participant_ids)
        
        meeting.leaders.set(leaders)
        if leaders.exists():
            meeting.leader = leaders.first()
        else:
            meeting.leader = None
            
        meeting.participants.set(participants)
        meeting.save()
        
        # Sinkronkan juga ke Agenda Kerja
        sync_meeting_to_agenda(meeting)
        
        # Kirim notifikasi WA Undangan jika diminta
        if request.POST.get('send_wa') == 'on':
            send_meeting_wa_notifications(meeting, is_notulensi=False)
            msg_wa = " & Notifikasi WA Terkirim"
        else:
            msg_wa = ""
            
        AuditService.log_action(request.user, f"Perbarui Presensi Rapat: {meeting.title}", request)
        messages.success(request, f"✅ Presensi Pimpinan & Peserta Hadir Rapat '{meeting.title}' berhasil disesuaikan{msg_wa}.")
    return redirect('internal_meetings:detail', pk=pk)


@login_required
def meeting_delete(request, pk):
    """
    Hapus Agenda Rapat Internal & Agenda Kerja Terkait.
    """
    meeting = get_object_or_404(InternalMeeting, pk=pk)
    if request.method == 'POST':
        title = meeting.title
        try:
            from agendas.models import Agenda
            Agenda.objects.filter(description__icontains=f"InternalMeetingID:{meeting.pk}").delete()
        except Exception:
            pass
        meeting.delete()
        AuditService.log_action(request.user, f"Hapus Agenda Rapat: {title}", request)
        messages.success(request, f"Agenda Rapat '{title}' dan Agenda Kerja terkait berhasil dihapus.")
        return redirect('internal_meetings:list')

    return redirect('internal_meetings:detail', pk=pk)


@login_required
def action_plan_list(request):
    """
    Halaman Khusus Monitoring & Analytics Action Plan Rapat Internal BAZNAS.
    Menampilkan Donut Chart Capaian Global, Bar Chart per PIC, dan Tabel Action Items.
    """
    items_qs = MeetingActionItem.objects.filter(is_tracked=True).select_related('meeting', 'pic', 'completed_by').order_by('-id')

    # Filter parameters
    status_filter = request.GET.get('status', '')
    pic_filter = request.GET.get('pic', '')
    meeting_filter = request.GET.get('meeting', '')
    search_q = request.GET.get('q', '').strip()

    if status_filter:
        if status_filter == 'overdue':
            items_qs = [item for item in items_qs if item.is_overdue or item.status == 'overdue']
        else:
            items_qs = items_qs.filter(status=status_filter)

    if pic_filter and pic_filter.isdigit():
        if isinstance(items_qs, list):
            items_qs = [i for i in items_qs if i.pic_id == int(pic_filter)]
        else:
            items_qs = items_qs.filter(pic_id=int(pic_filter))

    if meeting_filter and meeting_filter.isdigit():
        if isinstance(items_qs, list):
            items_qs = [i for i in items_qs if i.meeting_id == int(meeting_filter)]
        else:
            items_qs = items_qs.filter(meeting_id=int(meeting_filter))

    if search_q:
        if isinstance(items_qs, list):
            items_qs = [i for i in items_qs if search_q.lower() in i.title.lower()]
        else:
            items_qs = items_qs.filter(title__icontains=search_q)

    items_list = list(items_qs) if not isinstance(items_qs, list) else items_qs

    # Global stats across all tracked items
    all_tracked = list(MeetingActionItem.objects.filter(is_tracked=True).select_related('pic'))
    total_all = len(all_tracked)
    completed_all = sum(1 for item in all_tracked if item.status == 'completed')
    in_progress_all = sum(1 for item in all_tracked if item.status == 'in_progress')
    pending_all = sum(1 for item in all_tracked if item.status == 'pending')
    overdue_all = sum(1 for item in all_tracked if item.is_overdue or item.status == 'overdue')
    completion_percentage = round((completed_all / total_all) * 100) if total_all > 0 else 0

    # Analytics per PIC for Bar Chart
    pic_stats_map = {}
    for item in all_tracked:
        pic_name = item.pic.full_name if item.pic else 'Tanpa PIC'
        if pic_name not in pic_stats_map:
            pic_stats_map[pic_name] = {'completed': 0, 'total': 0}
        pic_stats_map[pic_name]['total'] += 1
        if item.status == 'completed':
            pic_stats_map[pic_name]['completed'] += 1

    chart_pic_labels = list(pic_stats_map.keys())
    chart_pic_completed = [pic_stats_map[k]['completed'] for k in chart_pic_labels]
    chart_pic_total = [pic_stats_map[k]['total'] for k in chart_pic_labels]

    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    meetings = InternalMeeting.objects.order_by('-scheduled_at')[:50]

    return render(request, 'internal_meetings/action_plan_list.html', {
        'action_items': items_list,
        'total_all': total_all,
        'completed_all': completed_all,
        'in_progress_all': in_progress_all,
        'pending_all': pending_all,
        'overdue_all': overdue_all,
        'completion_percentage': completion_percentage,
        'chart_pic_labels': chart_pic_labels,
        'chart_pic_completed': chart_pic_completed,
        'chart_pic_total': chart_pic_total,
        'employees': employees,
        'meetings': meetings,
        'selected_status': status_filter,
        'selected_pic': pic_filter,
        'selected_meeting': meeting_filter,
        'search_q': search_q,
    })


@login_required
def action_plan_upload_proof(request, item_id):
    """
    Upload dokumen/foto bukti realisasi hasil rapat untuk Action Item.
    """
    action_item = get_object_or_404(MeetingActionItem, pk=item_id)
    if request.method == 'POST':
        proof_file = request.FILES.get('proof_file')
        notes = request.POST.get('notes', '')
        if proof_file:
            action_item.proof_file = proof_file
            action_item.status = 'completed'
            action_item.completed_at = timezone.now()
            action_item.completed_by = request.user
            if notes:
                action_item.notes = notes
            action_item.save()
            AuditService.log_action(request.user, f"Upload Bukti Realisasi Action Item: {action_item.title}", request)
            messages.success(request, f"Bukti realisasi untuk '{action_item.title}' berhasil diunggah!")
        else:
            messages.error(request, "File bukti realisasi tidak ditemukan.")

    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('internal_meetings:action_plan_list')


@login_required
def action_plan_print(request):
    """
    Format Cetak Lembar Kerja / Tabel Data Action Plan Resmi.
    """
    items_qs = MeetingActionItem.objects.filter(is_tracked=True).select_related('meeting', 'pic', 'completed_by').order_by('meeting__scheduled_at', 'id')

    status_filter = request.GET.get('status', '')
    pic_filter = request.GET.get('pic', '')
    if status_filter:
        items_qs = items_qs.filter(status=status_filter)
    if pic_filter and pic_filter.isdigit():
        items_qs = items_qs.filter(pic_id=int(pic_filter))

    return render(request, 'internal_meetings/print_action_plan.html', {
        'action_items': items_qs,
        'printed_at': timezone.now(),
    })

