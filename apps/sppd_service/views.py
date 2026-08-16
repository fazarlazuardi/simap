from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.db import models
from django.utils import timezone

from .models import SPPD
from archives.models import Archive
from dispositions.models import Disposition
from agendas.models import Agenda
from users.models import User, Employee
from services.archives.numbering_service import NumberingService
from users.decorators import pimpinan_required, staff_or_kabid_or_pimpinan_required


@login_required
def sppd_list(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    pegawai = request.GET.get('pegawai')
    status = request.GET.get('status')
    archive_type = request.GET.get('type')

  
    active_pov = request.session.get('active_pov')
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)
    current_emp = getattr(request.user, 'employee', None)

    if (request.user.is_superadmin and not active_pov) or is_waka_or_kabid_2 or getattr(request.user, 'is_pimpinan', False) or getattr(request.user, 'is_kabid', False):
        sppds = SPPD.objects.select_related('disposition__archive', 'disposition__report').prefetch_related('assigned_employees', 'followers').all()
    elif current_emp:
        sppds = SPPD.objects.filter(
            Q(assigned_employees=current_emp) | Q(followers=current_emp) | Q(created_by=request.user)
        ).select_related('disposition__archive', 'disposition__report').prefetch_related('assigned_employees', 'followers').distinct()
    else:
        sppds = SPPD.objects.filter(created_by=request.user).select_related('disposition__archive', 'disposition__report').prefetch_related('assigned_employees', 'followers').distinct()

    if date_from:
        sppds = sppds.filter(departure_date__gte=date_from)
    if date_to:
        sppds = sppds.filter(departure_date__lte=date_to)
    if pegawai:
        sppds = sppds.filter(assigned_employees__id=pegawai)
    if archive_type:
        sppds = sppds.filter(disposition__archive__archive_type=archive_type)
    if status == 'active':
        sppds = sppds.filter(is_cancelled=False)
    elif status == 'cancelled':
        sppds = sppds.filter(is_cancelled=True)

    sppds = sppds.order_by('-created_at')

    # Khusus Waka II & Kabid II / POV Waka II: filter daftar SPPD & kandidat disposisi SPPD (Hanya Bantuan Terverifikasi Kabid IV)
    active_pov = request.session.get('active_pov')
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)
    if is_waka_or_kabid_2:
        from services.workflows.workflow_engine import WorkflowEngine
        valid_sppd_ids = [
            sp.id for sp in sppds 
            if sp.disposition and sp.disposition.archive and 
            (sp.disposition.archive.verified_by_kabid or sp.disposition.archive.status != 'baru') and 
            WorkflowEngine.is_bantuan(sp.disposition.archive)
        ]
        sppds = sppds.filter(id__in=valid_sppd_ids)

    # Disposisi yang bisa dibuat SPPD
    from surat_tugas.models import SuratTugas
    st_dispo_ids = SuratTugas.objects.filter(disposition__isnull=False).values_list('disposition_id', flat=True)

    raw_dispositions = Disposition.objects.filter(
        id__in=st_dispo_ids
    ).exclude(
        archive__status='ditolak'
    ).select_related('archive', 'sender').prefetch_related('forwarded_to', 'sppd_list')

    if is_waka_or_kabid_2:
        raw_dispositions = raw_dispositions.filter(
            Q(archive__verified_by_kabid=True) | ~Q(archive__status='baru')
        )

    # Syarat SPPD Multi-tahap: Dokumen Bantuan dengan 1 SPPD (Survei) tetap boleh diterbitkan SPPD Tahap 2 (Penyaluran)
    valid_dispo_ids = []
    for d in raw_dispositions:
        arch = d.archive
        sppds_item_list = list(d.sppd_list.all())
        cnt = len(sppds_item_list)
        
        is_bantuan = False
        if arch:
            from services.workflows.workflow_engine import WorkflowEngine
            is_bantuan = WorkflowEngine.is_bantuan(arch)

        if is_waka_or_kabid_2 and not is_bantuan:
            continue

        max_sppd = 2 if is_bantuan else 1

        if cnt < max_sppd:
            valid_dispo_ids.append(d.id)

    dispositions = Disposition.objects.filter(id__in=valid_dispo_ids).select_related('archive', 'sender').prefetch_related('forwarded_to', 'sppd_list')

    if date_from:
        dispositions = dispositions.filter(created_at__date__gte=date_from)
    if date_to:
        dispositions = dispositions.filter(created_at__date__lte=date_to)
    if pegawai:
        dispositions = dispositions.filter(forwarded_to__id=pegawai)
    if archive_type:
        dispositions = dispositions.filter(archive__archive_type=archive_type)
    if status == 'cancelled':
        dispositions = dispositions.filter(archive__status='ditolak')

    dispositions = dispositions.order_by('-created_at')

    employees = Employee.objects.all().order_by('full_name')
    status_choices = [('active', 'Aktif'), ('cancelled', 'Dibatalkan')]
    active_tab = request.GET.get('tab', 'create')

    per_page = int(request.GET.get('per_page', 25))
    paginator_sppd = Paginator(sppds, per_page)
    paginator_dispo = Paginator(dispositions, per_page)
    page_number = request.GET.get('page')
    page_obj_sppd = paginator_sppd.get_page(page_number)
    page_obj_dispo = paginator_dispo.get_page(page_number)

    from services.analytics.reporting_service import ReportingService
    sppd_recap = ReportingService.get_sppd_recap()
    sppd_chart_labels = [item['employee'].full_name for item in sppd_recap[:7]]
    sppd_chart_series = [item['total_sppd'] for item in sppd_recap[:7]]

    can_create_sppd = not (is_waka_or_kabid_2 and not getattr(request.user, 'is_superadmin', False))

    return render(request, 'sppd/list.html', {
        'page_obj': page_obj_sppd,
        'page_obj_dispo': page_obj_dispo,
        'sppds': page_obj_sppd,
        'dispositions': page_obj_dispo,
        'employees': employees,
        'status_choices': status_choices,
        'active_tab': active_tab,
        'archive_types': Archive.TYPE_CHOICES,
        'current_type': archive_type or '',
        'sppd_recap': sppd_recap,
        'sppd_chart_labels': sppd_chart_labels,
        'sppd_chart_series': sppd_chart_series,
        'can_create_sppd': can_create_sppd,
        'is_waka_or_kabid_2': is_waka_or_kabid_2,
        'filters': {
            'date_from': date_from or '',
            'date_to': date_to or '',
            'pegawai': pegawai or '',
            'status': status or '',
        },
    })


