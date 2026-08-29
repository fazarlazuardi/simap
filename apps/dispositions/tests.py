from django.test import TestCase
from archives.models import Archive, Category
from dispositions.models import Disposition
from users.models import User, Employee, Department

class DispositionWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Proposal Bantuan Mustahik')
        self.user_ketua = User.objects.create_user(username='ketua_user', password='Password123!', role='pimpinan')
        self.archive = Archive.objects.create(
            title='Proposal Permohonan Bantuan Rutilahu',
            archive_type='proposal',
            category=self.category,
            uploaded_by=self.user_ketua,
            status='disposisi_pimpinan'
        )
        self.dept_bidang2 = Department.objects.create(name='Bidang II (Pendistribusian)')
        self.emp_waka2 = Employee.objects.create(
            nip='198505052020011002',
            full_name='Wakil Ketua II',
            dept_relation=self.dept_bidang2,
            leadership_type='waka_2'
        )

    def test_disposition_creation(self):
        dispo = Disposition.objects.create(
            archive=self.archive,
            sender=self.user_ketua,
            disposition_number='DISP-001-TEST',
            status='didisposisi_ketua',
            disposition_stage='ketua',
            note='Harap diproses dan diverifikasi lapangan.'
        )
        dispo.forwarded_to.add(self.emp_waka2)
        self.assertEqual(dispo.status, 'didisposisi_ketua')
        self.assertTrue(dispo.is_stage_ketua)
        self.assertIn('DISP-001-TEST', str(dispo))

    def test_disposition_stage_waka_transition(self):
        dispo = Disposition.objects.create(
            archive=self.archive,
            sender=self.user_ketua,
            disposition_stage='waka_iv',
            status='proses',
            waka_note='Diteruskan ke Bidang II untuk survei.'
        )
        self.assertTrue(dispo.is_stage_waka)
        self.assertTrue(dispo.has_waka_disposition)

