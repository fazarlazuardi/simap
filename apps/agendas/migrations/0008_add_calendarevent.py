# Generated manually: add CalendarEvent model
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('agendas', '0007_alter_agenda_options_agenda_assigned_employees_and_more'),
        ('archives', '0013_documentworkflow_workflow_workflowstep_and_more'),
        ('surat_tugas', '0001_initial'),
        ('sppd_service', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_key', models.CharField(max_length=200, unique=True, help_text="Unique key like 'sppd:123' or 'agenda:45'")),
                ('title', models.CharField(max_length=255)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('external_event_id', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(default='scheduled', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('archive', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calendar_events', to='archives.archive')),
                ('surat_tugas', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calendar_events', to='surat_tugas.surattugas')),
                ('sppd', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calendar_events', to='sppd_service.sppd')),
                ('agenda', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calendar_events', to='agendas.agenda')),
            ],
            options={
                'verbose_name': 'Calendar Event',
                'verbose_name_plural': 'Calendar Events',
            },
        ),
    ]
