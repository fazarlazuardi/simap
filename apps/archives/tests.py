from django.test import TestCase
from django.utils import timezone
from archives.models import Archive, Category
from users.models import User
from services.archives.numbering_service import NumberingService

class ArchiveModelAndNumberingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fo_user', password='Password123!')
        self.category = Category.objects.create(name='Surat Dinas Umum')

    def test_category_creation(self):
        self.assertEqual(str(self.category), 'Surat Dinas Umum')

    def test_archive_number_generation_and_creation(self):
        num = NumberingService.generate_number('archive', {'archive_type': 'surat_masuk'})
        self.assertIsNotNone(num)

        archive = Archive.objects.create(
            archive_number=num,
            title='Surat Permohonan Kerjasama BAZNAS',
            archive_type='surat_masuk',
            category=self.category,
            uploaded_by=self.user,
            sender='Dinas Sosial Kabupaten Tangerang',
            letter_date=timezone.now().date(),
            status='baru'
        )
        self.assertEqual(archive.status, 'baru')
        self.assertEqual(archive.safe_title, 'Surat Permohonan Kerjasama BAZNAS')
        self.assertIn('Surat Masuk', str(archive))

    def test_numbering_service_default_number(self):
        default_num = NumberingService.get_default_number('archive', {'archive_type': 'proposal'})
        self.assertTrue(len(default_num) > 0)

