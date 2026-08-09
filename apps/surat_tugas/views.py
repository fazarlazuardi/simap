from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from dispositions.models import Disposition
from archives.models import Archive

from .forms import SuratTugasForm
from .models import SuratTugas
from sppd_service.views import determine_smart_purpose



@login_required
def surat_list(request):
    surat_list = SuratTugas.objects.select_related('disposition__archive', 'created_by').prefetch_related('pegawai_ditugaskan').order_by('-created_at')
    
    st_dispo_ids = SuratTugas.objects.filter(disposition__isnull=False).values_list('disposition_id', flat=True)
    dispositions_pending_st = Disposition.objects.select_related('archive', 'sender', 'sender__employee').prefetch_related('forwarded_to', 'waka_forwarded_to').order_by('-created_at')

    return render(request, 'surat_tugas/list.html', {
        'surat_list': surat_list,
        'dispositions_pending_st': dispositions_pending_st,
    })



@login_required
def surat_detail(request, pk):
    surat = get_object_or_404(SuratTugas, pk=pk)
    return render(request, 'surat_tugas/detail.html', {'surat': surat})


@login_required
def surat_create(request):
    archive_id = request.GET.get('archive') or request.POST.get('archive_id')
    archive = None
    if archive_id:
        archive = Archive.objects.filter(pk=archive_id).first()

    surat_terakhir = (
        SuratTugas.objects.exclude(nomor_surat__isnull=True)
        .exclude(nomor_surat__exact='')
        .order_by('-created_at')[:5]
    )

    if request.method == 'POST':
        form = SuratTugasForm(request.POST)
        if form.is_valid():
            surat = form.save(commit=False)
            
            # Hubungkan dengan arsip jika tersedia dari parameter URL/POST
            if archive:
                if hasattr(surat, 'archive') and not surat.archive:
                    surat.archive = archive

            if hasattr(surat, 'created_by') and not surat.created_by:
                surat.created_by = request.user
            
            surat.save()
            form.save_m2m()

            # Sinkronisasi status arsip terkait agar berubah menjadi sudah_ditugaskan
            target_archive = getattr(surat, 'archive', None) or archive
            if target_archive:
                target_archive.status = 'sudah_ditugaskan'
                target_archive.updated_at = timezone.now()
                target_archive.save(update_fields=['status', 'updated_at'])

            messages.success(request, 'Surat Tugas berhasil dibuat.')
            
            if target_archive:
                return redirect('archives:detail', pk=target_archive.pk)
            return redirect('surat_tugas:detail', pk=surat.pk)
    else:
        initial_data = {}
        if archive:
            initial_data['tentang'] = archive.title or archive.subject
            if hasattr(SuratTugas, 'archive'):
                initial_data['archive'] = archive
        form = SuratTugasForm(initial=initial_data)

    dispositions_pending_st = Disposition.objects.select_related('archive', 'sender').prefetch_related('forwarded_to').order_by('-created_at')


    return render(request, 'surat_tugas/create.html', {
        'form': form,
        'archive': archive,
        'surat_terakhir': surat_terakhir,
        'dispositions_pending_st': dispositions_pending_st,
    })



@login_required
def surat_create_from_archive(request, pk):
    """
    Membuat Surat Tugas yang terikat langsung dari halaman Detail Arsip (pk).
    Sekaligus menyelaraskan status arsip menjadi 'sudah_ditugaskan'.
    """
    archive = get_object_or_404(Archive, pk=pk)
    surat_terakhir = (
        SuratTugas.objects.exclude(nomor_surat__isnull=True)
        .exclude(nomor_surat__exact='')
        .order_by('-created_at')[:5]
    )

    if request.method == 'POST':
        form = SuratTugasForm(request.POST)
        if form.is_valid():
            surat = form.save(commit=False)
            if hasattr(surat, 'archive') and not surat.archive:
                surat.archive = archive

            if hasattr(surat, 'created_by') and not surat.created_by:
                surat.created_by = request.user
            
            surat.save()
            form.save_m2m()

            archive.status = 'sudah_ditugaskan'
            archive.updated_at = timezone.now()
            archive.save(update_fields=['status', 'updated_at'])

            messages.success(
                request, 
                f'Surat Tugas berhasil dicatat. Status dokumen {archive.archive_number} menjadi "Penugasan".'
            )
            return redirect('archives:detail', pk=archive.pk)
    else:
        initial_data = {}
        if hasattr(SuratTugas, 'archive'):
            initial_data['archive'] = archive
        smart_p, _ = determine_smart_purpose(archive=archive)
        initial_data['tentang'] = smart_p
            
        form = SuratTugasForm(initial=initial_data)


    dispositions_pending_st = Disposition.objects.select_related('archive', 'sender').prefetch_related('forwarded_to').order_by('-created_at')


    context = {
        'form': form,
        'archive': archive,
        'surat_terakhir': surat_terakhir,
        'dispositions_pending_st': dispositions_pending_st,
    }
    return render(request, 'surat_tugas/create.html', context)


