from django.db import models
from django.conf import settings
from users.models import Employee

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
    ]

    CATEGORY_CHOICES = [
        ('disposition', 'Disposisi'),
        ('sppd', 'SPPD & Surat Tugas'),
        ('agenda', 'Agenda Kerja'),
        ('archive', 'Arsip & Dokumen'),
        ('general', 'Umum'),
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
    category = models.CharField(
        max_length=30, 
        choices=CATEGORY_CHOICES, 
        default='general', 
        verbose_name="Kategori"
    )
    title = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Judul Notifikasi"
    )
    message = models.TextField(verbose_name="Pesan Notifikasi")
    
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
        verbose_name="Status Pengiriman/Baca"
    )
    
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notifikasi"
        verbose_name_plural = "Log Notifikasi"
        ordering = ['-created_at']

    def __str__(self):
        recipient = self.user.username if self.user else (self.employee.full_name if self.employee else 'Anonim')
        return f"[{self.get_notification_type_display()}] Untuk {recipient}: {self.message[:30]}..."

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