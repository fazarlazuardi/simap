from django.test import TestCase
from services.integrations.google_calendar_service import GoogleCalendarService
from services.calendar.calendar_service import CalendarService

class HolidayDurationTestCase(TestCase):
    def test_national_holidays_single_day_duration(self):
        """
        Memastikan hari libur nasional 1 hari (seperti Hari Kemerdekaan 17 Agt & Maulid Nabi 25 Agt)
        memiliki start == end, tidak ditambahkan +1 hari yang menyebabkan tercatat 2 hari di kalender.
        """
        events = GoogleCalendarService.get_national_holidays_events(2026, 2026)
        kemerdekaan = [e for e in events if 'Kemerdekaan' in e['title']]
        maulid = [e for e in events if 'Maulid' in e['title']]

        self.assertTrue(len(kemerdekaan) > 0)
        self.assertEqual(kemerdekaan[0]['start'], '2026-08-17')
        self.assertEqual(kemerdekaan[0]['end'], '2026-08-17')

        self.assertTrue(len(maulid) > 0)
        self.assertEqual(maulid[0]['start'], '2026-08-25')
        self.assertEqual(maulid[0]['end'], '2026-08-25')

        # Pastikan seluruh event libur nasional di GoogleCalendarService memiliki start == end
        for e in events:
            self.assertEqual(e['start'], e['end'], f"Holiday event '{e['title']}' spans across days ({e['start']} to {e['end']})")

    def test_calendar_service_holiday_events(self):
        events = CalendarService.get_calendar_events()
        kemerdekaan_2026 = [e for e in events if 'Kemerdekaan' in e['title'] and '2026' in e['start']]
        maulid_2026 = [e for e in events if 'Maulid' in e['title'] and '2026' in e['start']]

        self.assertEqual(kemerdekaan_2026[0]['start'], '2026-08-17')
        self.assertEqual(kemerdekaan_2026[0]['end'], '2026-08-17')

        self.assertEqual(maulid_2026[0]['start'], '2026-08-25')
        self.assertEqual(maulid_2026[0]['end'], '2026-08-25')