@login_required
def sppd_detail(request, pk):
    sppd = get_object_or_404(SPPD.objects.select_related('disposition__archive', 'disposition__report', 'created_by').prefetch_related('assigned_employees', 'followers'), pk=pk)
    return render(request, 'sppd/detail.html', {'sppd': sppd})


def determine_smart_purpose(archive=None, dispo=None, st=None):
    if st and not hasattr(st, 'tentang') and hasattr(st, 'first'):
        st = st.first()

    base_title = ""
    if st and hasattr(st, 'tentang') and st.tentang:
        base_title = st.tentang.strip()
    elif archive and hasattr(archive, 'title') and archive.title:
        base_title = archive.title.strip()
    elif dispo and hasattr(dispo, 'archive') and dispo.archive and dispo.archive.title:
        base_title = dispo.archive.title.strip()

    title_lower = base_title.lower()
    archive_obj = archive or (dispo.archive if (dispo and hasattr(dispo, 'archive')) else None)
    if not archive_obj and st and hasattr(st, 'disposition') and st.disposition:
        st_dispo = st.disposition
        if hasattr(st_dispo, 'archive'):
            archive_obj = st_dispo.archive

    archive_type = archive_obj.archive_type if archive_obj else ''
    category_name = (archive_obj.category.name if (archive_obj and archive_obj.category) else '').lower()

    is_bantuan = (
        archive_type == 'proposal' or
        'bantuan' in category_name or
        any(k in title_lower for k in ['permohonan bantuan', 'proposal bantuan', 'mustahik', 'rutilahu', 'bedah rumah', 'santunan', 'kursi roda', 'kaki palsu', 'alat bantu'])
    )

    if is_bantuan:
        if any(k in title_lower for k in ['survei', 'verifikasi', 'tinjau', 'lapangan', 'pemeriksaan', 'cek']):
            return "Survei Lapangan / Peninjauan Mustahik", "Survei / Verifikasi Lapangan Mustahik"
        elif any(k in title_lower for k in ['penyaluran', 'peresmian', 'rtlh', 'bedah rumah', 'kursi roda', 'kaki palsu', 'alat bantu', 'penyerahan', 'santunan', 'pentasyarufan']):
            return "Penyaluran Bantuan / Pentasyarufan Mustahik", "Penyaluran Bantuan / Pentasyarufan Mustahik"
        else:
            return "Tindak Lanjut Penanganan Permohonan Bantuan", "Penanganan Permohonan Bantuan Mustahik"
    else:
        if any(k in title_lower for k in ['menghadiri', 'rakor', 'rapat', 'undangan', 'pelatihan', 'bimbingan', 'sosialisasi', 'audiensi', 'kegiatan', 'kunjungan']):
            if base_title:
                if not title_lower.startswith('menghadiri') and not title_lower.startswith('rakor'):
                    purpose_text = f"Menghadiri {base_title}"
                else:
                    purpose_text = base_title
            else:
                purpose_text = "Menghadiri Acara / Rapat Koordinasi"
            return purpose_text, "Menghadiri Undangan / Acara"
        else:
            if base_title and len(base_title) > 5:
                return f"Tindak Lanjut Bidang Terkait ({base_title})", "Tindak Lanjut Bidang Terkait"
            return "Tindak Lanjut Bidang Terkait", "Tindak Lanjut Bidang Terkait"


