from django.db import models
from django.conf import settings
from django.utils import timezone
from users.models import Employee
from core.validators import validate_file_extension, validate_file_size


class InternalMeeting(models.Model):
    MEETING_TYPE_CHOICES = [
        ('pimpinan', 'Rapat Pimpinan (Rapim)'),
        ('pleno', 'Rapat Pleno Bidang'),
        ('evaluasi', 'Rapat Evaluasi & Koordinasi'),
        ('khusus', 'Rapat Internal / Khusus'),
    ]

    STATUS_CHOICES = [
        ('terjadwal', 'Terjadwal'),
        ('berlangsung', 'Sedang Berlangsung'),
        ('selesai', 'Selesai (Notulensi Terbit)'),
        ('dibatalkan', 'Dibatalkan'),
    ]

    meeting_number = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
        verbose_name="Nomor Risalah / Agenda"
    )
    title = models.CharField(max_length=255, verbose_name="Judul / Perihal Rapat")
    meeting_type = models.CharField(
        max_length=30, choices=MEETING_TYPE_CHOICES, default='pimpinan',
        verbose_name="Jenis Rapat"
    )
    scheduled_at = models.DateTimeField(verbose_name="Waktu & Tanggal Pelaksanaan", db_index=True)
    location = models.CharField(
        max_length=255, default="Ruang Rapat Utama BAZNAS",
        verbose_name="Tempat / Ruang Rapat"
    )

    leader = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='led_internal_meetings', verbose_name="Pimpinan Rapat Utama"
    )
    leaders = models.ManyToManyField(
        Employee, blank=True, related_name='led_internal_meetings_m2m',
        verbose_name="Pimpinan Rapat (Multi)"
    )
    participants = models.ManyToManyField(
        Employee, blank=True, related_name='attended_internal_meetings',
        verbose_name="Peserta Rapat (Pegawai / Amil)"
    )

    agenda_topics = models.TextField(verbose_name="Agenda & Topik Pembahasan")
    attachment = models.FileField(
        upload_to='meetings/attachments/%Y/%m/', null=True, blank=True,
        validators=[validate_file_extension, validate_file_size],
        verbose_name="Berkas Lampiran / Undangan"
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='terjadwal', db_index=True,
        verbose_name="Status Rapat"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='created_internal_meetings', verbose_name="Dibuat Oleh"
    )

    # ─── RISALAH / NOTULENSI RAPAT ───
    notulensi_summary = models.TextField(
        blank=True, null=True, verbose_name="Ringkasan Pembahasan & Risalah"
    )
    notulensi_decision = models.TextField(
        blank=True, null=True, verbose_name="Kesimpulan & Keputusan Rapat"
    )
    notulensi_action_items = models.TextField(
        blank=True, null=True, verbose_name="Rencana Tindak Lanjut (Action Plan)"
    )
    notulis = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_notulensi', verbose_name="Notulis Rapat"
    )
    notulensi_file = models.FileField(
        upload_to='meetings/notulensi/%Y/%m/', null=True, blank=True,
        validators=[validate_file_extension, validate_file_size],
        verbose_name="Dokumen Bukti / Foto Notulensi"
    )
    notulensi_created_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Waktu Notulensi Disimpan"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at']
        verbose_name = "Rapat Internal"
        verbose_name_plural = "Daftar Rapat Internal"

    def __str__(self):
        number_str = self.meeting_number or f"RPT-{self.id}"
        return f"[{number_str}] {self.title}"

    @property
    def is_notulensi_completed(self):
        return bool(self.status == 'selesai' or self.notulensi_summary or self.notulensi_decision)

    @property
    def participants_names_display(self):
        names = [p.full_name for p in self.participants.all() if p.full_name]
        return ", ".join(names) if names else "-"

    @property
    def ordered_leaders(self):
        """Mengembalikan daftar pimpinan rapat terurut berdasarkan hirarki jabatan struktural (Ketua -> Waka I -> Waka II -> Waka III -> Waka IV -> Kabid)."""
        leaders_set = set()
        if self.leader:
            leaders_set.add(self.leader)
        for l in self.leaders.all():
            leaders_set.add(l)

        leaders_list = list(leaders_set)

        def get_rank(emp):
            pos = (emp.position or "").lower().strip()
            if 'ketua' in pos and 'wakil' not in pos:
                return 1
            if 'wakil ketua iv' in pos or 'wakil ketua 4' in pos or 'waka iv' in pos or 'waka 4' in pos:
                return 5
            if 'wakil ketua iii' in pos or 'wakil ketua 3' in pos or 'waka iii' in pos or 'waka 3' in pos:
                return 4
            if 'wakil ketua ii' in pos or 'wakil ketua 2' in pos or 'waka ii' in pos or 'waka 2' in pos:
                return 3
            if 'wakil ketua i' in pos or 'wakil ketua 1' in pos or 'waka i' in pos or 'waka 1' in pos:
                return 2
            if 'wakil' in pos:
                return 6
            if 'sekretaris' in pos:
                return 7
            if 'kabid' in pos or 'kepala' in pos:
                return 8
            return 9

        leaders_list.sort(key=get_rank)
        return leaders_list

    @property
    def leader_names_display(self):
        leaders_list = self.ordered_leaders
        if leaders_list:
            names = []
            for l in leaders_list:
                pos = f" ({l.position})" if l.position else ""
                names.append(f"{l.full_name}{pos}")
            return ", ".join(names)
        return "Pimpinan BAZNAS"

    @property
    def notulis_name_display(self):
        if self.notulis and self.notulis.full_name:
            return self.notulis.full_name
        return "-"

    def save(self, *args, **kwargs):
        if not self.meeting_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.meeting_number = NumberingService.generate_number('meeting')
            except Exception:
                pass
        super().save(*args, **kwargs)
