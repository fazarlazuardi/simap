from django.db.models import Q
from django.core.cache import cache
from notifications.models import Notification, DirectMessage
from users.models import AppConfig
from archives.models import Archive
from dispositions.models import Disposition
from surat_tugas.models import SuratTugas

def notification_context(request):
    try:
        config = cache.get_or_set('app_config_obj', AppConfig.get_config, 300)
    except Exception:
        config = AppConfig.get_config()

    context = {
        'app_config': config,
    }
    
    if request.user.is_authenticated:
        active_pov = request.session.get('active_pov', '')
        context['dispo_perms'] = request.user.get_disposition_permissions(active_pov)
        cache_key = f"notif_ctx_u{request.user.pk}_pov{active_pov}"
        cached_user_ctx = None
        try:
            cached_user_ctx = cache.get(cache_key)
        except Exception:
            cached_user_ctx = None

        if cached_user_ctx is not None:
            context.update(cached_user_ctx)
        else:
            # Optimized Notification Lookup: hanya filter Disposition jika ada notifikasi disposisi unread
            raw_notifs = list(Notification.objects.filter(
                user=request.user, 
                status='unread'
            ).order_by('-created_at')[:15])

            dispo_archive_ids = []
            for n in raw_notifs:
                if n.link_url and '/dispositions/' in n.link_url and '/create/' in n.link_url:
                    try:
                        parts = n.link_url.split('/dispositions/')[1].split('/create/')[0]
                        if parts.isdigit():
                            dispo_archive_ids.append(int(parts))
                    except Exception:
                        pass

            completed_archive_set = set()
            if dispo_archive_ids:
                completed_archive_set = set(
                    Disposition.objects.filter(
                        archive_id__in=dispo_archive_ids
                    ).exclude(status='baru').values_list('archive_id', flat=True)
                )

            unread_notifications = []
            for n in raw_notifs:
                is_completed_dispo = False
                if completed_archive_set and n.link_url:
                    for aid in completed_archive_set:
                        if f"/dispositions/{aid}/create/" in n.link_url:
                            is_completed_dispo = True
                            break
                if not is_completed_dispo:
                    unread_notifications.append(n)

            global_notif_count = len(unread_notifications)

            # Pesan Unread Direct Amil Khusus Penerima
            unread_direct_msgs = DirectMessage.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
            unread_direct_msg_count = unread_direct_msgs.count()
            latest_unread_direct_msg = unread_direct_msgs.first()
            
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

            user_ctx = {
                'global_notifications': unread_notifications[:5],
                'global_notif_count': global_notif_count,
                'unread_direct_msg_count': unread_direct_msg_count,
                'latest_unread_direct_msg': latest_unread_direct_msg,
                'is_kabid_4_active': is_kabid_4_active,
                'is_waka_4_active': is_waka_4_active,
                'unverified_count': unverified_count,
                'pending_waka4_dispo_count': pending_waka4_dispo_count,
                'pending_st_sppd_count': pending_st_sppd_count,
            }
            try:
                cache.set(cache_key, user_ctx, 30)  # Cache for 30 seconds
            except Exception:
                pass

            context.update(user_ctx)

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
            try:
                public_host = cache.get('public_domain_setting')
                if not public_host:
                    from users.models import SystemSetting
                    saved_domain = SystemSetting.get_value('public_domain', '')
                    if saved_domain:
                        if not saved_domain.startswith('http'):
                            saved_domain = f"https://{saved_domain}"
                        public_host = saved_domain
                        cache.set('public_domain_setting', public_host, 300)
                    else:
                        public_host = f"{request.scheme}://{host}"
            except Exception:
                public_host = f"{request.scheme}://{host}"

    context['public_base_url'] = public_host
    return context
