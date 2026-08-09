from django.core.management.base import BaseCommand
from archives.models import Archive
from dispositions.models import Disposition
from sppd_service.models import SPPD
from surat_tugas.models import SuratTugas
from reports.models import Report
from notifications.models import Notification
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Menghapus seluruh data dokumen (proposal & surat) dan menyisakan data pegawai'

    def handle(self, *args, **kwargs):
        n_rep, _ = Report.objects.all().delete()
        n_sppd, _ = SPPD.objects.all().delete()
        n_st, _ = SuratTugas.objects.all().delete()
        n_dispo, _ = Disposition.objects.all().delete()
        n_arc, _ = Archive.objects.all().delete()
        n_notif, _ = Notification.objects.all().delete()
        
        User = get_user_model()
        self.stdout.write(self.style.SUCCESS(
            f"BERHASIL DIBERSIHKAN:\n"
            f"- Archive (Proposal & Surat): {n_arc} record\n"
            f"- Disposisi: {n_dispo} record\n"
            f"- SPPD: {n_sppd} record\n"
            f"- Surat Tugas: {n_st} record\n"
            f"- Laporan & Notifikasi: {n_rep + n_notif} record\n"
            f"\nDATA PEGAWAI TETAP UTUH: {User.objects.count()} akun pegawai aman."
        ))
