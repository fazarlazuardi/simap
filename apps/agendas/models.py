from django.db import models
from django.conf import settings
from django.utils import timezone
from archives.models import Archive
from users.models import Employee
from core.validators import validate_file_extension, validate_file_size

class Agenda(models.Model):
    STATUS_CHOICES = [
        ('terjadwal', 'Terjadwal'),
        ('diundur', 'Diundur'),
        ('dibatalkan', 'Dibatalkan'),
        ('selesai', 'Selesai'),
    ]

    title = models.CharField(max_length=255, verbose_name="Nama Kegiatan / Agenda")
    location = models.CharField(max_length=255, null=True, blank=True, verbose_name="Tempat / Lokasi Kegiatan")
    description = models.TextField(blank=True, verbose_name="Deskripsi / Acara")
    archive = models.ForeignKey(
        Archive, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='agendas',
        verbose_name="Arsip / Dokumen Terkait"
    )
    scheduled_at = models.DateTimeField(verbose_name="Waktu Pelaksanaan", db_index=True)
    
    # Penugasan Ke Akun User & Pegawai
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True,
        related_name='assigned_agendas',
        verbose_name="Ditugaskan ke User"
    )
    assigned_employees = models.ManyToManyField(
        Employee,
        blank=True,
        related_name='assigned_agendas',
        verbose_name="Ditugaskan ke Pegawai"
    )
    
    # File Lampiran & Berkas Pendukung
    attachment = models.FileField(
        upload_to='agendas/%Y/%m/%d/', 
        null=True, 
        blank=True, 
        validators=[validate_file_extension, validate_file_size],
        verbose_name="File Lampiran / Undangan"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_agendas',
        verbose_name="Dibuat Oleh"
    )
    is_completed = models.BooleanField(default=False, verbose_name="Status Selesai")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='terjadwal', verbose_name="Status Agenda")
    
    RECURRENCE_CHOICES = [
        ('none', 'Tidak Berulang'),
        ('daily', 'Setiap Hari'),
        ('weekly', 'Setiap Minggu (Hari yang Sama)'),
        ('monthly', 'Setiap Bulan'),
    ]

    DAY_CHOICES = [
        (0, 'Senin'),
        (1, 'Selasa'),
        (2, 'Rabu'),
        (3, 'Kamis'),
        (4, 'Jumat'),
        (5, 'Sabtu'),
        (6, 'Minggu'),
    ]

    WA_TIMING_CHOICES = [
        ('instant', 'Langsung Saat Terbit'),
        ('h_minus_1', 'H-1 Pelaksanaan (08:00 WIB)'),
        ('h_minus_1_hour', 'Hari H (1 Jam Sebelum Acara)'),
    ]

    # In-memory @property dynamic accessors to avoid MySQL OperationalError 1054
    @property
    def sppd_ref(self):
        """Mendapatkan SPPD terkait secara in-memory."""
        if hasattr(self, '_sppd_ref_cache'):
            return self._sppd_ref_cache
        if self.archive:
            dispo = self.archive.dispositions.first()
            if dispo:
                return dispo.sppd_list.first()
        return None

    @sppd_ref.setter
    def sppd_ref(self, value):
        self._sppd_ref_cache = value

    @property
    def is_undangan_luar(self):
        """Mengecek apakah agenda ini merupakan penugasan luar / hadiri undangan luar kantor."""
        if self.location:
            loc_lower = self.location.lower()
            in_office_keywords = ['kantor baznas', 'kantor', 'ruang rapat', 'aula baznas', 'dalam kantor', 'internal']
            if any(k in loc_lower for k in in_office_keywords):
                return False

        if self.archive and getattr(self.archive, 'archive_type', '') == 'undangan':
            return True

        text = f"{self.title or ''} {self.description or ''} {self.location or ''}".lower()
        if self.archive:
            text += f" {self.archive.title or ''} {self.archive.archive_type or ''}".lower()
        
        if any(kw in text for kw in ['hadiri undangan luar', 'luar kantor', 'hotel', 'gedung pemkab', 'luar kota', 'penugasan luar']):
            return True
            
        if self.location:
            loc_lower = self.location.lower()
            if not any(k in loc_lower for k in ['kantor baznas', 'kantor', 'ruang rapat', 'aula']):
                return True
                
        return False

    @property
    def is_sppd_generated(self):
        """Mengecek apakah agenda bersumber dari SPPD."""
        if hasattr(self, '_is_sppd_generated_cache'):
            return self._is_sppd_generated_cache
        return bool(self.title and self.title.startswith('SPPD:')) or bool(self.sppd_ref)

    @is_sppd_generated.setter
    def is_sppd_generated(self, value):
        self._is_sppd_generated_cache = bool(value)

    @property
    def internal_meeting_id(self):
        """Mendapatkan ID Rapat Internal terkait jika agenda ini disinkronkan dari Rapat Internal."""
        if hasattr(self, '_internal_meeting_id_cache'):
            return self._internal_meeting_id_cache
        if self.description and 'InternalMeetingID:' in self.description:
            try:
                import re
                match = re.search(r'InternalMeetingID:(\d+)', self.description)
                if match:
                    return int(match.group(1))
            except Exception:
                pass
        return None

    @internal_meeting_id.setter
    def internal_meeting_id(self, value):
        self._internal_meeting_id_cache = value

    @property
    def is_recurring(self):
        if hasattr(self, '_is_recurring_cache'):
            return self._is_recurring_cache
        return False

    @is_recurring.setter
    def is_recurring(self, value):
        self._is_recurring_cache = bool(value)

    @property
    def recurrence_type(self):
        return getattr(self, '_recurrence_type_cache', 'none')

    @recurrence_type.setter
    def recurrence_type(self, value):
        self._recurrence_type_cache = value

    @property
    def recurrence_day(self):
        return getattr(self, '_recurrence_day_cache', None)

    @recurrence_day.setter
    def recurrence_day(self, value):
        self._recurrence_day_cache = value

    @property
    def recurrence_end_date(self):
        return getattr(self, '_recurrence_end_date_cache', None)

    @recurrence_end_date.setter
    def recurrence_end_date(self, value):
        self._recurrence_end_date_cache = value

    @property
    def wa_notification_timing(self):
        return getattr(self, '_wa_notification_timing_cache', 'instant')

    @wa_notification_timing.setter
    def wa_notification_timing(self, value):
        self._wa_notification_timing_cache = value

    def get_recurrence_type_display(self):
        mapping = {'weekly': 'Setiap Minggu', 'daily': 'Setiap Hari', 'monthly': 'Setiap Bulan', 'none': 'Tidak Berulang'}
        return mapping.get(self.recurrence_type, 'Setiap Minggu')


    # Laporan Pertanggungjawaban / Hasil Notulensi
    completed_notes = models.TextField(blank=True, verbose_name="Catatan Penyelesaian / Notulensi")
    completed_file = models.FileField(
        upload_to='agendas/completed/%Y/%m/%d/', 
        null=True, 
        blank=True, 
        validators=[validate_file_extension, validate_file_size],
        verbose_name="Dokumentasi / Hasil Kegiatan"
    )

    
    notification_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Notifikasi Terakhir Dikirim")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Dibuat")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Waktu Diperbarui")

    class Meta:
        verbose_name = "Agenda Kerja"
        verbose_name_plural = "Agenda Kerja BAZNAS"
        ordering = ['-scheduled_at']

    @property
    def is_upcoming(self):
        """Mengecek apakah agenda masih di masa depan dan berstatus terjadwal."""
        return self.status == 'terjadwal' and self.scheduled_at > timezone.now()

    @property
    def formatted_schedule(self):
        """Format tanggal & waktu yang rapi untuk tampilan template."""
        if self.scheduled_at:
            return self.scheduled_at.strftime('%d/%m/%Y %H:%M WIB')
        return '-'

    def save(self, *args, **kwargs):
        """Override save untuk men-trigger CalendarEvent dan notifikasi ketika agenda dibuat/diperbarui."""
        is_new = self.pk is None
        old_status = None
        if not is_new:
            try:
                old_status = Agenda.objects.get(pk=self.pk).status
            except Exception:
                old_status = None

        super().save(*args, **kwargs)

        try:
            import threading
            agenda_pk = self.pk
            agenda_title = self.title
            sched_iso = self.scheduled_at.isoformat() if self.scheduled_at else None
            loc = self.location
            sched_fmt = self.formatted_schedule

            # Collect phones
            phones = []
            if is_new or (old_status != self.status and self.status == 'terjadwal'):
                for u in self.assigned_to.all():
                    emp = getattr(u, 'employee', None)
                    if emp and hasattr(emp, 'phone') and emp.phone:
                        phones.append(emp.phone)
                for emp in self.assigned_employees.all():
                    if hasattr(emp, 'phone') and emp.phone:
                        if emp.phone not in phones:
                            phones.append(emp.phone)

            def _bg_agenda_notifications(pk_val, title_val, dt_iso, loc_val, fmt_val, phone_list):
                try:
                    from notifications.tasks import create_calendar_event, send_wa_message
                    if dt_iso:
                        try:
                            create_calendar_event.delay('agenda', pk_val, title_val, dt_iso, None, loc_val)
                        except Exception as e_ev:
                            print("Error creating agenda calendar event:", e_ev)

                    if phone_list:
                        msg_text = f"Agenda: {title_val} - {fmt_val}. Lokasi: {loc_val}"
                        for p in phone_list:
                            try:
                                send_wa_message.delay(p, msg_text, metadata={'agenda_id': pk_val})
                            except Exception as e_wa:
                                print("Error sending agenda WA:", e_wa)
                except Exception as err_bg:
                    print("Error in background agenda post-save:", err_bg)

            threading.Thread(
                target=_bg_agenda_notifications,
                args=(agenda_pk, agenda_title, sched_iso, loc, sched_fmt, phones),
                daemon=True
            ).start()
        except Exception as e:
            print('Error in Agenda post-save integration:', e)

    @property
    def assigned_names_display(self):
        """Mengembalikan daftar nama penerima/staf yang ditugaskan."""
        names = []
        # Ambil dari user yang terhubung
        for u in self.assigned_to.select_related('employee').all():
            if hasattr(u, 'employee') and u.employee:
                names.append(u.employee.full_name)
            else:
                names.append(u.username)
        
        # Ambil dari pegawai langsung jika ada
        for emp in self.assigned_employees.all():
            if emp.full_name not in names:
                names.append(emp.full_name)
                
        return ', '.join(names) if names else '-'


class AgendaAttachment(models.Model):
    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='agendas/attachments/%Y/%m/%d/', validators=[validate_file_extension, validate_file_size])
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lampiran Agenda #{self.agenda_id}: {self.description or self.file.name}"


class CalendarEvent(models.Model):
    """Central Calendar Event model to record organization-wide events.

    This model is source-agnostic and can be created/updated by SPPD, SuratTugas, or Agenda.
    """
    source_key = models.CharField(max_length=200, unique=True, help_text="Unique key like 'sppd:123' or 'agenda:45'")
    title = models.CharField(max_length=255)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    archive = models.ForeignKey('archives.Archive', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_events')
    surat_tugas = models.ForeignKey('surat_tugas.SuratTugas', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_events')
    sppd = models.ForeignKey('sppd_service.SPPD', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_events')
    agenda = models.ForeignKey('Agenda', on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_events')
    external_event_id = models.CharField(max_length=255, null=True, blank=True, help_text='ID on external calendar provider if synced')
    status = models.CharField(max_length=50, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Calendar Event'
        verbose_name_plural = 'Calendar Events'

    def __str__(self):
        return f"{self.title} ({self.start})"