from typing import Dict, Any, List
from django.db.models import Count, Q
from django.utils import timezone
from sppd_service.models import SPPD
from archives.models import Archive
from users.models import Employee
from services.workflows.workflow_engine import WorkflowEngine

class ReportingService:
    """
    SIMAP Analytics & Reporting Service
    - Rekapitulasi SPPD Pegawai
    - Rekapitulasi Penanganan Dokumen Bantuan & Dokumen Umum (Dua Grafik Visual)
    """

    @classmethod
    def get_sppd_recap(cls, year: int = None, month: int = None) -> List[Dict[str, Any]]:
        """
        Rekap SPPD Pegawai bulanan/tahunan untuk ranking frekuensi perjalanan dinas.
        Termasuk Pegawai Ditugaskan Utama dan Pengikut. Fallback ke rekap akumulatif jika bulan ini belum ada data.
        """
        now = timezone.now()
        sppds_qs = SPPD.objects.filter(is_cancelled=False).select_related('disposition__archive').prefetch_related('assigned_employees', 'followers')

        if year and month:
            sppds = list(sppds_qs.filter(
                Q(departure_date__year=year, departure_date__month=month) |
                Q(created_at__year=year, created_at__month=month)
            ).distinct())
        else:
            # Utamakan data SPPD bulan berjalan
            sppds = list(sppds_qs.filter(
                Q(departure_date__year=now.year, departure_date__month=now.month) |
                Q(created_at__year=now.year, created_at__month=now.month)
            ).distinct())
            
            # Jika bulan berjalan belum ada SPPD terbit, tampilkan rekap akumulatif seluruh data SPPD aktif
            if not sppds:
                sppds = list(sppds_qs.distinct())

        emp_map = {}
        for sppd in sppds:
            all_emps = set(sppd.assigned_employees.all()).union(set(sppd.followers.all()))
            for emp in all_emps:
                if emp.id not in emp_map:
                    emp_map[emp.id] = {
                        'employee': emp,
                        'total_sppd': 0,
                        'destinations': set(),
                        'sppds': []
                    }
                emp_map[emp.id]['total_sppd'] += 1
                if sppd.destination:
                    emp_map[emp.id]['destinations'].add(sppd.destination)
                emp_map[emp.id]['sppds'].append(sppd)

        result = []
        for item in emp_map.values():
            item['destinations'] = list(item['destinations'])
            result.append(item)

        result.sort(key=lambda x: (-x['total_sppd'], x['employee'].full_name))
        return result



    @classmethod
    def get_bantuan_analytics(cls, year: int = None, month: int = None, all_time: bool = False) -> Dict[str, Any]:
        """
        Rekapitulasi Penanganan Dokumen Bantuan & Umum + Sub-Klasifikasi dan 2 Grafik Visual.
        Tersinkronisasi secara dinamis 100% dengan Kategori Arsip dari Database.
        """
        from archives.models import Category
        archives = Archive.objects.select_related('category', 'uploaded_by').prefetch_related('dispositions__surat_tugas', 'dispositions__sppd_list', 'dispositions__report')

        if not all_time:
            if year:
                archives = archives.filter(created_at__year=year)
            if month:
                archives = archives.filter(created_at__month=month)

        total_umum = 0
        total_bantuan = 0
        survei_count = 0
        direct_count = 0
        sppd_penyaluran_count = 0
        transfer_penyaluran_count = 0
        
        # Ambil seluruh kategori terkini dari database untuk inisialisasi count
        db_categories = list(Category.objects.all())
        bantuan_subcat_counts = {}
        umum_subcat_counts = {}

        bantuan_cat_keywords = [
            'bantuan', 'rutilahu', 'kesehatan', 'gharimin', 'pendidikan',
            'peribadatan', 'meubelair', 'meubellair', 'mebeulair', 'sarpras', 'sarana', 'prasarana',
            'sekolah', 'pesantren', 'pembangunan',
            'umkm', 'musafir', 'muallaf', 'santunan', 'sembako', 'lpj',
            'pendistribusian', 'penyaluran', 'rtlh', 'bencana', 'tanggap', 'penanggulangan', 'kebakaran', 'banjir', 'longsor', 'gempa'
        ]

        for cat in db_categories:
            c_name = cat.name
            c_lower = c_name.lower()
            if any(kw in c_lower for kw in bantuan_cat_keywords):
                bantuan_subcat_counts[c_name] = 0
            else:
                umum_subcat_counts[c_name] = 0

        if not bantuan_subcat_counts:
            bantuan_subcat_counts['Bantuan Lainnya'] = 0
        if not umum_subcat_counts:
            umum_subcat_counts['Permohonan Umum'] = 0

        bantuan_details = []
        umum_details = []
        total_completed = 0
        bantuan_completed = 0
        umum_completed = 0

        for arc in archives.order_by('-created_at'):
            cat_obj = getattr(arc, 'category', None)
            c_name = cat_obj.name if cat_obj else ''
            c_lower = c_name.lower()

            if any(kw in c_lower for kw in ['kerjasama', 'kerja sama', 'undangan', 'audiensi', 'surat dinas', 'nota dinas', 'dokumen internal', 'upz', 'vendor']):
                is_bantuan_doc = False
            elif any(kw in c_lower for kw in bantuan_cat_keywords):
                is_bantuan_doc = True
            else:
                is_bantuan_doc = WorkflowEngine.is_bantuan(arc)

            is_done = arc.status in ['selesai', 'telah_disalurkan']
            if is_done:
                total_completed += 1

            cat_name = c_name or (WorkflowEngine.get_bantuan_subcategory(arc) if is_bantuan_doc else 'Permohonan Umum')

            if is_bantuan_doc:
                total_bantuan += 1
                if is_done:
                    bantuan_completed += 1
                if cat_name not in bantuan_subcat_counts:
                    bantuan_subcat_counts[cat_name] = 0
                bantuan_subcat_counts[cat_name] += 1

                # Analisis Skema Penyaluran Bidang II (4 Skema Operasional)
                st_list = []
                sppd_list = []
                dispos = list(arc.dispositions.all())
                for d in dispos:
                    if hasattr(d, 'surat_tugas'):
                        st_list.extend(list(d.surat_tugas.all()))
                    if hasattr(d, 'sppd_list'):
                        sppd_list.extend(list(d.sppd_list.all()))
                
                has_survei_st = any('survei' in (getattr(st, 'tentang', '') or '').lower() for st in st_list)
                has_survei_sppd = any('survei' in (getattr(s, 'maksud_perjalanan', '') or '').lower() for s in sppd_list)
                is_via_survei = has_survei_st or has_survei_sppd or (len(st_list) > 1 and not has_survei_st)

                has_penyaluran_sppd = any('penyaluran' in (getattr(s, 'maksud_perjalanan', '') or '').lower() or 'pengantaran' in (getattr(s, 'maksud_perjalanan', '') or '').lower() for s in sppd_list)
                if not has_penyaluran_sppd and len(sppd_list) > 0 and (not is_via_survei or len(sppd_list) >= 2):
                    has_penyaluran_sppd = True

                if is_via_survei:
                    survei_count += 1
                    if has_penyaluran_sppd:
                        scheme_code = 'S-1'
                        scheme_label = '📋 SURVEI ➔ 🚗 SPPD LAPANGAN'
                        scheme_badge = 'amber'
                        sppd_penyaluran_count += 1
                    else:
                        scheme_code = 'S-2'
                        scheme_label = '📋 SURVEI ➔ 💳 TRANSFER BANK'
                        scheme_badge = 'sky'
                        transfer_penyaluran_count += 1
                else:
                    direct_count += 1
                    if has_penyaluran_sppd:
                        scheme_code = 'D-1'
                        scheme_label = '⚡ DIRECT ➔ 🚗 SPPD LAPANGAN'
                        scheme_badge = 'purple'
                        sppd_penyaluran_count += 1
                    else:
                        scheme_code = 'D-2'
                        scheme_label = '⚡ DIRECT ➔ 💳 TRANSFER / KANTOR'
                        scheme_badge = 'emerald'
                        transfer_penyaluran_count += 1

                if has_penyaluran_sppd and arc.status not in ['selesai', 'telah_disalurkan']:
                    arc.status = 'telah_disalurkan'

                latest_st = st_list[-1] if st_list else None
                latest_sppd = sppd_list[-1] if sppd_list else None
                latest_report = None
                latest_dispo = arc.dispositions.order_by('-created_at').first()
                for d in arc.dispositions.all():
                    try:
                        rep = getattr(d, 'report', None)
                        if rep:
                            latest_report = rep
                            break
                    except Exception:
                        pass
                    if not latest_report:
                        from reports.models import Report
                        rep = Report.objects.filter(disposition=d).first()
                        if rep:
                            latest_report = rep
                            break

                amil_names = "-"
                survei_st = None
                for st in st_list:
                    if 'survei' in (getattr(st, 'tentang', '') or '').lower() or 'survei' in (getattr(st, 'maksud', '') or '').lower():
                        survei_st = st
                        break
                target_st = survei_st or latest_st
                if target_st and hasattr(target_st, 'pegawai_ditugaskan'):
                    names = [e.full_name for e in target_st.pegawai_ditugaskan.all() if hasattr(e, 'full_name')]
                    if names:
                        amil_names = ", ".join(names)

                # Extract Survey Specific Files & Notes
                survei_files = []
                survei_notes = ""
                is_survei_completed = False

                for s in sppd_list:
                    if s.sppd_type == 'survei' or 'survei' in (s.purpose or '').lower() or 'verifikasi' in (s.purpose or '').lower():
                        if s.status == 'selesai':
                            is_survei_completed = True
                        if s.report_notes:
                            survei_notes = s.report_notes
                        if s.report_file:
                            survei_files.append({'url': s.report_file.url, 'name': 'Dokumen Laporan Hasil Survei'})
                        if hasattr(s, 'attachments'):
                            for att in s.attachments.all():
                                if att.file:
                                    survei_files.append({'url': att.file.url, 'name': att.title or 'Lampiran / Foto Survei'})

                # Extract Final Disbursement LHP Files (Only when disbursed/completed)
                report_files = []
                has_completed_lhp = False
                if arc.status in ['selesai', 'telah_disalurkan']:
                    has_completed_lhp = True

                if latest_report and has_completed_lhp:
                    if latest_report.file:
                        report_files.append({'url': latest_report.file.url, 'name': 'Dokumen Utama LHP Penyaluran'})
                    if hasattr(latest_report, 'attachments'):
                        for att in latest_report.attachments.all():
                            if att.file:
                                report_files.append({'url': att.file.url, 'name': att.description or 'Lampiran Bukti Penyaluran'})
                    report_num = latest_report.report_number or 'LHP Terbit'
                else:
                    report_num = '-'

                amount_disbursed = float(getattr(latest_report, 'amount_disbursed', 0) or 0) if latest_report else 0.0
                disbursement_type = getattr(latest_report, 'disbursement_type', 'transfer') if latest_report else 'transfer'

                item_dict = {
                    'archive': arc,
                    'sub_category': cat_name,
                    'scheme_code': scheme_code,
                    'scheme_label': scheme_label,
                    'scheme_badge': scheme_badge,
                    'is_via_survei': is_via_survei,
                    'has_penyaluran_sppd': has_penyaluran_sppd,
                    'st_number': latest_st.nomor_surat if latest_st else '-',
                    'sppd_number': latest_sppd.sppd_number if latest_sppd else '-',
                    'report_number': report_num,
                    'dispo_pk': latest_dispo.pk if latest_dispo else None,
                    'dispo_number': latest_dispo.disposition_number if latest_dispo else (arc.archive_number or 'DISPOSISI'),
                    'amil_names': amil_names,
                    'survei_files': survei_files,
                    'survei_files_count': len(survei_files),
                    'survei_notes': survei_notes,
                    'is_survei_completed': is_survei_completed,
                    'report_files': report_files,
                    'report_files_count': len(report_files),
                    'amount_disbursed': amount_disbursed,
                    'disbursement_type': disbursement_type,
                }
                bantuan_details.append(item_dict)
            else:
                total_umum += 1
                if is_done:
                    umum_completed += 1
                if cat_name not in umum_subcat_counts:
                    umum_subcat_counts[cat_name] = 0
                umum_subcat_counts[cat_name] += 1
                umum_details.append({
                    'archive': arc,
                    'sub_category': cat_name,
                })

        total_docs = archives.count()
        completion_rate = round((total_completed / total_docs * 100), 1) if total_docs > 0 else 0
        bantuan_pct = round((total_bantuan / total_docs * 100), 1) if total_docs > 0 else 0
        umum_pct = round((total_umum / total_docs * 100), 1) if total_docs > 0 else 0

        # Sub-list untuk Penyaluran Bantuan & Survei Lapangan
        penyaluran_details = [item for item in bantuan_details if item['archive'].status in ['selesai', 'telah_disalurkan']]
        survei_details = [item for item in bantuan_details if item['is_via_survei'] or item['archive'].status == 'dalam_survei']
        total_nominal_disbursed = sum(item['amount_disbursed'] for item in penyaluran_details)

        # Ensure complete category catalog is represented with real-time truthful counts
        complete_bantuan_counts = {k: 0 for k in bantuan_subcat_counts.keys()}
        for item in bantuan_details:
            sc = item.get('sub_category') or 'Bantuan Lainnya'
            complete_bantuan_counts[sc] = complete_bantuan_counts.get(sc, 0) + 1
        
        # Sort descending by count, then alphabetically
        sorted_bantuan = sorted(complete_bantuan_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        b_chart_labels = [k for k, v in sorted_bantuan]
        b_chart_series = [v for k, v in sorted_bantuan]

        complete_umum_counts = {k: 0 for k in umum_subcat_counts.keys()}
        for item in umum_details:
            sc = item.get('sub_category') or 'Permohonan Umum'
            complete_umum_counts[sc] = complete_umum_counts.get(sc, 0) + 1
        
        sorted_umum = sorted(complete_umum_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        u_chart_labels = [k for k, v in sorted_umum]
        u_chart_series = [v for k, v in sorted_umum]

        return {
            'year': year,
            'month': month,
            'total_documents': total_docs,
            'total_umum': total_umum,
            'total_bantuan': total_bantuan,
            'total_completed': total_completed,
            'total_in_progress': total_docs - total_completed,
            'completion_rate': completion_rate,
            'bantuan_pct': bantuan_pct,
            'umum_pct': umum_pct,
            'bantuan_completed': bantuan_completed,
            'umum_completed': umum_completed,
            'survei_count': survei_count,
            'direct_count': direct_count,
            'sppd_penyaluran_count': sppd_penyaluran_count,
            'transfer_penyaluran_count': transfer_penyaluran_count,
            'total_nominal_disbursed': total_nominal_disbursed,
            'bantuan_subcat_counts': complete_bantuan_counts,
            'bantuan_chart_labels': b_chart_labels,
            'bantuan_chart_series': b_chart_series,
            'umum_subcat_counts': complete_umum_counts,
            'umum_chart_labels': u_chart_labels,
            'umum_chart_series': u_chart_series,
            'bantuan_details': bantuan_details,
            'penyaluran_details': penyaluran_details,
            'survei_details': survei_details,
            'umum_details': umum_details,
        }

    @classmethod
    def get_disposition_sla_analytics(cls) -> Dict[str, Any]:
        """
        Dashboard Analytics & SLA Response Time Pimpinan:
        - Distribusi Disposisi berdasarkan Bidang Pelaksana (Bidang 1 s/d Bidang 4)
        - Indikator Rata-rata Kecepatan Penyelesaian Tugas (SLA Response Time dalam Jam/Hari)
        - Breakdown Kinerja per Bidang
        """
        from dispositions.models import Disposition

        dispositions = Disposition.objects.select_related('archive', 'sender', 'archive__category').prefetch_related('forwarded_to', 'waka_forwarded_to')

        bidang_counts = {
            'Bidang 1 (Pengumpulan)': 0,
            'Bidang 2 (Pendistribusian)': 0,
            'Bidang 3 (Perencanaan & Keuangan)': 0,
            'Bidang 4 (Administrasi & Umum)': 0,
        }

        bidang_completed_counts = {
            'Bidang 1 (Pengumpulan)': 0,
            'Bidang 2 (Pendistribusian)': 0,
            'Bidang 3 (Perencanaan & Keuangan)': 0,
            'Bidang 4 (Administrasi & Umum)': 0,
        }

        bidang_durations = {
            'Bidang 1 (Pengumpulan)': [],
            'Bidang 2 (Pendistribusian)': [],
            'Bidang 3 (Perencanaan & Keuangan)': [],
            'Bidang 4 (Administrasi & Umum)': [],
        }

        total_dispositions = dispositions.count()
        total_completed = 0
        all_completion_times = []

        for dispo in dispositions:
            assigned_emps = list(dispo.waka_forwarded_to.all()) or list(dispo.forwarded_to.all())
            target_bidang_key = None

            for emp in assigned_emps:
                pos = (emp.position or '').lower()
                ltype = (emp.leadership_type or '').lower()
                dept = (emp.dept_relation.name if emp.dept_relation else '').lower()
                combined = f"{pos} {ltype} {dept}"

                if any(k in combined for k in ['4', 'iv', 'administrasi', 'sdm', 'umum', 'kabid 4', 'kabid iv', 'waka 4', 'waka iv']):
                    target_bidang_key = 'Bidang 4 (Administrasi & Umum)'
                    break
                elif any(k in combined for k in ['3', 'iii', 'perencanaan', 'keuangan', 'pelaporan', 'kabid 3', 'kabid iii', 'waka 3', 'waka iii']):
                    target_bidang_key = 'Bidang 3 (Perencanaan & Keuangan)'
                    break
                elif any(k in combined for k in ['2', 'ii', 'pendistribusian', 'pendayagunaan', 'pentasyarufan', 'kabid 2', 'kabid ii', 'waka 2', 'waka ii']):
                    target_bidang_key = 'Bidang 2 (Pendistribusian)'
                    break
                elif any(k in combined for k in ['1', 'i', 'pengumpulan', 'kabid 1', 'kabid i', 'waka 1', 'waka i']):
                    target_bidang_key = 'Bidang 1 (Pengumpulan)'
                    break

            if not target_bidang_key:
                arc_title = (dispo.archive.title if dispo.archive else '').lower()
                cat_name = (dispo.archive.category.name if dispo.archive and dispo.archive.category else '').lower()
                combined_arc = f"{arc_title} {cat_name}"

                if any(kw in combined_arc for kw in ['bantuan', 'rutilahu', 'kesehatan', 'pentasyarufan', 'sembako', 'mustahik']):
                    target_bidang_key = 'Bidang 2 (Pendistribusian)'
                elif any(kw in combined_arc for kw in ['pengumpulan', 'zakat', 'infaq', 'sedekah', 'upz', 'munfiq']):
                    target_bidang_key = 'Bidang 1 (Pengumpulan)'
                elif any(kw in combined_arc for kw in ['rencana', 'anggaran', 'keuangan', 'laporan keuangan', 'rkab']):
                    target_bidang_key = 'Bidang 3 (Perencanaan & Keuangan)'
                else:
                    target_bidang_key = 'Bidang 4 (Administrasi & Umum)'

            bidang_counts[target_bidang_key] += 1

            if dispo.status == 'selesai' and dispo.completed_at and dispo.created_at:
                total_completed += 1
                bidang_completed_counts[target_bidang_key] += 1

                duration_hours = (dispo.completed_at - dispo.created_at).total_seconds() / 3600.0
                all_completion_times.append(duration_hours)
                bidang_durations[target_bidang_key].append(duration_hours)

        if all_completion_times:
            avg_hours = sum(all_completion_times) / len(all_completion_times)
            avg_days = avg_hours / 24.0
        else:
            avg_hours = 0
            avg_days = 0

        bidang_sla_breakdown = {}
        for b_name in bidang_counts:
            c_total = bidang_counts[b_name]
            c_done = bidang_completed_counts[b_name]
            d_list = bidang_durations[b_name]

            if d_list:
                b_avg_h = sum(d_list) / len(d_list)
                b_avg_d = b_avg_h / 24.0
            else:
                b_avg_h = 0
                b_avg_d = 0

            completion_pct = round((c_done / c_total * 100), 1) if c_total > 0 else 0

            bidang_sla_breakdown[b_name] = {
                'total': c_total,
                'completed': c_done,
                'avg_hours': round(b_avg_h, 1),
                'avg_days': round(b_avg_d, 1),
                'completion_percent': completion_pct
            }

        sla_score_percent = round((total_completed / total_dispositions * 100), 1) if total_dispositions > 0 else 100

        return {
            'total_dispositions': total_dispositions,
            'total_completed': total_completed,
            'overall_avg_hours': round(avg_hours, 1),
            'overall_avg_days': round(avg_days, 1),
            'sla_score_percent': sla_score_percent,
            'bidang_chart_labels': list(bidang_counts.keys()),
            'bidang_chart_series': list(bidang_counts.values()),
            'bidang_sla_breakdown': bidang_sla_breakdown
        }
