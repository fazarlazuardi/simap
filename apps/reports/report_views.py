from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Report
from dispositions.models import Disposition
from services.audit_logs.audit_service import AuditService


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['report_number', 'title', 'content', 'file']


@login_required
def report_detail(request, pk):
    """
    Menampilkan detail laporan hasil tindak lanjut.
    """
    report = get_object_or_404(Report, pk=pk)
    return render(request, 'reports/detail.html', {'report': report})


@login_required
def report_edit(request, pk):
    """
    Mengubah atau memperbarui laporan hasil pelaksanaan tugas.
    """
    report = get_object_or_404(Report, pk=pk)
    
    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES, instance=report)
        if form.is_valid():
            form.save()
            AuditService.log_action(request.user, f"Memperbarui Laporan #{report.report_number}", request)
            messages.success(request, f"Laporan {report.report_number} berhasil diperbarui.")
            return redirect('reports:detail', pk=report.pk)
    else:
        form = ReportForm(instance=report)

    return render(request, 'reports/create.html', {
        'form': form,
        'report': report,
        'disposition': report.disposition
    })


@login_required
def report_create(request, disposition_pk):
    """
    Membuat laporan hasil pelaksanaan tugas berdasarkan disposisi.
    """
    disposition = get_object_or_404(Disposition, pk=disposition_pk)
    
    # Cek apakah laporan sudah pernah dibuat sebelumnya
    if hasattr(disposition, 'report'):
        messages.info(request, "Laporan untuk disposisi ini sudah ada.")
        return redirect('reports:detail', pk=disposition.report.pk)

    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.disposition = disposition
            report.created_by = request.user
            report.save()

            # Perbarui status disposisi menjadi selesai
            disposition.status = 'selesai'
            disposition.completed_at = timezone.now()
            disposition.save(update_fields=['status', 'completed_at'])

            AuditService.log_action(request.user, f"Membuat Laporan #{report.report_number} untuk Disposisi #{disposition.disposition_number}", request)
            messages.success(request, f"Laporan {report.report_number} berhasil dikirim dan arsip dinyatakan selesai.")
            return redirect('reports:detail', pk=report.pk)
    else:
        initial_data = {
            'title': f"Laporan Tindak Lanjut - {disposition.archive.title if disposition.archive else ''}"
        }
        form = ReportForm(initial=initial_data)

    return render(request, 'reports/create.html', {
        'form': form,
        'disposition': disposition
    })