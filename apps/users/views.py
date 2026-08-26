from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth, TruncMonth
from django.utils import timezone
from django.core.cache import cache
from .models import User, SystemSetting, Employee, AppConfig, Department
from archives.models import Archive, Category
from dispositions.models import Disposition
from agendas.models import Agenda
from notifications.models import Notification
from django.conf import settings
from django.http import JsonResponse
from services.integrations.gateway_service import WhatsAppService

def superuser_only(user): return getattr(user, 'is_superadmin', False) or user.is_superuser

def get_active_pov_role(request):
    if request.user.is_authenticated and request.user.is_superadmin:
        return request.session.get('active_pov', 'admin')
    if getattr(request.user, 'is_waka_2', False):
        return 'waka_2'
    if getattr(request.user, 'is_kabid_2', False):
        return 'kabid_2'
    return 'admin' if getattr(request.user, 'is_superadmin', False) else 'staff'

@login_required
def switch_pov(request):
    """
    Endpoint untuk Superadmin beralih mode simulasi Tampilan (POV Switcher)
    ke peran Front Office, Kabid IV, Ketua BAZNAS, Waka IV, Waka II, Kabid II, atau Reset ke Default.
    """
    if not request.user.is_superadmin:
        messages.error(request, "Hanya Superadmin yang berhak mengakses simulasi POV Tampilan.")
        return redirect('users:dashboard')

    target_pov = request.GET.get('role', 'admin').strip().lower()
    allowed_roles = ['admin', 'sdm', 'kabid_4', 'ketua', 'waka_4', 'waka_2', 'kabid_2']
    
    role_labels = {
        'admin': 'Superadmin IT Default',
        'sdm': 'Front Office / Resepsionis',
        'kabid_4': 'Kabid IV (Administrasi & SDM)',
        'ketua': 'Ketua BAZNAS',
        'waka_4': 'Waka IV (Administrasi, SDM & Umum)',
        'waka_2': 'Waka II (Pendistribusian & Bantuan)',
        'kabid_2': 'Kabid II (Pendistribusian & Pendayagunaan)',
    }
    
    if target_pov in allowed_roles:
        if target_pov == 'admin':
            request.session.pop('active_pov', None)
            messages.success(request, "Tampilan berhasil dikembalikan ke Superadmin IT Default.")
        else:
            request.session['active_pov'] = target_pov
            messages.info(request, f"Mode Simulasi POV Aktif: Anda sedang melihat sistem dari perspektif {role_labels.get(target_pov, target_pov.upper())}.")
    else:
        messages.error(request, "Pilihan Peran POV tidak valid.")

    return redirect(request.META.get('HTTP_REFERER') or 'users:dashboard')

