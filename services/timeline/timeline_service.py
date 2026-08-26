from typing import List, Dict, Any
from audit_logs.models import AuditLog
from archives.models import Archive
from dispositions.models import Disposition

class TimelineService:
    """
    SIMAP Audit & Timeline Service
    Menyusun riwayat aktivitas & alur posisi dokumen secara terstruktur dengan badge kontras tinggi.
    """

    @classmethod
    def get_document_timeline(cls, archive: Archive) -> List[Dict[str, Any]]:
        if not archive:
            return []

        timeline = []

        # 1. Registration step
        timeline.append({
            'timestamp': archive.created_at,
            'actor': archive.uploaded_by.get_full_name() or archive.uploaded_by.username if archive.uploaded_by else 'Front Office',
            'action': 'Registrasi Surat Masuk / Proposal Baru',
            'badge_color': 'bg-primary',
            'badge_class': 'badge-actor-primary',
            'note': f"No. Arsip: {archive.archive_number or 'DRAFT'}"
        })

        # 2. Dispositions step
        for dispo in archive.dispositions.all().order_by('created_at'):
            sender_name = dispo.sender.employee.full_name if (dispo.sender and hasattr(dispo.sender, 'employee') and dispo.sender.employee) else (dispo.sender.get_full_name() or dispo.sender.username)
            penerima_names = ', '.join(emp.full_name for emp in dispo.forwarded_to.all()) or '—'
            
            timeline.append({
                'timestamp': dispo.created_at,
                'actor': sender_name,
                'action': f"Disposisi Diterbitkan ({dispo.get_priority_display()})",
                'badge_color': 'bg-info',
                'badge_class': 'badge-actor-info',
                'note': f"Penerima: {penerima_names} | Catatan: {dispo.note or '—'}"
            })

            # 3. Surat Tugas
            if hasattr(dispo, 'surat_tugas'):
                for st in dispo.surat_tugas.all():
                    timeline.append({
                        'timestamp': st.created_at,
                        'actor': st.created_by.get_full_name() if st.created_by else 'Kabid II / Waka II',
                        'action': f"Penerbitan Surat Tugas (ST: {st.nomor_surat or 'Draft'})",
                        'badge_color': 'bg-warning',
                        'badge_class': 'badge-actor-warning',
                        'note': f"Perihal: {st.tentang} | Tujuan: {st.lokasi_tujuan}"
                    })

            # 4. SPPD (Survei / Perjalanan Dinas / Penyaluran)
            from sppd_service.models import SPPD
            sppds = SPPD.objects.filter(disposition=dispo).order_by('created_at')
            for sppd in sppds:
                is_survei = sppd.sppd_type == 'survei' or 'survei' in (sppd.purpose or '').lower()
                act_label = "Penerbitan SPPD Survei Lapangan Mustahik" if is_survei else "Penerbitan SPPD Penyaluran Bantuan"
                
                timeline.append({
                    'timestamp': sppd.created_at,
                    'actor': sppd.created_by.get_full_name() or sppd.created_by.username if sppd.created_by else 'Bidang IV',
                    'action': f"{act_label} ({sppd.sppd_number})",
                    'badge_color': 'bg-warning',
                    'badge_class': 'badge-actor-warning',
                    'note': f"Tujuan: {sppd.destination} ({sppd.departure_date} s.d {sppd.return_date}) | Maksud: {sppd.purpose}"
                })

                if sppd.status == 'selesai':
                    res_label = "📋 Laporan Hasil Survei Lapangan Tersimpan" if is_survei else "📜 SPPD Penyaluran Selesai"
                    timeline.append({
                        'timestamp': sppd.updated_at,
                        'actor': sppd.created_by.get_full_name() if sppd.created_by else 'Tim Pelaksana',
                        'action': res_label,
                        'badge_color': 'bg-success',
                        'badge_class': 'badge-actor-success',
                        'note': f"Catatan: {sppd.report_notes or 'Telah dilaksanakan'}"
                    })

            # 5. Final Disbursement LHP Report (Only if archive status is completed/disbursed & has report_number)
            if hasattr(dispo, 'report'):
                rep = dispo.report
                if rep.report_number and archive.status in ['selesai', 'telah_disalurkan']:
                    timeline.append({
                        'timestamp': rep.created_at,
                        'actor': rep.created_by.get_full_name() or rep.created_by.username if rep.created_by else 'Petugas',
                        'action': f"Laporan Hasil Pelaksanaan (LHP) Penyaluran ({rep.report_number})",
                        'badge_color': 'bg-success',
                        'badge_class': 'badge-actor-success',
                        'note': f"Judul: {rep.title} | Nominal: Rp {rep.amount_disbursed:,.0f}"
                    })

        # Audit logs matched by title/archive_number
        if archive.archive_number:
            logs = AuditLog.objects.filter(action__icontains=archive.archive_number).order_by('created_at')
            for log in logs:
                timeline.append({
                    'timestamp': log.created_at,
                    'actor': log.user.get_full_name() or log.user.username if log.user else 'Sistem',
                    'action': log.action,
                    'badge_color': 'bg-secondary',
                    'badge_class': 'badge-actor-secondary',
                    'note': f"IP: {log.ip_address or '-'}"
                })

        timeline.sort(key=lambda x: x['timestamp'], reverse=True)
        return timeline
