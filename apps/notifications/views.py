from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db.models import Q
from users.views import superuser_only

from .models import Notification, WANotificationSetting
from services.integrations.gateway_service import WhatsAppService


@login_required
def notification_list(request):
    """Halaman lengkap riwayat dan manajemen notifikasi user."""
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    status_filter = request.GET.get('status')
    if status_filter in ['unread', 'read']:
        notifs = notifs.filter(status=status_filter)

    return render(request, 'notifications/list.html', {
        'notifications': notifs,
        'current_status': status_filter or 'all',
        'unread_count': Notification.objects.filter(user=request.user, status='unread').count(),
    })


@login_required
def read_and_redirect(request, pk):
    """Menandai 1 notifikasi tertentu sebagai 'read' dan mengarahkan ke link tautan tujuan."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if notif.status == 'unread':
        notif.status = 'read'
        notif.save(update_fields=['status'])
    
    if notif.link_url:
        return redirect(notif.link_url)
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_as_read(request):
    """Menandai seluruh notifikasi user sebagai 'read'."""
    updated_count = Notification.objects.filter(user=request.user, status='unread').update(status='read')

    if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        context = {
            'global_notifications': [],
            'global_notif_count': 0,
            'user': request.user,
        }
        return render(request, 'includes/notification_dropdown_inner.html', context)

    messages.success(request, f"✅ {updated_count} notifikasi telah ditandai sebagai sudah dibaca.")
    return redirect(request.META.get('HTTP_REFERER', 'notifications:list'))


@login_required
@require_POST
def clear_all(request):
    """Menghapus seluruh notifikasi milik user terpilih."""
    Notification.objects.filter(user=request.user).delete()
    messages.success(request, "Riwayat notifikasi berhasil dibersihkan.")
    return redirect('notifications:list')


@login_required
@user_passes_test(superuser_only)
def wa_outbox_list(request):
    """
    KONSOL PEMANTAUAN OUTBOX WA & MATRIKS KONTROL NOTIFIKASI
    Menampilkan riwayat outbox WA, status terkirim/draft manual/gagal, serta pengeditan mode matriks.
    """
    # Pastikan default settings kategori dibuat jika belum ada
    categories = [
        ('disposition', 'Disposisi Pimpinan (Stage 1 & 2)', 'Surat masuk yang didisposisikan oleh Ketua / Waka IV.'),
        ('bantuan_survei', 'Penugasan Survei Lapangan Bantuan (Bidang II)', 'Penerbitan ST/SPPD amil untuk survei kelayakan mustahik.'),
        ('bantuan_penyaluran', 'LHP Penyaluran Direct (Bidang II)', 'Pemberitahuan laporan pentasyarufan bantuan langsung.'),
        ('sppd', 'SPPD & Perjalanan Dinas', 'Penerbitan Surat Perintah Perjalanan Dinas amil.'),
        ('internal_meeting', 'Risalah & Notulensi Rapat Internal', 'Undangan dan risalah kegiatan rapat internal BAZNAS.'),
        ('archive', 'Notifikasi Arsip Baru', 'Pengunggahan dokumen arsip baru oleh Front Office.'),
    ]

    for cat_code, cat_label, cat_desc in categories:
        WANotificationSetting.objects.get_or_create(
            category=cat_code,
            defaults={'dispatch_mode': 'auto', 'description': cat_desc}
        )

    # Handle update matriks mode dari form
    if request.method == 'POST' and request.POST.get('action') == 'update_wa_matrix':
        for cat_code, _, _ in categories:
            mode_val = request.POST.get(f'mode_{cat_code}', 'auto')
            WANotificationSetting.objects.filter(category=cat_code).update(dispatch_mode=mode_val)
        messages.success(request, "Matriks Mode Pengiriman WA (Otomatis vs Manual) berhasil diperbarui.")
        return redirect('notifications:wa_outbox')

    # Query Outbox WA
    wa_logs = Notification.objects.filter(notification_type='whatsapp').order_by('-created_at')

    # Filters
    status_filter = request.GET.get('status', '').strip()
    category_filter = request.GET.get('category', '').strip()
    query = request.GET.get('q', '').strip()

    if status_filter:
        wa_logs = wa_logs.filter(status=status_filter)
    if category_filter:
        wa_logs = wa_logs.filter(category=category_filter)
    if query:
        wa_logs = wa_logs.filter(
            Q(title__icontains=query) |
            Q(message__icontains=query) |
            Q(recipient_phone__icontains=query) |
            Q(user__username__icontains=query) |
            Q(employee__full_name__icontains=query)
        )

    # Stats Counts
    total_count = Notification.objects.filter(notification_type='whatsapp').count()
    sent_count = Notification.objects.filter(notification_type='whatsapp', status='sent').count()
    manual_count = Notification.objects.filter(notification_type='whatsapp', status='draft_manual').count()
    failed_count = Notification.objects.filter(notification_type='whatsapp', status='failed').count()

    context = {
        'wa_logs': wa_logs,
        'wa_settings': WANotificationSetting.objects.all(),
        'status_filter': status_filter,
        'category_filter': category_filter,
        'query': query,
        'total_count': total_count,
        'sent_count': sent_count,
        'manual_count': manual_count,
        'failed_count': failed_count,
        'wa_health': WhatsAppService.check_health(),
    }
    return render(request, 'notifications/wa_outbox.html', context)


@login_required
@user_passes_test(superuser_only)
@require_POST
def resend_wa_notification(request, pk):
    """Trigger resend outbox WA message dari konsol."""
    success, msg = WhatsAppService.resend_outbox(pk)
    if success:
        messages.success(request, f"✅ {msg}")
    else:
        messages.error(request, f"❌ {msg}")
    return redirect(request.META.get('HTTP_REFERER', 'notifications:wa_outbox'))