@login_required
def dashboard_index(request):
    today = timezone.now().date()
    active_pov = get_active_pov_role(request)
    is_waka_or_kabid_2 = active_pov in ['waka_2', 'kabid_2'] or getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)

    # 1. Stat Counters
    surat_masuk_count = Archive.objects.filter(archive_type='surat_masuk').count()
    proposal_aktif_count = Archive.objects.filter(archive_type='proposal').exclude(status__in=['selesai', 'ditolak']).count()
    today_agendas_qs = Agenda.objects.filter(scheduled_at__date=today).order_by('scheduled_at')
    today_agendas_count = today_agendas_qs.count()

    from sppd_service.models import SPPD
    active_sppd_qs = SPPD.objects.filter(is_cancelled=False).select_related('disposition__archive').prefetch_related('assigned_employees').order_by('-departure_date')
    sppd_berjalan_count = active_sppd_qs.count()

    menunggu_laporan_count = Archive.objects.filter(status__in=['sudah_ditugaskan', 'proses', 'didisposisikan']).exclude(status='selesai').distinct().count()
    dokumen_selesai_count = Archive.objects.filter(status='selesai').count()
    total_archives = Archive.objects.count()

    # Disposisi Pending (Fokus Dokumen Terverifikasi yang Siap Didisposisikan Ketua BAZNAS)
    if request.user.is_superadmin and not is_waka_or_kabid_2:
        pending_dispositions = Archive.objects.filter(status__in=['terverifikasi', 'disposisi_pimpinan']).exclude(dispositions__isnull=False).count() + Disposition.objects.filter(status='baru').count()
    elif request.user.is_pimpinan or request.user.is_kabid or is_waka_or_kabid_2:
        pending_dispositions = Archive.objects.filter(status__in=['terverifikasi', 'disposisi_pimpinan']).exclude(dispositions__isnull=False).count() + Disposition.objects.filter(status='baru').distinct().count()
    else:
        pending_dispositions = Disposition.objects.filter(forwarded_to__user_account=request.user, status='terverifikasi').distinct().count()

    # 2. Timeline Aktivitas Hari Ini (Audit Log Trail)
    from audit_logs.models import AuditLog
    recent_activity_logs = AuditLog.objects.select_related('user').all().order_by('-created_at')[:7]


    # 3. Proposal / Document Pipeline Tracker (5 Latest Active Documents)
    tracker_proposals = Archive.objects.select_related('category', 'uploaded_by').prefetch_related('dispositions__sppd_list', 'dispositions__report').exclude(status='ditolak').order_by('-updated_at')

    # Khusus Waka II & Kabid II: HANYA menampilkan Dokumen Bantuan yang SUDAH diverifikasi Kabid IV
    if is_waka_or_kabid_2:
        from services.workflows.workflow_engine import WorkflowEngine
        tracker_proposals = tracker_proposals.filter(
            Q(verified_by_kabid=True) | ~Q(status='baru')
        )
        bantuan_ids = [arc.id for arc in tracker_proposals if WorkflowEngine.is_bantuan(arc)]
        tracker_proposals = Archive.objects.filter(id__in=bantuan_ids).select_related('category', 'uploaded_by').prefetch_related('dispositions__sppd_list', 'dispositions__report').order_by('-updated_at')

    tracker_proposals = tracker_proposals[:5]

    from services.workflows.workflow_engine import WorkflowEngine
    tracker_items = []
    for arc in tracker_proposals:
        is_bantuan = WorkflowEngine.is_bantuan(arc)
        s = arc.status
        latest_sppd = arc.latest_sppd
        latest_report = arc.latest_report
        has_completed_lhp = bool(s in ['selesai', 'telah_disalurkan'] and latest_report and latest_report.report_number)

        if is_bantuan:
            # 8-step pipeline: Masuk -> Verifikasi -> Disposisi -> Proses Bidang II -> Survei -> Penyaluran -> Laporan -> Selesai
            steps = ['Masuk', 'Verifikasi', 'Disposisi', 'Proses Bidang II', 'Survei', 'Penyaluran', 'Laporan', 'Selesai']
            
            has_penyaluran_sppd = False
            if latest_sppd:
                purp_str = ((latest_sppd.purpose or '') + ' ' + (latest_sppd.sppd_type or '')).lower()
                if latest_sppd.sppd_type == 'penyaluran' or any(k in purp_str for k in ['penyaluran', 'pentasyarufan', 'cair', 'santunan', 'rutilahu', 'gharimin', 'bedah rumah', 'kursi roda']):
                    has_penyaluran_sppd = True

            has_penyaluran_st = False
            if arc.latest_st:
                st_str = (arc.latest_st.tentang or '').lower()
                if any(k in st_str for k in ['penyaluran', 'pentasyarufan', 'disalurkan']):
                    has_penyaluran_st = True

            if s == 'selesai':
                step_idx = 8 # Selesai
            elif has_completed_lhp and s == 'telah_disalurkan':
                step_idx = 7 # Laporan (LHP Pentasyarufan Akhir)
            elif s == 'telah_disalurkan' or has_penyaluran_sppd or has_penyaluran_st:
                step_idx = 6 # Penyaluran Bantuan Mustahik
            elif s in ['dalam_survei', 'telah_disurvei'] or (latest_sppd and ('survei' in (latest_sppd.purpose or '').lower() or 'verifikasi' in (latest_sppd.purpose or '').lower())) or (arc.latest_st and 'survei' in (arc.latest_st.tentang or '').lower()):
                step_idx = 5 # Survei Lapangan Mustahik
            elif s == 'proses':
                step_idx = 4 # Proses Bidang II
            elif s in ['didisposisikan', 'disposisi_pimpinan', 'didisposisi_ketua', 'meja_waka4', 'disposisi_waka'] or arc.dispositions.exists():
                step_idx = 3 # Disposisi Pimpinan
            elif arc.verified_by_kabid or s in ['verifikasi_kabid', 'terverifikasi']:
                step_idx = 2 # Verifikasi Kabid IV
            else:
                step_idx = 1 # Masuk (Registrasi FO)

            progress_percent = int(((step_idx - 1) / 7.0) * 100)
            
            bantuan_labels_by_step = {
                1: 'REGISTRASI MASUK',
                2: 'VERIFIKASI KABID IV',
                3: 'DISPOSISI PIMPINAN',
                4: 'PROSES BIDANG II',
                5: 'SURVEI LAPANGAN MUSTAHIK',
                6: 'PENYALURAN BANTUAN',
                7: 'LAPORAN HASIL (LHP)',
                8: 'SELESAI & TEREKAP',
            }
            status_label = bantuan_labels_by_step.get(step_idx, arc.workflow_status_display)
        else:
            # 7-step pipeline: Masuk -> Verifikasi -> Disposisi -> Proses -> (Menghadiri / Tindak Lanjut) -> Laporan -> Selesai
            step5_name = 'Menghadiri' if (latest_sppd and any(k in (latest_sppd.purpose or '').lower() for k in ['hadir', 'undangan', 'acara', 'rapat'])) else 'Tindak Lanjut'
            steps = ['Masuk', 'Verifikasi', 'Disposisi', 'Proses', step5_name, 'Laporan', 'Selesai']

            if s == 'selesai':
                step_idx = 7 # Selesai
            elif s in ['laporan', 'telah_dilaporkan'] or (has_completed_lhp and s == 'selesai'):
                step_idx = 6 # Laporan
            elif latest_sppd or s in ['sudah_ditugaskan', 'menghadiri_undangan'] or arc.latest_st:
                step_idx = 5 # Menghadiri / Tindak Lanjut
            elif s == 'proses':
                step_idx = 4
            elif s in ['didisposisikan', 'disposisi_pimpinan', 'didisposisi_ketua', 'meja_waka4', 'disposisi_waka'] or arc.dispositions.exists():
                step_idx = 3
            elif arc.verified_by_kabid or s in ['verifikasi_kabid', 'terverifikasi']:
                step_idx = 2
            else:
                step_idx = 1 # Masuk

            progress_percent = int(((step_idx - 1) / 6.0) * 100)

            umum_labels_by_step = {
                1: 'DOKUMEN MASUK',
                2: 'VERIFIKASI KABID IV',
                3: 'DISPOSISI PIMPINAN',
                4: 'DIPROSES BIDANG TERKAIT',
                5: 'MENGHADIRI UNDANGAN' if 'Menghadiri' in step5_name else 'TINDAK LANJUT',
                6: 'LAPORAN HASIL (LHP)',
                7: 'SELESAI & TEREKAP',
            }
            status_label = umum_labels_by_step.get(step_idx, arc.workflow_status_display)

        tracker_items.append({
            'archive': arc,
            'is_bantuan': is_bantuan,
            'steps': steps,
            'step_idx': step_idx,
            'progress_percent': progress_percent,
            'status_label': status_label,
        })


    # 4. SPPD Berjalan List (Top 5)
    sppd_list_recent = active_sppd_qs[:5]

    # 5. Chart Data (100% Realtime Dynamic Data dari Database)
    chart_doc_counts = [
        surat_masuk_count,
        proposal_aktif_count,
        sppd_berjalan_count,
        Archive.objects.filter(archive_type='laporan').count(),
        Archive.objects.exclude(archive_type__in=['surat_masuk', 'proposal', 'laporan']).count()
    ]

    # Chart 2: Status Seluruh Dokumen Permohonan Bantuan (Proposal + Surat Masuk Permohonan Bantuan)
    all_archives_list = list(Archive.objects.select_related('category').prefetch_related('dispositions__surat_tugas', 'dispositions__sppd_list', 'dispositions__report').all())
    
    bantuan_cat_keywords = [
        'bantuan', 'rutilahu', 'kesehatan', 'gharimin', 'pendidikan',
        'peribadatan', 'meubelair', 'meubellair', 'mebeulair', 'sarpras', 'sarana', 'prasarana',
        'sekolah', 'pesantren', 'pembangunan',
        'umkm', 'musafir', 'muallaf', 'santunan', 'sembako', 'lpj',
        'pendistribusian', 'penyaluran', 'rtlh', 'bencana', 'tanggap', 'penanggulangan', 'kebakaran', 'banjir', 'longsor', 'gempa'
    ]

    def is_bantuan_doc_check(arc):
        cat_obj = getattr(arc, 'category', None)
        c_name = cat_obj.name if cat_obj else ''
        c_lower = c_name.lower()
        if any(kw in c_lower for kw in ['kerjasama', 'kerja sama', 'undangan', 'audiensi', 'surat dinas', 'nota dinas', 'dokumen internal', 'upz', 'vendor']):
            return False
        elif any(kw in c_lower for kw in bantuan_cat_keywords):
            return True
        return WorkflowEngine.is_bantuan(arc)

    all_bantuan_docs = [arc for arc in all_archives_list if is_bantuan_doc_check(arc)]

    diproses_bantuan_count = 0
    survei_bantuan_count = 0
    penyaluran_bantuan_count = 0
    laporan_bantuan_count = 0
    selesai_bantuan_count = 0

    for arc in all_bantuan_docs:
        s = arc.status
        sppd = arc.latest_sppd
        st = arc.latest_st
        rep = arc.latest_report
        has_completed_lhp = bool(rep and rep.report_number)

        has_penyaluran_sppd = False
        if sppd:
            purp_str = ((sppd.purpose or '') + ' ' + (sppd.sppd_type or '')).lower()
            if sppd.sppd_type == 'penyaluran' or any(k in purp_str for k in ['penyaluran', 'pentasyarufan', 'cair', 'santunan', 'rutilahu', 'gharimin', 'bedah rumah', 'kursi roda']):
                has_penyaluran_sppd = True

        has_penyaluran_st = False
        if st:
            st_str = (st.tentang or '').lower()
            if any(k in st_str for k in ['penyaluran', 'pentasyarufan', 'disalurkan']):
                has_penyaluran_st = True

        if s == 'selesai':
            selesai_bantuan_count += 1
        elif s in ['laporan', 'telah_dilaporkan'] or (has_completed_lhp and s == 'telah_disalurkan'):
            laporan_bantuan_count += 1
        elif s == 'telah_disalurkan' or has_penyaluran_sppd or has_penyaluran_st:
            penyaluran_bantuan_count += 1
        elif s in ['dalam_survei', 'telah_disurvei'] or (sppd and ('survei' in (sppd.purpose or '').lower() or 'verifikasi' in (sppd.purpose or '').lower())) or (st and 'survei' in (st.tentang or '').lower()):
            survei_bantuan_count += 1
        else:
            diproses_bantuan_count += 1

    chart_proposal_status = [
        diproses_bantuan_count,
        survei_bantuan_count,
        penyaluran_bantuan_count,
        laporan_bantuan_count,
        selesai_bantuan_count
    ]

    # Fetch up to 10 agendas (today first, then all latest agendas in DB)
    agendas_list = list(today_agendas_qs[:10])
    if len(agendas_list) < 10:
        other_agendas = Agenda.objects.exclude(id__in=[a.id for a in agendas_list]).order_by('-scheduled_at')[:10 - len(agendas_list)]
        agendas_list.extend(list(other_agendas))

    # Bar Chart Data for Bantuan Handling Breakdown (100% Real Database Query)
    from services.analytics.reporting_service import ReportingService
    bantuan_analytics = ReportingService.get_bantuan_analytics()
    bantuan_bar_labels = bantuan_analytics.get('bantuan_chart_labels', [])
    bantuan_bar_series = bantuan_analytics.get('bantuan_chart_series', [])

    dispo_sla_analytics = ReportingService.get_disposition_sla_analytics()

    wa_health = cache.get('wa_health')
    if wa_health is None:
        wa_health = WhatsAppService.check_health()
        cache.set('wa_health', wa_health, 60)

    pov_names = {
        'admin': 'Superadmin IT (Default)',
        'sdm': 'Front Office / Resepsionis (Registrasi & Upload)',
        'kabid_4': 'Kabid IV (Administrasi & SDM)',
        'ketua': 'Ketua BAZNAS (Disposisi Tahap 1)',
        'waka_4': 'Waka IV (Administrasi, SDM & Umum)',
        'waka_2': 'Waka II (Pendistribusian & Bantuan Mustahik)',
        'kabid_2': 'Kabid II (Pendistribusian & Pendayagunaan Mustahik)',
        'staff': 'Staf Pelaksana Amil'
    }
    active_pov_name = pov_names.get(active_pov, 'Superadmin IT')

    from archives.views import can_upload_archive

    context = {
        'active_pov': active_pov,
        'active_pov_name': active_pov_name,
        'can_upload': can_upload_archive(request),
        'surat_masuk_count': surat_masuk_count,
        'proposal_aktif_count': proposal_aktif_count,
        'today_agendas_count': today_agendas_count,
        'today_agendas_list': agendas_list[:10],
        'sppd_berjalan_count': sppd_berjalan_count,
        'menunggu_laporan_count': menunggu_laporan_count,
        'dokumen_selesai_count': dokumen_selesai_count,
        'total_archives': total_archives,
        'pending_dispositions': pending_dispositions,
        'recent_activity_logs': recent_activity_logs,
        'tracker_items': tracker_items,
        'sppd_list_recent': sppd_list_recent,
        'chart_doc_counts': chart_doc_counts,
        'chart_proposal_status': chart_proposal_status,
        'bantuan_bar_labels': bantuan_bar_labels,
        'bantuan_bar_series': bantuan_bar_series,
        'dispo_sla_analytics': dispo_sla_analytics,
        'today': timezone.now(),
        'wa_status': wa_health['status'],
        'wa_ready': wa_health['ready'],
        'wa_message': wa_health['message'],
    }
    return render(request, 'dashboard/index.html', context)




