import datetime
import logging
from django import forms
from django.utils import timezone
from .models import SuratTugas, Disposition
from users.models import Employee
from services.integrations.gateway_service import WhatsAppService

logger = logging.getLogger(__name__)

from django.db.models import Q

BIDANG2_PIMPINAN_CHOICES = [
    ("Drs. Achmad Nawawi, M.Si|Ketua BAZNAS", "Drs. Achmad Nawawi, M.Si (Ketua BAZNAS)"),
    ("Andi Irawan, S.Pd.I, M.Pd|Wakil Ketua II", "Andi Irawan, S.Pd.I, M.Pd (Wakil Ketua II - Pendistribusian & Pendayagunaan)"),
]

PIMPINAN_CHOICES = [
    ("Drs. Achmad Nawawi, M.Si|Ketua BAZNAS", "Drs. Achmad Nawawi, M.Si (Ketua BAZNAS)"),
    ("Haris Syarif Mansyur, S.H, M.H|Wakil Ketua I", "Haris Syarif Mansyur, S.H, M.H (Wakil Ketua I - Pengumpulan)"),
    ("Andi Irawan, S.Pd.I, M.Pd|Wakil Ketua II", "Andi Irawan, S.Pd.I, M.Pd (Wakil Ketua II - Pendistribusian & Pendayagunaan)"),
    ("H. Supriyadinata, M.Si|Wakil Ketua III", "H. Supriyadinata, M.Si (Wakil Ketua III - Perencanaan, Keuangan, & Pelaporan)"),
    ("Haetami, S.Sos.I|Wakil Ketua IV", "Haetami, S.Sos.I (Wakil Ketua IV - Administrasi, Umum, & SDM)"),
]

HARI_CHOICES = [
    ("", "-- Pilih Hari Kegiatan --"),
    ("Senin", "Senin"),
    ("Selasa", "Selasa"),
    ("Rabu", "Rabu"),
    ("Kamis", "Kamis"),
    ("Jumat", "Jumat"),
    ("Sabtu", "Sabtu"),
    ("Minggu", "Minggu"),
    ("Senin s.d. Selasa", "Senin s.d. Selasa"),
    ("Senin s.d. Rabu", "Senin s.d. Rabu"),
    ("Senin s.d. Kamis", "Senin s.d. Kamis"),
    ("Senin s.d. Jumat", "Senin s.d. Jumat"),
    ("Senin s.d. Sabtu", "Senin s.d. Sabtu"),
    ("Selasa s.d. Rabu", "Selasa s.d. Rabu"),
    ("Selasa s.d. Kamis", "Selasa s.d. Kamis"),
    ("Selasa s.d. Jumat", "Selasa s.d. Jumat"),
    ("Rabu s.d. Kamis", "Rabu s.d. Kamis"),
    ("Rabu s.d. Jumat", "Rabu s.d. Jumat"),
    ("Kamis s.d. Jumat", "Kamis s.d. Jumat"),
    ("custom", "-- Ketik Kustom / Manual --"),
]

