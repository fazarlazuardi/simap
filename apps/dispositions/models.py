import re
from django.db import models
from django.conf import settings
from django.utils import timezone
from archives.models import Archive
from users.models import Employee


class Disposition(models.Model):
    STATUS_CHOICES = [
        ('baru', 'Menunggu Disposisi Ketua'),
        ('didisposisi_ketua', 'Sudah Disposisi Ketua — Menunggu Waka IV'),
        ('proses', 'Sedang Diproses Bidang'),
        ('selesai', 'Selesai'),
    ]

    STAGE_CHOICES = [
        ('ketua', 'Disposisi Ketua'),
        ('waka_iv', 'Disposisi Waka IV'),
    ]

    PRIORITY_CHOICES = [
        ('sangat_segera', 'Sangat Segera'),
        ('segera', 'Segera'),
        ('penting', 'Penting / Mendesak'),
        ('biasa', 'Biasa'),
    ]

    disposition_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    archive = models.ForeignKey(Archive, on_delete=models.CASCADE, related_name='dispositions')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_dispositions')

    # Label nama pimpinan yang tercantum pada lembar cetak (Ketua atau Waka IV)
    # Diisi otomatis dari helper _resolve_sender_label saat disubmit
    sender_label = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name='Nama Pimpinan Pengirim (Label Cetak)'
    )

    # Tahap disposisi saat ini: ketua (tahap 1) atau waka_iv (tahap 2)
    disposition_stage = models.CharField(
        max_length=20, choices=STAGE_CHOICES, default='ketua', db_index=True,
        verbose_name='Tahap Disposisi'
    )

    # "Diteruskan Kepada" dari Ketua → Waka IV
    forwarded_to = models.ManyToManyField(Employee, related_name='received_dispositions', blank=True)

    # Instruksi / tujuan dari Waka IV ke Bidang Pelaksana (tahap 2)
    waka_forwarded_to = models.ManyToManyField(
        Employee, related_name='waka_received_dispositions', blank=True,
        verbose_name='Diteruskan Ke (Waka IV → Bidang)'
    )
    waka_note = models.TextField(
        blank=True, null=True,
        verbose_name='Arahan / Catatan Waka IV'
    )

    # Instruction Checkboxes dari Lembar Fisik BAZNAS
    inst_selesaikan = models.BooleanField(default=False, verbose_name="Selesaikan / Jawab")
    inst_untuk_diketahui = models.BooleanField(default=False, verbose_name="Untuk diketahui / Simpan")
    inst_laporkan_hasilnya = models.BooleanField(default=False, verbose_name="Laporkan hasilnya")
    inst_koordinasikan = models.BooleanField(default=False, verbose_name="Koordinasikan")

    # Instruksi khusus Waka IV
    waka_inst_selesaikan = models.BooleanField(default=False)
    waka_inst_untuk_diketahui = models.BooleanField(default=False)
    waka_inst_laporkan_hasilnya = models.BooleanField(default=False)
    waka_inst_koordinasikan = models.BooleanField(default=False)

    # Flag penanda kebutuhan tindak lanjut perjalanan dinas / lokasi luar
    requires_sppd = models.BooleanField(default=False, verbose_name="Memerlukan SPPD / Dinas Luar")

    # Status/Checklist Verifikasi oleh Kabid 4 (SDM, Administrasi & Umum)
    checked_by_kabid = models.BooleanField(default=False, verbose_name="Telah Diperiksa/Diverifikasi Kabid 4")
    kabid_note = models.TextField(blank=True, null=True, verbose_name="Catatan Khusus Kabid 4")

    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='biasa')
    note = models.TextField(blank=True, verbose_name="Catatan/Instruksi Tambahan Pimpinan")
    implementation_date = models.DateField(null=True, blank=True, verbose_name="Tanggal Pelaksanaan / Audiensi")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='baru', db_index=True)

    # ─── BUKTI / LAPORAN HASIL TINDAK LANJUT STAF ───
    result_note = models.TextField(blank=True, null=True, verbose_name="Catatan Hasil Tindak Lanjut")
    result_file = models.FileField(upload_to='uploads/dispositions/results/', null=True, blank=True, verbose_name="Dokumen Bukti Tindak Lanjut")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Diselesaikan")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Disposisi"
        verbose_name_plural = "Daftar Disposisi"

    @property
    def is_stage_ketua(self):
        return self.disposition_stage == 'ketua'

    @property
    def is_stage_waka(self):
        return self.disposition_stage == 'waka_iv'

    @property
    def has_waka_disposition(self):
        """Menentukan apakah disposisi Waka IV (Tahap 2) sudah pernah dibuat/diisi."""
        return bool(self.waka_note or self.waka_forwarded_to.exists() or self.disposition_stage == 'waka_iv')

    @property
    def st_count(self):
        """Menghitung jumlah Surat Tugas (ST) yang telah dibuat untuk disposisi/arsip ini."""
        try:
            from surat_tugas.models import SuratTugas
            if self.archive_id:
                return SuratTugas.objects.filter(models.Q(disposition=self) | models.Q(disposition__archive_id=self.archive_id)).distinct().count()
            return self.surat_tugas.count()
        except Exception:
            return 0

    @property
    def can_create_waka_disposition(self):
        """
        Menentukan apakah tombol 'Buat Disposisi Waka IV' (Tahap 2) boleh tampil:
        - Dokumen BELUM selesai
        - Disposisi Waka IV BELUM pernah diisi
        """
        if self.is_completed:
            return False
        if self.has_waka_disposition:
            return False
        return True

    @property
    def can_create_surat_tugas(self):
        """
        Menentukan apakah tombol 'Buat Surat Tugas (ST)' boleh tampil:
        - Dokumen BELUM selesai (status != 'selesai' dan archive.status != 'selesai')
        - Jumlah Surat Tugas (ST) saat ini MASIH kurang dari 2 (Maksimal 2x ST per dokumen)
        - Aturan 1: Jika Disposisi Ketua mengarah ke Waka IV (chk_waka4=True), HARUS MENUNGGU Disposisi Waka IV terisi (has_waka_disposition=True).
        - Aturan 2: Jika Disposisi Ketua TIDAK ke Waka IV (misal ke Waka I/II/III/Bidang), LANGSUNG BISA buat Surat Tugas.
        """
        if self.is_completed:
            return False
        if self.st_count >= 2:
            return False

        # Skenario 1: Jika Disposisi Ketua ditujukan ke Waka IV
        if self.chk_waka4:
            # Menunggu Disposisi Waka IV (Tahap 2) dibuat/diisi
            return self.has_waka_disposition

        # Skenario 2: Jika Disposisi Ketua TIDAK ditujukan ke Waka IV (langsung ke Waka I/II/III/Bidang)
        if self.status in ['didisposisi_ketua', 'proses'] and self.forwarded_to.exists():
            return True

        # Skenario 3: Sudah ada disposisi Waka IV atau status 'proses'
        if self.has_waka_disposition or self.status == 'proses':
            return True

        return False

    @property
    def display_sender_name(self):
        """
        Nama pimpinan pengirim utama (Ketua BAZNAS) yang ditampilkan di tabel list dan cetakan.
        Mendukung penuh skenario Take Over oleh Superadmin (admin).
        """
        # 1. Gunakan sender_label jika sudah tersimpan di database
        if self.sender_label:
            return self.sender_label

        # 2. Cari dari data Employee khusus yang menjabat 'ketua'
        try:
            from users.models import Employee as Emp
            ketua = Emp.objects.filter(leadership_type='ketua', is_active=True).first()
            if ketua and ketua.full_name:
                return ketua.full_name
        except Exception:
            pass

        # 3. Fallback baku dan aman ke Nama Ketua BAZNAS Kabupaten Tangerang
        return 'Drs. H. Achmad Nawawi, M.Si.'

    @property
    def display_waka_name(self):
        """
        Nama Wakil Ketua IV BAZNAS yang meneruskan pada Tahap 2.
        """
        try:
            from users.models import Employee as Emp
            waka = Emp.objects.filter(leadership_type='waka_4', is_active=True).first()
            if waka and waka.full_name:
                return waka.full_name
        except Exception:
            pass
        return 'Wakil Ketua IV'

    @property
    def latest_sender_position(self):
        """
        Mengembalikan JABATAN pengirim dari alur disposisi terakhir.
        Jika sudah disposisi Waka IV (waka_iv / waka_forwarded_to ada), pengirim adalah Wakil Ketua IV.
        Jika masih disposisi Ketua, pengirim adalah Ketua BAZNAS (atau Jabatan pengirim).
        """
        if self.disposition_stage == 'waka_iv' or self.waka_forwarded_to.exists():
            return "Wakil Ketua IV"
        
        if hasattr(self.sender, 'employee') and self.sender.employee and self.sender.employee.position:
            pos = self.sender.employee.position
            if pos and pos.strip().lower() not in ['staff pelaksana', 'staf pelaksana']:
                return pos
        return "Ketua BAZNAS"

    @property
    def latest_receiver_positions(self):
        """
        Mengembalikan JABATAN penerima dari alur disposisi terakhir.
        Jika sudah disposisi Waka IV, ambil Jabatan dari waka_forwarded_to.
        Jika masih disposisi Ketua, ambil Jabatan dari forwarded_to.
        """
        if self.disposition_stage == 'waka_iv' or self.waka_forwarded_to.exists():
            targets = self.waka_forwarded_to.all()
            if not targets.exists():
                targets = self.forwarded_to.all()
        else:
            targets = self.forwarded_to.all()
            if not targets.exists():
                targets = self.waka_forwarded_to.all()

        positions = []
        for emp in targets:
            pos = emp.position or emp.full_name
            if pos and pos not in positions:
                positions.append(pos)
        
        return ", ".join(positions) if positions else "Semua Bidang"

    def user_permissions(self, user, active_pov=None):
        """Mendapatkan permission kustom per pengguna untuk objek Disposisi ini."""
        if not user or not user.is_authenticated:
            return {'can_create_dispo': False, 'can_edit_dispo': False, 'can_edit_waka_dispo': False, 'can_delete_dispo': False, 'is_read_only': True}
        return user.get_disposition_permissions(active_pov=active_pov, dispo=self)

    @property
    def has_result(self):
        return bool(self.result_note or self.result_file or hasattr(self, 'report'))

    @property
    def is_completed(self):
        return bool(
            self.status == 'selesai' or 
            hasattr(self, 'report') or 
            (self.archive and self.archive.status in ['selesai', 'telah_disalurkan'])
        )

    @property
    def _forwarded_text(self):
        return " ".join([f"{e.full_name} {e.position}" for e in self.forwarded_to.all()]).lower()

    @property
    def chk_ketua(self):
        return bool(re.search(r'\bketua\b', self._forwarded_text) and not re.search(r'waka|wakil', self._forwarded_text))

    @property
    def chk_waka4(self):
        return bool(re.search(r'waka\s*iv\b|waka\s*4\b|wakil ketua iv\b|wakil ketua 4\b', self._forwarded_text))

    def save(self, *args, **kwargs):
        # Otomatisasi Waktu Selesai & Sinkronisasi Status Arsip Utama
        if self.status == 'selesai':
            if not self.completed_at:
                self.completed_at = timezone.now()
            if self.archive and self.archive.status != 'selesai':
                self.archive.status = 'selesai'
                self.archive.save(update_fields=['status', 'updated_at'])

        # Otomasi nomor disposisi
        if not self.disposition_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.disposition_number = NumberingService.generate_number('disposition')
            except Exception:
                last_dispo = Disposition.objects.filter(
                    disposition_number__startswith='DISP-'
                ).order_by('-id').first()
                if last_dispo and last_dispo.disposition_number:
                    match = re.search(r'DISP-(\d+)', last_dispo.disposition_number)
                    next_number = int(match.group(1)) + 1 if match else 1
                else:
                    next_number = 1
                candidate = f"DISP-{next_number:03d}"
                while Disposition.objects.filter(disposition_number=candidate).exists():
                    next_number += 1
                    candidate = f"DISP-{next_number:03d}"
                self.disposition_number = candidate

        super().save(*args, **kwargs)

        # WORKFLOW: status arsip saat proses
        if self.archive and getattr(self.archive, 'archive_type', None) in ['proposal', 'permohonan_bantuan']:
            if self.status not in ['selesai']:
                if self.archive.status != 'proses':
                    self.archive.status = 'proses'
                    self.archive.save(update_fields=['status', 'updated_at'])

        # Trigger notifikasi WhatsApp (Sentralisasi via WhatsAppService untuk mematuhi Matriks Pengaturan WA)
        # Trigger notifikasi WhatsApp via Celery task engine / transaction.on_commit
        if self.pk:
            dispo_pk = self.pk
            note_val = (self.note or '')[:120]
            num_val = self.disposition_number or ''
            arc_title_val = self.archive.title if self.archive else ''

            def _notify_dispo_save():
                try:
                    from dispositions.models import Disposition
                    from services.integrations.gateway_service import WhatsAppService

                    d_obj = Disposition.objects.filter(pk=dispo_pk).first()
                    if not d_obj:
                        return
                    for emp in d_obj.forwarded_to.all():
                        if emp and (getattr(emp, 'phone_number', None) or getattr(emp, 'phone', None)):
                            message = f"Disposisi {num_val} untuk arsip: {arc_title_val}. Instruksi: {note_val}"
                            WhatsAppService.send_notification(
                                user=getattr(emp, 'user_account', None),
                                message=message,
                                employee=emp,
                                category='disposition',
                                title="Disposisi Pimpinan"
                            )
                except Exception as ex:
                    import logging
                    logging.getLogger(__name__).warning(f"Failed to trigger dispo WA notification: {ex}")

            try:
                from django.db import transaction
                transaction.on_commit(_notify_dispo_save)
            except Exception:
                _notify_dispo_save()

    def __str__(self):
        num = self.disposition_number or f"DISP-{self.pk:03d}"
        if self.archive and (self.archive.archive_number or self.archive.title):
            return f"{num} ({self.archive.archive_number or self.archive.title[:30]})"
        return num