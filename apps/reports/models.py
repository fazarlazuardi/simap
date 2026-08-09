import json
from django.db import models
from django.conf import settings
from django.utils import timezone
from dispositions.models import Disposition

from core.validators import validate_file_extension, validate_file_size

class Report(models.Model):
    disposition = models.OneToOneField(Disposition, on_delete=models.CASCADE, related_name='report')
    report_number = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    file = models.FileField(upload_to='reports/%Y/%m/%d/', null=True, blank=True, validators=[validate_file_extension, validate_file_size])
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Laporan: {self.report_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.report_number:
            try:
                from services.archives.numbering_service import NumberingService
                self.report_number = NumberingService.generate_number('report')
            except Exception:
                pass
        super().save(*args, **kwargs)


class ReportAttachment(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='reports/%Y/%m/%d/', validators=[validate_file_extension, validate_file_size])
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description or 'Lampiran'} - {self.report.report_number}"


class GoogleOAuthToken(models.Model):
    refresh_token = models.TextField()
    access_token = models.TextField(blank=True, default='')
    token_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Google OAuth Token'
        verbose_name_plural = 'Google OAuth Tokens'

    def is_valid(self):
        if not self.access_token or not self.token_expiry:
            return False
        now = timezone.now()
        expiry = self.token_expiry
        if timezone.is_aware(expiry):
            expiry = timezone.make_naive(expiry, timezone=timezone.utc)
        if timezone.is_aware(now):
            now = timezone.make_naive(now, timezone=timezone.utc)
        return now < expiry

    @staticmethod
    def get_client_config():
        from users.models import SystemSetting
        raw = SystemSetting.get_value('GOOGLE_OAUTH_CLIENT_CONFIG', '')
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def get_credentials(self):
        client_config = self.get_client_config()
        if not client_config:
            return None
        from google.oauth2.credentials import Credentials
        expiry = self.token_expiry
        if expiry and timezone.is_aware(expiry):
            expiry = timezone.make_naive(expiry, timezone=timezone.utc)
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_config.get('installed', client_config.get('web', client_config)).get('client_id'),
            client_secret=client_config.get('installed', client_config.get('web', client_config)).get('client_secret'),
            scopes=['https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/spreadsheets'],
            expiry=expiry
        )

    def refresh_if_expired(self):
        if not self.is_valid() and self.refresh_token:
            creds = self.get_credentials()
            if creds:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                self.access_token = creds.token
                expiry = creds.expiry
                if expiry and not timezone.is_naive(expiry):
                    expiry = timezone.make_naive(expiry, timezone=timezone.utc)
                self.token_expiry = expiry
                self.save(update_fields=['access_token', 'token_expiry', 'updated_at'])
                return True
        return False

    def __str__(self):
        return f'OAuth Token (expires: {self.token_expiry})'


class MonthlyBackup(models.Model):
    MONTH_NAMES = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                   'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

    month = models.IntegerField()
    year = models.IntegerField()
    spreadsheet_id = models.CharField(max_length=200)
    spreadsheet_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('month', 'year')
        ordering = ['-year', '-month']

    def month_name(self):
        return self.MONTH_NAMES[self.month - 1] if 1 <= self.month <= 12 else str(self.month)

    def __str__(self):
        return f"Backup {self.month_name()} {self.year}"
