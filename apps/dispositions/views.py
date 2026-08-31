from datetime import datetime, time as dt_time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
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
from notifications.tasks import task_trigger_disposisi_notifications



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
    active_pov = request.session.get('active_pov')
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)

    # SEMUA akun pengguna (FO, Kabid IV, Ketua, Waka IV, Waka II, Kabid II, Pelaksana/Staf, dan Superadmin)
    # dapat melihat seluruh daftar disposisi yang sedang berjalan di SIMAP.
    qs = Disposition.objects.select_related('archive', 'sender').prefetch_related('forwarded_to', 'waka_forwarded_to').exclude(status='baru', note='').all()

    # Jika pengguna memicu filter spesifik Waka II / Kabid II
    if is_waka_or_kabid_2 and request.GET.get('filter') == 'bidang2':
        bantuan_q = Q(archive__category__name__icontains='bantuan') | Q(archive__title__icontains='bantuan') | Q(archive__subject__icontains='bantuan')
        if current_emp:
            qs = qs.filter(Q(forwarded_to=current_emp) | Q(waka_forwarded_to=current_emp) | bantuan_q)
        else:
            qs = qs.filter(bantuan_q)

    qs = qs.distinct().order_by('-created_at')

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

    # Antrean Dokumen Terverifikasi yang belum dibuatkan disposisi HANYA untuk Superadmin, Ketua BAZNAS, dan Kabid IV (SDM/FO)
    show_pending_no_dispo = (
        getattr(request.user, 'is_superadmin', False) or
        getattr(request.user, 'is_superuser', False) or
        getattr(request.user, 'is_ketua', False) or
        getattr(request.user, 'is_kabid_4', False) or
        getattr(request.user, 'is_waka_4', False) or
        getattr(request.user, 'is_sdm', False) or
        getattr(request.user, 'is_fo', False) or
        (active_pov in ['admin', 'superadmin', 'ketua', 'waka_4', 'kabid_4', 'sdm', 'fo'])
    )

    if show_pending_no_dispo:
        archives_verified_no_dispo = Archive.objects.filter(
            Q(status__in=['terverifikasi', 'disposisi_pimpinan', 'baru']) | Q(verified_by_kabid=True)
        ).filter(
            Q(dispositions__isnull=True) | Q(dispositions__status='baru', dispositions__note='')
        ).exclude(
            status__in=['didisposisikan', 'proses', 'sudah_ditugaskan', 'dalam_survei', 'telah_disalurkan', 'selesai', 'ditolak']
        ).select_related('category', 'uploaded_by').distinct().order_by('-updated_at')
        if archive_type:
            archives_verified_no_dispo = archives_verified_no_dispo.filter(archive_type=archive_type)
    else:
        archives_verified_no_dispo = Archive.objects.none()

    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    from services.notifications.notification_service import NotificationService
    pending_batch_count = NotificationService.get_pending_disposition_count()
    is_batch_ready = NotificationService.is_batch_ready()

    dispo_success_id = request.GET.get('dispo_success_id')
    dispo_success_obj = None
    if dispo_success_id:
        dispo_success_obj = Disposition.objects.filter(pk=dispo_success_id).select_related('archive').first()

    for d in page_obj:
        d.item_perms = request.user.get_disposition_permissions(active_pov, dispo=d)
        d.is_targeted_to_user_bidang = request.user.is_dispo_targeted_to_bidang(d, active_pov=active_pov)

    dispo_perms = request.user.get_disposition_permissions(active_pov)

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
        'dispo_success_obj': dispo_success_obj,
        'dispo_perms': dispo_perms,
    })


@login_required
def disposition_detail(request, pk):
    dispo = get_object_or_404(Disposition, pk=pk)
    active_pov = request.session.get('active_pov')
    dispo.item_perms = request.user.get_disposition_permissions(active_pov, dispo=dispo)
    return render(request, 'dispositions/detail.html', {'dispo': dispo, 'disposition': dispo})