@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        
        avatar_file = request.FILES.get('profile_picture')
        if avatar_file:
            user.profile_picture = avatar_file
            
        new_password = request.POST.get('password')
        if new_password: user.set_password(new_password)
        user.save()
        messages.success(request, "Profil dan Foto Profil berhasil diperbarui.")
        return redirect('users:profile')
    return render(request, 'users/profile.html', {'user_obj': request.user})


@login_required
@user_passes_test(superuser_only)
def app_settings_view(request):
    config = AppConfig.get_config()
    if request.method == 'POST':
        if request.POST.get('action') == 'clear_all_notifications' or 'clear_notifications' in request.POST:
            from notifications.models import Notification
            count = Notification.objects.count()
            Notification.objects.all().delete()
            messages.success(request, f"Berhasil membersihkan total {count} notifikasi lonceng dari seluruh akun pengguna di sistem SIMAP.")
            return redirect('users:app_settings')

        config.app_name = request.POST.get('app_name')
        new_logo = request.FILES.get('app_logo')
        if new_logo: config.app_logo = new_logo
        config.save()

        # Handle credentials file upload (Service Account)
        creds_file = request.FILES.get('drive_credentials')
        if creds_file:
            import os
            import uuid
            from django.conf import settings as django_settings
            creds_dir = os.path.join(django_settings.MEDIA_ROOT, 'credentials')
            os.makedirs(creds_dir, exist_ok=True)
            safe_name = f"{uuid.uuid4().hex}.json"
            creds_path = os.path.join(creds_dir, safe_name)
            with open(creds_path, 'wb+') as f:
                for chunk in creds_file.chunks():
                    f.write(chunk)
            SystemSetting.objects.update_or_create(
                key='GOOGLE_DRIVE_CREDENTIALS',
                defaults={'value': creds_path}
            )

        # Handle OAuth client config upload
        oauth_file = request.FILES.get('oauth_credentials')
        if oauth_file:
            import json
            try:
                content = oauth_file.read().decode('utf-8')
                json.loads(content)
                SystemSetting.objects.update_or_create(
                    key='GOOGLE_OAUTH_CLIENT_CONFIG',
                    defaults={'value': content}
                )
                messages.success(request, "File OAuth Client ID berhasil diupload.")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                messages.error(request, f"File OAuth tidak valid: {e}")

        settings_data = {
            'WA_GATEWAY_URL': request.POST.get('wa_url'),
            'GOOGLE_DRIVE_ID': request.POST.get('drive_id'),
            'DRIVE_BACKUP_ENABLED': request.POST.get('DRIVE_BACKUP_ENABLED', 'off'),
            'OFFICE_ADDRESS': request.POST.get('office_address'),
            'OFFICE_EMAIL': request.POST.get('office_email'),
            'SYSTEM_MAINTENANCE': request.POST.get('maintenance', 'off'),
            'SMTP_HOST': request.POST.get('smtp_host'),
            'SMTP_PORT': request.POST.get('smtp_port'),
            'SMTP_USE_TLS': request.POST.get('smtp_use_tls', 'on'),
            'SMTP_HOST_USER': request.POST.get('smtp_host_user'),
            'SMTP_HOST_PASSWORD': request.POST.get('smtp_host_password'),
            'SMTP_FROM_EMAIL': request.POST.get('smtp_from_email'),
        }
        for key, value in settings_data.items():
            if value is not None:
                SystemSetting.objects.update_or_create(key=key, defaults={'value': value})

        # Save numbering config
        numbering_keys = [
            'NUMBERING_ARCHIVE_PATTERN', 'NUMBERING_SPPD_PATTERN',
            'NUMBERING_REPORT_PATTERN', 'NUMBERING_DISPOSITION_PATTERN',
            'NUMBERING_INDEX_DIGITS', 'NUMBERING_RESET',
        ]
        for key in numbering_keys:
            val = request.POST.get(key)
            if val is not None:
                SystemSetting.objects.update_or_create(key=key, defaults={'value': val})

        messages.success(request, "Pengaturan aplikasi berhasil disimpan.")
        return redirect('users:app_settings')

    sys_settings = {s.key: s.value for s in SystemSetting.objects.all()}
    if 'GOOGLE_DRIVE_CREDENTIALS' not in sys_settings or not sys_settings['GOOGLE_DRIVE_CREDENTIALS']:
        sys_settings['GOOGLE_DRIVE_CREDENTIALS'] = getattr(settings, 'GOOGLE_DRIVE_CREDENTIALS', 'credentials/google-service-account.json')

    # Check OAuth status
    from reports.models import GoogleOAuthToken
    oauth_token = GoogleOAuthToken.objects.first()
    oauth_status = None
    if oauth_token and oauth_token.refresh_token:
        oauth_status = 'connected'
    elif sys_settings.get('GOOGLE_OAUTH_CLIENT_CONFIG'):
        oauth_status = 'config_uploaded'
    else:
        oauth_status = 'not_configured'

    context = {
        'config': config,
        'settings': sys_settings,
        'departments': Department.objects.all(),
        'categories': Category.objects.all().annotate(doc_count=Count('archive')),
        'oauth_status': oauth_status,
    }
    return render(request, 'users/app_settings.html', context)

