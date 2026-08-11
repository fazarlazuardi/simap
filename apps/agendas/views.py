from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from archives.models import Archive
from dispositions.models import Disposition
from users.models import User, Employee
from services.integrations.gateway_service import WhatsAppService
from services.audit_logs.audit_service import AuditService
from users.decorators import pimpinan_required, staff_or_kabid_or_pimpinan_required
from .models import Agenda


class AgendaForm(forms.ModelForm):
    class Meta:
        model = Agenda
        fields = ['title', 'location', 'description', 'scheduled_at', 'archive', 'attachment']


from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def build_agenda_export_workbook(agendas):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rekap Agenda BAZNAS'

    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = "BADAN AMIL ZAKAT NASIONAL (BAZNAS) KABUPATEN TANGERANG"
    title_cell.font = Font(name='Arial', size=13, bold=True, color='046C4E')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:H2')
    sub_cell = ws['A2']
    sub_cell.value = "LAPORAN REKAPITULASI AGENDA KERJA, PENUGASAN & SPPD"
    sub_cell.font = Font(name='Arial', size=11, bold=True, color='1E293B')
    sub_cell.alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A3:H3')
    meta_cell = ws['A3']
    meta_cell.value = f"Tanggal Unduh: {timezone.now().strftime('%d %B %Y %H:%M')} WIB  |  Total Agenda: {len(agendas)} Record"
    meta_cell.font = Font(name='Arial', size=9, italic=True, color='64748B')
    meta_cell.alignment = Alignment(horizontal='center', vertical='center')

    ws.append([])

    headers = [
        'No', 'Waktu & Tanggal', 'Nama Agenda / Kegiatan', 'Lokasi Tujuan',
        'Referensi Arsip / Dokumen', 'Status Agenda', 'Pegawai Ditugaskan', 'Notulensi / Hasil'
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color='046C4E', end_color='046C4E', fill_type='solid')
    header_font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border
    
    ws.row_dimensions[5].height = 26

    even_fill = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
    odd_fill = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')

    for idx, agenda in enumerate(agendas, 1):
        row_num = 5 + idx
        waktu = agenda.scheduled_at.strftime('%d/%m/%Y %H:%M WIB') if agenda.scheduled_at else '-'
        lokasi = agenda.location or '-'
        
        archive_ref = f"{agenda.archive.archive_number} - {agenda.archive.title}" if (agenda.archive and agenda.archive.archive_number) else (agenda.archive.title if agenda.archive else 'Agenda Internal')
        status_str = agenda.get_status_display().upper() if hasattr(agenda, 'get_status_display') else agenda.status.upper()
        
        assigned_names = []
        if agenda.assigned_employees.exists():
            assigned_names = [e.full_name for e in agenda.assigned_employees.all()]
        elif agenda.assigned_to.exists():
            assigned_names = [u.get_full_name() or u.username for u in agenda.assigned_to.all()]
        
        pegawai_str = ', '.join(assigned_names) if assigned_names else '-'
        notulensi = agenda.completed_notes[:100] if agenda.completed_notes else ('Berkas Terunggah' if agenda.completed_file else '-')

        ws.append([
            idx,
            waktu,
            agenda.title,
            lokasi,
            archive_ref,
            status_str,
            pegawai_str,
            notulensi
        ])

        fill = even_fill if idx % 2 == 0 else odd_fill
        ws.row_dimensions[row_num].height = 22

        for col_idx in range(1, 9):
            c = ws.cell(row=row_num, column=col_idx)
            c.fill = fill
            c.border = thin_border
            c.font = Font(name='Arial', size=9)
            if col_idx in [1, 2, 6]:
                c.alignment = Alignment(horizontal='center', vertical='center')
            else:
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

    col_widths = {1: 6, 2: 22, 3: 35, 4: 25, 5: 30, 6: 18, 7: 30, 8: 35}
    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    return wb


