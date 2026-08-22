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


@login_required
def chat_inbox(request, recipient_id=None):
    """
    RUANG CHAT & PESAN INTERNAL AMIL SIMAP
    Menampilkan obrolan interaktif antarsesama pemegang akun (User/Amil).
    """
    from users.models import User
    from .models import DirectMessage
    from django.utils import timezone

    all_users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).select_related('employee', 'employee__dept_relation').order_by('username')
    
    active_recipient = None
    if recipient_id:
        active_recipient = get_object_or_404(User, pk=recipient_id, is_active=True)
    elif all_users.exists():
        last_msg = DirectMessage.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).order_by('-created_at').first()
        if last_msg:
            active_recipient = last_msg.recipient if last_msg.sender == request.user else last_msg.sender
        else:
            active_recipient = all_users.first()

    messages_list = []
    if active_recipient:
        DirectMessage.objects.filter(sender=active_recipient, recipient=request.user, is_read=False).update(is_read=True)
        Notification.objects.filter(
            user=request.user, 
            category='general', 
            link_url__icontains=f"/notifications/chat/{active_recipient.pk}/",
            status='unread'
        ).update(status='read')

        messages_list = DirectMessage.objects.filter(
            (Q(sender=request.user) & Q(recipient=active_recipient)) |
            (Q(sender=active_recipient) & Q(recipient=request.user))
        ).order_by('created_at')

    unread_counts = {}
    unread_qs = DirectMessage.objects.filter(recipient=request.user, is_read=False)
    for msg in unread_qs:
        unread_counts[msg.sender_id] = unread_counts.get(msg.sender_id, 0) + 1

    last_messages = {}
    all_direct_msgs = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).order_by('-created_at')

    for msg in all_direct_msgs:
        other_id = msg.recipient_id if msg.sender_id == request.user.pk else msg.sender_id
        if other_id not in last_messages:
            last_messages[other_id] = msg

    user_chat_list = []
    for u in all_users:
        user_chat_list.append({
            'user': u,
            'unread_count': unread_counts.get(u.pk, 0),
            'last_message': last_messages.get(u.pk),
        })

    user_chat_list.sort(key=lambda item: item['last_message'].created_at if item['last_message'] else timezone.now() - timezone.timedelta(days=3650), reverse=True)

    context = {
        'user_chat_list': user_chat_list,
        'active_recipient': active_recipient,
        'messages_list': messages_list,
        'total_unread_chat': sum(unread_counts.values()),
    }
    return render(request, 'notifications/chat_inbox.html', context)


@login_required
@require_POST
def send_direct_message(request):
    """Fungsi AJAX/Form untuk mengirim pesan direct amil."""
    from users.models import User
    from .models import DirectMessage

    recipient_id = request.POST.get('recipient_id')
    body = request.POST.get('body', '').strip()

    if not recipient_id or not body:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Pesan tidak boleh kosong.'}, status=400)
        messages.error(request, "Pesan tidak boleh kosong.")
        return redirect('notifications:chat_inbox')

    recipient = get_object_or_404(User, pk=recipient_id, is_active=True)

    msg = DirectMessage.objects.create(
        sender=request.user,
        recipient=recipient,
        body=body
    )

    sender_name = request.user.employee.full_name if hasattr(request.user, 'employee') and request.user.employee else request.user.username
    Notification.create_system_notif(
        user=recipient,
        title=f"💬 Pesan Baru dari {sender_name}",
        message=f"{body[:50]}..." if len(body) > 50 else body,
        link_url=f"/notifications/chat/{request.user.pk}/",
        category="general"
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message_id': msg.id,
            'body': msg.body,
            'created_at': msg.created_at.strftime('%H:%M WIB'),
            'sender_name': sender_name,
        })

    messages.success(request, f"Pesan terkirim ke {recipient.username}")
    return redirect('notifications:chat_inbox_user', recipient_id=recipient.pk)


@login_required
@require_POST
def delete_direct_message(request, pk):
    """Menghapus 1 pesan direct tertentu."""
    from .models import DirectMessage
    msg = get_object_or_404(DirectMessage, pk=pk)
    
    if msg.sender != request.user and msg.recipient != request.user:
        messages.error(request, "Anda tidak memiliki hak akses untuk menghapus pesan ini.")
        return redirect('notifications:chat_inbox')
        
    recipient_id = msg.recipient_id if msg.sender == request.user else msg.sender_id
    msg.delete()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Pesan berhasil dihapus.'})
        
    messages.success(request, "Pesan berhasil dihapus.")
    return redirect('notifications:chat_inbox_user', recipient_id=recipient_id)


@login_required
@require_POST
def clear_chat_thread(request, recipient_id):
    """Membersihkan seluruh percakapan antara request.user dan recipient_id."""
    from users.models import User
    from .models import DirectMessage
    recipient = get_object_or_404(User, pk=recipient_id)
    
    deleted_count, _ = DirectMessage.objects.filter(
        (Q(sender=request.user) & Q(recipient=recipient)) |
        (Q(sender=recipient) & Q(recipient=request.user))
    ).delete()
    
    messages.success(request, f"Obrolan dengan {recipient.username} ({deleted_count} pesan) berhasil dibersihkan.")
    return redirect('notifications:chat_inbox_user', recipient_id=recipient.pk)


