import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from openpyxl import Workbook

from users.models import User
from users.decorators import sdm_required, pimpinan_required
from .models import Archive, Category
from dispositions.models import Disposition
from repositories.archives.archive_repository import ArchiveRepository
from services.archives.archive_service import ArchiveService
from services.archives.numbering_service import NumberingService
from services.integrations.gateway_service import WhatsAppService, GoogleIntegrationService
from services.audit_logs.audit_service import AuditService

# Initialize Service
archive_repo = ArchiveRepository()
archive_service = ArchiveService(archive_repo)

def can_manage_archive(request):
    """
    Menentukan apakah user memiliki hak akses melakukan aksi/tindakan pada arsip
    (Upload, Edit, Verifikasi Kabid IV, Teruskan ke Ketua, Penolakan, dsb):
    HANYA Waka IV, Kabid IV, Front Office (Staff SDM Bidang IV), dan Superadmin IT.
    Pengguna/bidang lainnya berstatus READ-ONLY.
    """
    user = request.user
    if not user.is_authenticated:
        return False

    active_pov = request.session.get('active_pov')
    if active_pov:
        # Dalam mode POV, hanya pov Waka IV, Kabid IV, Front Office / SDM, dan Admin yang dapat beraksi
        return active_pov in ['waka_4', 'kabid_4', 'sdm', 'front_office', 'fo', 'admin']

    if getattr(user, 'is_superadmin', False) or getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'admin':
        return True

    if getattr(user, 'is_waka_4', False) or getattr(user, 'is_kabid_4', False):
        return True

    if getattr(user, 'is_sdm', False):
        return True

    emp = getattr(user, 'employee', None)
    if emp and emp.dept_relation:
        dept_name = (emp.dept_relation.name or "").lower()
        if any(k in dept_name for k in ['front office', 'resepsionis', 'sekretariat', 'sdm', 'administrasi', 'bidang iv', 'bidang 4']):
            return True

    return False

def can_view_arsip_sdm(request):
    """
    Seluruh akun / seluruh bidang yang login dapat melihat (read) modul manajemen arsip.
    """
    return request.user.is_authenticated

def can_upload_archive(request):
    """
    Menentukan apakah user berhak mengunggah arsip/dokumen baru:
    - Front Office / Resepsionis / Staf SDM
    - Kabid IV (Kepala Bidang IV - Administrasi, SDM & Umum)
    - Superadmin IT
    """
    user = request.user
    if not user.is_authenticated:
        return False

    active_pov = request.session.get('active_pov')
    if active_pov:
        return active_pov in ['sdm', 'front_office', 'fo', 'admin', 'kabid_4']
        
    if getattr(user, 'is_superadmin', False) or getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'admin':
        return True
        
    # Kabid IV berhak mengunggah arsip
    if getattr(user, 'is_kabid_4', False):
        return True
        
    # Pimpinan & Kabid lainnya (selain Kabid 4) TIDAK BOLEH upload
    if getattr(user, 'is_pimpinan', False) or (getattr(user, 'is_kabid', False) and not getattr(user, 'is_kabid_4', False)) or getattr(user, 'is_waka_4', False):
        return False
        
    emp = getattr(user, 'employee', None)
    if emp and emp.dept_relation:
        dept_name = (emp.dept_relation.name or "").lower()
        if any(k in dept_name for k in ['front office', 'resepsionis', 'sekretariat', 'sdm', 'administrasi', 'bidang iv', 'bidang 4']):
            return True
            
    return getattr(user, 'is_sdm', False)


