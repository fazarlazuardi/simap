from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_alter_user_role_delete_role'),
        ('dispositions', '0006_disposition_disposition_number'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='disposition',
            name='forwarded_to',
        ),
        migrations.AddField(
            model_name='disposition',
            name='forwarded_to',
            field=models.ManyToManyField(related_name='received_dispositions', to='users.employee'),
        ),
    ]
