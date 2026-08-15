from datetime import datetime, time as dt_time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Disposition
from archives.models import Archive
from agendas.models import Agenda
from sppd_service.models import SPPD
from users.models import User, Employee
from services.integrations.gateway_service import WhatsAppService
from services.audit_logs.audit_service import AuditService
from services.archives.numbering_service import NumberingService
from users.decorators import pimpinan_required


def _resolve_sender_label(user, stage):
    """
    Menentukan nama pimpinan yang tercantum di lembar disposisi.
    Mendukung penuh fitur Take Over oleh Superadmin (admin).
    """
    if stage == 'ketua':
        # 1. Jika user sendiri adalah Ketua BAZNAS
        if hasattr(user, 'employee') and user.employee and getattr(user.employee, 'leadership_type', None) == 'ketua':
            return user.employee.full_name
        
        # 2. Jika disubmit oleh Superadmin/User lain → Cari Employee dengan jabatan Ketua
        try:
            ketua = Employee.objects.filter(leadership_type='ketua', is_active=True).first()
            if ketua and ketua.full_name:
                return ketua.full_name
        except Exception:
            pass
            
        return 'Drs. H. Achmad Nawawi, M.Si.'

    elif stage == 'waka_iv':
        # 1. Jika user sendiri adalah Waka IV
        if hasattr(user, 'employee') and user.employee and getattr(user.employee, 'leadership_type', None) == 'waka_4':
            return user.employee.full_name
            
        # 2. Jika disubmit oleh Superadmin/User lain → Cari Employee dengan jabatan Waka IV
        try:
            waka4 = Employee.objects.filter(leadership_type='waka_4', is_active=True).first()
            if waka4 and waka4.full_name:
                return waka4.full_name
        except Exception:
            pass
            
        return 'Wakil Ketua IV'

    return 'Drs. H. Achmad Nawawi, M.Si.'


@login_required
def disposition_list(request):
    current_emp = getattr(request.user, 'employee', None)
    if request.user.is_superadmin:
        qs = Disposition.objects.select_related('archive', 'sender').prefetch_related('forwarded_to', 'waka_forwarded_to').all()
    elif request.user.is_pimpinan or request.user.is_kabid:
        qs = Disposition.objects.filter(
            Q(sender=request.user)
        ).select_related('archive', 'sender').prefetch_related('forwarded_to', 'waka_forwarded_to')
        if current_emp:
            qs |= Disposition.objects.filter(
                Q(forwarded_to=current_emp) | Q(waka_forwarded_to=current_emp)
            )
            # Khusus Waka II & Kabid II: sertakan juga disposisi berlabel bantuan & pendistribusian
            if request.user.is_waka_2 or request.user.is_kabid_2:
                qs |= Disposition.objects.filter(
                    Q(archive__title__icontains='bantuan') |
                    Q(archive__title__icontains='pendistribusian') |
                    Q(archive__title__icontains='pendayagunaan') |
                    Q(archive__title__icontains='mustahik') |
                    Q(archive__description__icontains='bantuan')
                )
        qs = qs.distinct()
    else:
        qs = Disposition.objects.none()
        if current_emp:
            qs = Disposition.objects.filter(
                Q(forwarded_to=current_emp) | Q(waka_forwarded_to=current_emp)
            ).select_related('archive', 'sender').prefetch_related('forwarded_to', 'waka_forwarded_to')

    qs = qs.order_by('-created_at')

    penerima = request.GET.get('penerima')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    archive_type = request.GET.get('type')

    if penerima:
        qs = qs.filter(
            Q(forwarded_to__user_account__id=penerima) | Q(waka_forwarded_to__user_account__id=penerima)
        )
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if archive_type:
        qs = qs.filter(archive__archive_type=archive_type)

    users = User.objects.filter(is_active_account=True).order_by('username')

    # Archives verified but have no disposition yet
    archives_verified_no_dispo = Archive.objects.filter(
        status='terverifikasi'
    ).exclude(
        dispositions__isnull=False
    ).select_related('category', 'uploaded_by').order_by('-updated_at')
    if archive_type:
        archives_verified_no_dispo = archives_verified_no_dispo.filter(archive_type=archive_type)

    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    from services.notifications.notification_service import NotificationService
    pending_batch_count = NotificationService.get_pending_disposition_count()
    is_batch_ready = NotificationService.is_batch_ready()

    return render(request, 'dispositions/list.html', {
        'page_obj': page_obj,
        'dispositions': page_obj,
        'users': users,
        'status_choices': Disposition.STATUS_CHOICES,
        'penerima': penerima or '',
        'status_filter': status or '',
        'date_from': date_from or '',
        'date_to': date_to or '',
        'archive_types': Archive.TYPE_CHOICES,
        'current_type': archive_type or '',
        'archives_verified_no_dispo': archives_verified_no_dispo,
        'pending_batch_count': pending_batch_count,
        'is_batch_ready': is_batch_ready,
    })