@login_required
@user_passes_test(superuser_only)
def department_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Department.objects.get_or_create(name=name)
            messages.success(request, f"Bidang '{name}' berhasil ditambahkan.")
    return redirect('users:app_settings')

@login_required
@user_passes_test(superuser_only)
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if dept.employees.exists():
        messages.error(request, "Bidang tidak bisa dihapus karena masih digunakan.")
    else:
        name = dept.name
        dept.delete()
        messages.success(request, f"Bidang '{name}' berhasil dihapus.")
    return redirect('users:app_settings')

@login_required
@user_passes_test(superuser_only)
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Category.objects.get_or_create(name=name)
            messages.success(request, f"Kategori '{name}' berhasil ditambahkan.")
    return redirect('users:app_settings')

@login_required
@user_passes_test(superuser_only)
def category_edit(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if new_name:
            old_name = cat.name
            cat.name = new_name
            cat.save()
            messages.success(request, f"Kategori '{old_name}' berhasil diperbarui menjadi '{new_name}'.")
        else:
            messages.error(request, "Nama kategori tidak boleh kosong.")
    return redirect('users:app_settings')

@login_required
@user_passes_test(superuser_only)
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    if cat.archive_set.exists():
        messages.error(request, "Kategori tidak bisa dihapus karena masih digunakan.")
    else:
        name = cat.name
        cat.delete()
        messages.success(request, f"Kategori '{name}' berhasil dihapus.")
    return redirect('users:app_settings')

@login_required
def user_list(request):
    from django.db.models import Q
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users_qs = User.objects.all().select_related('employee').order_by('-date_joined')

    # Total counts for KPI Stat Cards
    total_users = users_qs.count()
    active_users = users_qs.filter(is_active=True).count()
    pimpinan_super_count = users_qs.filter(Q(is_superuser=True) | Q(role__in=['pimpinan', 'waka_1', 'waka_2', 'waka_3', 'waka_4'])).count()
    inactive_users = users_qs.filter(is_active=False).count()

    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(employee__full_name__icontains=query)
        )

    if role_filter:
        users_qs = users_qs.filter(role=role_filter)

    if status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    per_page = int(request.GET.get('per_page', 10))
    paginator = Paginator(users_qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'users/list.html', {
        'page_obj': page_obj,
        'users_list': page_obj,
        'total_users': total_users,
        'active_users': active_users,
        'pimpinan_super_count': pimpinan_super_count,
        'inactive_users': inactive_users,
        'roles': User.ROLE_CHOICES if hasattr(User, 'ROLE_CHOICES') else [],
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
    })