@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_create(request, dispo_pk=None, surat_tugas_pk=None):
    from surat_tugas.models import SuratTugas

    active_pov = request.session.get('active_pov')
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or (not getattr(request.user, 'is_superadmin', False) and (getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)))
    if is_waka_or_kabid_2:
        messages.warning(request, "Akun Bidang II hanya dapat melihat daftar SPPD & grafik. Pembuatan berkas SPPD dilakukan oleh Kabid IV / Front Office.")
        return redirect('sppd_service:list')

    st = None
    if dispo_pk:
        dispo = get_object_or_404(Disposition, pk=dispo_pk)
        st_pk = request.GET.get('st') or request.POST.get('st_pk')
        if st_pk:
            st = SuratTugas.objects.filter(pk=st_pk, disposition=dispo).first()
        if not st:
            used_st_ids = dispo.sppd_list.exclude(surat_tugas__isnull=True).values_list('surat_tugas_id', flat=True)
            st = SuratTugas.objects.filter(disposition=dispo).exclude(pk__in=used_st_ids).last()
        if not st:
            st = SuratTugas.objects.filter(disposition=dispo).last()
    elif surat_tugas_pk:
        st = get_object_or_404(SuratTugas, pk=surat_tugas_pk)
        dispo = st.disposition
    else:
        messages.error(request, "Disposisi tidak ditemukan.")
        return redirect('sppd_service:list')

    existing_sppds = list(dispo.sppd_list.all()) if (dispo and hasattr(dispo, 'sppd_list')) else []
    existing_sppd_count = len(existing_sppds)
    next_tahap = existing_sppd_count + 1

    if existing_sppd_count >= 1:
        if existing_sppd_count >= 2:
            messages.warning(request, "Dokumen ini sudah mencapai batas maksimal 2 tahap SPPD.")
            return redirect('sppd_service:list')

        # Syarat SPPD 2 Langkah: Dokumen harus memiliki histori SPPD Survei!
        has_survei_history = any(
            sp.sppd_type == 'survei' or any(k in ((sp.purpose or '') + ' ' + (sp.sppd_type or '')).lower() for k in ['survei', 'peninjauan', 'verifikasi', 'lapangan'])
            for sp in existing_sppds
        )
        if not has_survei_history:
            messages.warning(
                request,
                "Proses SPPD 2 langkah hanya untuk penanganan dokumen yang memiliki histori SPPD Survei. Dokumen ini tidak memiliki histori SPPD Survei sehingga cukup 1 tahap SPPD saja."
            )
            return redirect('sppd_service:list')

    last_sppd = dispo.sppd_list.order_by('-created_at').first() if hasattr(dispo, 'sppd_list') else None
    
    is_agenda_done = False
    if dispo and dispo.archive:
        is_agenda_done = Agenda.objects.filter(archive=dispo.archive, status='selesai').exists()

    if last_sppd and last_sppd.status not in ['selesai', 'dibatalkan'] and not is_agenda_done:
        messages.warning(
            request,
            f"SPPD tahap {last_sppd.tahap} ({last_sppd.sppd_number}) masih aktif (status: {last_sppd.get_status_display()}). "
            f"Selesaikan dulu sebelum membuat SPPD tahap {next_tahap}."
        )
        return redirect('sppd_service:list')
    
    if last_sppd and is_agenda_done and last_sppd.status not in ['selesai', 'dibatalkan']:
        last_sppd.status = 'selesai'
        last_sppd.save(update_fields=['status'])

    if request.method == 'POST':
        sppd_number = request.POST.get('sppd_number')
        if not sppd_number or SPPD.objects.filter(sppd_number=sppd_number).exists():
            sppd_number = NumberingService.generate_number('sppd')

        smart_p, smart_act = determine_smart_purpose(archive=dispo.archive if dispo else None, dispo=dispo, st=st)
        purpose = request.POST.get('purpose') or smart_p
        destination = request.POST.get('destination')
        
        from datetime import datetime
        dep_str = request.POST.get('departure_date')
        ret_str = request.POST.get('return_date') or dep_str
        try:
            departure_date = datetime.strptime(dep_str, '%Y-%m-%d').date() if isinstance(dep_str, str) else dep_str
        except Exception:
            departure_date = timezone.now().date()

        try:
            return_date = datetime.strptime(ret_str, '%Y-%m-%d').date() if isinstance(ret_str, str) else ret_str
        except Exception:
            return_date = departure_date

        transportation = request.POST.get('transportation')
        assigned_ids = request.POST.getlist('assigned_employees')
        
        sppd_type = request.POST.get('sppd_type', 'umum')
        if sppd_type == 'umum' and purpose:
            pl = purpose.lower()
            if any(k in pl for k in ['survei', 'verifikasi', 'lapangan', 'peninjauan']):
                sppd_type = 'survei'
            elif any(k in pl for k in ['penyaluran', 'bantuan', 'pentasyarufan', 'santunan']):
                sppd_type = 'penyaluran'

        if sppd_type == 'survei':
            activity_text = "Survei / Verifikasi Lapangan Mustahik"
        elif sppd_type == 'penyaluran':
            activity_text = "Penyaluran Bantuan / Pentasyarufan Mustahik"
        else:
            activity_text = smart_act

        sppd = SPPD.objects.create(
            surat_tugas=st,
            disposition=dispo,
            sppd_number=sppd_number,
            purpose=purpose,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            transportation=transportation,
            sppd_type=sppd_type,
            tahap=next_tahap,
            status='disetujui',
            created_by=request.user
        )
        sppd.assigned_employees.set(Employee.objects.filter(id__in=assigned_ids))
        
        follower_ids = request.POST.getlist('followers')
        sppd.followers.set(Employee.objects.filter(id__in=follower_ids))
        
       
        archive = dispo.archive if dispo else None
        if archive:
            archive.status = 'proses'
            archive.activity_name = activity_text
            archive.status_note = f'SPPD ({sppd_number}) diterbitkan untuk {purpose}.'
            archive.save()

        if dispo and dispo.status in ['terisi', 'terverifikasi']:
            dispo.status = 'proses'
            dispo.save()

        try:
            from datetime import datetime, time, date
            sch_date = departure_date if isinstance(departure_date, date) else datetime.strptime(str(departure_date), '%Y-%m-%d').date()
            ret_date = return_date if isinstance(return_date, date) else datetime.strptime(str(return_date), '%Y-%m-%d').date()
            raw_dt = datetime.combine(sch_date, time(8, 0))
            try:
                sch_datetime = timezone.make_aware(raw_dt)
            except Exception:
                sch_datetime = raw_dt
            
            tgl_str = sch_date.strftime('%d/%m/%Y') if sch_date == ret_date else f"{sch_date.strftime('%d/%m/%Y')} s/d {ret_date.strftime('%d/%m/%Y')}"

            agenda_title = f"SPPD: {purpose}" if len(purpose) <= 70 else f"SPPD: {purpose[:67]}..."
            agenda_desc = f"Perjalanan Dinas SPPD {sppd_number} ke {destination} ({tgl_str}). Maksud Keberangkatan SPPD: {purpose}"

            agenda = Agenda.objects.filter(description__icontains=sppd_number).first()

            if not agenda:
                agenda = Agenda.objects.create(
                    title=agenda_title,
                    location=destination,
                    description=agenda_desc,
                    archive=archive,
                    scheduled_at=sch_datetime,
                    created_by=request.user,
                    status='terjadwal',
                )
            else:
                agenda.title = agenda_title
                agenda.location = destination
                agenda.description = agenda_desc
                agenda.scheduled_at = sch_datetime
                agenda.status = 'terjadwal'
                agenda.save()

            agenda.sppd_ref = sppd
            if sppd.assigned_employees.exists():
                agenda.assigned_employees.set(sppd.assigned_employees.all())
                from users.models import User
                user_ids = list(User.objects.filter(employee__in=sppd.assigned_employees.all()).values_list('id', flat=True))
                if user_ids:
                    agenda.assigned_to.set(user_ids)
        except Exception as ae:
            import logging
            logging.getLogger(__name__).exception("Auto agenda registration notice: %s", ae)

        import threading
        from services.notifications.notification_service import NotificationService
        threading.Thread(target=NotificationService.send_sppd_notification_auto_by_id, args=(sppd.id,), daemon=True).start()

        messages.success(request, f"SPPD {sppd_number} berhasil dibuat & Notifikasi WA terkirim.")
        return redirect('sppd_service:list')

    agenda = Agenda.objects.filter(archive=dispo.archive, status='terjadwal').last()
    default_departure = (
        st.tanggal_mulai.strftime('%Y-%m-%d') if (st and st.tanggal_mulai)
        else (agenda.scheduled_at.strftime('%Y-%m-%d') if agenda else timezone.now().strftime('%Y-%m-%d'))
    )
    default_return = default_departure
    smart_p, _ = determine_smart_purpose(archive=dispo.archive if dispo else None, dispo=dispo, st=st)
    default_purpose = (st.tentang if (st and st.tentang) else smart_p)
    default_destination = (st.lokasi_tujuan if (st and st.lokasi_tujuan) else (dispo.archive.sender_receiver if (dispo and dispo.archive) else 'Tangerang'))
    default_transportation = 'Mobil Dinas / Umum'

    # Poin 1: Pegawai yang ditugaskan di SPPD ADALAH pegawai yang ditugaskan di Surat Tugas!
    if st and st.pegawai_ditugaskan.exists():
        employees = st.pegawai_ditugaskan.all().order_by('full_name')
    elif dispo and dispo.forwarded_to.exists():
        employees = dispo.forwarded_to.all().order_by('full_name')
    else:
        employees = Employee.objects.all().order_by('full_name')

    default_assigned_emp_ids = list(employees.values_list('id', flat=True))
    default_sppd_number = NumberingService.get_default_number('sppd')

    return render(request, 'sppd/sppd_form.html', {
        'dispo': dispo,
        'surat_tugas': st,
        'employees': employees,
        'default_assigned_emp_ids': default_assigned_emp_ids,
        'default_departure': default_departure,
        'default_return': default_return,
        'default_destination': default_destination,
        'default_purpose': default_purpose,
        'default_transportation': default_transportation,
        'default_sppd_number': default_sppd_number,
        'form_title': 'Buat Surat Perintah Perjalanan Dinas (SPPD)',
        'submit_label': 'Simpan SPPD'
    })



