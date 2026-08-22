import json
import urllib.request
import logging
from typing import List, Dict, Any
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    """
    SIMAP Google Calendar & National Holiday Integration Service
    - Realtime SKB 3 Menteri Libur Nasional & Cuti Bersama (2025, 2026, 2027)
    - Google Calendar 1-Click Subscribe URL & Webcal Feed Generator
    """

    OFFICIAL_HOLIDAYS = {
        2025: [
            {"title": "🔴 LIBUR: Tahun Baru 2025 Masehi", "start": "2025-01-01"},
            {"title": "🔴 LIBUR: Isra Mikraj Nabi Muhammad SAW", "start": "2025-01-27"},
            {"title": "🔴 LIBUR: Tahun Baru Imlek 2576 Kongzili", "start": "2025-01-29"},
            {"title": "🔴 CUTI BERSAMA: Imlek 2576", "start": "2025-01-28"},
            {"title": "🔴 LIBUR: Hari Suci Nyepi Saka 1947", "start": "2025-03-29"},
            {"title": "🔴 CUTI BERSAMA: Nyepi Saka 1947", "start": "2025-03-28"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1446 H", "start": "2025-03-31"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1446 H", "start": "2025-04-01"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1446 H", "start": "2025-04-02"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1446 H", "start": "2025-04-03"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1446 H", "start": "2025-04-04"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1446 H", "start": "2025-04-07"},
            {"title": "🔴 LIBUR: Wafat Yesus Kristus", "start": "2025-04-18"},
            {"title": "🔴 LIBUR: Hari Paskah", "start": "2025-04-20"},
            {"title": "🔴 LIBUR: Hari Buruh Internasional", "start": "2025-05-01"},
            {"title": "🔴 LIBUR: Hari Raya Waisak 2569 BE", "start": "2025-05-12"},
            {"title": "🔴 CUTI BERSAMA: Waisak 2569 BE", "start": "2025-05-13"},
            {"title": "🔴 LIBUR: Kenaikan Yesus Kristus", "start": "2025-05-29"},
            {"title": "🔴 CUTI BERSAMA: Kenaikan Yesus Kristus", "start": "2025-05-30"},
            {"title": "🔴 LIBUR: Hari Lahir Pancasila", "start": "2025-06-01"},
            {"title": "🔴 LIBUR: Hari Raya Idul Adha 1446 H", "start": "2025-06-06"},
            {"title": "🔴 CUTI BERSAMA: Idul Adha 1446 H", "start": "2025-06-09"},
            {"title": "🔴 LIBUR: Tahun Baru Islam 1447 H", "start": "2025-06-27"},
            {"title": "🔴 LIBUR: Hari Kemerdekaan RI Ke-80", "start": "2025-08-17"},
            {"title": "🔴 LIBUR: Maulid Nabi Muhammad SAW", "start": "2025-09-05"},
            {"title": "🔴 LIBUR: Hari Raya Natal", "start": "2025-12-25"},
            {"title": "🔴 CUTI BERSAMA: Hari Raya Natal", "start": "2025-12-26"},
        ],
        2026: [
            {"title": "🔴 LIBUR: Tahun Baru 2026 Masehi", "start": "2026-01-01"},
            {"title": "🔴 LIBUR: Isra Mikraj Nabi Muhammad SAW", "start": "2026-01-16"},
            {"title": "🔴 CUTI BERSAMA: Imlek 2577", "start": "2026-02-16"},
            {"title": "🔴 LIBUR: Tahun Baru Imlek 2577 Kongzili", "start": "2026-02-17"},
            {"title": "🔴 CUTI BERSAMA: Hari Suci Nyepi Saka 1948", "start": "2026-03-18"},
            {"title": "🔴 LIBUR: Hari Suci Nyepi Saka 1948", "start": "2026-03-19"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1447 H", "start": "2026-03-20"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1447 H", "start": "2026-03-21"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-22"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-23"},
            {"title": "🔴 CUTI BERSAMA: Idul Fitri 1447 H", "start": "2026-03-24"},
            {"title": "🔴 LIBUR: Wafat Yesus Kristus", "start": "2026-04-03"},
            {"title": "🔴 LIBUR: Hari Paskah", "start": "2026-04-05"},
            {"title": "🔴 LIBUR: Hari Buruh Internasional", "start": "2026-05-01"},
            {"title": "🔴 LIBUR: Kenaikan Yesus Kristus", "start": "2026-05-14"},
            {"title": "🔴 LIBUR: Hari Raya Idul Adha 1447 H", "start": "2026-05-27"},
            {"title": "🔴 CUTI BERSAMA: Idul Adha 1447 H", "start": "2026-05-28"},
            {"title": "🔴 LIBUR: Hari Raya Waisak 2570 BE", "start": "2026-05-31"},
            {"title": "🔴 LIBUR: Hari Lahir Pancasila", "start": "2026-06-01"},
            {"title": "🔴 LIBUR: Tahun Baru Islam 1448 H", "start": "2026-06-16"},
            {"title": "🔴 LIBUR: Hari Kemerdekaan RI Ke-81", "start": "2026-08-17"},
            {"title": "🔴 LIBUR: Maulid Nabi Muhammad SAW", "start": "2026-08-25"},
            {"title": "🔴 LIBUR: Hari Raya Natal", "start": "2026-12-25"},
            {"title": "🔴 CUTI BERSAMA: Hari Raya Natal", "start": "2026-12-26"},
        ],
        2027: [
            {"title": "🔴 LIBUR: Tahun Baru 2027 Masehi", "start": "2027-01-01"},
            {"title": "🔴 LIBUR: Isra Mikraj Nabi Muhammad SAW", "start": "2027-02-05"},
            {"title": "🔴 LIBUR: Tahun Baru Imlek 2578", "start": "2027-02-06"},
            {"title": "🔴 LIBUR: Hari Suci Nyepi Saka 1949", "start": "2027-03-09"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1448 H", "start": "2027-03-10"},
            {"title": "🔴 LIBUR: Hari Raya Idul Fitri 1448 H", "start": "2027-03-11"},
            {"title": "🔴 LIBUR: Wafat Yesus Kristus", "start": "2027-03-26"},
            {"title": "🔴 LIBUR: Hari Buruh Internasional", "start": "2027-05-01"},
            {"title": "🔴 LIBUR: Kenaikan Yesus Kristus", "start": "2027-05-06"},
            {"title": "🔴 LIBUR: Hari Raya Idul Adha 1448 H", "start": "2027-05-17"},
            {"title": "🔴 LIBUR: Hari Raya Waisak 2571 BE", "start": "2027-05-20"},
            {"title": "🔴 LIBUR: Hari Lahir Pancasila", "start": "2027-06-01"},
            {"title": "🔴 LIBUR: Tahun Baru Islam 1449 H", "start": "2027-06-06"},
            {"title": "🔴 LIBUR: Maulid Nabi Muhammad SAW", "start": "2027-08-15"},
            {"title": "🔴 LIBUR: Hari Kemerdekaan RI Ke-82", "start": "2027-08-17"},
            {"title": "🔴 LIBUR: Hari Raya Natal", "start": "2027-12-25"},
        ]
    }

    @classmethod
    def get_national_holidays_events(cls, start_year: int = 2025, end_year: int = 2027) -> List[Dict[str, Any]]:
        """
        Mengembalikan daftar event FullCalendar untuk Hari Libur Nasional & Cuti Bersama.
        """
        events = []
        for year in range(start_year, end_year + 1):
            holidays = cls.OFFICIAL_HOLIDAYS.get(year, [])
            for h in holidays:
                is_cuti = "CUTI BERSAMA" in h['title']
                bg_color = "#E11D48" if not is_cuti else "#D97706"
                border_color = "#991B1B" if not is_cuti else "#B45309"
                
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(h['start'], '%Y-%m-%d')
                end_str = (start_dt + timedelta(days=1)).strftime('%Y-%m-%d')

                events.append({
                    'id': f"holiday-{h['start']}",
                    'title': h['title'],
                    'start': h['start'],
                    'end': end_str,
                    'display': 'block',
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': '#FFFFFF',
                    'allDay': True,
                    'url': '#',
                    'extendedProps': {
                        'location': 'Seluruh Wilayah Indonesia (SKB 3 Menteri)',
                        'assigned_to': 'Seluruh Pegawai & Amil BAZNAS',
                        'source_type': 'holiday',
                        'status': 'Cuti Bersama' if is_cuti else 'Libur Nasional Official'
                    }
                })
        return events

    @classmethod
    def get_google_calendar_direct_url(cls, request) -> str:
        """
        Menghasilkan URL 1-Click untuk menambahkan kalender SIMAP BAZNAS ke Google Calendar.
        """
        host = request.get_host()
        protocol = "https" if request.is_secure() else "http"
        feed_url = f"{protocol}://{host}/agenda/ical/"
        return f"https://calendar.google.com/calendar/render?cid={feed_url}"