@login_required
@login_required
def user_create(request):
    if not (getattr(request.user, 'is_superuser', False) or getattr(request.user, 'is_superadmin', False)) or request.session.get('active_pov'):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak menambah pengguna.")
        return redirect('users:employee_list')
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role_code = request.POST.get('role')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username sudah digunakan.")
        else:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role_code
            )
            messages.success(request, f"Pengguna {username} berhasil ditambahkan.")
            return redirect('users:employee_list')
    roles = User.ROLE_CHOICES
    return render(request, 'users/create.html', {'roles': roles})

@login_required
def wa_health_check(request):
    health = WhatsAppService.check_health()
    return JsonResponse(health)

@login_required
def user_edit(request, pk):
    if not (getattr(request.user, 'is_superuser', False) or getattr(request.user, 'is_superadmin', False)) or request.session.get('active_pov'):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak mengedit pengguna.")
        return redirect('users:employee_list')
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user_obj.username = request.POST.get('username'); user_obj.email = request.POST.get('email')
        user_obj.first_name = request.POST.get('first_name'); user_obj.last_name = request.POST.get('last_name')
        user_obj.role = request.POST.get('role')
        new_password = request.POST.get('password')
        if new_password: user_obj.set_password(new_password)
        user_obj.save(); messages.success(request, f"Data pengguna {user_obj.username} diperbarui.")
        return redirect('users:employee_list')
    roles = User.ROLE_CHOICES
    return render(request, 'users/edit.html', {'user_obj': user_obj, 'roles': roles})