@login_required
def disposition_detail(request, pk):
    dispo = get_object_or_404(Disposition, pk=pk)
    return render(request, 'dispositions/detail.html', {'dispo': dispo, 'disposition': dispo})


@login_required
def disposition_edit(request, pk):
    """Edit disposisi tahap 1 (Ketua) — mengisi forwarded_to, note, instruksi."""
    dispo = get_object_or_404(Disposition.objects.select_related('archive'), pk=pk)
    if not request.user.is_pimpinan and not request.user.is_kabid and not request.user.is_superadmin:
        messages.error(request, "Akses ditolak.")
        if hasattr(dispo, 'archive') and dispo.archive:
            return redirect('archives:detail', pk=dispo.archive.pk)
        return redirect('dispositions:list')

    if dispo.status not in ('baru',):
        messages.error(request, "Disposisi Ketua sudah diisi, tidak bisa diedit ulang dari sini.")
        return redirect('dispositions:detail', pk=dispo.pk)

    archive = dispo.archive

    if request.method == 'POST':
        dispo.disposition_number = request.POST.get('disposition_number') or dispo.disposition_number
        dispo.priority = request.POST.get('priority')
        dispo.note = request.POST.get('note', '')
        imp_date = request.POST.get('implementation_date') or request.POST.get('target_date')
        if imp_date:
            dispo.implementation_date = imp_date
        dispo.inst_selesaikan = 'inst_selesaikan' in request.POST
        dispo.inst_untuk_diketahui = 'inst_untuk_diketahui' in request.POST
        dispo.inst_laporkan_hasilnya = 'inst_laporkan_hasilnya' in request.POST
        dispo.inst_koordinasikan = 'inst_koordinasikan' in request.POST

        forwarded_emp_ids = request.POST.getlist('forwarded_to')
        dispo.forwarded_to.set(Employee.objects.filter(id__in=forwarded_emp_ids))

        # Tentukan sender_label Ketua
        dispo.sender_label = _resolve_sender_label(request.user, 'ketua')
        dispo.disposition_stage = 'ketua'
        dispo.status = 'didisposisi_ketua'

        # Update status arsip → terverifikasi sudah didisposisi ketua
        if archive:
            archive.status = 'didisposisikan'
            archive.save(update_fields=['status', 'updated_at'])

        dispo.save()
        AuditService.log_action(request.user, f"Disposisi Ketua: {dispo.disposition_number}", request)
        messages.success(request, f"Disposisi Ketua berhasil dikirim atas nama: {dispo.sender_label}")
        return redirect('dispositions:list')

    employees = Employee.objects.select_related('user_account', 'dept_relation').order_by('full_name')
    generated_disp_no = dispo.disposition_number
    if not generated_disp_no and archive:
        generated_disp_no = NumberingService.get_default_number('disposition', {})

    return render(request, 'dispositions/edit.html', {
        'dispo': dispo,
        'disposition': dispo,
        'archive': archive,
        'employees': employees,
        'generated_disp_no': generated_disp_no,
        'stage': 'ketua',
        'sender_label': _resolve_sender_label(request.user, 'ketua'),
    })


