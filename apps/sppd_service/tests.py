from django.test import TestCase
from django.utils import timezone
from archives.models import Archive, Category
from dispositions.models import Disposition
from sppd_service.models import SPPD
from users.models import User, Employee

class SPPDModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin_sppd', password='Password123!', role='admin')
        self.category = Category.objects.create(name='Survei Mustahik')
        self.archive = Archive.objects.create(
            title='Permohonan Bantuan Rutilahu Bpk Sulaeman',
            archive_type='proposal',
            category=self.category,
            uploaded_by=self.user,
            status='proses'
        )
        self.disposition = Disposition.objects.create(
            archive=self.archive,
            sender=self.user,
            disposition_number='DISP-SPPD-01',
            status='proses'
        )
        self.employee = Employee.objects.create(
            nip='199001012022011003',
            full_name='Budi Amil Survei',
            position='Pelaksana Survei'
        )

    def test_sppd_creation(self):
        sppd = SPPD.objects.create(
            disposition=self.disposition,
            sppd_number='SPPD-001-TEST',
            purpose='Survei Lapangan Kelayakan Mustahik Rutilahu',
            destination='Kecamatan Balaraja',
            departure_date=timezone.now().date(),
            return_date=timezone.now().date(),
            sppd_type='survei',
            status='disetujui',
            created_by=self.user
        )
        sppd.assigned_employees.add(self.employee)
        self.assertEqual(sppd.sppd_number, 'SPPD-001-TEST')
        self.assertEqual(sppd.status, 'disetujui')
        self.assertIn('SPPD-001-TEST', str(sppd))
