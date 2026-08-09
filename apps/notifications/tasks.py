from config.celery import app
from django.conf import settings
import requests
from django.utils import timezone
from django.apps import apps


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_wa_message(self, to_number, message, metadata=None):
    """Send a WhatsApp message via configured WA_GATEWAY_URL.

    The task is idempotent on caller side (caller should ensure uniqueness if needed).
    """
    url = getattr(settings, 'WA_GATEWAY_URL', '')
    if not url:
        # No gateway configured; log and exit
        print('WA_GATEWAY_URL not configured; skipping WA send')
        return {'status': 'no_gateway'}

    payload = {
        'to': to_number,
        'message': message,
        'metadata': metadata or {},
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        # Try to return json only if response has json content
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None
        return {'status': 'sent', 'response': resp_json}
    except Exception as e:
        # Let task be retried by Celery retry policy
        print(f'Error sending WA message: {e}')
        raise


@app.task(bind=True)
def create_calendar_event(self, source_type, source_id, title, start_dt, end_dt=None, location=None, attendees=None):
    """Create or update an internal CalendarEvent record.

    source_type: 'sppd'|'surat_tugas'|'agenda'|'archive' etc.
    source_id: PK of the source object
    """
    AgendaApp = apps.get_model('agendas', 'CalendarEvent')
    now = timezone.now()
    # Unique key: source_type + source_id
    key = f"{source_type}:{source_id}"
    try:
        defaults = {
            'title': title,
            'start': start_dt,
            'end': end_dt,
            'location': location,
            'updated_at': now,
        }
        # set FK based on source_type if applicable
        if source_type == 'sppd':
            defaults['sppd_id'] = source_id
        elif source_type == 'surat_tugas':
            defaults['surat_tugas_id'] = source_id
        elif source_type == 'agenda':
            defaults['agenda_id'] = source_id
        elif source_type == 'archive':
            defaults['archive_id'] = source_id

        ev, created = AgendaApp.objects.update_or_create(
            source_key=key,
            defaults=defaults,
        )
        return {'created': created, 'id': ev.pk}
    except Exception as e:
        print('Failed to create calendar event:', e)
        raise