@login_required
def archive_list(request):
    """
    Archive list with client-side DataTables handling.
    Dapat diakses oleh seluruh akun / seluruh bidang (Read-Only bagi non-Bidang IV/Admin).
    """
    archives = Archive.objects.all().select_related('category', 'uploaded_by').order_by('-created_at')

    status_filter = request.GET.get('status', 'all')
    if status_filter == 'perlu_verifikasi':
        archives = archives.filter(Q(verified_by_kabid=False) | Q(status__in=['baru', 'pending', 'masuk', 'verifikasi_kabid'])).exclude(status__in=['selesai', 'ditolak'])
    elif status_filter == 'belum_disposition':
        archives = archives.filter(
            Q(status__in=['terverifikasi', 'disposisi_pimpinan', 'meja_waka4', 'disposisi_waka', 'baru']) |
            Q(dispositions__isnull=True) |
            Q(dispositions__status='baru', dispositions__note='')
        ).exclude(status__in=['didisposisikan', 'proses', 'sudah_ditugaskan', 'dalam_survei', 'telah_disalurkan', 'selesai']).distinct()
    elif status_filter == 'sudah_disposition':
        archives = archives.filter(
            Q(status__in=['didisposisikan', 'proses', 'sudah_ditugaskan', 'dalam_survei', 'telah_disalurkan', 'selesai']) |
            Q(dispositions__status__in=['didisposisi_ketua', 'proses', 'selesai'])
        ).exclude(status__in=['baru', 'terverifikasi', 'disposisi_pimpinan'], dispositions__isnull=True).distinct()

    archive_type_filter = request.GET.get('type')
    if archive_type_filter:
        archives = archives.filter(archive_type=archive_type_filter)

    # Khusus Waka II & Kabid II: hanya tampilkan Dokumen Bantuan Mustahik yang SUDAH diverifikasi Kabid IV
    active_pov = request.session.get('active_pov')
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)
    if is_waka_or_kabid_2:
        from services.workflows.workflow_engine import WorkflowEngine
        archives = archives.filter(
            Q(verified_by_kabid=True) | ~Q(status='baru')
        )
        bantuan_ids = [arc.id for arc in archives if WorkflowEngine.is_bantuan(arc)]
        archives = archives.filter(id__in=bantuan_ids)

    # Handle Export
    if 'export' in request.GET:
        wb = Workbook()
        ws = wb.active
        ws.title = "Rekap Arsip SDM"
        ws.append(['No. Arsip', 'Jenis', 'Tanggal', 'Judul/Perihal', 'Pengirim/Penerima', 'Kategori', 'Status'])
        for arc in archives:
            ws.append([
                arc.archive_number or 'DRAFT',
                arc.get_archive_type_display(),
                arc.letter_date.strftime('%d/%m/%Y') if arc.letter_date else '-',
                arc.title,
                arc.sender_receiver or '-',
                arc.category.name,
                arc.status.upper()
            ])
        
        AuditService.log_action(request.user, "Ekspor Data Arsip ke Excel", request)
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=Rekap_Arsip_{timezone.now().strftime("%Y%m%d")}.xlsx'
        wb.save(response)
        return response

    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(archives, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    uploaded_id = request.GET.get('uploaded_id') or request.GET.get('success_id')
    uploaded_archive = None
    if uploaded_id:
        uploaded_archive = Archive.objects.filter(pk=uploaded_id).first()

    can_manage = can_manage_archive(request)

    return render(request, 'archives/list.html', {
        'page_obj': page_obj,
        'archives': page_obj,
        'archive_types': Archive.TYPE_CHOICES,
        'current_type': archive_type_filter or '',
        'status_filter': status_filter,
        'is_waka_or_kabid_2': is_waka_or_kabid_2,
        'can_upload': can_upload_archive(request),
        'can_manage': can_manage,
        'uploaded_archive': uploaded_archive,
    })

@login_required
def archive_quick_detail(request, pk):
    """View HTMX/AJAX untuk Slide-Over Drawer quick view data arsip."""
    archive = get_object_or_404(
        Archive.objects.select_related('category', 'uploaded_by').prefetch_related('dispositions', 'dispositions__sender'),
        pk=pk
    )
    return render(request, 'archives/quick_detail.html', {
        'archive': archive,
        'can_manage': can_manage_archive(request)
    })


@login_required
def archive_upload(request):
    if not can_view_arsip_sdm(request):
        messages.error(request, "Modul Arsip SDM hanya dapat diakses oleh Bidang IV (Administrasi, SDM & Umum) dan Superadmin IT.")
        return redirect('users:dashboard')

    if not can_upload_archive(request):
        messages.error(request, "Hak akses mengunggah arsip/dokumen baru hanya dimiliki oleh Front Office / Resepsionis, Kabid IV, dan Superadmin IT.")
        return redirect('archives:list')

    if request.method == 'POST':
        archive_type = request.POST.get('archive_type')
        archive_number_input = request.POST.get('archive_number', '').strip()
        letter_date = request.POST.get('letter_date')
        sender_receiver = request.POST.get('sender_receiver')
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        file = request.FILES.get('file_path')

        errors = []
        if not archive_type:
            errors.append("Jenis dokumen harus dipilih.")
        if not letter_date:
            errors.append("Tanggal surat harus diisi.")
        if not sender_receiver:
            errors.append("Pengirim / Penerima harus diisi.")
        if not title:
            errors.append("Perihal / Judul dokumen harus diisi.")
        if not category_id:
            errors.append("Kategori bidang harus dipilih.")
        if not file:
            errors.append("Berkas digital harus diunggah.")

        if errors:
            for err in errors:
                messages.error(request, err)
            categories = Category.objects.all()
            selected_type = archive_type or 'surat_masuk'
            if selected_type not in dict(Archive.TYPE_CHOICES):
                selected_type = 'surat_masuk'
            default_by_type = {}
            for code, _ in Archive.TYPE_CHOICES:
                default_by_type[code] = NumberingService.get_default_number('archive', {'archive_type': code})
            return render(request, 'archives/upload.html', {
                'archive_types': Archive.TYPE_CHOICES,
                'categories': categories,
                'selected_type': selected_type,
                'default_archive_number': default_by_type.get(selected_type, ''),
                'default_by_type_json': json.dumps(default_by_type),
                'title_value': title,
                'sender_receiver_value': sender_receiver,
                'letter_date_value': letter_date,
            })

        # Utamakan nomor dari input form JS, jika dikosongkan baru generate otomatis
        if archive_number_input:
            archive_number = archive_number_input
        else:
            archive_number = NumberingService.generate_number(
                "archive",
                {
                    "archive_type": archive_type
                }
            )
        
        auto_verify = request.POST.get('auto_verify') == 'on' or request.POST.get('auto_verify') == 'true'

        initial_status = "disposisi_pimpinan" if auto_verify else "baru"
        
        address = request.POST.get('address', '').strip()
        category = get_object_or_404(Category, id=category_id)
        
        from django.utils.dateparse import parse_date
        letter_date_val = parse_date(letter_date) if letter_date else timezone.now().date()
        received_date_input = request.POST.get('received_date')
        received_date_val = parse_date(received_date_input) if received_date_input else timezone.now().date()

        archive = Archive.objects.create(
            archive_type=archive_type,
            archive_number=archive_number,
            letter_date=letter_date_val,
            received_date=received_date_val,
            sender=sender_receiver,
            address=address,
            title=title,
            category=category,
            description=description,
            uploaded_by=request.user,
            file_path=file,
            status=initial_status,
            verified_by_kabid=True if (auto_verify or initial_status in ['disposisi_pimpinan', 'terverifikasi']) else False,
        )

        AuditService.log_action(request.user, f"Upload Arsip Baru ({initial_status}): {title}", request)

        # Notifikasi ke Ketua BAZNAS & Pimpinan untuk mengisi disposisi jika status terverifikasi/disposisi_pimpinan
        if initial_status in ['disposisi_pimpinan', 'terverifikasi'] or auto_verify:
            from notifications.models import Notification
            from django.db.models import Q
            ketua_users = User.objects.filter(
                Q(username__icontains='ketua') | 
                Q(role='ketua') | 
                Q(employee__position__icontains='ketua') | 
                Q(employee__leadership_type='ketua') | 
                Q(role='pimpinan') | 
                Q(is_superuser=True)
            ).distinct()
            for k_user in ketua_users:
                Notification.create_system_notif(
                    user=k_user,
                    title="📋 Disposisi Baru Perlu Diisi",
                    message=f"Dokumen '{archive.title}' siap diisi disposisinya oleh Ketua BAZNAS.",
                    link_url=f"/dispositions/{archive.pk}/create/",
                    category="disposition"
                )

            # Notifikasi ke Waka II & Kabid II jika dokumen bersifat bantuan
            from services.notifications.notification_service import NotificationService
            NotificationService.notify_bidang2_for_bantuan_document(archive)

        if auto_verify:
            messages.success(request, "Dokumen berhasil diunggah & terverifikasi (Siap Disposisi Ketua BAZNAS).")
        else:
            messages.success(request, "Dokumen berhasil diunggah dengan status BARU.")
        return redirect(f"/archives/?uploaded_id={archive.pk}")
    
    # --- Handling GET Method ---
    categories = Category.objects.all()

    selected_type = request.GET.get('type', 'surat_masuk')
    if selected_type not in dict(Archive.TYPE_CHOICES):
        selected_type = 'surat_masuk'

    default_by_type = {}
    for code, _ in Archive.TYPE_CHOICES:
        default_by_type[code] = NumberingService.get_default_number('archive', {'archive_type': code})

    success_id = request.GET.get('success_id')
    success_archive = None
    if success_id:
        success_archive = Archive.objects.filter(pk=success_id).first()

    return render(request, 'archives/upload.html', {
        'archive_types': Archive.TYPE_CHOICES,
        'categories': categories,
        'selected_type': selected_type,
        'default_archive_number': default_by_type.get(selected_type, ''),
        'default_by_type_json': json.dumps(default_by_type),
        'success_archive': success_archive,
    })

@login_required
def archive_print_disposition(request, pk):
    """
    Mencetak Lembar Disposisi Fisik BAZNAS langsung dari Arsip (Front Office / FO).
    Otomatis memverifikasi arsip jika masih berstatus 'baru' dan menyiapkan nomor agenda disposisi.
    """
    archive = get_object_or_404(Archive, pk=pk)

    # Otomatis verifikasi & teruskan jika masih baru
    if archive.status in ['baru', 'pending', 'masuk']:
        archive.status = 'disposisi_pimpinan'
        archive.verified_by_kabid = True
        archive.save(update_fields=['status', 'verified_by_kabid', 'updated_at'])

    # Ambil atau buat disposisi draf (agar memiliki Nomor Agenda Resmi)
    dispo = archive.latest_dispo
    if not dispo:
        dispo_number = NumberingService.generate_number('disposition')
        from dispositions.models import Disposition
        dispo = Disposition.objects.create(
            archive=archive,
            sender=request.user,
            disposition_number=dispo_number,
            status='baru',
            disposition_stage='ketua',
            note=''
        )
        
    # Memastikan notifikasi sistem terkirim ke Ketua BAZNAS & Pimpinan untuk mengisi disposisi
    from notifications.models import Notification
    from django.db.models import Q
    ketua_users = User.objects.filter(
        Q(username__icontains='ketua') | 
        Q(role='ketua') | 
        Q(employee__position__icontains='ketua') | 
        Q(employee__leadership_type='ketua') | 
        Q(role='pimpinan') | 
        Q(is_superuser=True)
    ).distinct()
    for k_user in ketua_users:
        if not Notification.objects.filter(user=k_user, link_url=f"/dispositions/{archive.pk}/create/").exists():
            Notification.create_system_notif(
                user=k_user,
                title="📋 Disposisi Baru Perlu Diisi",
                message=f"Dokumen '{archive.title}' siap diisi disposisinya oleh Ketua BAZNAS.",
                link_url=f"/dispositions/{archive.pk}/create/",
                category="disposition"
            )

    return render(request, 'dispositions/print.html', {
        'dispositions': [dispo],
        'archive': archive,
    })

@login_required
def archive_reject(request, pk):
    """
    Penolakan Dokumen: Hanya Waka IV, Kabid IV, Front Office, dan Superadmin.
    """
    if not can_manage_archive(request):
        messages.error(request, "Akses ditolak. Aksi penolakan dokumen hanya dapat dilakukan oleh Waka IV, Kabid IV, Front Office, dan Superadmin IT.")
        return redirect('archives:detail', pk=pk)
    if request.method == 'POST':
        archive = get_object_or_404(Archive, pk=pk)
        if archive.status == 'baru':
            archive.status = 'ditolak'
            archive.rejection_note = request.POST.get('rejection_note', '')
            archive.save()
            AuditService.log_action(request.user, f"Tolak Dokumen: {archive.archive_number}", request)
            messages.success(request, f"Dokumen {archive.archive_number or archive.title} ditolak.")
        return redirect('archives:detail', pk=pk)
    return redirect('archives:list')

@login_required
def archive_edit(request, pk):
    """
    Allow editing file if status is 'baru'.
    Hanya Waka IV, Kabid IV, Front Office, dan Superadmin.
    """
    if not can_manage_archive(request):
        messages.error(request, "Akses ditolak. Aksi edit data arsip hanya dapat dilakukan oleh Waka IV, Kabid IV, Front Office, dan Superadmin IT.")
        return redirect('archives:detail', pk=pk)

    archive = get_object_or_404(Archive, pk=pk)
    if archive.status != 'baru' and not request.user.is_superadmin:
        messages.error(request, "Dokumen sudah diproses, tidak dapat diubah.")
        return redirect('archives:detail', pk=pk)
        
    if request.method == 'POST':
        archive.archive_type = request.POST.get('archive_type')
        archive.letter_date = request.POST.get('letter_date')
        archive.sender = request.POST.get('sender_receiver')
        archive.address = request.POST.get('address', '').strip()
        archive.title = request.POST.get('title')
        category_id = request.POST.get('category')
        archive.category = get_object_or_404(Category, id=category_id)
        archive.description = request.POST.get('description')
        
        if request.FILES.get('file_path'):
            archive.file_path = request.FILES.get('file_path')
            
        archive.save()
        messages.success(request, "Dokumen berhasil diperbarui.")
        return redirect('archives:detail', pk=pk)
        
    categories = Category.objects.all()
    return render(request, 'archives/edit.html', {
        'archive': archive, 
        'categories': categories, 
        'archive_types': Archive.TYPE_CHOICES
    })

def archive_detail(request, pk):
    """
    Detail Arsip & Berkas Digital.
    Dapat diakses oleh seluruh akun / seluruh bidang (Read-Only bagi non-Bidang IV/Admin).
    Jika dibuka oleh publik/tanpa login, otomatis diarahkan ke halaman Tracking Alur BPMN.
    """
    if not request.user.is_authenticated:
        return redirect('archives:public_track', pk=pk)

    from services.workflows.workflow_engine import WorkflowEngine
    from services.timeline.timeline_service import TimelineService
    archive = get_object_or_404(
        Archive.objects.select_related('uploaded_by', 'category')
        .prefetch_related(
            'dispositions__sender__employee',
            'dispositions__forwarded_to',
            'dispositions__waka_forwarded_to',
            'dispositions__surat_tugas',
            'dispositions__sppd_list',
            'dispositions__report'
        ),
        pk=pk
    )

    can_manage = can_manage_archive(request)

    # Handle Upload Berkas Digital Langsung di Halaman Detail (Hanya Waka IV, Kabid IV, FO, Superadmin)
    if request.method == 'POST' and request.FILES.get('file_path'):
        if not can_manage:
            messages.error(request, "Akses ditolak. Mengunggah atau mengganti berkas digital hanya dapat dilakukan oleh Waka IV, Kabid IV, Front Office, dan Superadmin IT.")
            return redirect('archives:detail', pk=pk)

        archive.file_path = request.FILES.get('file_path')
        archive.save(update_fields=['file_path', 'updated_at'])
        AuditService.log_action(request.user, f"Upload Berkas Digital: {archive.archive_number or archive.title}", request)
        messages.success(request, "Berkas digital (PDF/Gambar) berhasil diunggah ke dokumen ini.")
        return redirect('archives:detail', pk=pk)

    workflow_info = WorkflowEngine.get_workflow_info(archive)
    timeline_items = TimelineService.get_document_timeline(archive)
    
    dispositions = list(archive.dispositions.all())
    latest_dispo = dispositions[-1] if dispositions else None
    
    from surat_tugas.models import SuratTugas
    from sppd_service.models import SPPD

    surat_tugas_qs = SuratTugas.objects.filter(disposition__archive=archive).order_by('created_at')
    latest_st = surat_tugas_qs.last()

    sppd_qs = SPPD.objects.filter(
        Q(disposition__archive=archive) | Q(surat_tugas__disposition__archive=archive)
    ).distinct().order_by('created_at')
    sppd_list = list(sppd_qs)
    
    if not WorkflowEngine.is_bantuan(archive) and archive.status == 'dalam_survei':
        archive.status = 'proses'
        archive.save(update_fields=['status', 'updated_at'])
        workflow_info = WorkflowEngine.get_workflow_info(archive)

    for s in sppd_list:
        if "survei" in (s.purpose or '').lower() or "mustahik" in (s.purpose or '').lower():
            from sppd_service.views import determine_smart_purpose
            correct_p, _ = determine_smart_purpose(archive=archive, dispo=s.disposition, st=s.surat_tugas)
            if correct_p and correct_p != s.purpose:
                s.purpose = correct_p

    latest_sppd = sppd_list[-1] if sppd_list else None

    from reports.models import Report
    latest_report = Report.objects.filter(disposition__archive=archive).last()

    return render(request, 'archives/detail.html', {
        'archive': archive,
        'workflow_info': workflow_info,
        'timeline_items': timeline_items,
        'latest_dispo': latest_dispo,
        'latest_st': latest_st,
        'surat_tugas_list': list(surat_tugas_qs),
        'sppd_list': sppd_list,
        'latest_sppd': latest_sppd,
        'latest_report': latest_report,
        'can_manage': can_manage,
        'default_archive_number': NumberingService.get_default_number('archive', {'archive_type': archive.archive_type}),
    })

@login_required
def archive_verify(request, pk):
    """
    Verifikasi Dokumen Berjenjang (Kabid IV -> Terverifikasi / Siap Diteruskan ke Ketua BAZNAS).
    HANYA Waka IV, Kabid IV, Front Office, dan Superadmin.
    BARU -> TERVERIFIKASI
    """
    if not can_manage_archive(request):
        messages.error(request, "Akses ditolak. Verifikasi dokumen hanya dapat dilakukan oleh Kabid IV, Waka IV, Front Office, dan Superadmin IT.")
        return redirect('archives:detail', pk=pk)

    if request.method == 'POST':
        archive = get_object_or_404(Archive, pk=pk)
        note = request.POST.get('verification_note', '').strip()
        if archive.status == 'baru':
            if not archive.archive_number:
                archive.archive_number = NumberingService.generate_number('archive', {'archive_type': archive.archive_type})
            archive.status = 'terverifikasi'
            archive.verified_by_kabid = True
            if note:
                archive.status_note = f"Catatan Verifikasi: {note}"
            archive.save()

            AuditService.log_action(request.user, f"Verifikasi Kabid IV: {archive.archive_number}", request)
            messages.success(request, f"Dokumen {archive.archive_number} Telah Diverifikasi Kabid IV, Siap Diteruskan ke Ketua BAZNAS.")
            return redirect('archives:detail', pk=archive.pk)
        elif archive.status in ['terverifikasi', 'disposisi_pimpinan']:
            messages.info(request, f"Dokumen {archive.archive_number} sudah dalam status Terverifikasi Kabid IV.")
            return redirect('archives:detail', pk=archive.pk)

    return redirect('archives:list')

@login_required
def forward_to_ketua(request, pk):
    """
    Penerusan Dokumen Terverifikasi oleh Front Office / Kabid IV ke Ketua BAZNAS (Siap Disposisi Pimpinan).
    HANYA Waka IV, Kabid IV, Front Office, dan Superadmin.
    TERVERIFIKASI -> DISPOSISI_PIMPINAN
    """
    if not can_manage_archive(request):
        messages.error(request, "Akses ditolak. Penerusan ke Ketua BAZNAS hanya dilakukan oleh Front Office, Kabid IV, Waka IV, dan Superadmin IT.")
        return redirect('archives:detail', pk=pk)

    if request.method == 'POST':
        archive = get_object_or_404(Archive, pk=pk)
        referer = request.META.get('HTTP_REFERER', '')
        redirect_target = 'archives:list' if 'archives/detail' not in referer else 'archives:detail'
        
        if archive.status == 'terverifikasi':
            archive.status = 'disposisi_pimpinan'
            archive.verified_by_kabid = True
            archive.save(update_fields=['status', 'verified_by_kabid', 'updated_at'])

            AuditService.log_action(request.user, f"Teruskan Dokumen ke Ketua BAZNAS: {archive.archive_number or archive.title}", request)
            messages.success(request, f"Dokumen {archive.archive_number or archive.title} berhasil diteruskan ke Meja Ketua BAZNAS (Status: Meja Ketua).")
            if redirect_target == 'archives:list':
                return redirect('archives:list')
            return redirect('archives:detail', pk=archive.pk)
        elif archive.status == 'disposisi_pimpinan':
            messages.info(request, f"Dokumen {archive.archive_number or archive.title} sudah berada di Meja Ketua BAZNAS.")
            if redirect_target == 'archives:list':
                return redirect('archives:list')
            return redirect('archives:detail', pk=archive.pk)
        else:
            messages.warning(request, f"Dokumen belum diverifikasi Kabid IV.")
            if redirect_target == 'archives:list':
                return redirect('archives:list')
            return redirect('archives:detail', pk=archive.pk)

    return redirect('archives:list')

@login_required
def batch_verify_view(request):
    """
    Verifikasi Massal: Hanya Waka IV, Kabid IV, Front Office, dan Superadmin.
    """
    if not can_manage_archive(request):
        messages.error(request, "Akses ditolak. Verifikasi massal hanya dapat dilakukan oleh Waka IV, Kabid IV, Front Office, dan Superadmin IT.")
        return redirect('archives:list')
    if request.method == 'POST':
        ids = request.POST.getlist('ids') or request.POST.getlist('archive_ids')
        if ids:
            archives = Archive.objects.filter(id__in=ids, status='baru')
            count = 0
            for arc in archives:
                if not arc.archive_number:
                    arc.archive_number = NumberingService.generate_number('archive', {'archive_type': arc.archive_type})
                arc.status = 'terverifikasi'
                arc.verified_by_kabid = True
                arc.save()
                count += 1
            messages.success(request, f"Berhasil memverifikasi {count} dokumen (Siap Disposisi).")
    return redirect('archives:list')

@login_required
def archive_receipt(request, pk):
    archive = get_object_or_404(Archive, pk=pk)
    return render(request, 'archives/receipt.html', {'archive': archive})

@login_required
def create_surat_tugas_view(request, pk):
    archive = get_object_or_404(Archive, pk=pk)
    dispo = archive.dispositions.first()
    if dispo:
        return redirect('sppd_service:create', dispo_pk=dispo.pk)
    messages.error(request, "Dokumen belum memiliki disposisi.")
    return redirect('archives:detail', pk=pk)

@login_required
def create_sppd_view(request, pk):
    archive = get_object_or_404(Archive, pk=pk)
    dispo = archive.dispositions.first()
    if dispo:
        return redirect('sppd_service:create', dispo_pk=dispo.pk)
    messages.error(request, "Dokumen belum memiliki disposisi.")
    return redirect('archives:detail', pk=pk)

@login_required
def upload_report_view(request, pk):
    archive = get_object_or_404(Archive, pk=pk)
    dispo = archive.dispositions.first()
    if dispo:
        return redirect('reports:create', dispo_pk=dispo.pk)
    messages.error(request, "Dokumen belum memiliki disposisi.")
    return redirect('archives:detail', pk=pk)

@csrf_exempt
@login_required
def scan_document_ocr(request):
    """
    Endpoint AJAX untuk memindai dokumen (PDF/Gambar) secara cerdas.
    """
    if request.method == 'POST' and request.FILES.get('file_path'):
        uploaded_file = request.FILES['file_path']
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_ocr')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(temp_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        from services.ai.document_ocr_service import SmartDocumentOCRService
        result = SmartDocumentOCRService.analyze_document(temp_path, uploaded_file.name)

        try:
            os.remove(temp_path)
        except Exception:
            pass

        return JsonResponse(result)

    return JsonResponse({'status': 'error', 'message': 'Tidak ada berkas yang diunggah.'}, status=400)

@login_required
def reset_all_documents(request):
    """
    Endpoint pembersihan data dokumen (Proposal, Surat, Disposisi, SPPD, Surat Tugas, Laporan).
    """
    from reports.models import Report
    from dispositions.models import Disposition
    from sppd_service.models import SPPD
    from surat_tugas.models import SuratTugas
    from notifications.models import Notification

    n_rep, _ = Report.objects.all().delete()
    n_sppd, _ = SPPD.objects.all().delete()
    n_st, _ = SuratTugas.objects.all().delete()
    n_dispo, _ = Disposition.objects.all().delete()
    n_arc, _ = Archive.objects.all().delete()
    n_notif, _ = Notification.objects.all().delete()

    messages.success(request, f"Pembersihan sukses: {n_arc} Proposal/Surat, {n_dispo} Disposisi, {n_sppd} SPPD, {n_st} Surat Tugas berhasil dihapus! Data pegawai 100% tetap aman.")
    return redirect('archives:list')


@login_required
def trigger_backup_gdrive_email(request):
    """
    Trigger 1-click backup dokumen SIMAP ke Google Drive dan pengiriman laporan email.
    """
    from django.core.management import call_command
    try:
        call_command('backup_gdrive_email')
        messages.success(request, "Pencadangan dokumen SIMAP ke Google Drive & laporan email berhasil diproses.")
    except Exception as err:
        err_msg = str(err)
        if "Google OAuth" in err_msg or "otorisasi" in err_msg or "credentials" in err_msg:
            messages.warning(
                request,
                "⚠️ Akun Google Drive belum dihubungkan. Silakan buka Pengaturan Aplikasi -> klik 'Login dengan Google' untuk memberikan izin otorisasi Google Drive."
            )
        else:
            messages.error(request, f"Gagal memproses pencadangan: {err_msg}")
    return redirect(request.META.get('HTTP_REFERER') or 'archives:list')


def archive_public_track(request, pk):
    """
    Halaman Publik Tracking Alur BPMN (Hasil Scan QR Barcode Tanda Terima).
    Dapat diakses oleh publik / siapa saja (Tanpa Login).
    HANYA menampilkan Log Alur Tahap BPMN yang SUDAH / SEDANG dilalui.
    Tahap yang belum tercapai TIDAK ditampilkan.
    Tahap penugasan hanya tampil jika ada ST/SPPD.
    Sama sekali tidak menampilkan nama-nama amil/pimpinan, tanpa berkas/file, tanpa tombol aksi.
    """
    from services.workflows.workflow_engine import WorkflowEngine

    archive = get_object_or_404(Archive, pk=pk)
    is_bantuan = WorkflowEngine.is_bantuan(archive)
    status = archive.status

    has_st_or_sppd = archive.dispositions.filter(
        Q(surat_tugas__isnull=False) | Q(sppd_list__isnull=False)
    ).exists() or archive.latest_st is not None or archive.latest_sppd is not None

    # Tentukan secara dinamis tahap-tahap yang SUDAH / SEDANG dilalui
    stages = []

    # 1. Tahap 1: Registrasi Arsip (Front Office) - Selalu Tampil
    stages.append({
        'key': 'registrasi',
        'title': 'Tahap 1: Registrasi Arsip (Front Office)',
    })

    # 2. Tahap 2: Verifikasi & Penomoran (Kabid IV) - Tampil jika status bukan 'baru' atau sudah diverifikasi
    if status != 'baru' or archive.verified_by_kabid:
        stages.append({
            'key': 'verifikasi',
            'title': 'Tahap 2: Verifikasi & Penomoran (Kabid IV)',
        })

    # 3. Disposisi (Pimpinan) / Disposisi - Tampil jika sudah tahap disposisi atau seterusnya
    if status in ['disposisi_pimpinan', 'didisposisikan', 'proses', 'sudah_ditugaskan', 'dalam_survei', 'telah_disalurkan', 'laporan', 'telah_dilaporkan', 'selesai'] or archive.dispositions.exists():
        stages.append({
            'key': 'disposisi',
            'title': 'Disposisi (Pimpinan)' if is_bantuan else 'Disposisi',
        })

    # 4. Penugasan - Hanya tampil jika ada Surat Tugas (ST) atau SPPD
    if has_st_or_sppd or status == 'sudah_ditugaskan':
        stages.append({
            'key': 'penugasan',
            'title': 'penugasan' if is_bantuan else 'penugasan (jika ada ST/SPPD)',
        })

    # 5. Penyaluran - Untuk dokumen bantuan jika sudah survei / penyaluran
    if is_bantuan and status in ['dalam_survei', 'telah_disalurkan', 'laporan', 'telah_dilaporkan']:
        stages.append({
            'key': 'penyaluran',
            'title': 'penyaluran',
        })

    # 6. Selesai - Hanya tampil jika dokumen sudah selesai
    if status == 'selesai':
        if is_bantuan and not any(s['key'] == 'penyaluran' for s in stages):
            stages.append({
                'key': 'penyaluran',
                'title': 'penyaluran',
            })
        stages.append({
            'key': 'selesai',
            'title': 'selesai',
        })

    # Atur penomoran dan status visual untuk setiap tahap (completed / active)
    total_stages = len(stages)
    for idx, s in enumerate(stages):
        s['num'] = idx + 1
        is_last = (idx == total_stages - 1)
        if status == 'selesai':
            s['state'] = 'completed'
            s['state_label'] = 'SELESAI'
            s['icon'] = 'bi-check-circle-fill'
            s['badge_class'] = 'bg-emerald-500 text-white shadow-xs'
            s['circle_class'] = 'bg-emerald-600 text-white ring-4 ring-emerald-500/20'
            s['text_class'] = 'text-slate-900 dark:text-white font-bold'
        else:
            if is_last:
                s['state'] = 'active'
                s['state_label'] = 'SEDANG DIPROSES'
                s['icon'] = 'bi-arrow-repeat animate-spin'
                s['badge_class'] = 'bg-amber-500 text-slate-950 font-bold shadow-xs'
                s['circle_class'] = 'bg-amber-500 text-slate-950 ring-4 ring-amber-500/30 font-bold scale-110'
                s['text_class'] = 'text-emerald-700 dark:text-emerald-400 font-extrabold'
            else:
                s['state'] = 'completed'
                s['state_label'] = 'SELESAI'
                s['icon'] = 'bi-check-circle-fill'
                s['badge_class'] = 'bg-emerald-500 text-white shadow-xs'
                s['circle_class'] = 'bg-emerald-600 text-white ring-4 ring-emerald-500/20'
                s['text_class'] = 'text-slate-900 dark:text-white font-bold'

    return render(request, 'archives/public_track.html', {
        'archive': archive,
        'is_bantuan': is_bantuan,
        'stages': stages,
        'current_step': total_stages,
    })