@login_required
def surat_create_from_disposition(request, disposition_id):
    disposition = get_object_or_404(Disposition, pk=disposition_id)
    archive = getattr(disposition, 'archive', None)
    
    surat_terakhir = (
        SuratTugas.objects.exclude(nomor_surat__isnull=True)
        .exclude(nomor_surat__exact='')
        .order_by('-created_at')[:5]
    )

    if request.method == 'POST':
        form = SuratTugasForm(request.POST)
        if form.is_valid():
            surat = form.save(commit=False)
            surat.disposition = disposition
            
            # Hubungkan foreign key archive jika ada pada model SuratTugas
            if archive and hasattr(surat, 'archive'):
                surat.archive = archive

            if hasattr(surat, 'created_by') and not surat.created_by:
                surat.created_by = request.user
            
            surat.save()
            form.save_m2m()

            # Sinkronisasi status arsip terkait dari disposisi
            target_archive = archive or getattr(disposition, 'archive', None)
            if target_archive:
                target_archive.status = 'sudah_ditugaskan'
                target_archive.updated_at = timezone.now()
                target_archive.save(update_fields=['status', 'updated_at'])

            messages.success(request, 'Surat Tugas dari Disposisi berhasil dibuat.')
            
            if target_archive:
                return redirect('archives:detail', pk=target_archive.pk)
            return redirect('surat_tugas:detail', pk=surat.pk)
    else:
        smart_p, _ = determine_smart_purpose(archive=archive, dispo=disposition)
        initial_data = {
            'tentang': smart_p,
            'disposition': disposition,
        }
        if archive and hasattr(SuratTugas, 'archive'):
            initial_data['archive'] = archive
            
        form = SuratTugasForm(initial=initial_data)


    dispositions_pending_st = Disposition.objects.select_related('archive', 'sender').prefetch_related('forwarded_to').order_by('-created_at')


    return render(request, 'surat_tugas/create.html', {
        'form': form,
        'disposition': disposition,
        'archive': archive,
        'surat_terakhir': surat_terakhir,
        'dispositions_pending_st': dispositions_pending_st,
    })



@login_required
def surat_update(request, pk):
    surat = get_object_or_404(SuratTugas, pk=pk)
    target_archive = getattr(surat, 'archive', None) or getattr(surat.disposition, 'archive', None)
    
    surat_terakhir = (
        SuratTugas.objects.exclude(nomor_surat__isnull=True)
        .exclude(nomor_surat__exact='')
        .order_by('-created_at')[:5]
    )

    if request.method == 'POST':
        form = SuratTugasForm(request.POST, instance=surat)
        if form.is_valid():
            form.save()
            
            # Pastikan status arsip tetap 'sudah_ditugaskan' ketika diperbarui
            if target_archive:
                target_archive.status = 'sudah_ditugaskan'
                target_archive.updated_at = timezone.now()
                target_archive.save(update_fields=['status', 'updated_at'])

            messages.success(request, 'Surat Tugas berhasil diperbarui.')
            
            if target_archive:
                return redirect('archives:detail', pk=target_archive.pk)
            return redirect('surat_tugas:detail', pk=surat.pk)
    else:
        form = SuratTugasForm(instance=surat)

    return render(request, 'surat_tugas/create.html', {
        'form': form,
        'surat': surat,
        'archive': target_archive,
        'surat_terakhir': surat_terakhir
    })


@login_required
def surat_print(request, pk):
    surat = get_object_or_404(SuratTugas, pk=pk)
    return render(request, 'surat_tugas/print.html', {'surat': surat})


@login_required
def surat_delete(request, pk):
    surat = get_object_or_404(SuratTugas, pk=pk)
    target_archive = getattr(surat, 'archive', None) or getattr(surat.disposition, 'archive', None)
    
    if request.method == 'POST':
        surat.delete()
        
        # Kembalikan status arsip ke 'proses' jika surat tugas dihapus
        if target_archive and target_archive.status == 'sudah_ditugaskan':
            target_archive.status = 'proses'
            target_archive.updated_at = timezone.now()
            target_archive.save(update_fields=['status', 'updated_at'])

        messages.success(request, 'Surat Tugas berhasil dihapus.')
        if target_archive:
            return redirect('archives:detail', pk=target_archive.pk)
        return redirect('surat_tugas:list')
        
    return redirect('surat_tugas:list')