@login_required
def disposition_waka_edit(request, pk):
    """
    Edit disposisi tahap 2 (Waka IV) — update record yang SAMA, nomor disposisi tetap.
    Superadmin mengambil peran Waka IV jika Waka IV belum aksi.
    """
    dispo = get_object_or_404(Disposition.objects.select_related('archive'), pk=pk)

    if not request.user.is_pimpinan and not request.user.is_superadmin:
        messages.error(request, "Hanya Pimpinan atau Superadmin yang bisa melakukan disposisi Waka IV.")
        return redirect('dispositions:list')

    if dispo.status != 'didisposisi_ketua':
        messages.warning(request, "Disposisi Waka IV hanya bisa diisi setelah Disposisi Ketua selesai.")
        return redirect('dispositions:detail', pk=dispo.pk)

    archive = dispo.archive
    waka_label = _resolve_sender_label(request.user, 'waka_iv')

    if request.method == 'POST':
        dispo.waka_note = request.POST.get('waka_note', '')
        imp_date = request.POST.get('implementation_date')
        if imp_date:
            dispo.implementation_date = imp_date
        dispo.waka_inst_selesaikan = 'waka_inst_selesaikan' in request.POST
        dispo.waka_inst_untuk_diketahui = 'waka_inst_untuk_diketahui' in request.POST
        dispo.waka_inst_laporkan_hasilnya = 'waka_inst_laporkan_hasilnya' in request.POST
        dispo.waka_inst_koordinasikan = 'waka_inst_koordinasikan' in request.POST

        waka_fwd_ids = request.POST.getlist('waka_forwarded_to')
        dispo.waka_forwarded_to.set(Employee.objects.filter(id__in=waka_fwd_ids))

        # Update stage ke waka_iv, status ke proses
        dispo.disposition_stage = 'waka_iv'
        dispo.status = 'proses'

        if archive:
            archive.status = 'proses'
            archive.save(update_fields=['status', 'updated_at'])

        dispo.save()

        # Notif WA ke penerima Waka
        try:
            import threading
            def _send_waka_notif():
                file_url = request.build_absolute_uri(archive.file_path.url) if archive and archive.file_path else "—"
                msg = (
                    f"📄 *DISPOSISI WAKA IV - BAZNAS Kab. Tangerang*\n\n"
                    f"*No. Disposisi:* {dispo.disposition_number or '—'}\n"
                    f"*Perihal:* {archive.title if archive else '—'}\n"
                    f"*Dari:* {waka_label}\n"
                    f"*Arahan:* {(dispo.waka_note or '—')[:200]}\n\n"
                    f"🔗 {file_url}\n\nSilakan segera tindak lanjuti."
                )
                for emp in dispo.waka_forwarded_to.all():
                    WhatsAppService.send_notification(user=getattr(emp, 'user_account', None), message=msg, employee=emp)
            threading.Thread(target=_send_waka_notif, daemon=True).start()
        except Exception:
            pass

        AuditService.log_action(request.user, f"Disposisi Waka IV: {dispo.disposition_number}", request)
        messages.success(request, f"Disposisi Waka IV berhasil dikirim atas nama: {waka_label}")
        return redirect('dispositions:list')

    employees = Employee.objects.select_related('user_account', 'dept_relation').order_by('full_name')

    return render(request, 'dispositions/waka_edit.html', {
        'dispo': dispo,
        'disposition': dispo,
        'archive': archive,
        'employees': employees,
        'stage': 'waka_iv',
        'waka_label': waka_label,
    })


