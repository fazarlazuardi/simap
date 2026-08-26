from django.db.models import Q
from notifications.models import Notification, DirectMessage
from users.models import AppConfig
from archives.models import Archive
from dispositions.models import Disposition
from surat_tugas.models import SuratTugas

def notification_context(request):
    config = AppConfig.get_config()
    context = {
        'app_config': config,
    }
    if request.user.is_authenticated:
        # Jika semua arsip dan disposisi telah dihapus bersih di Django Admin -> Hapus notifikasi lama otomatis
        if not Archive.objects.exists() and not Disposition.objects.exists():
            Notification.objects.filter(category__in=['disposition', 'archive']).delete()

        # Filter disposisi yang sudah diisi agar notifikasi lamanya tidak menumpuk di lonceng
        completed_archive_ids = Disposition.objects.exclude(status='baru').values_list('archive_id', flat=True)
        completed_urls = [f"/dispositions/{aid}/create/" for aid in completed_archive_ids if aid]

        unread_notifications = Notification.objects.filter(
            user=request.user, 
            status='unread'
        ).exclude(
            link_url__in=completed_urls
        ).order_by('-created_at')

        # Pesan Unread Direct Amil Khusus Penerima
        unread_direct_msgs = DirectMessage.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
        unread_direct_msg_count = unread_direct_msgs.count()
        latest_unread_direct_msg = unread_direct_msgs.first()
        
        active_pov = request.session.get('active_pov')
        is_kabid_4_active = active_pov == 'kabid_4' or (not active_pov and getattr(request.user, 'is_kabid_4', False))
        is_waka_4_active = active_pov == 'waka_4' or (not active_pov and (getattr(request.user, 'is_waka_4', False) or getattr(request.user, 'is_pimpinan', False)))

        unverified_count = 0
        pending_st_sppd_count = 0
        if is_kabid_4_active or (request.user.is_superadmin and not active_pov):
            unverified_count = Archive.objects.filter(
                verified_by_kabid=False,
                status__in=['baru', 'pending', 'masuk']
            ).count()

            pending_st_sppd_count = SuratTugas.objects.filter(
                sppd_records__isnull=True
            ).filter(
                Q(disposition__isnull=True) | ~Q(disposition__archive__status__in=['selesai', 'ditolak'])
            ).count()

        pending_waka4_dispo_count = 0
        if is_waka_4_active or is_kabid_4_active or (request.user.is_superadmin and not active_pov):
            pending_waka4_dispo_count = Disposition.objects.filter(status='didisposisi_ketua').count()

        context.update({
            'global_notifications': unread_notifications[:5],
            'global_notif_count': unread_notifications.count(),
            'unread_direct_msg_count': unread_direct_msg_count,
            'latest_unread_direct_msg': latest_unread_direct_msg,
            'is_kabid_4_active': is_kabid_4_active,
            'is_waka_4_active': is_waka_4_active,
            'unverified_count': unverified_count,
            'pending_waka4_dispo_count': pending_waka4_dispo_count,
            'pending_st_sppd_count': pending_st_sppd_count,
        })

    # Tentukan public_base_url untuk QR Code scan
    from django.conf import settings as django_settings
    public_host = getattr(django_settings, 'PUBLIC_HOST_URL', '')
    if not public_host:
        host = request.get_host()
        if host and not host.startswith('127.0.0.1') and not host.startswith('localhost'):
            public_host = f"{request.scheme}://{host}"
        elif request.META.get('HTTP_X_FORWARDED_HOST'):
            fhost = request.META.get('HTTP_X_FORWARDED_HOST')
            scheme = request.META.get('HTTP_X_FORWARDED_PROTO', request.scheme)
            public_host = f"{scheme}://{fhost}"
        else:
            from users.models import SystemSetting
            saved_domain = SystemSetting.get_value('public_domain', '')
            if saved_domain:
                if not saved_domain.startswith('http'):
                    saved_domain = f"https://{saved_domain}"
                public_host = saved_domain
            else:
                public_host = f"{request.scheme}://{host}"

    context['public_base_url'] = public_host
    return context