@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_create_with_st(request, surat_tugas_pk):
    return sppd_create(request, surat_tugas_pk=surat_tugas_pk)


@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_complete(request, pk):
    """
    Selesaikan SPPD secara manual dari Modul SPPD & Unggah LHP.
    Setelah tersimpan, otomatis arahkan kembali ke halaman Detail Arsip (jika ada).
    """
    sppd = get_object_or_404(SPPD, pk=pk)
    
    if request.method == 'POST':
        notes = request.POST.get('report_notes', '').strip()
        report_file = request.FILES.get('report_file')

        sppd.status = 'selesai'
        if notes:
            sppd.report_notes = notes
        if report_file:
            sppd.report_file = report_file
        sppd.save()

        # Proses Unggah Berkas / Foto Lampiran Tambahan
        additional_files = request.FILES.getlist('additional_files') or request.FILES.getlist('report_files')
        if additional_files:
            from .models import SPPDAttachment
            for f in additional_files:
                if f:
                    SPPDAttachment.objects.create(
                        sppd=sppd,
                        file=f,
                        title=f.name
                    )

        
        if hasattr(sppd, 'agenda_set'):
            sppd.agenda_set.filter(status='terjadwal').update(status='selesai', is_completed=True)

        if sppd.sppd_type == 'survei':
            messages.success(request, f"LHP Survei Tersimpan! Lanjutkan tindakan berikutnya (Penyaluran / Laporan Akhir).")
        else:
            messages.success(request, f"LHP Tersimpan! SPPD {sppd.sppd_number} berhasil dinyatakan SELESAI.")

        
        if hasattr(sppd, 'disposition') and sppd.disposition and hasattr(sppd.disposition, 'archive') and sppd.disposition.archive:
            return redirect('archives:detail', pk=sppd.disposition.archive.pk)
            
    return redirect('sppd_service:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_edit(request, pk):
    sppd = get_object_or_404(SPPD.objects.select_related('disposition__report'), pk=pk)
    if sppd.is_cancelled:
        messages.error(request, "SPPD yang dibatalkan tidak bisa diedit.")
        return redirect('sppd_service:list')
    if hasattr(sppd.disposition, 'report') and sppd.disposition.report:
        messages.error(request, "SPPD tidak bisa diedit karena laporan sudah dibuat.")
        return redirect('sppd_service:list')
    dispo = sppd.disposition

    if request.method == 'POST':
        sppd.sppd_number = request.POST.get('sppd_number')
        sppd.destination = request.POST.get('destination')
        sppd.purpose = (request.POST.get('purpose') or sppd.purpose or '').strip()
        sppd.departure_date = request.POST.get('departure_date')
        sppd.return_date = request.POST.get('return_date')
        sppd.transportation = request.POST.get('transportation')
        assigned_ids = request.POST.getlist('assigned_employees')
        sppd.save()
        sppd.assigned_employees.set(Employee.objects.filter(id__in=assigned_ids))

        follower_ids = request.POST.getlist('followers')
        sppd.followers.set(Employee.objects.filter(id__in=follower_ids))

        try:
            from datetime import datetime, time, date
            d_date = sppd.departure_date
            r_date = sppd.return_date
            sch_date = d_date if isinstance(d_date, date) else datetime.strptime(str(d_date), '%Y-%m-%d').date()
            ret_date = r_date if isinstance(r_date, date) else datetime.strptime(str(r_date), '%Y-%m-%d').date()
            raw_dt = datetime.combine(sch_date, time(8, 0))
            try:
                sch_datetime = timezone.make_aware(raw_dt)
            except Exception:
                sch_datetime = raw_dt

            tgl_str = sch_date.strftime('%d/%m/%Y') if sch_date == ret_date else f"{sch_date.strftime('%d/%m/%Y')} s/d {ret_date.strftime('%d/%m/%Y')}"

            purpose = sppd.purpose or (dispo.archive.title if (dispo and dispo.archive) else sppd.destination)
            agenda_title = f"SPPD: {purpose}" if len(purpose) <= 70 else f"SPPD: {purpose[:67]}..."
            agenda_desc = f"Perjalanan Dinas SPPD {sppd.sppd_number} ke {sppd.destination} ({tgl_str}). Maksud Keberangkatan SPPD: {purpose}"

            agenda = Agenda.objects.filter(description__icontains=sppd.sppd_number).first()
            
            if not agenda:
                agenda = Agenda.objects.create(
                    title=agenda_title,
                    location=sppd.destination,
                    description=agenda_desc,
                    archive=dispo.archive if dispo else None,
                    scheduled_at=sch_datetime,
                    created_by=request.user,
                    status='terjadwal',
                )
            else:
                agenda.title = agenda_title
                agenda.location = sppd.destination
                agenda.description = agenda_desc
                agenda.scheduled_at = sch_datetime
                agenda.status = 'terjadwal'
                agenda.save()

            agenda.sppd_ref = sppd
            if sppd.assigned_employees.exists():
                agenda.assigned_employees.set(sppd.assigned_employees.all())
                from users.models import User
                user_ids = list(User.objects.filter(employee__in=sppd.assigned_employees.all()).values_list('id', flat=True))
                if user_ids:
                    agenda.assigned_to.set(user_ids)
        except Exception as ae:
            import logging
            logging.getLogger(__name__).exception("Agenda update sync notice: %s", ae)

        messages.success(request, f"SPPD {sppd.sppd_number} berhasil diperbarui.")
        return redirect('sppd_service:list')

    st = sppd.surat_tugas
    if not st and dispo:
        st_rel = getattr(dispo, 'surat_tugas', None) or getattr(dispo, 'surat_tugas_list', None)
        if st_rel:
            st = st_rel.first() if hasattr(st_rel, 'first') else st_rel

    default_departure = (
        sppd.departure_date.strftime('%Y-%m-%d') if (hasattr(sppd.departure_date, 'strftime') and sppd.departure_date)
        else (str(sppd.departure_date) if sppd.departure_date else timezone.now().strftime('%Y-%m-%d'))
    )
    default_return = (
        sppd.return_date.strftime('%Y-%m-%d') if (hasattr(sppd.return_date, 'strftime') and sppd.return_date)
        else (str(sppd.return_date) if sppd.return_date else default_departure)
    )
    smart_p, _ = determine_smart_purpose(archive=dispo.archive if (dispo and hasattr(dispo, 'archive')) else None, dispo=dispo, st=st)
    default_purpose = sppd.purpose or smart_p
    default_destination = sppd.destination or (st.lokasi_tujuan if (st and hasattr(st, 'lokasi_tujuan') and st.lokasi_tujuan) else (dispo.archive.sender_receiver if (dispo and dispo.archive) else 'Tangerang'))
    default_transportation = sppd.transportation or 'Mobil Dinas / Umum'

    # Poin 1: Opsi pegawai pada edit SPPD dibatasi dari Surat Tugas jika ada
    if st and st.pegawai_ditugaskan.exists():
        employees = (st.pegawai_ditugaskan.all() | sppd.assigned_employees.all()).distinct().order_by('full_name')
    elif dispo and dispo.forwarded_to.exists():
        employees = (dispo.forwarded_to.all() | sppd.assigned_employees.all()).distinct().order_by('full_name')
    else:
        employees = Employee.objects.all().order_by('full_name')
    default_sppd_number = sppd.sppd_number or NumberingService.get_default_number('sppd')
    return render(request, 'sppd/sppd_form.html', {
        'dispo': dispo,
        'sppd': sppd,
        'employees': employees,
        'default_departure': default_departure,
        'default_return': default_return,
        'default_destination': default_destination,
        'default_purpose': default_purpose,
        'default_transportation': default_transportation,
        'default_sppd_number': default_sppd_number,
        'form_title': 'Edit Surat Perintah Perjalanan Dinas (SPPD)',
        'submit_label': 'Perbarui SPPD',
    })


@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_delete(request, pk):
    sppd = get_object_or_404(SPPD, pk=pk)
    if request.method == 'POST':
        number = sppd.sppd_number
        sppd.delete()
        messages.success(request, f"SPPD {number} berhasil dihapus.")
    return redirect('sppd_service:list')


@login_required
@staff_or_kabid_or_pimpinan_required
def sppd_cancel(request, pk):
    sppd = get_object_or_404(SPPD.objects.select_related('disposition__report'), pk=pk)
    if hasattr(sppd.disposition, 'report') and sppd.disposition.report:
        messages.error(request, "SPPD tidak bisa dibatalkan karena laporan sudah dibuat.")
        return redirect('sppd_service:list')
    if request.method == 'POST':
        sppd.is_cancelled = True
        sppd.status = 'dibatalkan'
        sppd.save()
        messages.success(request, f"SPPD {sppd.sppd_number} dibatalkan.")
    return redirect('sppd_service:list')


@login_required
def sppd_print(request):
    ids = request.GET.getlist('ids')
    if not ids:
        messages.error(request, "Pilih SPPD yang ingin dicetak.")
        return redirect('sppd_service:list')
        
    sppds = SPPD.objects.filter(id__in=ids).select_related('disposition__archive', 'created_by').prefetch_related('assigned_employees', 'followers')
    return render(request, 'sppd/print_sppd.html', {'sppds': sppds})