@login_required
def agenda_list(request):
    query = request.GET.get('q')
    status = request.GET.get('status')
    disposer = request.GET.get('disposer')
    terkait_user = request.GET.get('terkait_user')
    archive_type = request.GET.get('type')

    # Update otomatis status agenda yang arsipnya sudah selesai
    Agenda.objects.filter(archive__status='selesai', status='terjadwal').update(is_completed=True, status='selesai')

    # Backfill SPPD lama ke agenda
    try:
        from sppd_service.models import SPPD
        from datetime import datetime, time
        existing_sppds = SPPD.objects.select_related('disposition__archive', 'created_by').prefetch_related('assigned_employees').filter(is_cancelled=False)
        for sppd_obj in existing_sppds:
            arc = sppd_obj.disposition.archive if (sppd_obj.disposition and sppd_obj.disposition.archive) else None
            num_str = sppd_obj.sppd_number
            if not Agenda.objects.filter(description__icontains=num_str).exists() and not (arc and Agenda.objects.filter(archive=arc, title__startswith='SPPD:').exists()):
                sch_date = sppd_obj.departure_date
                if sch_date:
                    raw_dt = datetime.combine(sch_date, time(8, 0))
                    try:
                        sch_dt = timezone.make_aware(raw_dt)
                    except Exception:
                        sch_dt = raw_dt
                    
                    purp = sppd_obj.purpose or sppd_obj.destination or "Perjalanan Dinas"
                    new_agenda = Agenda.objects.create(
                        title=f"SPPD: {purp[:50]}",
                        location=sppd_obj.destination,
                        description=f"Perjalanan Dinas SPPD {num_str} ke {sppd_obj.destination}. Maksud: {purp}",
                        archive=arc,
                        scheduled_at=sch_dt,
                        created_by=sppd_obj.created_by or request.user,
                        status='terjadwal',
                    )
                    if sppd_obj.assigned_employees.exists():
                        new_agenda.assigned_employees.set(sppd_obj.assigned_employees.all())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("SPPD agenda backfill notice: %s", e)

    agendas = Agenda.objects.select_related('archive', 'created_by').prefetch_related(
        'assigned_to',
        Prefetch(
            'archive__dispositions',
            queryset=Disposition.objects.prefetch_related('forwarded_to')
        )
    ).all().order_by('-scheduled_at')

    if query:
        agendas = agendas.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    if status in ['completed', 'selesai']:
        agendas = agendas.filter(status='selesai')
    elif status in ['upcoming', 'terjadwal']:
        agendas = agendas.filter(status='terjadwal')
    elif status in ['cancelled', 'dibatalkan']:
        agendas = agendas.filter(status='dibatalkan')
    elif status in ['postponed', 'diundur']:
        agendas = agendas.filter(status='diundur')

    if disposer:
        agendas = agendas.filter(
            archive__dispositions__sender_id=disposer
        ).distinct()

    if archive_type:
        agendas = agendas.filter(archive__archive_type=archive_type)

    if terkait_user:
        agendas = agendas.filter(
            Q(archive__dispositions__forwarded_to__user_account__id=terkait_user) |
            Q(archive__dispositions__sppd_list__assigned_employees__user_account__id=terkait_user) |
            Q(assigned_to__id=terkait_user)
        ).distinct()

    disposer_users = User.objects.filter(
        sent_dispositions__isnull=False
    ).distinct().order_by('username')

    terkait_users = User.objects.filter(
        Q(employee__received_dispositions__isnull=False) |
        Q(employee__sppd_assignments__isnull=False)
    ).distinct().order_by('username')

    if 'export' in request.GET:
        wb = build_agenda_export_workbook(agendas)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=Agenda_BAZNAS_{timezone.now().strftime("%Y%m%d")}.xlsx'
        wb.save(response)
        return response

    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(agendas, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'agendas/list.html', {
        'page_obj': page_obj,
        'agendas': page_obj,
        'filters': {
            'status': status or '',
            'disposer': disposer or '',
            'terkait_user': terkait_user or '',
            'q': query or '',
        },
        'disposer_users': disposer_users,
        'terkait_users': terkait_users,
        'archive_types': Archive.TYPE_CHOICES if hasattr(Archive, 'TYPE_CHOICES') else [],
        'current_type': archive_type or '',
        'employees': Employee.objects.filter(is_active=True).order_by('full_name'),
    })


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_complete(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    if request.method == 'POST':
        notes = request.POST.get('completed_notes', '')
        uploaded_file = request.FILES.get('completed_file')

        # 1. Update status Agenda
        agenda.is_completed = True
        agenda.status = 'selesai'
        agenda.completed_notes = notes
        if uploaded_file:
            agenda.completed_file = uploaded_file
        agenda.save()

        # 2. SINKRONISASI OTOMATIS KE SPPD TERKAIT -> SELESAI
        from sppd_service.models import SPPD
        if hasattr(agenda, 'sppd_ref') and agenda.sppd_ref:
            agenda.sppd_ref.status = 'selesai'
            if notes and not agenda.sppd_ref.report_notes:
                agenda.sppd_ref.report_notes = notes
            if uploaded_file and not agenda.sppd_ref.report_file:
                agenda.sppd_ref.report_file = uploaded_file
            agenda.sppd_ref.save()

        # 3. KELOLA STATUS ARSIP (Tetap 'proses' jika masih dalam alur SPPD)
        if agenda.archive:
            SPPD.objects.filter(
                disposition__archive=agenda.archive, 
                sppd_ref=agenda.sppd_ref if hasattr(agenda, 'sppd_ref') else None,
                status__in=['draft', 'disetujui', 'berlangsung']
            ).update(status='selesai')

            if uploaded_file and hasattr(agenda.archive, 'file_path') and not agenda.archive.file_path:
                agenda.archive.file_path = uploaded_file
                agenda.archive.save(update_fields=['file_path'])
        else:
            if uploaded_file or notes:
                new_archive = Archive.objects.create(
                    title=f"Notulensi: {agenda.title}",
                    description=notes or f"Laporan hasil pelaksanaan agenda {agenda.title}",
                    file_path=uploaded_file if hasattr(Archive, 'file_path') else None,
                    status='selesai',
                    created_by=request.user
                )
                agenda.archive = new_archive
                agenda.save(update_fields=['archive'])

        AuditService.log_action(request.user, f"Selesaikan Agenda: {agenda.title}", request)
        messages.success(request, f"Agenda '{agenda.title}' dan SPPD terkait berhasil diselesaikan!")
    return redirect('agendas:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_cancel(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    if request.method == 'POST':
        agenda.status = 'dibatalkan'
        agenda.save()
        
        # Batalkan SPPD terkait jika agenda dibatalkan
        if hasattr(agenda, 'sppd_ref') and agenda.sppd_ref:
            agenda.sppd_ref.is_cancelled = True
            agenda.sppd_ref.status = 'dibatalkan'
            agenda.sppd_ref.save()

        AuditService.log_action(request.user, f"Batalkan Agenda: {agenda.title}", request)
        messages.success(request, f"Agenda '{agenda.title}' berhasil dibatalkan.")
    return redirect('agendas:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_edit(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    if agenda.is_sppd_generated or agenda.sppd_ref:
        messages.warning(request, "Agenda yang terbit dari SPPD tidak dapat diedit secara manual di modul Agenda. Silakan lakukan pengubahan jadwal melalui modul SPPD.")
        return redirect('agendas:list')

    if request.method == 'POST':
        form = AgendaForm(request.POST, request.FILES, instance=agenda)
        if form.is_valid():
            title = request.POST.get('title')
            location = request.POST.get('location')
            description = request.POST.get('description')
            scheduled_at = request.POST.get('scheduled_at')
            archive_id = request.POST.get('archive')
            assigned_emp_ids = request.POST.getlist('assigned_to')
            wa_emp_ids = request.POST.getlist('wa_recipients')
            send_wa = request.POST.get('send_wa') == 'on'
            attachment = request.FILES.get('attachment')

            is_recurring = request.POST.get('is_recurring') == 'on'
            recurrence_type = request.POST.get('recurrence_type', 'none')
            recurrence_day = request.POST.get('recurrence_day') or None
            recurrence_end_date = request.POST.get('recurrence_end_date') or None
            wa_notification_timing = request.POST.get('wa_notification_timing', 'instant')

            archive = Archive.objects.filter(id=archive_id).first() if archive_id else agenda.archive

            old_scheduled_at = agenda.scheduled_at
            agenda = form.save(commit=False)
            agenda.title = title
            agenda.location = location
            agenda.description = description
            if scheduled_at:
                agenda.scheduled_at = scheduled_at
            agenda.archive = archive
            agenda.is_recurring = is_recurring
            agenda.recurrence_type = recurrence_type if is_recurring else 'none'
            agenda.recurrence_day = int(recurrence_day) if (is_recurring and recurrence_day is not None and str(recurrence_day).isdigit()) else None
            agenda.recurrence_end_date = recurrence_end_date if is_recurring else None
            agenda.wa_notification_timing = wa_notification_timing
            
            if old_scheduled_at and str(old_scheduled_at) != str(scheduled_at):
                agenda.status = 'diundur'
            
            if attachment:
                agenda.attachment = attachment
            agenda.save()

            assigned_emps = Employee.objects.filter(id__in=assigned_emp_ids)
            assigned_users = User.objects.filter(employee__in=assigned_emps)
            agenda.assigned_employees.set(assigned_emps)
            agenda.assigned_to.set(assigned_users)

            if send_wa:
                wa_emps = Employee.objects.filter(id__in=wa_emp_ids) if wa_emp_ids else assigned_emps
                
                file_link = ""
                if agenda.attachment:
                    file_link = f"\n📎 *Lampiran:* {request.build_absolute_uri(agenda.attachment.url)}"
                elif archive and hasattr(archive, 'file_path') and archive.file_path:
                    file_link = f"\n🔗 *Berkas:* {request.build_absolute_uri(archive.file_path.url)}"
                
                msg = (
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"     📅 *PERUBAHAN JADWAL AGENDA*\n"
                    f"   BAZNAS Kab. Tangerang\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📌 *Kegiatan:*\n{title}\n\n"
                    f"🔄 *Jadwal Lama:*\n{old_scheduled_at.strftime('%d/%m/%Y %H:%M') if old_scheduled_at else '-'} WIB\n\n"
                    f"🕐 *Jadwal Baru:*\n{scheduled_at} WIB\n\n"
                )
                if description:
                    msg += f"📝 *Keterangan:*\n{description}\n\n"
                msg += f"{file_link}\n\n" if file_link else ""
                msg += (
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Silakan tindak lanjuti\nagenda ini sesuai jadwal baru.\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━"
                )
                
                user_map = {u.employee_id: u for u in User.objects.filter(employee__in=wa_emps)}
                for emp in wa_emps:
                    user = user_map.get(emp.pk)
                    WhatsAppService.send_notification(
                        user=user, 
                        message=msg, 
                        employee=emp, 
                        category='agenda', 
                        title="Perubahan Jadwal Agenda"
                    )
                
                agenda.notification_sent_at = timezone.now()
                agenda.save(update_fields=['notification_sent_at'])

            AuditService.log_action(request.user, f"Perbarui Agenda: {title}", request)
            messages.success(request, f"Agenda '{title}' berhasil diperbarui.")
            return redirect('agendas:list')
        else:
            messages.error(request, 'Data agenda tidak valid.')

    archives = Archive.objects.exclude(status='baru')
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    assigned_emp_ids = set(
        agenda.assigned_employees.values_list('id', flat=True)
    ) | set(
        agenda.assigned_to.filter(employee__isnull=False).values_list('employee_id', flat=True)
    )
    return render(request, 'agendas/create.html', {
        'archives': archives,
        'employees': employees,
        'agenda': agenda,
        'reschedule': True,
        'assigned_emp_ids': assigned_emp_ids,
    })


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_delete(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    if request.method == 'POST':
        title = agenda.title
        try:
            from .models import AgendaAttachment
            AgendaAttachment.objects.filter(agenda=agenda).delete()
        except Exception:
            pass
        agenda.delete()
        AuditService.log_action(request.user, f"Hapus Agenda: {title}", request)
        messages.success(request, f"Agenda '{title}' berhasil dihapus.")
    return redirect('agendas:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        location = request.POST.get('location')
        description = request.POST.get('description')
        scheduled_at = request.POST.get('scheduled_at')
        archive_id = request.POST.get('archive')
        assigned_emp_ids = request.POST.getlist('assigned_to')
        wa_emp_ids = request.POST.getlist('wa_recipients')
        send_wa = request.POST.get('send_wa') == 'on'
        attachment = request.FILES.get('attachment')
        
        is_recurring = request.POST.get('is_recurring') == 'on'
        recurrence_type = request.POST.get('recurrence_type', 'none')
        recurrence_day = request.POST.get('recurrence_day') or None
        recurrence_end_date = request.POST.get('recurrence_end_date') or None
        wa_notification_timing = request.POST.get('wa_notification_timing', 'instant')

        archive = Archive.objects.filter(id=archive_id).first() if archive_id else None
        
        agenda = Agenda.objects.create(
            title=title,
            location=location,
            description=description,
            scheduled_at=scheduled_at,
            archive=archive,
            attachment=attachment,
            created_by=request.user,
            is_recurring=is_recurring,
            recurrence_type=recurrence_type if is_recurring else 'none',
            recurrence_day=int(recurrence_day) if (is_recurring and recurrence_day is not None and str(recurrence_day).isdigit()) else None,
            recurrence_end_date=recurrence_end_date if is_recurring else None,
            wa_notification_timing=wa_notification_timing
        )
        
        assigned_emps = Employee.objects.filter(id__in=assigned_emp_ids)
        assigned_users = User.objects.filter(employee__in=assigned_emps)
        agenda.assigned_employees.set(assigned_emps)
        agenda.assigned_to.set(assigned_users)
        
        if send_wa:
            wa_emps = Employee.objects.filter(id__in=wa_emp_ids) if wa_emp_ids else assigned_emps
            
            file_link = ""
            if agenda.attachment:
                file_link = f"\n📎 *Lampiran:* {request.build_absolute_uri(agenda.attachment.url)}"
            elif archive and hasattr(archive, 'file_path') and archive.file_path:
                file_link = f"\n🔗 *Berkas:* {request.build_absolute_uri(archive.file_path.url)}"
            
            msg = (
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"     📅 *AGENDA BARU*\n"
                f"   BAZNAS Kab. Tangerang\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 *Kegiatan:*\n{title}\n\n"
                f"🕐 *Waktu:*\n{scheduled_at} WIB\n\n"
            )
            if description:
                msg += f"📝 *Keterangan:*\n{description}\n\n"
            msg += f"{file_link}\n\n" if file_link else ""
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Silakan tindak lanjuti\nagenda ini sesuai ketentuan.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            user_map = {u.employee_id: u for u in User.objects.filter(employee__in=wa_emps)}
            for emp in wa_emps:
                user = user_map.get(emp.pk)
                WhatsAppService.send_notification(
                    user=user, 
                    message=msg, 
                    employee=emp, 
                    category='agenda', 
                    title="Agenda Baru"
                )
            
            agenda.notification_sent_at = timezone.now()
            agenda.save(update_fields=['notification_sent_at'])
            msg_notif = f"dan notifikasi WA terkirim ke {wa_emps.count()} pegawai"
        else:
            msg_notif = "tanpa notifikasi WA"

        AuditService.log_action(request.user, f"Buat Agenda Manual: {title}", request)
        messages.success(request, f"Agenda berhasil ditambahkan {msg_notif}.")
        return redirect('agendas:list')

        
    archive_param = request.GET.get('archive_id') or request.GET.get('archive')
    dispo_param = request.GET.get('disposition_id') or request.GET.get('disposition')
    
    selected_archive = None
    if archive_param and archive_param.isdigit():
        selected_archive = Archive.objects.filter(id=int(archive_param)).first()
    elif dispo_param and dispo_param.isdigit():
        from dispositions.models import Disposition
        dispo = Disposition.objects.filter(id=int(dispo_param)).first()
        if dispo and dispo.archive:
            selected_archive = dispo.archive

    archives = Archive.objects.exclude(status='baru')
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    return render(request, 'agendas/create.html', {
        'archives': archives,
        'employees': employees,
        'selected_archive': selected_archive,
    })


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_notify(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    if request.method == 'POST':
        archive = agenda.archive
        tgl_pelaksanaan = '—'
        if archive:
            dispo = archive.dispositions.first()
            if dispo and dispo.implementation_date:
                tgl_pelaksanaan = dispo.implementation_date.strftime('%d/%m/%Y')

        msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"     📅 *PENGINGAT AGENDA*\n"
            f"   BAZNAS Kab. Tangerang\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 *Kegiatan:*\n{agenda.title}\n\n"
            f"🕐 *Waktu Agenda:*\n{agenda.scheduled_at.strftime('%d/%m/%Y %H:%M') if agenda.scheduled_at else '-'} WIB\n\n"
        )
        if tgl_pelaksanaan != '—':
            msg += f"📋 *Tanggal Pelaksanaan:*\n{tgl_pelaksanaan}\n\n"
        if agenda.description:
            msg += f"📝 *Keterangan:*\n{agenda.description}\n\n"
        if archive:
            msg += f"📄 *No. Arsip:*\n{archive.archive_number or '—'}\n"
            msg += f"📑 *Perihal:*\n{archive.title}\n\n"
            if hasattr(archive, 'file_path') and archive.file_path:
                msg += f"🔗 *Link Berkas:*\n{request.build_absolute_uri(archive.file_path.url)}\n\n"
        if agenda.attachment:
            msg += f"📎 *Lampiran:*\n{request.build_absolute_uri(agenda.attachment.url)}\n\n"
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Silakan tindak lanjuti\nagenda ini sesuai ketentuan.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━"
        )

        users = list(agenda.assigned_to.all())
        
        employees_from_dispo = Employee.objects.filter(
            received_dispositions__archive=archive, user_account__isnull=True
        ) if archive else Employee.objects.none()
        
        sent = 0
        for user in users:
            if WhatsAppService.send_notification(user=user, message=msg, category='agenda', title="Pengingat Agenda"):
                sent += 1
        for emp in employees_from_dispo:
            if WhatsAppService.send_notification(message=msg, employee=emp, category='agenda', title="Pengingat Agenda"):
                sent += 1

        total_target = len(users) + employees_from_dispo.count()
        if total_target == 0:
            messages.warning(request, f"Tidak ada pegawai yang terdaftar untuk agenda '{agenda.title}'. Tambahkan penerima melalui edit agenda/disposisi.")
            return redirect('agendas:list')

        agenda.notification_sent_at = timezone.now()
        agenda.save(update_fields=['notification_sent_at'])

        AuditService.log_action(request.user, f"Kirim Notifikasi Pengingat Agenda: {agenda.title}", request)
        messages.success(request, f"Notifikasi WA dikirim ke {sent} dari {total_target} penerima untuk agenda '{agenda.title}'.")
    return redirect('agendas:list')


@login_required
def agenda_events(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    disposer = request.GET.get('disposer')
    terkait_user = request.GET.get('terkait_user')
    
    events = Agenda.objects.select_related('archive').all()

    if start and end:
        events = events.filter(scheduled_at__range=[start, end])

    if disposer:
        events = events.filter(archive__dispositions__sender_id=disposer)
    if terkait_user:
        events = events.filter(
            Q(archive__dispositions__forwarded_to__user_account__id=terkait_user) |
            Q(archive__dispositions__sppd_list__assigned_employees__user_account__id=terkait_user) |
            Q(assigned_to__id=terkait_user)
        )
        
    data = []
    for event in events:
        if event.status == 'selesai':
            bg_color = '#6B7280'
            text_color = '#FFFFFF'
        elif event.status == 'dibatalkan':
            bg_color = '#EF4444'
            text_color = '#FFFFFF'
        elif event.status == 'diundur':
            bg_color = '#F59E0B'
            text_color = '#1F2937'
        else:
            bg_color = '#0E9F6E'
            text_color = '#FFFFFF'

        if event.archive and event.status == 'terjadwal':
            if event.archive.status == 'baru':
                bg_color = '#F59E0B'
            elif event.archive.status == 'proses':
                bg_color = '#3B82F6'

        event_url = '#'
        if event.completed_file:
            event_url = event.completed_file.url
        elif event.archive:
            event_url = f'/archives/{event.archive.pk}/'

        data.append({
            'id': event.id,
            'title': event.title,
            'start': event.scheduled_at.isoformat() if event.scheduled_at else None,
            'backgroundColor': bg_color,
            'borderColor': bg_color,
            'textColor': text_color,
            'url': event_url
        })

    holidays_2026 = [
        {"title": "🔴 LIBUR: Tahun Baru 2026 Masehi", "start": "2026-01-01"},
        {"title": "🔴 LIBUR: Isra Mikraj Nabi Muhammad SAW", "start": "2026-01-16"},
        {"title": "🔴 LIBUR: Tahun Baru Imlek 2577 Kongzili", "start": "2026-02-17"},
        {"title": "🔴 CUTI BERSAMA: Imlek 2577", "start": "2026-02-16"},
        {"title": "🔴 LIBUR: Hari Suci Nyepi Saka 1948", "start": "2026-03-19"},
        {"title": "🔴 CUTI BERSAMA: Hari Suci Nyepi", "start": "2026-03-18"},
        {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1447 H", "start": "2026-03-20"},
        {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1447 H", "start": "2026-03-21"},
        {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-22"},
        {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-23"},
        {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-24"},
        {"title": "🔴 LIBUR: Wafat Yesus Kristus", "start": "2026-04-03"},
        {"title": "🔴 LIBUR: Hari Paskah", "start": "2026-04-05"},
        {"title": "🔴 LIBUR: Hari Buruh Internasional", "start": "2026-05-01"},
        {"title": "🔴 LIBUR: Kenaikan Yesus Kristus", "start": "2026-05-14"},
        {"title": "🔴 LIBUR: Hari Raya Idul Adha 1447 H", "start": "2026-05-27"},
        {"title": "🔴 CUTI BERSAMA: Idul Adha 1447 H", "start": "2026-05-28"},
        {"title": "🔴 LIBUR: Hari Raya Waisak 2570 BE", "start": "2026-05-31"},
        {"title": "🔴 LIBUR: Hari Lahir Pancasila", "start": "2026-06-01"},
        {"title": "🔴 LIBUR: Tahun Baru Islam 1448 H", "start": "2026-06-16"},
        {"title": "🔴 LIBUR: Hari Kemerdekaan RI Ke-81", "start": "2026-08-17"},
        {"title": "🔴 LIBUR: Maulid Nabi Muhammad SAW", "start": "2026-08-25"},
        {"title": "🔴 LIBUR: Hari Raya Natal", "start": "2026-12-25"},
        {"title": "🔴 CUTI BERSAMA: Hari Raya Natal", "start": "2026-12-26"},
    ]

    for h in holidays_2026:
        data.append({
            'id': f"holiday-{h['start']}",
            'title': h['title'],
            'start': h['start'],
            'backgroundColor': '#DC2626',
            'borderColor': '#B91C1C',
            'textColor': '#FFFFFF',
            'allDay': True,
            'url': '#'
        })

    return JsonResponse(data, safe=False)


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_generate_sppd(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    scheduled_date = agenda.scheduled_at.date() if agenda.scheduled_at else timezone.now().date()
    
    archive = agenda.archive
    if not archive:
        from archives.models import Category
        category = Category.objects.filter(name__icontains='surat').first() or Category.objects.first()
        
        from services.archives.numbering_service import NumberingService
        arc_num = NumberingService.generate_number('surat_keluar')
        
        archive = Archive.objects.create(
            archive_number=arc_num,
            title=agenda.title,
            archive_type='surat_keluar',
            category=category,
            uploaded_by=request.user,
            sender='BAZNAS Kabupaten Tangerang',
            receiver=agenda.location or 'Lokasi Penugasan Agenda',
            letter_date=scheduled_date,
            received_date=scheduled_date,
            description=f"Dokumen Penugasan Internal dari Agenda: {agenda.title}",
            status='sudah_ditugaskan'
        )
        agenda.archive = archive
        agenda.save(update_fields=['archive', 'updated_at'])
    else:
        if not archive.letter_date:
            archive.letter_date = scheduled_date
            archive.received_date = scheduled_date
            archive.save(update_fields=['letter_date', 'received_date', 'updated_at'])

    dispo = archive.dispositions.first()
    if not dispo:
        dispo = Disposition.objects.create(
            archive=archive,
            sender=request.user,
            priority='segera',
            inst_laporkan=True,
            inst_koordinasikan=True,
            instructions='Laporkan Hasil Pelaksanaan, Koordinasikan / Tindak Lanjut',
            note=f"Disposisi Penugasan Agenda: {agenda.title}",
            status='terisi'
        )
        if agenda.assigned_employees.exists():
            dispo.forwarded_to.set(agenda.assigned_employees.all())
    else:
        dispo.priority = 'segera'
        dispo.inst_laporkan = True
        dispo.inst_koordinasikan = True
        if agenda.assigned_employees.exists() and not dispo.forwarded_to.exists():
            dispo.forwarded_to.set(agenda.assigned_employees.all())
        dispo.save()

    from surat_tugas.models import SuratTugas
    st = SuratTugas.objects.filter(disposition=dispo).first()
    if not st:
        st = SuratTugas.objects.create(
            disposition=dispo,
            tentang=agenda.title,
            lokasi_tujuan=agenda.location or 'Kabupaten Tangerang',
            tanggal_mulai=scheduled_date,
            created_by=request.user
        )
        if agenda.assigned_employees.exists():
            st.pegawai_ditugaskan.set(agenda.assigned_employees.all())
    else:
        if agenda.assigned_employees.exists() and not st.pegawai_ditugaskan.exists():
            st.pegawai_ditugaskan.set(agenda.assigned_employees.all())

    AuditService.log_action(request.user, f"Terbitkan SPPD dari Agenda: {agenda.title}", request)
    messages.success(request, f"Penugasan untuk Agenda '{agenda.title}' berhasil diselaraskan. Silakan lengkapi detail SPPD.")
    return redirect('sppd_service:create', dispo_pk=dispo.pk)


@login_required
def agenda_upload_notulensi(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    
    if request.method == 'POST':
        summary = request.POST.get('notulensi_summary') or request.POST.get('completed_notes', '').strip()
        decision = request.POST.get('notulensi_decision', '').strip()
        action_items = request.POST.get('notulensi_action_items', '').strip()
        notulis_id = request.POST.get('notulis')
        status_val = request.POST.get('status', 'selesai')
        
        files = request.FILES.getlist('completed_files') or request.FILES.getlist('completed_file') or request.FILES.getlist('notulensi_file')
        single_file = request.FILES.get('notulensi_file') or (files[0] if files else None)

        notes_combined = summary
        if decision:
            notes_combined += f"\n\nKeputusan:\n{decision}"
        if action_items:
            notes_combined += f"\n\nRencana Tindak Lanjut:\n{action_items}"

        agenda.completed_notes = notes_combined
            
        if single_file:
            agenda.completed_file = single_file
        if files:
            from .models import AgendaAttachment
            for idx, uploaded_f in enumerate(files):
                AgendaAttachment.objects.create(
                    agenda=agenda,
                    file=uploaded_f,
                    description=f"Dokumentasi #{idx+1} - {agenda.title}"
                )

        agenda.is_completed = True
        agenda.status = status_val if status_val in ['terjadwal', 'berlangsung', 'selesai', 'dibatalkan'] else 'selesai'
        agenda.save()

        # Update synced InternalMeeting if applicable
        if agenda.internal_meeting_id:
            try:
                from internal_meetings.models import InternalMeeting
                from users.models import Employee
                meeting = InternalMeeting.objects.filter(pk=agenda.internal_meeting_id).first()
                if meeting:
                    meeting.notulensi_summary = summary
                    meeting.notulensi_decision = decision
                    meeting.notulensi_action_items = action_items
                    if notulis_id and str(notulis_id).isdigit():
                        notulis_emp = Employee.objects.filter(pk=int(notulis_id)).first()
                        if notulis_emp:
                            meeting.notulis = notulis_emp
                            agenda.assigned_employees.set([notulis_emp])
                    if single_file:
                        meeting.notulensi_file = single_file
                    meeting.status = agenda.status
                    meeting.notulensi_created_at = timezone.now()
                    meeting.save()
            except Exception as err:
                print("Error updating InternalMeeting from Agenda notulensi:", err)
        agenda.status = 'selesai'
        agenda.save()

        # -------------------------------------------------------------
        # OTOMATIS SINKRON SIKLUS SPPD TAHAP 1 -> SELESAI
        # -------------------------------------------------------------
        from sppd_service.models import SPPD
        if hasattr(agenda, 'sppd_ref') and agenda.sppd_ref:
            agenda.sppd_ref.status = 'selesai'
            if notes_combined and not agenda.sppd_ref.report_notes:
                agenda.sppd_ref.report_notes = notes_combined
            if files and not agenda.sppd_ref.report_file:
                agenda.sppd_ref.report_file = files[0]
            agenda.sppd_ref.save()

        try:
            archive = agenda.archive
            dispo = archive.dispositions.first() if archive else None
            
            if archive:
                SPPD.objects.filter(
                    disposition__archive=archive, 
                    status__in=['draft', 'disetujui', 'berlangsung']
                ).update(status='selesai')

            if dispo:
                from reports.models import Report, ReportAttachment
                report, created = Report.objects.get_or_create(
                    disposition=dispo,
                    defaults={
                        'title': f"Laporan Hasil: {agenda.title}",
                        'content': notes_combined or f"Kegiatan '{agenda.title}' telah selesai dilaksanakan.",
                        'created_by': request.user
                    }
                )
                if not created:
                    if notes_combined:
                        report.content = notes_combined
                    report.save()

                if files:
                    report.file = files[0]
                    report.save(update_fields=['file'])
                    for idx, uploaded_f in enumerate(files):
                        ReportAttachment.objects.create(
                            report=report,
                            file=uploaded_f,
                            description=f"Dokumentasi #{idx+1} Agenda: {agenda.title}"
                        )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to auto sync Agenda Notulensi to Report: %s", e)

        AuditService.log_action(request.user, f"Upload Notulensi Agenda: {agenda.title}", request)
        messages.success(request, f"Notulensi & {len(files)} Berkas Dokumentasi Hasil Agenda '{agenda.title}' berhasil disimpan dan SPPD terkait diselesaikan.")
        return redirect('agendas:list')

    return redirect('agendas:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def agenda_complete(request, pk):
    agenda = get_object_or_404(Agenda, pk=pk)
    
    # Check if this is an SPPD agenda or has an archive / disposition
    archive = agenda.archive
    if not archive and hasattr(agenda, 'sppd_ref') and agenda.sppd_ref:
        archive = agenda.sppd_ref.disposition.archive if (agenda.sppd_ref and agenda.sppd_ref.disposition) else None

    if archive:
        dispo = archive.dispositions.first()
        if dispo:
            # Direct user to Report Input page for complete integration
            from reports.models import Report
            existing_report = Report.objects.filter(disposition=dispo).first()
            if existing_report:
                return redirect('reports:detail', pk=existing_report.pk)
            return redirect('reports:create', dispo_pk=dispo.pk)

    # Standard completion if no disposition attached
    agenda.is_completed = True
    agenda.status = 'selesai'
    if request.method == 'POST':
        notes = request.POST.get('completed_notes', '').strip()
        if notes:
            agenda.completed_notes = notes
    agenda.save()

    AuditService.log_action(request.user, f"Selesaikan Agenda: {agenda.title}", request)
    messages.success(request, f"Agenda '{agenda.title}' berhasil diselesaikan.")
    return redirect('agendas:list')