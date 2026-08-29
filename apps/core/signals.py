import os
from django.db.models.signals import post_delete
from django.dispatch import receiver
from reports.models import Report, ReportAttachment
from agendas.models import Agenda, AgendaAttachment
from internal_meetings.models import InternalMeeting
from sppd_service.models import SPPD


def _delete_file_safely(file_field):
    """
    Menghapus berkas fisik dari storage jika file_field memiliki path fisik.
    """
    try:
        if file_field and hasattr(file_field, 'path') and os.path.isfile(file_field.path):
            os.remove(file_field.path)
    except Exception as err:
        print("Error deleting physical file:", err)


@receiver(post_delete, sender=ReportAttachment)
def auto_delete_report_attachment_file(sender, instance, **kwargs):
    _delete_file_safely(instance.file)


@receiver(post_delete, sender=Report)
def auto_delete_report_file(sender, instance, **kwargs):
    _delete_file_safely(instance.file)


@receiver(post_delete, sender=AgendaAttachment)
def auto_delete_agenda_attachment_file(sender, instance, **kwargs):
    _delete_file_safely(instance.file)


@receiver(post_delete, sender=Agenda)
def auto_delete_agenda_file(sender, instance, **kwargs):
    _delete_file_safely(instance.attachment)
    _delete_file_safely(instance.completed_file)


@receiver(post_delete, sender=InternalMeeting)
def auto_delete_meeting_file(sender, instance, **kwargs):
    _delete_file_safely(instance.attachment)
    _delete_file_safely(instance.notulensi_file)


@receiver(post_delete, sender=SPPD)
def auto_delete_sppd_file(sender, instance, **kwargs):
    _delete_file_safely(instance.report_file)


# ------------------------------------------------------------------
# AUTOMATIC SEQUENCE COUNTER RESET ON DELETE (DJANGO ADMIN & VIEWS)
# ------------------------------------------------------------------
@receiver(post_delete, sender=Report)
@receiver(post_delete, sender=SPPD)
@receiver(post_delete, sender=InternalMeeting)
def auto_reset_model_sequence_counter(sender, instance, **kwargs):
    """
    Otomatis mereset SequenceCounter ke 0 jika seluruh record pada model terkait telah dihapus.
    """
    try:
        from archives.models import SequenceCounter
        if not sender.objects.exists():
            sender_name_map = {
                'Report': 'report',
                'SPPD': 'sppd',
                'InternalMeeting': 'meeting',
            }
            prefix = sender_name_map.get(sender.__name__)
            if prefix:
                SequenceCounter.objects.filter(name__startswith=prefix).update(value=0)
    except Exception as err:
        print("Error resetting sequence counter:", err)


from dispositions.models import Disposition
@receiver(post_delete, sender=Disposition)
def auto_reset_disposition_counter(sender, instance, **kwargs):
    """
    Otomatis mereset SequenceCounter 'disposition' ke 0 jika SELURUH record Disposisi dihapus.
    """
    try:
        from archives.models import SequenceCounter
        if not Disposition.objects.exclude(disposition_number__isnull=True).exclude(disposition_number='').exists():
            SequenceCounter.objects.filter(name='disposition').update(value=0)
    except Exception as err:
        print("Error resetting disposition sequence counter:", err)


from archives.models import Archive
@receiver(post_delete, sender=Archive)
def auto_reset_archive_counter(sender, instance, **kwargs):
    """
    Otomatis mereset SequenceCounter 'archive' ke 0 jika SELURUH record Arsip dihapus.
    """
    try:
        from archives.models import SequenceCounter
        if not Archive.objects.exclude(archive_number__isnull=True).exclude(archive_number='').exists():
            SequenceCounter.objects.filter(name__startswith='archive').update(value=0)
    except Exception as err:
        print("Error resetting archive sequence counter:", err)
