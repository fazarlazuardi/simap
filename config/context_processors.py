from django.db.models import Q
from notifications.models import Notification
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
        # Filter disposisi yang sudah diisi agar notifikasi lamanya tidak menumpuk di lonceng
        completed_archive_ids = Disposition.objects.exclude(status='baru').values_list('archive_id', flat=True)
        completed_urls = [f"/dispositions/{aid}/create/" for aid in completed_archive_ids if aid]

        unread_notifications = Notification.objects.filter(
            user=request.user, 
            status='unread'
        ).exclude(
            link_url__in=completed_urls
        ).order_by('-created_at')
        
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
            'is_kabid_4_active': is_kabid_4_active,
            'is_waka_4_active': is_waka_4_active,
            'unverified_count': unverified_count,
            'pending_waka4_dispo_count': pending_waka4_dispo_count,
            'pending_st_sppd_count': pending_st_sppd_count,
        })
    return context
