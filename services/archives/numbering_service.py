from django.db import transaction
from django.utils import timezone
from users.models import SystemSetting


class NumberingService:
    ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

    @staticmethod
    def to_roman(n):
        return NumberingService.ROMAN[n - 1] if 1 <= n <= 12 else str(n)

    @staticmethod
    def get_config(doc_type):
        pattern_key = f'NUMBERING_{doc_type.upper()}_PATTERN'
        digits_key = 'NUMBERING_INDEX_DIGITS'

        defaults = {
            'archive': '{index}/BZ-{type_code}/{month_roman}/{year}',
            'sppd': '{index}/SPPD/{month_roman}/{year}',
            'report': '{index}/LHP/{month_roman}/{year}',
            'disposition': 'DISP-{index}',
            'surat_tugas': '{index}/ST/{month_roman}/{year}',
            'meeting': '{index}/BZ-RPT/{month_roman}/{year}',
        }

        pattern = SystemSetting.get_value(pattern_key) or defaults.get(doc_type, '{index}')
        digits = int(SystemSetting.get_value(digits_key) or '3')

        return {
            'pattern': pattern,
            'index_digits': digits,
        }

    @classmethod
    def resolve_context(cls, doc_type, extra_context=None):
        now = timezone.now()
        context = {
            'year': now.year,
            'month': str(now.month).zfill(2),
            'month_roman': cls.to_roman(now.month),
            'day': str(now.day).zfill(2),
        }
        if extra_context and 'archive_type' in extra_context:
            type_codes = {
                'surat_masuk': 'IN',
                'surat_keluar': 'OUT',
                'proposal': 'PROP',
                'sppd': 'SPPD',
                'dokumen_lainnya': 'DOC',
            }
            context['type_code'] = type_codes.get(extra_context['archive_type'], 'BZ')
        if extra_context:
            context.update(extra_context)
        return context

    @classmethod
    def _get_model_and_field(cls, doc_type):
        """Return (model_class, field_name) for the given doc_type."""
        import archives.models
        import sppd_service.models
        import reports.models
        import dispositions.models
        import surat_tugas.models
        import internal_meetings.models
        mapping = {
            'archive': (archives.models.Archive, 'archive_number'),
            'sppd': (sppd_service.models.SPPD, 'sppd_number'),
            'report': (reports.models.Report, 'report_number'),
            'disposition': (dispositions.models.Disposition, 'disposition_number'),
            'surat_tugas': (surat_tugas.models.SuratTugas, 'nomor_surat'),
            'meeting': (internal_meetings.models.InternalMeeting, 'meeting_number'),
        }
        return mapping.get(doc_type)

    @classmethod
    @transaction.atomic
    def _get_next_index(cls, doc_type, config, extra_filter=None, save=True):
        """Return next index using an atomic SequenceCounter to avoid race conditions.

        Counter key composition:
        - For archives: 'archive:{archive_type}:{year}' if archive_type provided, else 'archive:{year}'
        - For sppd/report: '{doc_type}:{year}'
        - For disposition: 'disposition'
        """
        try:
            from archives.models import get_next_sequence, SequenceCounter
        except Exception:
            # Fallback to existing behavior if import fails
            model_info = cls._get_model_and_field(doc_type)
            if not model_info:
                return 1
            model_class, field_name = model_info
            qs = model_class.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
            if extra_filter:
                qs = qs.filter(**extra_filter)
            last = qs.order_by('-id').first()
            if not last:
                return 1
            try:
                return int(getattr(last, field_name).split('/')[0]) + 1
            except Exception:
                return 1

        now = timezone.now()
        year = now.year
        if doc_type == 'archive' and extra_filter and 'archive_type' in extra_filter:
            key = f'archive:{extra_filter.get("archive_type")}:{year}'
        elif doc_type == 'archive' and isinstance(extra_filter, dict) and extra_filter.get('archive_type'):
            key = f'archive:{extra_filter.get("archive_type")}:{year}'
        elif doc_type == 'disposition':
            key = 'disposition'
        else:
            key = f'{doc_type}:{year}'

        # Cek jika seluruh record pada model terkait kosong (semua arsip/disposisi dihapus admin) -> Reset counter ke 0 otomatis
        model_info = cls._get_model_and_field(doc_type)
        if model_info:
            model_class, field_name = model_info
            qs = model_class.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
            if extra_filter:
                qs = qs.filter(**extra_filter)
            if not qs.exists():
                try:
                    counter = SequenceCounter.objects.filter(name=key).first()
                    if counter and counter.value > 0:
                        counter.value = 0
                        counter.save()
                except Exception:
                    pass

        if save:
            try:
                return get_next_sequence(key)
            except Exception:
                pass
        else:
            counter = SequenceCounter.objects.filter(name=key).first()
            if counter:
                return int(counter.value or 0) + 1
            return 1

        # Fallback to previous last-record logic if counter fails during save.
        model_info = cls._get_model_and_field(doc_type)
        if not model_info:
            return 1
        model_class, field_name = model_info
        qs = model_class.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
        if extra_filter:
            qs = qs.filter(**extra_filter)
        last = qs.order_by('-id').first()
        if not last:
            return 1
        try:
            return int(getattr(last, field_name).split('/')[0]) + 1
        except Exception:
            return 1
    @classmethod
    def generate_number(cls, doc_type, extra_context=None, save=True):
        """
        Generate a number based on config pattern.
        
        doc_type: 'archive', 'sppd', 'report', 'disposition'
        extra_context: dict with additional variables for pattern
        save: if True, persist the index in SystemSetting (fallback)
        
        Returns formatted number string.
        """
        config = cls.get_config(doc_type)
        context = cls.resolve_context(doc_type, extra_context)

        extra_filter = None
        if doc_type == 'archive' and extra_context and 'archive_type' in extra_context:
            extra_filter = {'archive_type': extra_context['archive_type']}

        model_info = cls._get_model_and_field(doc_type)
        model_class = model_info[0] if model_info else None
        field_name = model_info[1] if model_info else None

        new_index = cls._get_next_index(doc_type, config, extra_filter, save=save)
        
        max_tries = 1000
        tries = 0
        while tries < max_tries:
            tries += 1
            context['index'] = str(new_index).zfill(config['index_digits'])

            number = config['pattern']
            for key, val in context.items():
                number = number.replace(f'{{{key}}}', str(val))

            if model_class and field_name:
                try:
                    if model_class.objects.filter(**{field_name: number}).exists():
                        new_index += 1
                        continue
                except Exception:
                    pass

            return number

        return number


    @staticmethod
    def _save_last_index(doc_type, index):
        return

    @classmethod
    def get_default_number(cls, doc_type, extra_context=None):
        """Generate a default number for form pre-fill (no counter saved)."""
        return cls.generate_number(doc_type, extra_context, save=False)
