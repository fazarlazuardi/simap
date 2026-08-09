from django.db import models
from django.conf import settings
from dispositions.models import Disposition
from surat_tugas.models import SuratTugas  
from users.models import Employee

from core.validators import validate_file_extension, validate_file_size

class SPPD(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft / Pengajuan'),
        ('disetujui', 'Disetujui / Diterbitkan'),
        ('berlangsung', 'Sedang Perjalanan Dinas'),
        ('selesai', 'Selesai & Laporan Terunggah'),
        ('dibatalkan', 'Dibatalkan'),
    ]

    SPPD_TYPE_CHOICES = [
        ('survei', 'Survei / Verifikasi Lapangan'),
        ('penyaluran', 'Penyaluran Bantuan / Pentasyarufan'),
        ('umum', 'Umum / Perjalanan Dinas Lainnya'),
    ]

    surat_tugas = models.ForeignKey(
        SuratTugas,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sppd_records',
        verbose_name="Dasar Surat Tugas"
    )

    disposition = models.ForeignKey(
        Disposition, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sppd_list', 
        verbose_name="Disposisi Acuan (Opsional)"
    )
    
    sppd_number = models.CharField(max_length=100, unique=True, verbose_name="Nomor SPPD")
    
    purpose = models.TextField(verbose_name="Maksud Perjalanan Dinas")
    transportation = models.CharField(max_length=100, default="Mobil", verbose_name="Alat Angkutan yang Digunakan")
    
    departure_place = models.CharField(max_length=255, default="KANTOR Jl. Islamic Center No. 01 Citra Raya", verbose_name="Tempat Berangkat")
    destination = models.CharField(max_length=255, verbose_name="Tempat Tujuan")
    
    duration_days = models.IntegerField(default=1, verbose_name="Lamanya Perjalanan Dinas (Hari)")
    departure_date = models.DateField(verbose_name="Tanggal Keberangkatan")
    return_date = models.DateField(verbose_name="Tanggal Kepulangan")
    
    budget_source = models.CharField(max_length=255, default="BAZNAS Kabupaten Tangerang", verbose_name="Pembebanan Anggaran")
    notes = models.TextField(blank=True, null=True, verbose_name="Keterangan Tambahan")

    sppd_type = models.CharField(
        max_length=20,
        choices=SPPD_TYPE_CHOICES,
        default='umum',
        verbose_name="Jenis/Tujuan SPPD"
    )
    tahap = models.PositiveIntegerField(
        default=1,
        verbose_name="Tahap SPPD ke-",
        help_text="SPPD pertama=1, kedua=2, dst. Otomatis dihitung saat dibuat."
    )
    
    signed_by_ketua = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='signed_sppd_as_ketua', 
        verbose_name="Ketua BAZNAS (Penandatangan)"
    )

    assigned_employees = models.ManyToManyField(Employee, related_name='sppd_assignments', verbose_name="Amil / Pegawai yang Diperintah")
    followers = models.ManyToManyField(Employee, related_name='sppd_followers', blank=True, verbose_name="Pengikut (Jika Ada)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disetujui', db_index=True, verbose_name="Status SPPD")
    report_notes = models.TextField(blank=True, null=True, verbose_name="Ringkasan Hasil Perjalanan Dinas")
    report_file = models.FileField(upload_to='sppd_reports/%Y/%m/', null=True, blank=True, validators=[validate_file_extension, validate_file_size], verbose_name="File Laporan / Bukti Foto Kegiatan")

    is_cancelled = models.BooleanField(default=False, verbose_name="Dibatalkan")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SPPD"
        verbose_name_plural = "SPPD (Surat Perintah Perjalanan Dinas)"

    @property
    def task_letter_number(self):
        return self.surat_tugas.nomor_surat if self.surat_tugas else ""

    def __str__(self):
        return f"{self.sppd_number} - {self.purpose[:30]}"

    def save(self, *args, **kwargs):
        """Override save untuk sinkronisasi Kalender Kerja dan notifikasi minimal.
        
        - Ketika status menjadi 'disetujui' atau ada tanggal keberangkatan, akan membuat CalendarEvent.
        - Men-trigger task notifikasi WhatsApp (via Celery) ketika SPPD disetujui.
        """
        is_new = self.pk is None
        old_status = None
        if not is_new:
            try:
                old_status = SPPD.objects.get(pk=self.pk).status
            except SPPD.DoesNotExist:
                old_status = None

        if not self.sppd_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.sppd_number = NumberingService.generate_number('sppd')
            except Exception:
                pass

        super().save(*args, **kwargs)

        try:
            if self.status in ['disetujui', 'berlangsung'] or self.departure_date:
                from notifications.tasks import create_calendar_event
              
                title = f"SPPD {self.sppd_number} - {self.purpose[:80]}"
                start_dt = None
                end_dt = None
               
                try:
                    from datetime import datetime, time
                    start_dt = datetime.combine(self.departure_date, time(hour=8))
                    if self.return_date:
                        end_dt = datetime.combine(self.return_date, time(hour=17))
                except Exception:
                    start_dt = None

                if start_dt:
                    create_calendar_event.delay('sppd', self.pk, title, start_dt.isoformat(), end_dt.isoformat() if end_dt else None, self.destination)

            if (old_status != self.status) and self.status == 'disetujui':
                try:
                    from notifications.tasks import send_wa_message
                    phones = []
                    for emp in self.assigned_employees.all():
                        if hasattr(emp, 'phone') and emp.phone:
                            phones.append(emp.phone)
                    message = f"SPPD {self.sppd_number} sudah diterbitkan untuk {self.purpose[:80]}. Tanggal: {self.departure_date} - {self.return_date}."
                    for p in phones:
                        send_wa_message.delay(p, message, metadata={'sppd_id': self.pk})
                except Exception as e:
                    print('Failed to trigger WA send for SPPD:', e)
            try:
                if self.surat_tugas and getattr(self.surat_tugas, 'disposition', None):
                    arch = getattr(self.surat_tugas.disposition, 'archive', None)
                    if arch:
                        if self.status in ['disetujui', 'berlangsung'] and arch.status != 'sudah_ditugaskan':
                            arch.status = 'sudah_ditugaskan'
                            arch.current_user = self.created_by
                            arch.activity_name = 'SPPD Diterbitkan'
                            arch.status_note = f'SPPD {self.sppd_number} diterbitkan.'
                            arch.save()
                        elif self.status == 'selesai' and arch.status != 'selesai':
                            is_survei = self.sppd_type == 'survei' or any(k in (self.purpose or '').lower() for k in ['survei', 'peninjauan', 'verifikasi', 'lapangan'])
                            if is_survei:
                                arch.status = 'proses'
                                arch.current_user = self.created_by
                                arch.activity_name = 'Survei Selesai (Menunggu Penyaluran)'
                                arch.status_note = f'SPPD Survei {self.sppd_number} selesai dan LHP terunggah.'
                                arch.save()
                            else:
                                arch.status = 'selesai'
                                arch.current_user = self.created_by
                                arch.activity_name = 'SPPD Selesai'
                                arch.status_note = f'SPPD {self.sppd_number} selesai dan laporan terunggah.'
                                arch.save()
            except Exception as e:
                print('Failed to sync SPPD -> Archive status:', e)
        except Exception as e:
            print('Error in SPPD post-save integration:', e)