@login_required
def disposition_edit(request, pk):
    """Edit disposisi tahap 1 (Ketua) — mengisi forwarded_to, note, instruksi."""
    dispo = get_object_or_404(Disposition.objects.select_related('archive'), pk=pk)
    active_pov = request.session.get('active_pov')
    perms = request.user.get_disposition_permissions(active_pov, dispo=dispo)
    if not perms['can_edit_dispo']:
        messages.error(request, "Akses ditolak. Disposisi ini tidak ditujukan ke Bidang Anda, sehingga Anda hanya memiliki hak membaca (Read Only).")
        return redirect('dispositions:list')

    # Catatan: Pengguna (Pimpinan, Kabid IV, FO, Superadmin) dapat melakukan edit/perbaikan kapan saja jika ada kesalahan disposisi
    archive = dispo.archive

    if request.method == 'POST':
        with transaction.atomic():
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
            forwarded_emps = Employee.objects.filter(id__in=forwarded_emp_ids)
            dispo.forwarded_to.set(forwarded_emps)

            # Cek apakah penerima disposisi Ketua mencakup Waka IV / Bidang IV
            has_waka_4_target = False
            for emp in forwarded_emps:
                pos_lower = (emp.position or '').lower()
                lead_type = getattr(emp, 'leadership_type', '')
                if lead_type == 'waka_4' or any(kw in pos_lower for kw in ['waka iv', 'waka 4', 'wakil ketua iv', 'wakil ketua 4', 'bidang iv', 'bidang 4']):
                    has_waka_4_target = True
                    break

            # Tentukan sender_label Ketua
            dispo.sender_label = _resolve_sender_label(request.user, 'ketua')

            # Logika Cerdas: Jika Disposisi Ketua di-edit dan sebelumnya sudah ada Disposisi Waka IV
            had_waka_dispo = bool(dispo.waka_note or dispo.waka_forwarded_to.exists() or dispo.disposition_stage == 'waka_iv')
            if had_waka_dispo:
                if not has_waka_4_target:
                    # Ketua mendisposisikan langsung ke Waka/Bidang lain (misal Waka III / Waka II) tanpa melalui Waka IV -> Batalkan/Hapus disposisi Waka IV lama
                    dispo.waka_note = ''
                    dispo.waka_forwarded_to.clear()
                    dispo.waka_inst_selesaikan = False
                    dispo.waka_inst_untuk_diketahui = False
                    dispo.waka_inst_laporkan_hasilnya = False
                    dispo.waka_inst_koordinasikan = False
                    dispo.disposition_stage = 'ketua'
                    dispo.status = 'didisposisi_ketua'
                    messages.info(request, "Disposisi Ketua diperbarui ke unit lain. Disposisi Waka IV sebelumnya otomatis dibatalkan/dihapus.")
                else:
                    # Waka IV masih menjadi tujuan, reset status ke 'didisposisi_ketua' agar Waka IV dapat memperbarui arahan
                    dispo.disposition_stage = 'ketua'
                    dispo.status = 'didisposisi_ketua'
                    messages.info(request, "Disposisi Ketua diperbarui. Disposisi Waka IV dikembalikan ke status 'Menunggu Waka IV' untuk penyesuaian.")
            else:
                if dispo.status == 'baru':
                    dispo.disposition_stage = 'ketua'
                    dispo.status = 'didisposisi_ketua'

            if archive:
                archive.status = 'didisposisikan'
                archive.save(update_fields=['status', 'updated_at'])

            dispo.save()

            # Otomatis tandai notifikasi pengisian disposisi ini sebagai sudah dibaca ('read')
            from notifications.models import Notification
            if archive:
                Notification.objects.filter(
                    category='disposition',
                    link_url=f"/dispositions/{archive.pk}/create/"
                ).update(status='read')

            # Kirim notifikasi sistem lonceng & bantuan ke Waka & Kabid bidang terkait
            from services.notifications.notification_service import NotificationService
            NotificationService.notify_bidang2_for_bantuan_document(archive, dispo)
            NotificationService.send_disposition_system_notifications(dispo, stage='ketua', actor=request.user)

            dispo_pk_val = dispo.pk
            transaction.on_commit(lambda: task_trigger_disposisi_notifications.delay(dispo_pk_val))

        AuditService.log_action(request.user, f"Edit Disposisi Ketua: {dispo.disposition_number}", request)
        messages.success(request, f"Disposisi Ketua ({dispo.disposition_number}) berhasil diperbarui.")
        return redirect(f"/dispositions/?dispo_success_id={dispo.pk}")


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
    Edit disposisi tahap 2 (Waka IV / Waka Bidang) — update record yang SAMA, nomor disposisi tetap.
    Superadmin mengambil peran Waka IV jika Waka IV belum aksi.
    """
    dispo = get_object_or_404(Disposition.objects.select_related('archive'), pk=pk)

    active_pov = request.session.get('active_pov')
    perms = request.user.get_disposition_permissions(active_pov, dispo=dispo)
    if not perms['can_edit_waka_dispo']:
        messages.error(request, "Akses ditolak. Disposisi Tahap 2 hanya dapat dilakukan oleh Waka IV, Kabid IV, Superadmin, atau Waka/Kabid dari Bidang yang menerima disposisi ini.")
        return redirect('dispositions:list')

    if dispo.status == 'baru':
        messages.warning(request, "Disposisi Waka IV hanya bisa diisi setelah Disposisi Ketua dibuat.")
        return redirect('dispositions:detail', pk=dispo.pk)

    archive = dispo.archive
    waka_label = _resolve_sender_label(request.user, 'waka_iv')

    if request.method == 'POST':
        with transaction.atomic():
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

            # Update stage ke waka_iv, status ke proses jika sebelumnya baru didisposisi ketua
            if dispo.status == 'didisposisi_ketua':
                dispo.disposition_stage = 'waka_iv'
                dispo.status = 'proses'

                if archive:
                    archive.status = 'proses'
                    archive.save(update_fields=['status', 'updated_at'])

            dispo.save()

            # Kirim notifikasi sistem lonceng & bantuan ke Waka & Kabid bidang terkait
            from services.notifications.notification_service import NotificationService
            NotificationService.notify_bidang2_for_bantuan_document(archive, dispo)
            NotificationService.send_disposition_system_notifications(dispo, stage='waka_iv', actor=request.user)

            dispo_pk_val = dispo.pk
            transaction.on_commit(lambda: task_trigger_disposisi_notifications.delay(dispo_pk_val))

        AuditService.log_action(request.user, f"Disposisi Waka IV: {dispo.disposition_number}", request)
        messages.success(request, f"Disposisi Waka IV berhasil dikirim atas nama: {waka_label}")
        return redirect(f"/dispositions/?dispo_success_id={dispo.pk}")

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

    with transaction.atomic():
        archive = dispo.archive
        archive.status = 'proses'
        archive.save()

        dispo_pk_val = dispo.pk
        transaction.on_commit(lambda: task_trigger_disposisi_notifications.delay(dispo_pk_val))

    AuditService.log_action(request.user, f"Verifikasi Disposisi: {archive.archive_number}", request)
    messages.success(request, "Disposisi berhasil diverifikasi.")
    return redirect('dispositions:list')


@login_required
def disposition_create(request, archive_pk):
    archive = get_object_or_404(Archive, pk=archive_pk)

    # Tandai notifikasi terkait sebagai 'read' untuk user ini saat diakses
    from notifications.models import Notification
    Notification.objects.filter(user=request.user, link_url=f"/dispositions/{archive.pk}/create/").update(status='read')

    active_pov = request.session.get('active_pov')
    perms = request.user.get_disposition_permissions(active_pov)
    if not perms['can_create_dispo']:
        messages.error(request, "Akses ditolak. Peran Anda (Waka I/II/III, Kabid I/II/III, Staf) hanya memiliki hak membaca (Read Only).")
        return redirect('archives:detail', pk=archive_pk)

    existing = Disposition.objects.filter(archive=archive).order_by('-created_at').first()

    if existing:
        if existing.disposition_stage == 'ketua' and existing.status == 'didisposisi_ketua':
            return redirect('dispositions:waka_edit', pk=existing.pk)
        elif existing.status in ('proses', 'selesai'):
            messages.info(request, "Dokumen ini sudah melalui tahap disposisi.")
            return redirect('dispositions:detail', pk=existing.pk)
        elif existing.note or existing.forwarded_to.exists():
            return redirect('dispositions:edit', pk=existing.pk)

    # PROSES FORM DISPOSISI KETUA SAAT USER MENEKAN SIMPAN (POST)
    if request.method == 'POST':
        with transaction.atomic():
            from services.archives.numbering_service import NumberingService
            dispo_number = request.POST.get('disposition_number') or NumberingService.generate_number('disposition')
            
            if not existing:
                dispo = Disposition.objects.create(
                    archive=archive,
                    sender=request.user,
                    disposition_number=dispo_number,
                    sender_label=_resolve_sender_label(request.user, 'ketua'),
                    disposition_stage='ketua',
                    status='didisposisi_ketua',
                )
            else:
                dispo = existing
                dispo.disposition_number = dispo_number or dispo.disposition_number
                dispo.status = 'didisposisi_ketua'

            dispo.priority = request.POST.get('priority', 'biasa')
            dispo.note = request.POST.get('note', '')
            imp_date = request.POST.get('target_date') or request.POST.get('implementation_date')
            if imp_date:
                dispo.implementation_date = imp_date
            dispo.inst_selesaikan = 'inst_selesaikan' in request.POST
            dispo.inst_untuk_diketahui = 'inst_untuk_diketahui' in request.POST
            dispo.inst_laporkan_hasilnya = 'inst_laporkan_hasilnya' in request.POST
            dispo.inst_koordinasikan = 'inst_koordinasikan' in request.POST

            forwarded_emp_ids = request.POST.getlist('forwarded_to')
            dispo.forwarded_to.set(Employee.objects.filter(id__in=forwarded_emp_ids))
            dispo.save()

            archive.status = 'didisposisikan'
            archive.save(update_fields=['status', 'updated_at'])

            # Kirim notifikasi lonceng ke Waka & Kabid bidang terkait
            from services.notifications.notification_service import NotificationService
            NotificationService.send_disposition_system_notifications(dispo, stage='ketua', actor=request.user)

            dispo_pk_val = dispo.pk
            transaction.on_commit(lambda: task_trigger_disposisi_notifications.delay(dispo_pk_val))

        AuditService.log_action(request.user, f"Buat Disposisi Ketua: {dispo.disposition_number}", request)
        messages.success(request, f"Disposisi Ketua ({dispo.disposition_number}) berhasil disimpan.")
        return redirect(f"/dispositions/?dispo_success_id={dispo.pk}")


    # JIKA HANYA TAMPILKAN FORM (GET): TIDAK SIMPAN DISPOSISI DRAFT AGAR STATUS ARSIP TIDAK BERUBAH JIKA BATAL
    employees = Employee.objects.select_related('user_account', 'dept_relation').order_by('full_name')
    from services.archives.numbering_service import NumberingService
    generated_disp_no = NumberingService.get_default_number('disposition', {})

    return render(request, 'dispositions/edit.html', {
        'dispo': existing,
        'disposition': existing,
        'archive': archive,
        'employees': employees,
        'generated_disp_no': generated_disp_no,
        'stage': 'ketua',
        'sender_label': _resolve_sender_label(request.user, 'ketua'),
    })


@login_required
def disposition_delete(request, pk):
    dispo = get_object_or_404(Disposition, pk=pk)
    active_pov = request.session.get('active_pov')
    perms = request.user.get_disposition_permissions(active_pov)
    if not perms['can_delete_dispo']:
        messages.error(request, "Akses ditolak. Anda tidak memiliki wewenang untuk menghapus disposisi ini.")
        return redirect('dispositions:list')

    num = dispo.disposition_number or f"ID-{dispo.pk}"
    AuditService.log_action(request.user, f"Hapus Disposisi: {num}", request)
    dispo.delete()
    messages.success(request, f"Lembar Disposisi {num} berhasil dihapus.")
    return redirect('dispositions:list')


@login_required
def disposition_print(request):
    blank = request.GET.get('blank') == '1'
    archive_id = request.GET.get('archive_id')
    ids = request.GET.getlist('ids')

    if blank:
        archive = get_object_or_404(Archive, pk=archive_id) if archive_id else None
        return render(request, 'dispositions/print_blank.html', {
            'archive': archive,
            'today': timezone.now(),
        })

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