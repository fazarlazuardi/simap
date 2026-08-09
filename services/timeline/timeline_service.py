from typing import List, Dict, Any
from audit_logs.models import AuditLog
from archives.models import Archive
from dispositions.models import Disposition

class TimelineService:
    """
    SIMAP Audit & Timeline Service
    Menyusun riwayat aktivitas & alur posisi dokumen secara terstruktur
    """

    @classmethod
    def get_document_timeline(cls, archive: Archive) -> List[Dict[str, Any]]:
        if not archive:
            return []

        timeline = []

        # 1. Registration step
        timeline.append({
            'timestamp': archive.created_at,
            'actor': archive.uploaded_by.username if archive.uploaded_by else 'Front Office',
            'action': 'Registrasi Surat Masuk / Proposal Baru',
            'badge_color': 'bg-primary',
            'note': f"No. Arsip: {archive.archive_number or 'DRAFT'}"
        })

        # 2. Verification / Dispositions
        for dispo in archive.dispositions.all().order_by('created_at'):
            sender_name = dispo.sender.employee.full_name if (dispo.sender and hasattr(dispo.sender, 'employee') and dispo.sender.employee) else dispo.sender.username
            penerima_names = ', '.join(emp.full_name for emp in dispo.forwarded_to.all()) or '—'
            
            timeline.append({
                'timestamp': dispo.created_at,
                'actor': sender_name,
                'action': f"Disposisi Diterbitkan ({dispo.get_priority_display()})",
                'badge_color': 'bg-info',
                'note': f"Penerima: {penerima_names} | Catatan: {dispo.note or '—'}"
            })

            # 3. SPPD if generated
            if hasattr(dispo, 'sppd'):
                sppd = dispo.sppd
                timeline.append({
                    'timestamp': sppd.created_at,
                    'actor': sppd.created_by.username if sppd.created_by else 'Sistem',
                    'action': f"Surat Tugas & SPPD Terbit ({sppd.sppd_number})",
                    'badge_color': 'bg-warning',
                    'note': f"Tujuan: {sppd.destination} ({sppd.departure_date} s.d {sppd.return_date})"
                })

            # 4. Report if generated
            if hasattr(dispo, 'report'):
                rep = dispo.report
                timeline.append({
                    'timestamp': rep.created_at,
                    'actor': rep.created_by.username if rep.created_by else 'Petugas',
                    'action': f"Upload Laporan Pelaksanaan ({rep.report_number})",
                    'badge_color': 'bg-success',
                    'note': f"Judul: {rep.title}"
                })

        # Audit logs matched by title/archive_number
        if archive.archive_number:
            logs = AuditLog.objects.filter(action__icontains=archive.archive_number).order_by('created_at')
            for log in logs:
                timeline.append({
                    'timestamp': log.created_at,
                    'actor': log.user.username if log.user else 'Sistem',
                    'action': log.action,
                    'badge_color': 'bg-secondary',
                    'note': f"IP: {log.ip_address or '-'}"
                })

        timeline.sort(key=lambda x: x['timestamp'], reverse=True)
        return timeline
