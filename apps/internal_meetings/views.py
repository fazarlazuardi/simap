from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import InternalMeetingForm, NotulensiForm
from .models import InternalMeeting, MeetingActionItem
from users.models import Employee
from services.audit_logs.audit_service import AuditService



def send_meeting_wa_notifications(meeting, is_notulensi=False):
    """Mengirimkan notifikasi WA Gateway untuk Undangan Rapat & Notulensi Terbit."""
    try:
        phones = []
        # Ambil HP Pimpinan Rapat
        for l in meeting.leaders.all():
            if hasattr(l, 'phone') and l.phone and l.phone not in phones:
                phones.append(l.phone)
        if meeting.leader and hasattr(meeting.leader, 'phone') and meeting.leader.phone:
            if meeting.leader.phone not in phones:
                phones.append(meeting.leader.phone)
                
        # Ambil HP Peserta Rapat
        for p in meeting.participants.all():
            if hasattr(p, 'phone') and p.phone and p.phone not in phones:
                phones.append(p.phone)

        if not phones:
            return

        if not is_notulensi:
            msg = (
                f"*UNDANGAN RAPAT INTERNAL BAZNAS*\n"
                f"---------------------------------------\n"
                f"📌 *Judul*: {meeting.title}\n"
                f"🔢 *No. Risalah*: {meeting.meeting_number or '-'}\n"
                f"📅 *Waktu*: {meeting.scheduled_at.strftime('%d/%m/%Y %H:%M')} WIB\n"
                f"📍 *Tempat*: {meeting.location}\n"
                f"👤 *Pimpinan Rapat*: {meeting.leader_names_display}\n\n"
                f"*Agenda Pembahasan*:\n{meeting.agenda_topics}\n\n"
                f"Dimohon kehadirannya tepat waktu. Terima Kasih.\n"
                f"_SIMAP BAZNAS Kab. Tangerang_"
            )
        else:
            msg = (
                f"*NOTULENSI RAPAT INTERNAL TERBIT*\n"
                f"---------------------------------------\n"
                f"📌 *Judul*: {meeting.title}\n"
                f"🔢 *No. Risalah*: {meeting.meeting_number or '-'}\n"
                f"📝 *Notulis*: {meeting.notulis_name_display}\n\n"
                f"*Kesimpulan & Keputusan Rapat*:\n{meeting.notulensi_decision or meeting.notulensi_summary or '-'}\n\n"
                f"_Risalah Notulensi Lengkap dapat diakses di SIMAP BAZNAS._"
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
                location=meeting.location,
                description=desc_text,
                scheduled_at=meeting.scheduled_at,
                created_by=meeting.created_by,
                status=status_val,
                is_completed=is_finished
            )
        else:
            agenda.title = agenda_title
            agenda.location = meeting.location
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

        # Sync assigned employees: khusus Rapat Internal, pegawai yang ditugaskan di tabel agenda adalah Notulis Rapat
        if meeting.notulis:
            agenda.assigned_employees.set([meeting.notulis])
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

    return render(request, 'internal_meetings/create.html', {
        'form': form,
        'is_edit': False,
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

    return render(request, 'internal_meetings/detail.html', {
        'meeting': meeting,
        'employees': employees,
        'notulensi_form': notulensi_form,
        'action_items': action_items,
        'action_stats': action_stats,
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

    return render(request, 'internal_meetings/create.html', {
        'form': form,
        'meeting': meeting,
        'is_edit': True,
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
    Format Cetak Risalah Notulensi Rapat Internal Resmi BAZNAS Kabupaten Tangerang.
    Ukuran Letter 1 Lembar Pas Presisi.
    """
    meeting = get_object_or_404(
        InternalMeeting.objects.select_related('leader', 'notulis', 'created_by').prefetch_related('leaders', 'participants'),
        pk=pk
    )

    return render(request, 'internal_meetings/print_notulensi.html', {
        'meeting': meeting,
    })


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
