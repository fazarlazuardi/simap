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