@login_required
def user_delete(request, pk):
    if not (getattr(request.user, 'is_superuser', False) or getattr(request.user, 'is_superadmin', False)) or request.session.get('active_pov'):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak menghapus pengguna.")
        return redirect('users:employee_list')
    if request.method == 'POST':
        user_obj = get_object_or_404(User, pk=pk)
        if not user_obj.is_superuser:
            username = user_obj.username; user_obj.delete()
            messages.success(request, f"Pengguna {username} dihapus.")
    return redirect('users:employee_list')

@login_required
def employee_position_json(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    return JsonResponse({
        'id': emp.id,
        'full_name': emp.full_name,
        'position': emp.position or '',
        'department': emp.dept_relation.name if emp.dept_relation else '',
    })

@login_required
def ai_assistant_view(request):
    return render(request, 'users/ai_assistant.html')

@login_required
@user_passes_test(superuser_only)
def test_email_connection(request):
    """
    Endpoint pengujian koneksi email SMTP via AJAX.
    """
    from services.notifications.email_service import send_test_email
    target_email = request.GET.get('email') or SystemSetting.get_value('OFFICE_EMAIL') or 'kabupatenbaznastangerang@gmail.com'
    try:
        send_test_email(target_email)
        return JsonResponse({
            'status': 'success',
            'message': f"Email pengujian berhasil dikirim ke {target_email}. Silakan periksa kotak masuk/spam email Anda."
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f"Gagal mengirim email pengujian: {str(e)}"
        }, status=400)