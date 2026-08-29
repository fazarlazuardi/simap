from django.db import models
from django.conf import settings
from users.models import Employee
import urllib.parse

class WANotificationSetting(models.Model):
    MODE_CHOICES = [
        ('auto', '🤖 Otomatis (Auto-Dispatch Queue)'),
        ('manual', '💬 Manual (1-Click WA Direct Link/Trigger)'),
        ('disabled', '🚫 Nonaktifkan Notifikasi WA'),
    ]

    CATEGORY_CHOICES = [
        ('disposition', 'Disposisi Pimpinan (Stage 1 & 2)'),
        ('bantuan_survei', 'Penugasan Survei Lapangan Bantuan (Bidang II)'),
        ('bantuan_penyaluran', 'LHP Penyaluran Direct (Bidang II)'),
        ('sppd', 'SPPD & Perjalanan Dinas'),
        ('internal_meeting', 'Risalah & Notulensi Rapat Internal'),
        ('agenda', 'Agenda Kerja & Pengingat'),
        ('archive', 'Notifikasi Arsip & Dokumen Baru'),
        ('general', 'Umum / System Default'),
    ]

    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES, 
        unique=True,
        verbose_name="Kategori Kejadian Notifikasi"
    )
    dispatch_mode = models.CharField(
        max_length=20, 
        choices=MODE_CHOICES, 
        default='auto', 
        verbose_name="Mode Pengiriman"
    )
    description = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Keterangan Notifikasi"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pengaturan Mode Notifikasi WA"
        verbose_name_plural = "Pengaturan Mode Notifikasi WA"
        ordering = ['category']

    def __str__(self):
        return f"{self.get_category_display()} [{self.get_dispatch_mode_display()}]"

    @classmethod
    def get_mode_for_category(cls, category_name):
        """Helper untuk mengambil mode pengiriman ('auto', 'manual', 'disabled') per kategori."""
        cat = category_name or 'general'
        setting = cls.objects.filter(category=cat).first()
        if setting:
            return setting.dispatch_mode
        
        # Pengecekan master: Jika SEMUA kategori yang terdaftar dalam DB diset 'disabled', kembalikan 'disabled'!
        try:
            total_count = cls.objects.count()
            disabled_count = cls.objects.filter(dispatch_mode='disabled').count()
            if total_count > 0 and disabled_count == total_count:
                return 'disabled'
        except Exception:
            pass

        gen_setting = cls.objects.filter(category='general').first()
        if gen_setting:
            return gen_setting.dispatch_mode

        return 'auto'

    @classmethod
    def is_disabled_for_category(cls, category_name):
        """Pengecekan instan apakah notifikasi WA untuk kategori tertentu (atau seluruhnya) dinonaktifkan."""
        mode = cls.get_mode_for_category(category_name)
        if mode == 'disabled':
            return True
        try:
            total_count = cls.objects.count()
            if total_count > 0:
                disabled_count = cls.objects.filter(dispatch_mode='disabled').count()
                if disabled_count == total_count:
                    return True
        except Exception:
            pass
        return False



class Notification(models.Model):
    TYPE_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('system', 'System / Web Dashboard'),
    ]

    STATUS_CHOICES = [
        ('unread', 'Belum Dibaca'),
        ('read', 'Sudah Dibaca'),
        ('pending', 'Menunggu Pengiriman'),
        ('sent', 'Terkirim'),
        ('failed', 'Gagal Terkirim'),
        ('draft_manual', 'Siap Kirim Manual'),
    ]

    CATEGORY_CHOICES = [
        ('disposition', 'Disposisi'),
        ('bantuan_survei', 'Survei Bantuan'),
        ('bantuan_penyaluran', 'Penyaluran Bantuan'),
        ('sppd', 'SPPD & Surat Tugas'),
        ('internal_meeting', 'Rapat Internal'),
        ('agenda', 'Agenda Kerja'),
        ('archive', 'Arsip & Dokumen'),
        ('general', 'Umum'),
    ]

    DISPATCH_MODE_CHOICES = [
        ('auto', 'Otomatis'),
        ('manual', 'Manual'),
    ]

    # Penerima Notifikasi (User Login atau Pegawai/Amil Fisik)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='notifications',
        verbose_name="User Penerima"
    )
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='notifications',
        verbose_name="Pegawai/Amil Penerima"
    )

    notification_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='system', 
        verbose_name="Tipe Notifikasi"
    )
    dispatch_mode = models.CharField(
        max_length=20, 
        choices=DISPATCH_MODE_CHOICES, 
        default='auto', 
        verbose_name="Mode Pengiriman WA"
    )
    category = models.CharField(
        max_length=30, 
        choices=CATEGORY_CHOICES, 
        default='general', 
        db_index=True,
        verbose_name="Kategori"
    )
    title = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Judul Notifikasi"
    )
    message = models.TextField(verbose_name="Pesan Notifikasi")
    recipient_phone = models.CharField(
        max_length=30, 
        blank=True, 
        null=True, 
        verbose_name="Nomor WA Penerima"
    )
    wa_direct_link = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Direct Link WA Web / App"
    )
    
    # Tautan Aksi (Misal: /archives/12/ atau /sppd/5/)
    link_url = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Link Tautan"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='unread', 
        db_index=True,
        verbose_name="Status Pengiriman/Baca"
    )
    
    retry_count = models.IntegerField(default=0, verbose_name="Jumlah Percobaan Kirim Ulang")

    # Catatan error jika pengiriman WhatsApp gagal
    error_log = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Log Kendala/Error"
    )
    
    sent_at = models.DateTimeField(
        blank=True, 
        null=True, 
        verbose_name="Waktu Terkirim"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notifikasi"
        verbose_name_plural = "Log Notifikasi"
        ordering = ['-created_at']

    def __str__(self):
        recipient = self.user.username if self.user else (self.employee.full_name if self.employee else 'Anonim')
        return f"[{self.get_notification_type_display()}] Untuk {recipient}: {self.message[:30]}..."

    def generate_wa_direct_link(self):
        """Membuat direct link WhatsApp (api.whatsapp.com) dengan teks terenkode."""
        if not self.recipient_phone:
            return ""
        clean_phone = ''.join(filter(str.isdigit, str(self.recipient_phone)))
        if clean_phone.startswith('0'):
            clean_phone = '62' + clean_phone[1:]
        encoded_msg = urllib.parse.quote(self.message)
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"

    def save(self, *args, **kwargs):
        if self.notification_type == 'whatsapp' and self.recipient_phone:
            self.wa_direct_link = self.generate_wa_direct_link()
        super().save(*args, **kwargs)

    @classmethod
    def create_system_notif(cls, user, title, message, link_url="", category="general"):
        """Helper ringkas untuk membuat notifikasi web dashboard."""
        return cls.objects.create(
            user=user,
            notification_type='system',
            category=category,
            title=title,
            message=message,
            link_url=link_url,
            status='unread'
        )


class DirectMessage(models.Model):
    """Model Pesan Langsung Interaktif Antar Amil/User SIMAP."""
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_direct_messages',
        verbose_name="Pengirim Pesan"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_direct_messages',
        verbose_name="Penerima Pesan"
    )
    body = models.TextField(verbose_name="Isi Pesan Chat")
    is_read = models.BooleanField(default=False, verbose_name="Sudah Dibaca")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pesan Direct Amil"
        verbose_name_plural = "Pesan Direct Amil"
        ordering = ['created_at']

    def __str__(self):
        return f"Pesan dari {self.sender.username} ke {self.recipient.username}: {self.body[:25]}..."