from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dispositions', '0013_alter_disposition_status'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Hapus field parent (tidak digunakan di workflow baru)
        migrations.RemoveField(
            model_name='disposition',
            name='parent',
        ),
        # Tambah field sender_label
        migrations.AddField(
            model_name='disposition',
            name='sender_label',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Nama Pimpinan Pengirim (Label Cetak)'),
        ),
        # Tambah field disposition_stage
        migrations.AddField(
            model_name='disposition',
            name='disposition_stage',
            field=models.CharField(
                choices=[('ketua', 'Disposisi Ketua'), ('waka_iv', 'Disposisi Waka IV')],
                default='ketua',
                max_length=20,
                verbose_name='Tahap Disposisi',
            ),
        ),
        # Tambah field waka_note
        migrations.AddField(
            model_name='disposition',
            name='waka_note',
            field=models.TextField(blank=True, null=True, verbose_name='Arahan / Catatan Waka IV'),
        ),
        # Tambah field waka_forwarded_to (ManyToMany ke Employee)
        migrations.AddField(
            model_name='disposition',
            name='waka_forwarded_to',
            field=models.ManyToManyField(
                blank=True,
                related_name='waka_received_dispositions',
                to='users.employee',
                verbose_name='Diteruskan Ke (Waka IV → Bidang)',
            ),
        ),
        # Tambah instruksi Waka IV
        migrations.AddField(
            model_name='disposition',
            name='waka_inst_selesaikan',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='disposition',
            name='waka_inst_untuk_diketahui',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='disposition',
            name='waka_inst_laporkan_hasilnya',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='disposition',
            name='waka_inst_koordinasikan',
            field=models.BooleanField(default=False),
        ),
        # Update STATUS_CHOICES dan max_length status
        migrations.AlterField(
            model_name='disposition',
            name='status',
            field=models.CharField(
                choices=[
                    ('baru', 'Menunggu Disposisi Ketua'),
                    ('didisposisi_ketua', 'Sudah Disposisi Ketua — Menunggu Waka IV'),
                    ('proses', 'Sedang Diproses Bidang'),
                    ('selesai', 'Selesai'),
                ],
                default='baru',
                max_length=30,
            ),
        ),
    ]
