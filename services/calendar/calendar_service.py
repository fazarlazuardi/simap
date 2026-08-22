from typing import Dict, Any, List
from django.utils import timezone
from datetime import datetime
from sppd_service.models import SPPD
from agendas.models import Agenda
from internal_meetings.models import InternalMeeting
from dispositions.models import Disposition

class CalendarService:
    """
    SIMAP Centralized Work Calendar Service
    Agregasi otomatis dari SPPD, Agenda Kerja, Rapat Internal, dan Disposisi
    """

    @classmethod
    def get_calendar_events(cls, start_date=None, end_date=None) -> List[Dict[str, Any]]:
        events = []

        # 1. SPPD Events
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
                'location': sppd.destination or 'Lokasi Penugasan',
                'source_type': 'sppd',
                'sppd_number': sppd.sppd_number,
                'assigned_to': assigned_names or 'Petugas SPPD',
                'status': 'Selesai' if sppd.status == 'selesai' else ('Dalam Pelaksanaan' if not sppd.is_cancelled else 'Dibatalkan'),
                'bg_color': '#3b82f6', # Primary Blue
                'text_color': '#ffffff',
            })

        # 2. Agenda Events (Includes synced Rapat Internal)
        from datetime import timedelta
        agendas = Agenda.objects.all().select_related('archive').prefetch_related('assigned_to', 'assigned_employees')
        if start_date:
            agendas = agendas.filter(scheduled_at__date__gte=start_date)
        if end_date:
            agendas = agendas.filter(scheduled_at__date__lte=end_date)

        for agenda in agendas:
            if not agenda.scheduled_at:
                continue
            local_dt = timezone.localtime(agenda.scheduled_at)
            assigned_names = agenda.assigned_names_display
            date_str = local_dt.strftime('%Y-%m-%d')
            time_str = local_dt.strftime('%H:%M WIB')
            bg = '#10b981' if agenda.status == 'selesai' else ('#ef4444' if agenda.status == 'dibatalkan' else ('#f59e0b' if agenda.status == 'diundur' else '#0e9f6e'))
            
            src_type = 'sppd' if (agenda.is_sppd_generated or agenda.sppd_ref) else ('meeting' if agenda.internal_meeting_id else 'agenda')
            prefix = '👥 [RAPAT]' if agenda.internal_meeting_id else '📅 [AGENDA]'

            events.append({
                'id': f"agenda-{agenda.id}",
                'title': f"{prefix} {agenda.title} ({time_str})",
                'start': date_str,
                'allDay': True,
                'display': 'block',
                'time': time_str,
                'location': agenda.location or 'Kantor BAZNAS / Sesuai Undangan',
                'source_type': src_type,
                'assigned_to': assigned_names or 'Internal',
                'status': agenda.get_status_display(),
                'bg_color': '#8b5cf6' if agenda.internal_meeting_id else bg,
                'text_color': '#ffffff',
            })

        # 3. Standalone Rapat Internal Events (Fallback for unlinked meetings)
        linked_meeting_ids = set()
        for agenda in agendas:
            mid = getattr(agenda, 'internal_meeting_id', None)
            if mid:
                linked_meeting_ids.add(mid)

        meetings = InternalMeeting.objects.exclude(id__in=linked_meeting_ids).select_related('leader', 'notulis').prefetch_related('leaders', 'participants')
        if start_date:
            meetings = meetings.filter(scheduled_at__date__gte=start_date)
        if end_date:
            meetings = meetings.filter(scheduled_at__date__lte=end_date)

        for mtg in meetings:
            if not mtg.scheduled_at:
                continue
            local_dt = timezone.localtime(mtg.scheduled_at)
            date_str = local_dt.strftime('%Y-%m-%d')
            time_str = local_dt.strftime('%H:%M WIB')
            leaders_text = mtg.leader_names_display if hasattr(mtg, 'leader_names_display') else (mtg.leader.full_name if mtg.leader else 'Pimpinan BAZNAS')
            events.append({
                'id': f"meeting-{mtg.id}",
                'title': f"👥 [RAPAT] {mtg.title} ({time_str})",
                'start': date_str,
                'allDay': True,
                'display': 'block',
                'time': time_str,
                'location': mtg.location or 'Ruang Rapat Utama BAZNAS',
                'source_type': 'meeting',
                'assigned_to': f"Pimpinan: {leaders_text}",
                'status': mtg.get_status_display(),
                'bg_color': '#8b5cf6',
                'text_color': '#ffffff',
            })

        # 4. Hari Libur Nasional & Cuti Bersama SKB 3 Menteri (Google Calendar Feed)
        from services.integrations.google_calendar_service import GoogleCalendarService
        holidays = GoogleCalendarService.get_national_holidays_events(start_year=2025, end_year=2027)
        
        for h in holidays:
            # Check date range filter if provided
            h_start = h['start']
            if start_date and h_start < start_date:
                continue
            if end_date and h_start > end_date:
                continue

            events.append({
                'id': h['id'],
                'title': h['title'],
                'start': h['start'],
                'end': h.get('end', h['start']),
                'location': h['extendedProps']['location'],
                'source_type': h['extendedProps']['source_type'],
                'assigned_to': h['extendedProps']['assigned_to'],
                'status': h['extendedProps']['status'],
                'bg_color': h['backgroundColor'],
                'text_color': '#FFFFFF',
                'allDay': True,
                'display': 'block',
            })

        events.sort(key=lambda x: x['start'])
        return events