@login_required
def disposition_verify(request, pk):
    if request.method != 'POST':
        return redirect('dispositions:list')
    if not request.user.is_pimpinan and not request.user.is_kabid and not request.user.is_superadmin:
        messages.error(request, "Akses ditolak.")
        return redirect('dispositions:list')
    dispo = get_object_or_404(Disposition, pk=pk)

    if dispo.status not in ('baru', 'didisposisi_ketua'):
        messages.warning(request, "Status disposisi tidak memungkinkan verifikasi.")
        return redirect('dispositions:list')

    archive = dispo.archive
    archive.status = 'proses'
    archive.save()

    import threading
    def async_post_verify():
        try:
            file_url = request.build_absolute_uri(archive.file_path.url) if archive.file_path else "Tidak ada berkas"
            inst_list = []
            if dispo.inst_selesaikan: inst_list.append("✅ Selesaikan / Jawab")
            if dispo.inst_untuk_diketahui: inst_list.append("📋 Untuk diketahui / simpan")
            if dispo.inst_laporkan_hasilnya: inst_list.append("📊 Laporkan hasilnya")
            if dispo.inst_koordinasikan: inst_list.append("🤝 Koordinasikan")
            instruksi = "\n".join(inst_list) if inst_list else "—"
            penerima = ', '.join(emp.full_name for emp in dispo.forwarded_to.all()) or "—"
            msg = (
                f"📄 *DISPOSISI BARU - BAZNAS Kab. Tangerang*\n\n"
                f"*No. Arsip:* {archive.archive_number or '—'}\n"
                f"*Perihal:* {archive.title}\n"
                f"*Dari Pimpinan:* {dispo.sender_label or dispo.display_sender_name}\n"
                f"*Penerima:* {penerima}\n"
                f"*Instruksi:*\n{instruksi}\n\n"
                f"🔗 {file_url}\n\nSilakan segera tindak lanjuti."
            )
            forwarded_emps = list(dispo.forwarded_to.all())
            user_map = {u.employee_id: u for u in User.objects.filter(employee__in=forwarded_emps)}
            for emp in forwarded_emps:
                user = user_map.get(emp.pk)
                WhatsAppService.send_notification(user=user, message=msg, employee=emp)
        except Exception:
            pass

    threading.Thread(target=async_post_verify, daemon=True).start()
    AuditService.log_action(request.user, f"Verifikasi Disposisi: {archive.archive_number}", request)
    messages.success(request, "Disposisi berhasil diverifikasi.")
    return redirect('dispositions:list')


@login_required
@pimpinan_required
def disposition_create(request, archive_pk):
    archive = get_object_or_404(Archive, pk=archive_pk)
    existing = Disposition.objects.filter(archive=archive).order_by('-created_at').first()

    if existing:
        if existing.disposition_stage == 'ketua' and existing.status == 'didisposisi_ketua':
            return redirect('dispositions:waka_edit', pk=existing.pk)
        elif existing.status in ('proses', 'selesai'):
            messages.info(request, "Dokumen ini sudah melalui kedua tahap disposisi.")
            return redirect('dispositions:detail', pk=existing.pk)
        else:
            return redirect('dispositions:edit', pk=existing.pk)

    # Otomatis kunci sender_label Ketua BAZNAS saat pembuatan disposisi baru
    dispo = Disposition.objects.create(
        archive=archive,
        sender=request.user,
        sender_label=_resolve_sender_label(request.user, 'ketua'),
        disposition_stage='ketua',
        status='baru',
    )
    messages.success(request, f"Lembar disposisi untuk '{archive.title}' berhasil dibuat. Silakan isi instruksi Ketua.")
    return redirect('dispositions:edit', pk=dispo.pk)


@login_required
@pimpinan_required
def disposition_delete(request, pk):
    dispo = get_object_or_404(Disposition, pk=pk)
    if request.method == 'POST':
        dispo.delete()
        messages.success(request, "Disposisi berhasil dihapus.")
    return redirect('dispositions:list')


@login_required
def disposition_print(request):
    ids = request.GET.getlist('ids')
    if not ids:
        messages.error(request, "Pilih disposisi yang ingin dicetak.")
        return redirect('dispositions:list')
    dispositions = Disposition.objects.filter(id__in=ids).select_related('archive', 'sender').prefetch_related('forwarded_to', 'waka_forwarded_to')
    return render(request, 'dispositions/print.html', {'dispositions': dispositions})


@login_required
def disposition_staff_followup(request, pk):
    dispo = get_object_or_404(Disposition, pk=pk)
    return redirect('reports:create', dispo_pk=dispo.pk)


@login_required
@pimpinan_required
def disposition_batch_notify(request):
    from services.notifications.notification_service import NotificationService
    if request.method == 'POST':
        result = NotificationService.send_batch_disposition_notifications(request.user)
        messages.success(request, f"Berhasil menyebarkan {result['sent_count']} Notifikasi WhatsApp Disposisi secara massal.")
    return redirect('dispositions:list')