class SuratTugasForm(forms.ModelForm):
    pilihan_penandatangan = forms.ChoiceField(
        choices=PIMPINAN_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select shadow-sm fw-bold text-success', 'id': 'id_pilihan_penandatangan'}),
        label="Pejabat Penandatangan"
    )

    class Meta:
        model = SuratTugas
        fields = [
            'nomor_surat', 'tentang', 'hari_kegiatan', 'tanggal_mulai',
            'lokasi_tujuan', 'disposition', 'pegawai_ditugaskan',
            'pilihan_penandatangan',
        ]
        widgets = {
            'nomor_surat': forms.TextInput(attrs={
                'class': 'form-control shadow-sm bg-light', 
                'readonly': 'readonly',  
                'placeholder': 'Otomatis digenerate oleh sistem'
            }),
            'tentang': forms.Textarea(attrs={'class': 'form-control shadow-sm', 'rows': 3, 'placeholder': 'Masukkan perihal atau tujuan penugasan...'}),
            'hari_kegiatan': forms.Select(choices=HARI_CHOICES, attrs={'class': 'form-select shadow-sm', 'id': 'id_hari_kegiatan'}),
            'tanggal_mulai': forms.DateInput(attrs={'class': 'form-control shadow-sm', 'type': 'date', 'id': 'id_tanggal_mulai'}),
            'lokasi_tujuan': forms.TextInput(attrs={'class': 'form-control shadow-sm', 'placeholder': 'Masukkan lokasi tujuan penugasan'}),
            'disposition': forms.Select(attrs={'class': 'form-select shadow-sm'}),
            'pegawai_ditugaskan': forms.SelectMultiple(attrs={'class': 'form-select select2-employee', 'data-placeholder': 'Ketik nama, jabatan, atau bidang pegawai...'}),
        }

    def clean_hari_kegiatan(self):
        hari = self.cleaned_data.get('hari_kegiatan')
        custom = self.data.get('hari_kegiatan_custom', '').strip()
        if hari == 'custom' and custom:
            return custom
        return hari

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        is_waka_or_kabid_2 = False
        is_survei = False
        if request:
            active_pov = request.session.get('active_pov')
            st_type = (request.GET.get('st_type', '') or request.POST.get('st_type', '')).strip().lower()
            if st_type == 'survei' or (request.GET.get('tentang') and 'survei' in request.GET.get('tentang').lower()):
                is_survei = True

            if active_pov in ['waka_2', 'kabid_2']:
                is_waka_or_kabid_2 = True
            elif request.user and (getattr(request.user, 'is_waka_2', False) or getattr(request.user, 'is_kabid_2', False)):
                is_waka_or_kabid_2 = True

        if (is_waka_or_kabid_2 or is_survei) and 'pilihan_penandatangan' in self.fields:
            self.fields['pilihan_penandatangan'].choices = BIDANG2_PIMPINAN_CHOICES

        if not self.instance.pk and 'nomor_surat' in self.fields:
            now = datetime.datetime.now()
            tahun_ini = now.year
            romawi_bulan = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
            bulan_romawi = romawi_bulan[now.month]
            
            last_st = SuratTugas.objects.filter(created_at__year=tahun_ini).order_by('-id').first()
            surat_ke = (int(last_st.nomor_surat.split('/')[1]) + 1) if (last_st and last_st.nomor_surat and len(last_st.nomor_surat.split('/')) >= 2 and last_st.nomor_surat.split('/')[1].isdigit()) else (SuratTugas.objects.filter(created_at__year=tahun_ini).count() + 1)
            
            self.initial['nomor_surat'] = f"ST/{str(surat_ke).zfill(3)}/BAZNAS-TGN/{bulan_romawi}/{tahun_ini}"

        if 'pegawai_ditugaskan' in self.fields:
            if is_waka_or_kabid_2 or is_survei:
                b2_qs = Employee.objects.filter(
                    Q(dept_relation__name__icontains='pendistribusian') |
                    Q(dept_relation__name__icontains='bidang ii:') |
                    Q(dept_relation__name__startswith='Bidang II')
                ).exclude(
                    dept_relation__name__icontains='bidang iii'
                ).select_related('dept_relation').order_by('full_name')
                self.fields['pegawai_ditugaskan'].queryset = b2_qs
            else:
                self.fields['pegawai_ditugaskan'].queryset = Employee.objects.all().select_related('dept_relation').order_by('full_name')

            self.fields['pegawai_ditugaskan'].required = False
            self.fields['pegawai_ditugaskan'].label_from_instance = lambda obj: (
                f"{obj.full_name} — {getattr(obj, 'position', 'Amil')} "
                f"({getattr(obj.dept_relation, 'name', 'Tanpa Bidang')})"
            )

        if 'disposition' in self.fields:
            initial_dispo = kwargs.get('initial', {}).get('disposition') or getattr(self.instance, 'disposition', None)
            valid_qs = Disposition.objects.exclude(archive__status__in=['selesai', 'ditolak']).exclude(status='selesai')
            if initial_dispo:
                dispo_pk = initial_dispo.pk if hasattr(initial_dispo, 'pk') else initial_dispo
                valid_qs = valid_qs | Disposition.objects.filter(pk=dispo_pk)

            self.fields['disposition'].queryset = valid_qs.select_related('archive', 'sender').order_by('-id').distinct()
            self.fields['disposition'].required = False
            if initial_dispo:
                self.fields['disposition'].initial = initial_dispo
            
            def get_disposition_perihal(obj):
                num_str = obj.disposition_number or f"DISP-{obj.pk:03d}"
                perihal_val = None
                try:
                    archive_obj = getattr(obj, 'archive', None)
                    if archive_obj:
                        perihal_val = (
                            getattr(archive_obj, 'title', None) or
                            getattr(archive_obj, 'subject', None) or
                            getattr(archive_obj, 'perihal', None) or
                            getattr(archive_obj, 'judul', None)
                        )
                except Exception:
                    pass

                if not perihal_val:
                    perihal_val = (
                        getattr(obj, 'note', None) or
                        getattr(obj, 'perihal', None) or
                        getattr(obj, 'subject', None)
                    )

                text_display = perihal_val[:60] if perihal_val else f"Disposisi {num_str}"
                return f"{num_str} — {text_display}"

            self.fields['disposition'].label_from_instance = get_disposition_perihal

        if self.instance and self.instance.pk:
            combined = f"{self.instance.pejabat_penandatangan}|{self.instance.jabatan_penandatangan}"
            if combined in [c[0] for c in PIMPINAN_CHOICES]:
                self.initial['pilihan_penandatangan'] = combined

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if not instance.tanggal_mulai:
            instance.tanggal_mulai = timezone.now().date()

        if not instance.nomor_surat:
            now = datetime.datetime.now()
            tahun_ini = now.year
            romawi_bulan = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
            bulan_romawi = romawi_bulan[now.month]
            
            last_st = SuratTugas.objects.filter(created_at__year=tahun_ini).order_by('-id').first()
            surat_ke = (int(last_st.nomor_surat.split('/')[1]) + 1) if (last_st and last_st.nomor_surat and len(last_st.nomor_surat.split('/')) >= 2 and last_st.nomor_surat.split('/')[1].isdigit()) else (SuratTugas.objects.filter(created_at__year=tahun_ini).count() + 1)
            instance.nomor_surat = f"ST/{str(surat_ke).zfill(3)}/BAZNAS-TGN/{bulan_romawi}/{tahun_ini}"

        pilihan = self.cleaned_data.get('pilihan_penandatangan')
        if pilihan and '|' in pilihan:
            nama, jabatan = pilihan.split('|', 1)
            instance.pejabat_penandatangan = nama.strip()
            instance.jabatan_penandatangan = jabatan.strip()
        else:
            instance.pejabat_penandatangan = "Drs. Achmad Nawawi, M.Si"
            instance.jabatan_penandatangan = "Ketua BAZNAS"

        instance.save()
        self.save_m2m()

        tanggal_format = instance.tanggal_mulai.strftime('%d-%m-%Y') if instance.tanggal_mulai else '-'
        
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"   📋 *SURAT TUGAS BARU*\n"
            f"   BAZNAS Kab. Tangerang\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📄 *Perihal:* {instance.tentang}\n"
            f"🔢 *No. Surat:* {instance.nomor_surat}\n"
            f"👤 *Pejabat Pemberi:* {instance.pejabat_penandatangan} ({instance.jabatan_penandatangan})\n"
            f"📅 *Tanggal:* {tanggal_format} ({instance.hari_kegiatan or '-'})\n"
            f"📍 *Lokasi Tujuan:* {instance.lokasi_tujuan}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Silakan login ke sistem untuk melihat detail dan mencetak surat."
        )

        for emp in instance.pegawai_ditugaskan.all():
            try:
                user_target = getattr(emp, 'user_account', None)
                WhatsAppService.send_notification(
                    user=user_target,
                    message=msg,
                    employee=emp,
                    category='surat_tugas',
                    title="Surat Tugas Baru"
                )
            except Exception as e:
                logger.error(f"Gagal mengirim notifikasi WA Surat Tugas ke {emp}: {str(e)}")

        # Kirim notifikasi WA & Web Dashboard ke Front Office (FO), Kabid IV, dan Superadmin
        try:
            from users.models import User
            from notifications.models import Notification
            from django.db.models import Q
            
            creator_name = self.request.user.username if hasattr(self, 'request') and self.request and self.request.user else 'Sistem'
            
            fo_kabid4_superadmin_users = User.objects.filter(
                Q(username__in=['fo', 'kabid4', 'admin', 'fajarl']) |
                Q(role='admin') |
                Q(is_superuser=True) |
                Q(employee__position__icontains='front office') |
                Q(employee__position__icontains='kabid iv') |
                Q(employee__position__icontains='kabid 4')
            ).distinct()
            
            msg_fo_kabid4 = (
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"   📋 *SURAT TUGAS BARU (PERLU SPPD)*\n"
                f"   BAZNAS Kab. Tangerang\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📄 *Perihal:* {instance.tentang}\n"
                f"🔢 *No. Surat:* {instance.nomor_surat}\n"
                f"👤 *Dibuat Oleh:* {creator_name}\n"
                f"✍️ *Penandatangan:* {instance.pejabat_penandatangan}\n"
                f"📅 *Tanggal:* {tanggal_format}\n"
                f"📍 *Lokasi:* {instance.lokasi_tujuan}\n\n"
                f"📌 *Pemberitahuan Bidang IV & FO:*\n"
                f"Surat Tugas ini telah diterbitkan dan memerlukan proses penanganan SPPD di sistem SIMAP BAZNAS.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Silakan login ke sistem SIMAP untuk memproses SPPD."
            )
            
            for f_user in fo_kabid4_superadmin_users:
                # Kirim WA Gateway
                WhatsAppService.send_notification(
                    user=f_user,
                    message=msg_fo_kabid4,
                    employee=getattr(f_user, 'employee', None),
                    category='surat_tugas',
                    title="Surat Tugas Baru Perlu SPPD"
                )
                # Kirim Notifikasi Web Dashboard (Lonceng)
                if not Notification.objects.filter(user=f_user, link_url=f"/surat-tugas/{instance.pk}/", status='unread').exists():
                    Notification.create_system_notif(
                        user=f_user,
                        title="📋 Surat Tugas Baru (Siap SPPD)",
                        message=f"Surat Tugas '{instance.nomor_surat}' ({instance.tentang}) diterbitkan. Siap diproses SPPD oleh FO & Bidang IV.",
                        link_url=f"/surat-tugas/{instance.pk}/",
                        category="sppd"
                    )
        except Exception as e:
            logger.error(f"Gagal mengirim notifikasi WA/Web Surat Tugas ke FO/Kabid4/Superadmin: {str(e)}")

        return instance