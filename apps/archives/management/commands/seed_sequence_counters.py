from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from archives.models import SequenceCounter, Archive
from dispositions.models import Disposition
from sppd_service.models import SPPD
from django.apps import apps
import re


def parse_archive_number(number):
    # Expected formats like 001/BZ-IN/II/2026 or 001/BZ-PROP/II/2026
    if not number:
        return None
    match = re.match(r'^(?P<seq>\d+)/(?:[^/]+)/(?:[^/]+)/(?P<year>\d{4})$', number)
    if not match:
        return None
    return int(match.group('seq')), int(match.group('year'))


def parse_disposition_number(number):
    if not number:
        return None
    match = re.match(r'^DISP-(?P<seq>\d+)$', number)
    if not match:
        return None
    return int(match.group('seq'))


def parse_sppd_number(number):
    # Expected formats like 001/SPPD/II/2026
    if not number:
        return None
    match = re.match(r'^(?P<seq>\d+)/(?:[^/]+)/(?:[^/]+)/(?P<year>\d{4})$', number)
    if not match:
        return None
    return int(match.group('seq')), int(match.group('year'))


class Command(BaseCommand):
    help = 'Seed SequenceCounter values from existing archive, disposition, and SPPD data.'

    def handle(self, *args, **options):
        self.stdout.write('Starting SequenceCounter seeding...')

        existing_archive_types = set([choice[0] for choice in Archive.TYPE_CHOICES])
        current_year = timezone.now().year
        archive_counters = {}
        disposition_max = 0
        sppd_counters = {}

        # Seed archive counters by archive_type and year
        for archive in Archive.objects.exclude(archive_number__isnull=True).exclude(archive_number=''):
            parsed = parse_archive_number(archive.archive_number)
            if not parsed:
                continue
            seq, year = parsed
            key = f'archive:{archive.archive_type}:{year}' if archive.archive_type else f'archive:{year}'
            archive_counters[key] = max(archive_counters.get(key, 0), seq)

        # Seed disposition counters
        for dispo in Disposition.objects.exclude(disposition_number__isnull=True).exclude(disposition_number=''):
            parsed = parse_disposition_number(dispo.disposition_number)
            if not parsed:
                continue
            disposition_max = max(disposition_max, parsed)

        # Seed SPPD counters
        for sppd in SPPD.objects.exclude(sppd_number__isnull=True).exclude(sppd_number=''):
            parsed = parse_sppd_number(sppd.sppd_number)
            if not parsed:
                continue
            seq, year = parsed
            key = f'sppd:{year}'
            sppd_counters[key] = max(sppd_counters.get(key, 0), seq)

        with transaction.atomic():
            for key, value in archive_counters.items():
                counter, created = SequenceCounter.objects.get_or_create(name=key)
                if value > counter.value:
                    counter.value = value
                    counter.save(update_fields=['value', 'updated_at'])
                self.stdout.write(f'Archive counter {key} set to {counter.value} (created={created})')

            if disposition_max > 0:
                counter, created = SequenceCounter.objects.get_or_create(name='disposition')
                if disposition_max > counter.value:
                    counter.value = disposition_max
                    counter.save(update_fields=['value', 'updated_at'])
                self.stdout.write(f'Disposition counter disposition set to {counter.value} (created={created})')
            else:
                self.stdout.write('No existing disposition numbers found to seed.')

            for key, value in sppd_counters.items():
                counter, created = SequenceCounter.objects.get_or_create(name=key)
                if value > counter.value:
                    counter.value = value
                    counter.save(update_fields=['value', 'updated_at'])
                self.stdout.write(f'SPPD counter {key} set to {counter.value} (created={created})')

        self.stdout.write('SequenceCounter seeding complete.')
