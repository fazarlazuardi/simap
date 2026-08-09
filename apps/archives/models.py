import os
from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'


class Archive(models.Model):
    STATUS_CHOICES = [
        ('baru', 'Baru (Menunggu Verifikasi Sekretariat)'),
        ('verifikasi_kabid', 'Proses Verifikasi Kabid 4'),
        ('disposisi_pimpinan', 'Menunggu Disposisi Pimpinan'),
        ('terverifikasi', 'Terverifikasi (Siap Didisposisikan)'),
        ('didisposisikan', 'Dalam Proses Disposisi Pimpinan'),
        ('proses', 'Diproses Staf / Bidang'),
        ('sudah_ditugaskan', 'Penugasan (Surat Tugas Terbit)'),
        ('menghadiri_undangan', 'Menghadiri Undangan / Acara Luar'),
        ('dalam_survei', 'Dalam Survei / Verifikasi Lapangan'),
        ('telah_disalurkan', 'Telah Disalurkan / Pentasyarufan'),
        ('selesai', 'Selesai & Terekap'),
        ('ditolak', 'Ditolak / Dikembalikan'),
    ]

    TYPE_CHOICES = [
        ('surat_masuk', 'Surat Masuk'),
        ('proposal', 'Proposal'),
        ('surat_keluar', 'Surat Keluar'),
        ('dokumen_internal', 'Dokumen Internal'),
    ]

    SECURITY_CHOICES = [
        ('biasa', 'Biasa'),
        ('penting', 'Penting'),
        ('rahasia', 'Rahasia'),
        ('sangat_rahasia', 'Sangat Rahasia'),
    ]

    URGENCY_CHOICES = [
        ('biasa', 'Biasa'),
        ('segera', 'Segera'),
        ('amat_segera', 'Amat Segera / Kilat'),
    ]

    archive_number = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Nomor Surat/Arsip',
    )
    title = models.CharField(max_length=255, verbose_name='Perihal / Judul Dokumen')
    archive_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default='surat_masuk',
        db_index=True,
        verbose_name='Jenis Dokumen',
    )

    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_archives',
    )

    letter_date = models.DateField(
        null=True, blank=True, verbose_name='Tanggal Surat'
    )
    received_date = models.DateField(
        null=True, blank=True, verbose_name='Tanggal Diterima / Dikirim'
    )

    sender = models.CharField(
        max_length=255, null=True, blank=True, verbose_name='Pengirim / Asal Instansi'
    )
    receiver = models.CharField(
        max_length=255, null=True, blank=True, verbose_name='Penerima / Tujuan Surat'
    )
    address = models.TextField(
        null=True, blank=True, verbose_name='Alamat Lengkap Pemohon / Mustahik / Instansi'
    )

    security_level = models.CharField(
        max_length=20, choices=SECURITY_CHOICES, default='biasa', verbose_name='Sifat Keamanan'
    )
    urgency_level = models.CharField(
        max_length=20, choices=URGENCY_CHOICES, default='biasa', verbose_name='Sifat Tanggapan'
    )

    description = models.TextField(
        blank=True, null=True, verbose_name='Keterangan Ringkas / Sinopsis'
    )
    file_path = models.FileField(
        upload_to='archives/%Y/%m/%d/', verbose_name='File Dokumen Utama'
    )

    verified_by_kabid = models.BooleanField(
        default=False, verbose_name='Telah Diverifikasi Kabid 4'
    )
    kabid_notes = models.TextField(
        blank=True, null=True, verbose_name='Catatan / Checklist Verifikasi Kabid 4'
    )
    verified_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Waktu Verifikasi Kabid 4'
    )

    result_file = models.FileField(
        upload_to='results/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name='File Bukti Tindak Lanjut / Laporan Akhir',
    )
    result_note = models.TextField(
        blank=True, null=True, verbose_name='Catatan Hasil / Laporan Staf'
    )

    rejection_note = models.TextField(
        blank=True, null=True, verbose_name='Alasan Penolakan Arsip'
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='baru', db_index=True
    )

    drive_backed_up = models.BooleanField(default=False)
    drive_file_id = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        number = self.archive_number if self.archive_number else 'DRAFT'
        return f'[{self.get_archive_type_display()}] {number} - {self.title}'

    @property
    def latest_dispo(self):
        return self.dispositions.order_by('created_at').last()

    @property
    def current_assignees(self):
        """
        Mengambil penanggung jawab aktif secara dinamis dari disposisi terakhir.
        Jika sudah di Tahap Waka IV -> ambil waka_forwarded_to (misal Waka II / Kabid).
        Jika masih Tahap Ketua -> ambil forwarded_to.
        """
        d = self.latest_dispo
        if d:
            if d.is_stage_waka and d.waka_forwarded_to.exists():
                return d.waka_forwarded_to.all()
            elif d.forwarded_to.exists():
                return d.forwarded_to.all()
        return []

    @property
    def current_assignee_names(self):
        """String daftar nama penanggung jawab aktif untuk laporan/tabel list."""
        assignees = self.current_assignees
        if assignees:
            return ", ".join([emp.full_name for emp in assignees])
        return "-"

    @property
    def latest_dispo(self):
        return self.dispositions.order_by('created_at').last()

    @property
    def latest_st(self):
        from surat_tugas.models import SuratTugas
        return SuratTugas.objects.filter(disposition__archive=self).order_by('created_at').last()

    @property
    def latest_sppd(self):
        from sppd_service.models import SPPD
        from django.db.models import Q
        return SPPD.objects.filter(
            Q(disposition__archive=self) | Q(surat_tugas__disposition__archive=self)
        ).distinct().order_by('created_at').last()

    @property
    def latest_report(self):
        from reports.models import Report
        return Report.objects.filter(disposition__archive=self).last()

    @property
    def latest_agenda_date(self):
        sppd = self.latest_sppd
        if sppd and sppd.departure_date:
            return sppd.departure_date
        st = self.latest_st
        if st and st.tanggal_mulai:
            return st.tanggal_mulai
        agenda = self.agendas.order_by('scheduled_at').last()
        if agenda and agenda.scheduled_at:
            return agenda.scheduled_at.date()
        return None

    @property
    def activity_name(self):
        s = self.status
        if s == 'selesai':
            return 'Dokumen Selesai / Terarsip Lengkap'
        elif s == 'ditolak':
            return 'Ditolak / Dikembalikan'

        # Smart SPPD & Surat Tugas Activity Detection
        sppd = self.latest_sppd
        if sppd:
            return f"SPPD Terbit ({sppd.sppd_number})"

        st = self.latest_st
        if st:
            return f"Surat Tugas Terbit ({st.nomor_surat or 'ST'})"

        # Check latest disposition stage
        d = self.latest_dispo
        if d:
            if d.is_stage_waka or d.disposition_stage == 'waka_iv' or d.waka_forwarded_to.exists():
                receivers = d.waka_forwarded_to.all()
                if receivers:
                    names = ", ".join([e.full_name for e in receivers])
                    positions = ", ".join([e.position for e in receivers if e.position])
                    if 'Wakil Ketua II' in positions or 'Waka II' in positions or 'Kabid II' in positions:
                        return 'Di Meja Waka II / Bidang II (Penyaluran Bantuan)'
                    elif 'Wakil Ketua III' in positions or 'Waka III' in positions or 'Kabid III' in positions:
                        return 'Di Meja Waka III / Bidang III'
                    elif 'Wakil Ketua I' in positions or 'Waka I' in positions or 'Kabid I' in positions:
                        return 'Di Meja Waka I / Bidang I'
                    elif positions:
                        return f'Di Meja {positions}'
                    return f'Di Meja {names}'
                return 'Di Meja Waka IV / Sekretariat'
            else:
                receivers = d.forwarded_to.all()
                if receivers:
                    positions = ", ".join([e.position for e in receivers if e.position])
                    if 'Wakil Ketua IV' in positions or 'Waka IV' in positions:
                        return 'Di Meja Waka IV (Disposisi Tahap 2)'
                    elif positions:
                        return f'Di Meja {positions}'
                return 'Di Meja Pimpinan (Ketua)'

        if s == 'baru':
            return 'Menunggu Verifikasi Sekretariat'
        elif s == 'verifikasi_kabid':
            return 'Proses Verifikasi Kabid IV'
        elif s == 'terverifikasi':
            return 'Siap Didisposisikan'
        elif s == 'didisposisikan':
            return 'Disposisi Aktif Pimpinan'
        return self.get_status_display()

    @activity_name.setter
    def activity_name(self, value):
        pass

    @property
    def is_disposition_completed(self):
        """Mengecek apakah disposisi dokumen sudah melalui 2 tahap (Ketua & Waka IV)."""
        d = self.latest_dispo
        if not d:
            return False
        has_waka_rec = d.waka_forwarded_to.exists() if hasattr(d, 'waka_forwarded_to') else False
        is_stage_waka = getattr(d, 'is_stage_waka', False)
        stage_val = getattr(d, 'disposition_stage', '')
        return bool(is_stage_waka or stage_val == 'waka_iv' or has_waka_rec or self.dispositions.count() >= 2)

    @property
    def status_note(self):
        return self.rejection_note or self.result_note or self.description or ''

    @status_note.setter
    def status_note(self, value):
        pass

    @property
    def related_disposition(self):
        try:
            return self.dispositions.first() or self.disposition_set.first()
        except Exception:
            try:
                from dispositions.models import Disposition
                return Disposition.objects.filter(archive=self).first()
            except Exception:
                return None

    @property
    def related_surat_tugas_list(self):
        disp = self.related_disposition
        if disp:
            try:
                if hasattr(disp, 'surat_tugas'):
                    return disp.surat_tugas.all()
            except Exception:
                pass
        return []

    @property
    def related_sppd_list(self):
        sppd_list = []
        for st in self.related_surat_tugas_list:
            try:
                if hasattr(st, 'sppd_records'):
                    for sppd in st.sppd_records.all():
                        sppd_list.append(sppd)
            except Exception:
                pass
        return sppd_list

    @property
    def is_pdf(self):
        if self.file_path and self.file_path.name:
            ext = os.path.splitext(self.file_path.name)[1].lower()
            return ext == '.pdf'
        return False

    @property
    def is_image(self):
        if self.file_path and self.file_path.name:
            ext = os.path.splitext(self.file_path.name)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        return False

    @property
    def result_is_pdf(self):
        if self.result_file and self.result_file.name:
            ext = os.path.splitext(self.result_file.name)[1].lower()
            return ext == '.pdf'
        return False

    @property
    def result_is_image(self):
        if self.result_file and self.result_file.name:
            ext = os.path.splitext(self.result_file.name)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        return False

    @property
    def status_badge_class(self):
        badge_map = {
            'baru': 'bg-warning text-dark',
            'verifikasi_kabid': 'bg-info text-dark',
            'disposisi_pimpinan': 'bg-primary text-white',
            'terverifikasi': 'bg-primary text-white',
            'didisposisikan': 'bg-info text-white',
            'proses': 'bg-secondary text-white',
            'sudah_ditugaskan': 'bg-indigo text-white',
            'menghadiri_undangan': 'bg-secondary text-white',
            'dalam_survei': 'bg-secondary text-white',
            'telah_disalurkan': 'bg-success text-white',
            'selesai': 'bg-success text-white',
            'ditolak': 'bg-danger text-white',
        }
        return badge_map.get(self.status, 'bg-secondary text-white')

    @property
    def workflow_status_display(self):
        """Label status yang dipakai konsisten di detail dokumen dan dashboard tracker."""
        if self.status in ['selesai', 'telah_disalurkan']:
            return 'SELESAI & TEREKAP'

        if self.status == 'ditolak':
            return 'DITOLAK / DIKEMBALIKAN'

        sppd = self.latest_sppd
        if sppd:
            purp_lower = (sppd.purpose or '').lower()
            if any(k in purp_lower for k in ['survei', 'peninjauan', 'lokasi', 'lapangan', 'cek', 'mustahik']):
                return 'SURVEI LAPANGAN MUSTAHIK'
            elif any(k in purp_lower for k in ['hadir', 'undangan', 'audiensi', 'rapat', 'acara']):
                return 'MENGHADIRI UNDANGAN / RAPAT'
            elif any(k in purp_lower for k in ['bantuan', 'penyaluran', 'pentasyarufan', 'cair', 'santunan', 'rutilahu', 'gharimin']):
                return 'PENYALURAN BANTUAN / PENTASYARUFAN'
            elif sppd.purpose:
                return f'PELAKSANAAN SPPD: {sppd.purpose[:35].upper()}'
            return 'PELAKSANAAN SPPD (PERJALANAN DINAS)'

        if self.latest_st:
            return 'TAHAP PENUGASAN (SURAT TUGAS TERBIT)'

        # Status 'proses' atau saat Waka IV sudah mendisposisikan
        if self.status in ['proses', 'didisposisikan'] or (self.latest_dispo and self.latest_dispo.is_stage_waka):
            return 'PROSES BIDANG II (PENYALURAN BANTUAN)' if self.is_proposal_bantuan else 'DIPROSES BIDANG TERKAIT'

        return self.get_status_display().upper()

    @property
    def is_proposal_bantuan(self):
        from services.workflows.workflow_engine import WorkflowEngine
        return WorkflowEngine.is_bantuan(self)

    @property
    def sender_receiver(self):
        return self.sender or self.receiver or '-'

    @sender_receiver.setter
    def sender_receiver(self, value):
        self.sender = value

    @property
    def agenda_set(self):
        return self.agendas

    @property
    def subject(self):
        return self.title or self.description or '-'

    @property
    def safe_title(self):
        return self.title or '-'

    @property
    def safe_description(self):
        return self.description or 'Tidak ada catatan tambahan.'

    def save(self, *args, **kwargs):
        """Override save untuk merekam setiap perpindahan status ke WorkflowHistory."""
        is_new = self.pk is None
        old_status = None
        if not is_new:
            try:
                old_status = Archive.objects.get(pk=self.pk).status
            except Archive.DoesNotExist:
                pass

        if not self.archive_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.archive_number = NumberingService.generate_number(
                    'archive',
                    extra_context={'archive_type': self.archive_type},
                )
            except Exception:
                pass

        super().save(*args, **kwargs)

        if is_new:
            WorkflowHistory.objects.create(
                archive=self,
                user=getattr(self, 'current_user', None),
                activity="Registrasi Surat Masuk",
                old_status="",
                new_status='baru',
                note="Dokumen baru diunggah ke sistem."
            )
        elif old_status and old_status != self.status:
            user = getattr(self, 'current_user', None)
            activity_name = getattr(self, 'activity_name', f"Update Status Dokumen ({self.get_status_display()})")
            note = getattr(self, 'status_note', f"Status berubah dari {old_status} menjadi {self.status}.")

            WorkflowHistory.objects.create(
                archive=self,
                user=user,
                activity=activity_name,
                old_status=old_status,
                new_status=self.status,
                note=note
            )

            try:
                if hasattr(self, 'document_workflow'):
                    self.document_workflow.update_current_step(self.status, user)
            except Exception:
                pass


