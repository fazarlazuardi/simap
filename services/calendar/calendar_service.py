from typing import Dict, Any, List
from django.utils import timezone
from datetime import datetime
from sppd_service.models import SPPD
from agendas.models import Agenda
from dispositions.models import Disposition

class CalendarService:
    """
    SIMAP Centralized Work Calendar Service
    Agregasi otomatis dari SPPD, Agenda Kerja, dan Disposisi
    """

    @classmethod
    def get_calendar_events(cls, start_date=None, end_date=None) -> List[Dict[str, Any]]:
        events = []

        # 1. SPPD Events (Integrated automatically into Work Calendar)
        sppds = SPPD.objects.filter(is_cancelled=False).select_related('disposition__archive').prefetch_related('assigned_employees')
        if start_date:
            sppds = sppds.filter(departure_date__gte=start_date)
        if end_date:
            sppds = sppds.filter(return_date__lte=end_date)

        for sppd in sppds:
            archive_title = sppd.disposition.archive.title if (sppd.disposition and sppd.disposition.archive) else 'Perjalanan Dinas'
            assigned_names = ', '.join(emp.full_name for emp in sppd.assigned_employees.all())
            events.append({
                'id': f"sppd-{sppd.id}",
                'title': f"🚗 [SPPD] {archive_title}",
                'start': sppd.departure_date.strftime('%Y-%m-%d'),
                'end': sppd.return_date.strftime('%Y-%m-%d'),
                'location': sppd.destination,
                'source_type': 'sppd',
                'sppd_number': sppd.sppd_number,
                'assigned_to': assigned_names or 'Petugas SPPD',
                'status': 'Dalam Pelaksanaan' if not sppd.is_cancelled else 'Dibatalkan',
                'bg_color': '#3b82f6', # Primary Blue
                'text_color': '#ffffff',
            })

        # 2. Agenda Events
        agendas = Agenda.objects.all().select_related('archive').prefetch_related('assigned_to')
        if start_date:
            agendas = agendas.filter(scheduled_at__date__gte=start_date)
        if end_date:
            agendas = agendas.filter(scheduled_at__date__lte=end_date)

        for agenda in agendas:
            assigned_names = ', '.join(u.username for u in agenda.assigned_to.all())
            date_str = agenda.scheduled_at.strftime('%Y-%m-%d')
            time_str = agenda.scheduled_at.strftime('%H:%M')
            events.append({
                'id': f"agenda-{agenda.id}",
                'title': f"📅 [AGENDA] {agenda.title}",
                'start': date_str,
                'end': date_str,
                'time': time_str,
                'location': 'Kantor BAZNAS / Sesuai Undangan',
                'source_type': 'agenda',
                'assigned_to': assigned_names or 'Internal',
                'status': agenda.get_status_display(),
                'bg_color': '#10b981' if agenda.status == 'selesai' else '#f59e0b',
                'text_color': '#ffffff',
            })

        events.sort(key=lambda x: x['start'])
        return events
