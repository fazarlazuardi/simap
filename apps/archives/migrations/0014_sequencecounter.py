# Generated manually: create SequenceCounter for atomic numbering
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0013_documentworkflow_workflow_workflowstep_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SequenceCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('value', models.BigIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Sequence Counter',
                'verbose_name_plural': 'Sequence Counters',
            },
        ),
    ]
