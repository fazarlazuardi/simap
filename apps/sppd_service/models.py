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

        if not self.sppd_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.sppd_number = NumberingService.generate_number('sppd')
            except Exception:
                pass

        super().save(*args, **kwargs)

        try:
            arch = None
            if self.disposition_id and hasattr(self, 'disposition') and self.disposition:
                arch = getattr(self.disposition, 'archive', None)
            elif self.surat_tugas_id and hasattr(self, 'surat_tugas') and self.surat_tugas:
                dispo = getattr(self.surat_tugas, 'disposition', None)
                arch = getattr(dispo, 'archive', None) if dispo else None

            if arch and arch.status != 'selesai':
                purp = ((self.purpose or '') + ' ' + (self.sppd_type or '')).lower()
                if self.sppd_type == 'penyaluran' or any(k in purp for k in ['penyaluran', 'pentasyarufan', 'cair', 'santunan', 'rutilahu', 'gharimin', 'bedah rumah', 'kursi roda']):
                    if arch.status != 'telah_disalurkan':
                        arch.status = 'telah_disalurkan'
                        arch.save(update_fields=['status', 'updated_at'])
                elif self.sppd_type == 'survei' or any(k in purp for k in ['survei', 'peninjauan', 'lokasi', 'lapangan', 'cek', 'mustahik']):
                    if arch.status not in ['dalam_survei', 'telah_disurvei', 'telah_disalurkan']:
                        arch.status = 'dalam_survei'
                        arch.save(update_fields=['status', 'updated_at'])
        except Exception as e:
            print('Failed to sync SPPD -> Archive status:', e)

        sppd_pk = self.pk
        sppd_num = self.sppd_number
        purpose_str = self.purpose
        dep_date = self.departure_date
        ret_date = self.return_date
        dest_str = self.destination
        sppd_stat = self.status

        def _trigger_sppd_bg_tasks():
            try:
                if sppd_stat in ['disetujui', 'berlangsung'] or dep_date:
                    from notifications.tasks import create_calendar_event
                    title = f"SPPD {sppd_num} - {(purpose_str or '')[:80]}"
                    start_dt = None
                    end_dt = None
                    try:
                        from datetime import datetime, time
                        if dep_date:
                            start_dt = datetime.combine(dep_date, time(hour=8))
                        if ret_date:
                            end_dt = datetime.combine(ret_date, time(hour=17))
                    except Exception:
                        start_dt = None

                    if start_dt:
                        create_calendar_event.delay('sppd', sppd_pk, title, start_dt.isoformat(), end_dt.isoformat() if end_dt else None, dest_str)

                if old_status != sppd_stat and sppd_stat == 'disetujui':
                    try:
                        from notifications.tasks import send_wa_message
                        from sppd_service.models import SPPD as SPPDModel
                        s_obj = SPPDModel.objects.filter(pk=sppd_pk).first()
                        if s_obj:
                            phones = [emp.phone for emp in s_obj.assigned_employees.all() if hasattr(emp, 'phone') and emp.phone]
                            message = f"SPPD {sppd_num} sudah diterbitkan untuk {(purpose_str or '')[:80]}. Tanggal: {dep_date} - {ret_date}."
                            for p in phones:
                                send_wa_message.delay(p, message, metadata={'sppd_id': sppd_pk})
                    except Exception as e:
                        print('Failed to trigger WA send for SPPD:', e)
            except Exception as ex:
                print('Error in SPPD background task trigger:', ex)

        try:
            from django.db import transaction
            transaction.on_commit(_trigger_sppd_bg_tasks)
        except Exception:
            _trigger_sppd_bg_tasks()


class SPPDAttachment(models.Model):
    sppd = models.ForeignKey(SPPD, on_delete=models.CASCADE, related_name='additional_attachments')
    file = models.FileField(upload_to='sppd_reports/%Y/%m/', validators=[validate_file_extension, validate_file_size], verbose_name="File Lampiran Tambahan")
    title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Keterangan / Nama File")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lampiran SPPD #{self.sppd.pk} - {self.file.name}"
