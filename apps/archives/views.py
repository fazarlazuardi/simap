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

def can_view_arsip_sdm(request):
    user = request.user
    active_pov = request.session.get('active_pov')
    if active_pov:
        if active_pov in ['waka_4', 'kabid_4', 'sdm']:
            return True
        return False
    if getattr(user, 'is_superadmin', False) or getattr(user, 'is_superuser', False):
        return True
    return getattr(user, 'is_sdm', False)

def can_upload_archive(request):
    """
    Hanya Front Office / Resepsionis (POV sdm / user.is_sdm tanpa role kabid/pimpinan)
    dan Superadmin IT (dalam mode default / tanpa POV) yang dapat mengunggah arsip baru.
    """
    user = request.user
    active_pov = request.session.get('active_pov')
    
    if active_pov:
        return active_pov in ['sdm', 'front_office']
        
    if getattr(user, 'is_superadmin', False) or getattr(user, 'is_superuser', False):
        return True
        
    # Pimpinan & Kabid (Ketua, Waka 4, Kabid 4, Waka 2, Kabid 2, dll) TIDAK BOLEH upload
    if getattr(user, 'is_pimpinan', False) or getattr(user, 'is_kabid', False) or getattr(user, 'is_waka_4', False) or getattr(user, 'is_kabid_4', False):
        return False
        
    emp = getattr(user, 'employee', None)
    if emp and emp.dept_relation:
        dept_name = (emp.dept_relation.name or "").lower()
        if any(k in dept_name for k in ['front office', 'resepsionis', 'sekretariat', 'sdm']):
            return True
            
    return getattr(user, 'is_sdm', False)


@login_required
def archive_list(request):
    """
    Archive list with client-side DataTables handling.
    """
    if not can_view_arsip_sdm(request):
        messages.error(request, "Modul Arsip SDM hanya dapat diakses oleh Bidang IV (Administrasi, SDM & Umum) dan Superadmin IT.")
        return redirect('users:dashboard')

    archives = Archive.objects.all().select_related('category', 'uploaded_by').order_by('-created_at')

    status_filter = request.GET.get('status', 'all')
    if status_filter == 'perlu_verifikasi':
        archives = archives.filter(Q(verified_by_kabid=False) | Q(status__in=['baru', 'pending', 'masuk', 'verifikasi_kabid'])).exclude(status__in=['selesai', 'ditolak'])
    elif status_filter == 'belum_disposition':
        archives = archives.filter(status__in=['terverifikasi', 'disposisi_pimpinan', 'meja_waka4', 'disposisi_waka'])
    elif status_filter == 'sudah_disposition':
        archives = archives.filter(status__in=['didisposisikan', 'proses', 'sudah_ditugaskan', 'dalam_survei', 'telah_disalurkan', 'selesai'])

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

    return render(request, 'archives/list.html', {
        'page_obj': page_obj,
        'archives': page_obj,
        'archive_types': Archive.TYPE_CHOICES,
        'current_type': archive_type_filter or '',
        'status_filter': status_filter,
        'is_waka_or_kabid_2': is_waka_or_kabid_2,
        'can_upload': can_upload_archive(request),
    })

@login_required
@sdm_required
def archive_upload(request):
    if not can_view_arsip_sdm(request):
        messages.error(request, "Modul Arsip SDM hanya dapat diakses oleh Bidang IV (Administrasi, SDM & Umum) dan Superadmin IT.")
        return redirect('users:dashboard')

    if not can_upload_archive(request):
        messages.error(request, "Hak akses mengunggah arsip/dokumen baru HANYA dimiliki oleh Front Office / Resepsionis dan Superadmin IT.")
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
        
        address = request.POST.get('address', '').strip()
        category = get_object_or_404(Category, id=category_id)
        
        archive = Archive.objects.create(
            archive_type=archive_type,
            archive_number=archive_number,
            letter_date=letter_date,
            sender=sender_receiver,
            address=address,
            title=title,
            category=category,
            description=description,
            uploaded_by=request.user,
            file_path=file,
            status="baru",
        )

        AuditService.log_action(request.user, f"Upload Arsip Baru: {title}", request)

        messages.success(request, "Dokumen berhasil diunggah dengan status BARU.")
        return redirect('archives:list')
    
    # --- Handling GET Method ---
    categories = Category.objects.all()

    selected_type = request.GET.get('type', 'surat_masuk')
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
    })