class Workflow(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nama Alur Kerja")
    description = models.TextField(blank=True, verbose_name="Deskripsi")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'archives'
        verbose_name = 'Alur Kerja'
        verbose_name_plural = 'Alur Kerja'

    def __str__(self):
        return self.name


class WorkflowStep(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='steps_template')
    name = models.CharField(max_length=100, verbose_name="Nama Langkah")
    status_key = models.CharField(max_length=50, blank=True, null=True, verbose_name="Status Arsip Terkait")
    order = models.IntegerField(default=1, verbose_name="Urutan")
    is_optional = models.BooleanField(default=False, verbose_name="Dapat Dilewati")

    class Meta:
        app_label = 'archives'
        ordering = ['order']
        verbose_name = 'Langkah Alur Kerja'

    def __str__(self):
        return f"{self.workflow.name} - {self.name} ({self.order})"


class DocumentWorkflow(models.Model):
    archive = models.OneToOneField(Archive, on_delete=models.CASCADE, related_name='document_workflow')
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='active_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'archives'

    def __str__(self):
        return f"Workflow: {self.archive.archive_number or self.archive.title}"


class DocumentWorkflowStep(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu'),
        ('current', 'Sedang Berjalan'),
        ('completed', 'Selesai'),
        ('skipped', 'Dilewati'),
    ]
    document_workflow = models.ForeignKey(DocumentWorkflow, on_delete=models.CASCADE, related_name='steps')
    name = models.CharField(max_length=100)
    status_key = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order = models.IntegerField(default=1)
    is_optional = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'archives'
        ordering = ['order']


class WorkflowHistory(models.Model):
    archive = models.ForeignKey(Archive, on_delete=models.CASCADE, related_name='workflow_history')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    activity = models.CharField(max_length=255)
    old_status = models.CharField(max_length=50, blank=True, null=True)
    new_status = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'archives'
        ordering = ['-created_at']


class SequenceCounter(models.Model):
    name = models.CharField(max_length=200, unique=True)
    value = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'archives'


def get_next_sequence(counter_name):
    from django.db import transaction
    with transaction.atomic():
        counter, created = SequenceCounter.objects.select_for_update().get_or_create(name=counter_name)
        counter.value = (counter.value or 0) + 1
        counter.save(update_fields=['value', 'updated_at'])
        return int(counter.value)