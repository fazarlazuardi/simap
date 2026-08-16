from django.db import models
from django.conf import settings
from dispositions.models import Disposition
from users.models import Employee  

class SuratTugas(models.Model):
    nomor_surat = models.CharField(max_length=100, blank=True, null=True, unique=True)
    tentang = models.TextField(help_text="Perihal atau tujuan penugasan")
    hari_kegiatan = models.CharField(max_length=50, blank=True, null=True)
    tanggal_mulai = models.DateField(blank=True, null=True)
    lokasi_tujuan = models.CharField(max_length=255, blank=True, null=True)
    
    # Relasi opsional ke Disposisi
    disposition = models.ForeignKey(Disposition, on_delete=models.SET_NULL, blank=True, null=True, related_name='surat_tugas')
    
    # Pegawai yang ditugaskan (Many-to-Many ke model Employee)
    pegawai_ditugaskan = models.ManyToManyField(
        Employee, 
        related_name='surat_tugas_list'
    )
    
    # Pejabat penandatangan fleksibel
    pejabat_penandatangan = models.CharField(max_length=150, default="Drs. Achmad Nawawi, M.Si")
    jabatan_penandatangan = models.CharField(max_length=150, default="Ketua BAZNAS")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='surat_tugas_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'surat_tugas'

    def __str__(self):
        return f"{self.nomor_surat or 'Draft'} - {self.tentang[:30]}"

    def save(self, *args, **kwargs):
        """Override save to sync calendar event and send notifications when tanggal_mulai is set."""
        is_new = self.pk is None
        old_tanggal = None
        if not is_new:
            try:
                old_tanggal = SuratTugas.objects.get(pk=self.pk).tanggal_mulai
            except Exception:
                old_tanggal = None

        if not self.nomor_surat:
            try:
                from services.archives.numbering_service import NumberingService
                self.nomor_surat = NumberingService.generate_number('surat_tugas')
            except Exception:
                pass

        super().save(*args, **kwargs)

        try:
            arch = getattr(self, 'archive', None) or (self.disposition.archive if getattr(self, 'disposition', None) else None)
            if arch and arch.status != 'selesai':
                st_text = (self.tentang or '').lower()
                if 'survei' in st_text:
                    new_status = 'dalam_survei'
                elif any(k in st_text for k in ['penyaluran', 'pentasyarufan', 'disalurkan']):
                    new_status = 'telah_disalurkan'
                else:
                    new_status = 'sudah_ditugaskan'
                
                if arch.status != new_status:
                    arch.status = new_status
                    arch.save(update_fields=['status', 'updated_at'])
        except Exception as e:
            print('Failed to sync SuratTugas -> Archive status:', e)


from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=SuratTugas)
def cleanup_surat_tugas_relations(sender, instance, **kwargs):
    """
    Mencegah IntegrityError 1452 MySQL saat Surat Tugas dihapus.
    Otomatis melepaskan (set NULL) seluruh relasi SPPD acuan.
    """
    try:
        from sppd_service.models import SPPD
        SPPD.objects.filter(surat_tugas=instance).update(surat_tugas=None)
    except Exception:
        pass

