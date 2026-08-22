from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string

from .models import Notification


@login_required
def notification_list(request):
    """Halaman lengkap riwayat dan manajemen notifikasi user."""
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter opsional berdasarkan status (unread/read)
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
        # Jika request dari HTMX, kembalikan snippet dropdown kosong / bersih
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
    """Hapus bersih seluruh log notifikasi user."""
    deleted_count, _ = Notification.objects.filter(user=request.user).delete()

    if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        context = {
            'global_notifications': [],
            'global_notif_count': 0,
            'user': request.user,
        }
        return render(request, 'includes/notification_dropdown_inner.html', context)

    messages.success(request, "🗑️ Seluruh notifikasi telah dihapus bersih.")
    return redirect(request.META.get('HTTP_REFERER', 'notifications:list'))