@login_required
def archive_reject(request, pk):
    if not request.user.is_pimpinan and not request.user.is_superadmin:
        messages.error(request, "Akses ditolak.")
        return redirect('archives:list')
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
    """
    if not can_view_arsip_sdm(request):
        messages.error(request, "Modul Arsip SDM hanya dapat diakses oleh Bidang IV (Administrasi, SDM & Umum) dan Superadmin IT.")
        return redirect('users:dashboard')

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

@login_required
def archive_detail(request, pk):
    if not can_view_arsip_sdm(request):
        messages.error(request, "Modul Arsip SDM hanya dapat diakses oleh Bidang IV (Administrasi, SDM & Umum) dan Superadmin IT.")
        return redirect('users:dashboard')
    from services.workflows.workflow_engine import WorkflowEngine
    from services.timeline.timeline_service import TimelineService
    archive = get_object_or_404(Archive, pk=pk)

    # Handle Upload Berkas Digital Langsung di Halaman Detail
    if request.method == 'POST' and request.FILES.get('file_path'):
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

    from sppd_service.views import determine_smart_purpose
    for s in sppd_list:
        if "survei" in (s.purpose or '').lower() or "mustahik" in (s.purpose or '').lower():
            correct_p, _ = determine_smart_purpose(archive=archive, dispo=s.disposition, st=s.surat_tugas)
            if correct_p != s.purpose:
                s.purpose = correct_p
                s.save(update_fields=['purpose'])

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
    })

@login_required
def archive_verify(request, pk):
    """
    Verifikasi Dokumen Berjenjang (Kabid IV -> Terverifikasi / Siap Diteruskan ke Ketua BAZNAS).
    BARU -> TERVERIFIKASI
    """
    if not (request.user.is_pimpinan or request.user.is_kabid or request.user.is_superadmin):
        messages.error(request, "Akses ditolak. Membutuhkan kewenangan Kabid IV / Pimpinan.")
        return redirect('archives:list')

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
    TERVERIFIKASI -> DISPOSISI_PIMPINAN
    """
    if not (request.user.is_sdm or request.user.is_kabid or request.user.is_superadmin):
        messages.error(request, "Akses ditolak. Penerusan ke Ketua BAZNAS hanya dilakukan oleh Front Office atau Kabid IV.")
        return redirect('archives:detail', pk=pk)

    if request.method == 'POST':
        archive = get_object_or_404(Archive, pk=pk)
        if archive.status == 'terverifikasi':
            archive.status = 'disposisi_pimpinan'
            archive.verified_by_kabid = True
            archive.save(update_fields=['status', 'verified_by_kabid', 'updated_at'])

            AuditService.log_action(request.user, f"Teruskan Dokumen ke Ketua BAZNAS: {archive.archive_number or archive.title}", request)
            messages.success(request, f"Dokumen {archive.archive_number or archive.title} berhasil diteruskan ke Meja Ketua BAZNAS untuk didisposisikan.")
            return redirect('archives:detail', pk=archive.pk)
        elif archive.status == 'disposisi_pimpinan':
            messages.info(request, f"Dokumen {archive.archive_number or archive.title} sudah berada di Meja Ketua BAZNAS.")
            return redirect('archives:detail', pk=archive.pk)
        else:
            messages.warning(request, f"Dokumen belum diverifikasi Kabid IV.")
            return redirect('archives:detail', pk=archive.pk)

    return redirect('archives:list')

@login_required
def batch_verify_view(request):
    if not (request.user.is_pimpinan or request.user.is_kabid or request.user.is_superadmin):
        messages.error(request, "Akses ditolak.")
        return redirect('archives:list')
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            archives = Archive.objects.filter(id__in=ids, status='baru')
            count = 0
            for arc in archives:
                if not arc.archive_number:
                    arc.archive_number = NumberingService.generate_number('archive', {'archive_type': arc.archive_type})
                arc.status = 'terverifikasi'
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