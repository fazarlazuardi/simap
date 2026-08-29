from django.db import models
from django.contrib.auth.models import AbstractUser

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nama Bidang / Bagian")
    # Menangani sub-bagian/bidang yang fleksibel di BAZNAS
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sub_departments', 
        verbose_name="Induk Bidang/Bagian"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI
        verbose_name = "Bidang / Bagian"
        verbose_name_plural = "Bidang / Bagian"
        ordering = ['name']

    def __str__(self): 
        if self.parent:
            return f"{self.parent.name} - {self.name}"
        return self.name

    @property
    def rank_order(self):
        """Menentukan urutan hirarki bidang (Ketua -> Bidang 1 -> Bidang 2 -> Bidang 3 -> Bidang 4)."""
        name_lower = self.name.lower()
        if 'ketua' in name_lower or 'pimpinan' in name_lower:
            return 0
        elif '1' in name_lower or 'i' in name_lower or 'pengumpulan' in name_lower:
            return 1
        elif '2' in name_lower or 'ii' in name_lower or 'pendistribusian' in name_lower or 'pendayagunaan' in name_lower:
            return 2
        elif '3' in name_lower or 'iii' in name_lower or 'perencanaan' in name_lower or 'keuangan' in name_lower:
            return 3
        elif '4' in name_lower or 'iv' in name_lower or 'administrasi' in name_lower or 'sdm' in name_lower or 'umum' in name_lower:
            return 4
        return 5

    @property
    def badge_color_class(self):
        """Menentukan warna badge terang, kontras, dan variatif per bidang."""
        rank = self.rank_order
        if rank == 0:
            return 'bg-success text-white border border-success-subtle shadow-xs fw-bold'
        elif rank == 1:
            return 'bg-primary text-white border border-primary-subtle shadow-xs fw-bold'
        elif rank == 2:
            return 'bg-warning text-dark border border-warning-subtle shadow-xs fw-bold'
        elif rank == 3:
            return 'bg-purple text-white border border-purple-subtle shadow-xs fw-bold'
        elif rank == 4:
            return 'bg-info text-white border border-info-subtle shadow-xs fw-bold'
        return 'bg-secondary text-white'


class Employee(models.Model):
    GENDER_CHOICES = [('L', 'Laki-laki'), ('P', 'Perempuan')]
    
    LEADERSHIP_TYPES = [
        ('ketua', 'Ketua BAZNAS'),
        ('waka_1', 'Wakil Ketua I (Pengumpulan)'),
        ('waka_2', 'Wakil Ketua II (Pendistribusian & Pendayagunaan)'),
        ('waka_3', 'Wakil Ketua III (Perencanaan, Keuangan & Pelaporan)'),
        ('waka_4', 'Wakil Ketua IV (Administrasi, SDM & Umum)'),
        ('none', 'Bukan Pimpinan / Struktur Standar'),
    ]

    nip = models.CharField(max_length=50, unique=True, verbose_name="NIP / NIK")
    full_name = models.CharField(max_length=255, verbose_name="Nama Lengkap & Gelar")
    position = models.CharField(max_length=100, verbose_name="Nama Jabatan (Contoh: Staf Pelaksana Administrasi, SDM dan Umum)")
    
    # Menghubungkan karyawan ke departemen utamanya
    dept_relation = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='employees', 
        verbose_name="Bidang/Bagian Utama"
    )
    
    # Mengakomodasi pimpinan spesifik (Ketua / Waka) untuk routing surat & penandatangan SPPD
    leadership_type = models.CharField(
        max_length=20, 
        choices=LEADERSHIP_TYPES, 
        default='none', 
        verbose_name="Tipe Pimpinan BAZNAS"
    )
    
    # Mengakomodasi dinamika lapangan: Karyawan ditunjuk jadi Pelaksana Tugas (Plt.) di divisi lain
    acting_in_department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='acting_employees', 
        verbose_name="Menjabat Sebagai Plt di Bidang"
    )
    is_acting_role = models.BooleanField(default=False, verbose_name="Status Jabatan Plt Aktif")

    EMPLOYMENT_STATUS_CHOICES = [
        ('amil_tetap', 'Amil Tetap'),
        ('amil_kontrak', 'Amil Kontrak'),
        ('honorer', 'Pegawai Honorer'),
        ('magang', 'Staf Magang / PKL'),
    ]

    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="No. WhatsApp / Telepon")
    email = models.EmailField(blank=True, null=True, verbose_name="Alamat Email")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='L', verbose_name="Jenis Kelamin")

    # Data Diri Pegawai / Amil
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True, verbose_name="Foto Resmi Pasfoto Pegawai")
    nik_ktp = models.CharField(max_length=20, blank=True, null=True, verbose_name="No. NIK KTP (16 Digit)")
    place_of_birth = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tempat Lahir")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Tanggal Lahir")
    address = models.TextField(blank=True, null=True, verbose_name="Alamat Lengkap Tempat Tinggal")
    last_education = models.CharField(max_length=100, blank=True, null=True, verbose_name="Pendidikan Terakhir")

    # Data SK Kepegawaian & Status Amil
    sk_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nomor SK Pengangkatan / SK Amil")
    sk_date = models.DateField(blank=True, null=True, verbose_name="Tanggal Terbit SK")
    tmt_date = models.DateField(blank=True, null=True, verbose_name="TMT (Terhitung Mulai Tanggal) Bergabung")
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_STATUS_CHOICES, default='amil_tetap', verbose_name="Status Kepegawaian")
    sk_file = models.FileField(upload_to='sk_pegawai/', blank=True, null=True, verbose_name="File Berkas SK (PDF/Gambar)")

    is_active = models.BooleanField(default=True, verbose_name="Status Aktif Pegawai")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI
        verbose_name = "Pegawai / Amil"
        verbose_name_plural = "Pegawai / Amil"
        ordering = ['full_name']

    def __str__(self): 
        status = " (Plt)" if self.is_acting_role else ""
        return f"{self.nip} - {self.full_name}{status}"

    @property
    def display_name(self):
        """Mengembalikan nama lengkap pegawai."""
        return self.full_name

    @property
    def avatar_url(self):
        """Mengembalikan URL foto resmi pegawai / amil."""
        if self.photo:
            return self.photo.url
        user = getattr(self, 'user_account', None)
        if user and user.profile_picture:
            return user.profile_picture.url
        name_str = (self.full_name or 'Pegawai BAZNAS').replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={name_str}&background=046C4E&color=fff&size=128&bold=true"

    @property
    def bidang_name(self):
        """Mendapatkan nama Bidang/Bagian pegawai secara cerdas untuk visualisasi & rekap."""
        if self.dept_relation and self.dept_relation.name:
            return self.dept_relation.name.strip()
        
        pos_lower = (self.position or '').lower()
        lead_lower = (self.leadership_type or '').lower()
        combined = f"{pos_lower} {lead_lower}"
        
        if 'ketua' in combined or 'pimpinan' in combined:
            return 'Pimpinan BAZNAS'
        elif any(k in combined for k in ['1', 'i', 'pengumpulan']):
            return 'Bidang I (Pengumpulan)'
        elif any(k in combined for k in ['2', 'ii', 'pendistribusian', 'pendayagunaan']):
            return 'Bidang II (Pendistribusian)'
        elif any(k in combined for k in ['3', 'iii', 'perencanaan', 'keuangan']):
            return 'Bidang III (Perencanaan & Keuangan)'
        elif any(k in combined for k in ['4', 'iv', 'administrasi', 'sdm', 'umum']):
            return 'Bidang IV (Administrasi & SDM)'
        return 'Staf Pelaksana'

    @property
    def bidang_color(self):
        """Mendapatkan kode warna HEX khas per Bidang untuk grafik visual yang variatif & futuristik."""
        b_name = self.bidang_name.lower()
        if any(k in b_name for k in ['ketua', 'pimpinan', 'waka']):
            return '#f43f5e'  # Rose Crimson (Pimpinan BAZNAS)
        if any(k in b_name for k in ['bidang iv', 'bidang 4', 'sdm', 'umum', 'administrasi', 'sekertaris', 'sekretariat', 'sekretaris']):
            return '#06b6d4'  # Electric Cyan (Bidang IV - SDM & Umum)
        if any(k in b_name for k in ['bidang iii', 'bidang 3', 'perencanaan', 'keuangan', 'pelaporan']):
            return '#8b5cf6'  # Purple Violet (Bidang III - Perencanaan & Keuangan)
        if any(k in b_name for k in ['bidang ii', 'bidang 2', 'pendistribusian', 'pendayagunaan', 'bantuan', 'mustahik']):
            return '#f59e0b'  # Amber Gold (Bidang II - Pendistribusian)
        if any(k in b_name for k in ['bidang i', 'bidang 1', 'pengumpulan', 'zakat', 'infaq', 'munfiq']):
            return '#10b981'  # Emerald Cyber (Bidang I - Pengumpulan)
        return '#3b82f6'  # Royal Blue (Default)

    @property
    def phone(self):
        """Property alias untuk phone_number agar notifikasi WA kompatibel di semua modul."""
        return self.phone_number

    @property
    def current_department(self):
        """Mengembalikan departemen aktif (jika sedang jadi Plt, gunakan departemen Plt)."""
        if self.is_acting_role and self.acting_in_department:
            return self.acting_in_department
        return self.dept_relation

    @property
    def department_rank(self):
        """Metode urutan hirarki pegawai: Ketua BAZNAS -> Waka -> Bidang I -> Bidang II -> Bidang III -> Bidang IV."""
        if self.leadership_type == 'ketua':
            return 0
        elif self.leadership_type == 'waka_1':
            return 1
        elif self.leadership_type == 'waka_2':
            return 2
        elif self.leadership_type == 'waka_3':
            return 3
        elif self.leadership_type == 'waka_4':
            return 4
        elif self.dept_relation:
            return 10 + self.dept_relation.rank_order
        return 99

    @property
    def department_badge_class(self):
        """Badge warna terang variatif per bidang/pimpinan."""
        if self.leadership_type == 'ketua':
            return 'bg-emerald text-white border border-emerald-subtle shadow-xs fw-bold'
        elif self.leadership_type == 'waka_1':
            return 'bg-primary text-white border border-primary-subtle shadow-xs fw-bold'
        elif self.leadership_type == 'waka_2':
            return 'bg-warning text-dark border border-warning-subtle shadow-xs fw-bold'
        elif self.leadership_type == 'waka_3':
            return 'bg-purple text-white border border-purple-subtle shadow-xs fw-bold'
        elif self.leadership_type == 'waka_4':
            return 'bg-info text-white border border-info-subtle shadow-xs fw-bold'
        elif self.dept_relation:
            return self.dept_relation.badge_color_class
        return 'bg-secondary text-white'

    @classmethod
    def get_ketua(cls):
        """Helper untuk mendapatkan objek pegawai yang menjabat sebagai Ketua BAZNAS."""
        return cls.objects.filter(leadership_type='ketua', is_active=True).first()

    @classmethod
    def get_waka(cls, waka_type='waka_1'):
        """Helper untuk mendapatkan objek Wakil Ketua BAZNAS spesifik."""
        return cls.objects.filter(leadership_type=waka_type, is_active=True).first()


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Superadmin'),
        ('pimpinan', 'Pimpinan (Ketua/Waka)'),
        ('kabid', 'Kepala Bidang/Bagian'),
        ('staff', 'Staf / Resepsionis'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff', verbose_name="Peran Akun")
    employee = models.OneToOneField(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='user_account',
        verbose_name="Profil Pegawai / Amil"
    )
    is_active_account = models.BooleanField(default=True, verbose_name="Akun Aktif")
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True, verbose_name="Foto Profil")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Terakhir Dilihat / Aktif")

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI

    def __str__(self): 
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_online(self):
        """Mengecek apakah akun user aktif di sistem dalam 60 detik (1 menit) terakhir."""
        from django.core.cache import cache
        from django.utils import timezone
        try:
            last_seen_cache = cache.get(f'user_last_seen_{self.pk}')
            if last_seen_cache:
                return True
        except Exception:
            pass
        if self.last_seen:
            now = timezone.now()
            return (now - self.last_seen).total_seconds() < 60
        return False

    @property
    def last_seen_display(self):
        """Format keterangan waktu presisi status online / offline."""
        from django.utils import timezone
        from django.template.defaultfilters import timesince
        if self.is_online:
            return "Online"
        if self.last_seen:
            return f"Aktif {timesince(self.last_seen)} lalu"
        return "Offline"

    @property
    def avatar_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        emp = getattr(self, 'employee', None)
        if emp and emp.photo:
            return emp.photo.url
        display_name = emp.full_name if (emp and emp.full_name) else (self.get_full_name() or self.username)
        name_str = display_name.replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={name_str}&background=046C4E&color=fff&size=128&bold=true"

    @property
    def display_name(self):
        emp = getattr(self, 'employee', None)
        if emp and emp.full_name:
            return emp.full_name
        return self.get_full_name() or self.username

    @property
    def is_superadmin(self):
        return self.role == 'admin' or self.is_superuser

    @property
    def is_pimpinan(self):
        return self.role == 'pimpinan'

    @property
    def is_ketua(self):
        return self.is_pimpinan and self.employee and self.employee.leadership_type == 'ketua'

    @property
    def is_kabid(self):
        return self.role == 'kabid'

    @property
    def is_staff_biasa(self):
        return self.role == 'staff'

    @property
    def is_waka_2(self):
        return self.is_pimpinan and self.employee and self.employee.leadership_type == 'waka_2'

    @property
    def is_kabid_2(self):
        if not (self.is_kabid and self.employee and self.employee.dept_relation):
            return False
        dept_name = (self.employee.dept_relation.name or "").lower()
        return 'pendistribusian' in dept_name or 'bidang ii' in dept_name or 'bidang 2' in dept_name

    @property
    def is_waka_4(self):
        return self.is_pimpinan and self.employee and self.employee.leadership_type == 'waka_4'

    @property
    def is_kabid_4(self):
        if not (self.is_kabid and self.employee and self.employee.dept_relation):
            return False
        dept_name = (self.employee.dept_relation.name or "").lower()
        return any(k in dept_name for k in ['sekretariat', 'sdm', 'administrasi', 'bidang iv', 'bidang 4'])

    @property
    def is_sdm(self):
        if self.is_waka_4 or self.is_kabid_4:
            return True
        emp = getattr(self, 'employee', None)
        if emp and emp.dept_relation:
            dept_name = (emp.dept_relation.name or "").lower()
            return any(k in dept_name for k in ['sekretariat', 'sdm', 'administrasi', 'front office', 'bidang iv', 'bidang 4'])
        return False

    @property
    def is_fo(self):
        emp = getattr(self, 'employee', None)
        if not emp:
            return False
        pos_lower = (emp.position or "").lower()
        dept_name = (emp.dept_relation.name if emp.dept_relation else "").lower()
        return any(k in pos_lower or k in dept_name for k in ['front office', 'resepsionis', 'fo'])

    @property
    def is_kabid_1(self):
        if not (self.is_kabid and self.employee and self.employee.dept_relation):
            return False
        dept_name = (self.employee.dept_relation.name or "").lower()
        return any(k in dept_name for k in ['pengumpulan', 'bidang i', 'bidang 1'])

    @property
    def is_kabid_3(self):
        if not (self.is_kabid and self.employee and self.employee.dept_relation):
            return False
        dept_name = (self.employee.dept_relation.name or "").lower()
        return any(k in dept_name for k in ['perencanaan', 'keuangan', 'bidang iii', 'bidang 3'])

    def is_dispo_targeted_to_bidang(self, dispo, active_pov=None):
        """
        Mengecek secara KETAT & PRESISI (menggunakan regex word-boundary) apakah
        suatu objek Disposisi telah secara eksplisit diteruskan ke Bidang user.
        """
        if not dispo:
            return False

        emp = getattr(self, 'employee', None)
        lead_type = getattr(emp, 'leadership_type', '') if emp else ''
        pov = str(active_pov or '').lower().strip()

        # Tentukan nomor bidang user (1, 2, 3, atau 4)
        user_bidang = None
        if pov in ['waka_1', 'kabid_1'] or lead_type == 'waka_1' or self.is_kabid_1:
            user_bidang = '1'
        elif pov in ['waka_2', 'kabid_2'] or lead_type == 'waka_2' or self.is_waka_2 or self.is_kabid_2:
            user_bidang = '2'
        elif pov in ['waka_3', 'kabid_3'] or lead_type == 'waka_3' or self.is_kabid_3:
            user_bidang = '3'
        elif pov in ['waka_4', 'kabid_4', 'sdm', 'fo'] or lead_type == 'waka_4' or self.is_waka_4 or self.is_kabid_4 or self.is_sdm or self.is_fo:
            user_bidang = '4'

        if not user_bidang:
            return False

        # Gabungkan daftar penerima dari Ketua (forwarded_to) dan Waka IV (waka_forwarded_to)
        target_emps = list(dispo.forwarded_to.all()) + list(dispo.waka_forwarded_to.all())
        if not target_emps:
            return False

        # Cek apakah user sendiri ada di daftar penerima
        if emp and (emp in target_emps):
            return True

        # Pola Regex Presisi dengan Word Boundary (\b) untuk mencegah 'bidang ii' mencocokkan 'bidang iii'
        patterns = {
            '1': r'\bwaka_1\b|\bkabid_1\b|\bbidang\s*(1|i)\b|\bpengumpulan\b',
            '2': r'\bwaka_2\b|\bkabid_2\b|\bbidang\s*(2|ii)\b|\bpendistribusian\b|\bpendayagunaan\b',
            '3': r'\bwaka_3\b|\bkabid_3\b|\bbidang\s*(3|iii)\b|\bperencanaan\b|\bkeuangan\b',
            '4': r'\bwaka_4\b|\bkabid_4\b|\bbidang\s*(4|iv)\b|\badministrasi\b|\bsdm\b|\bumum\b|\bsekretariat\b'
        }

        pattern = patterns.get(user_bidang)
        if not pattern:
            return False

        import re
        for target_emp in target_emps:
            dept_name = (target_emp.dept_relation.name if target_emp.dept_relation else '').lower()
            pos_dept = f"{target_emp.position or ''} {dept_name} {target_emp.leadership_type or ''}".lower()

            if re.search(pattern, pos_dept):
                return True

        return False

    def get_disposition_permissions(self, active_pov=None, dispo=None):
        """
        Menghitung hak akses Disposisi (Buat, Edit, Hapus) secara presisi & kontekstual.
        - Jika active_pov diset ke 'waka_2', 'waka_1', dll., sistem mensimulasikan persis peran tersebut.
        - Superadmin (tanpa active_pov khusus): Full Access di semua tahap.
        - Ketua BAZNAS: Full Access Tahap 1.
        - Waka IV / Kabid IV / SDM / FO: Full Access Tahap 2 / Pengelolaan Disposisi.
        - Waka I, II, III & Kabid I, II, III:
          * BISA EDIT / TERUSKAN DISPOSISI ke Tim/Kabid HANYA JIKA disposisi DITINJAU/DIDISPOSISIKAN ke Bidang mereka.
          * READ ONLY jika disposisi BUKAN untuk Bidang mereka.
        - Staf / Amil Pelaksana biasa: READ ONLY.
        """
        if not self.is_authenticated:
            return {
                'can_create_dispo': False,
                'can_edit_dispo': False,
                'can_edit_waka_dispo': False,
                'can_delete_dispo': False,
                'is_read_only': True
            }

        pov = str(active_pov or '').lower().strip()

        # 1. Superadmin IT (jika active_pov admin/superadmin atau tanpa active_pov)
        if pov in ['admin', 'superadmin'] or (not pov and self.is_superadmin):
            return {'can_create_dispo': True, 'can_edit_dispo': True, 'can_edit_waka_dispo': True, 'can_delete_dispo': True, 'is_read_only': False}

        # 2. Ketua BAZNAS
        if pov == 'ketua' or (not pov and (self.is_ketua or (getattr(self, 'employee', None) and self.employee.leadership_type == 'ketua'))):
            return {'can_create_dispo': True, 'can_edit_dispo': True, 'can_edit_waka_dispo': False, 'can_delete_dispo': True, 'is_read_only': False}

        # 3. Waka IV / Kabid IV / SDM / FO
        if pov in ['waka_4', 'kabid_4', 'sdm', 'fo'] or (not pov and (self.is_waka_4 or self.is_kabid_4 or self.is_sdm or self.is_fo)):
            return {'can_create_dispo': True, 'can_edit_dispo': True, 'can_edit_waka_dispo': True, 'can_delete_dispo': True, 'is_read_only': False}

        # 4. Waka I, II, III dan Kabid I, II, III (Pengecekan Kontekstual Berdasarkan Target Bidang Disposisi)
        emp = getattr(self, 'employee', None)
        lead_type = getattr(emp, 'leadership_type', '') if emp else ''
        is_waka_or_kabid_123 = (
            pov in ['waka_1', 'waka_2', 'waka_3', 'kabid_1', 'kabid_2', 'kabid_3'] or
            (not pov and (lead_type in ['waka_1', 'waka_2', 'waka_3'] or self.is_waka_2 or self.is_kabid_1 or self.is_kabid_2 or self.is_kabid_3 or self.is_kabid))
        )

        if is_waka_or_kabid_123:
            if dispo:
                is_targeted = self.is_dispo_targeted_to_bidang(dispo, active_pov=active_pov)
                if is_targeted:
                    return {
                        'can_create_dispo': False,
                        'can_edit_dispo': True,
                        'can_edit_waka_dispo': True,
                        'can_delete_dispo': False,
                        'is_read_only': False
                    }

            return {
                'can_create_dispo': False,
                'can_edit_dispo': False,
                'can_edit_waka_dispo': False,
                'can_delete_dispo': False,
                'is_read_only': True
            }

        # Default Staf / Amil
        return {'can_create_dispo': False, 'can_edit_dispo': False, 'can_edit_waka_dispo': False, 'can_delete_dispo': False, 'is_read_only': True}

    @property
    def role_display_badge(self):
        if self.is_superadmin:
            return "Superadmin IT"
        if self.is_ketua:
            return "Ketua BAZNAS"
        if self.is_waka_2:
            return "Waka II (Pendistribusian & Pendayagunaan)"
        if self.is_pimpinan:
            emp = self.employee
            if emp and emp.leadership_type != 'none':
                return f"Pimpinan: {emp.get_leadership_type_display()}"
            return "Pimpinan BAZNAS"
        if self.is_kabid_2:
            return "Kabid II (Pendistribusian & Pendayagunaan)"
        if self.is_kabid:
            dept = self.employee.dept_relation.name if (self.employee and self.employee.dept_relation) else "Bidang"
            return f"Kabid ({dept})"
        return "Amil / Staf Pelaksana"



class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI

    def __str__(self): 
        return self.key

    @classmethod
    def get_value(cls, key, default=None):
        obj = cls.objects.filter(key=key).first()
        return obj.value if obj else default


class AppConfig(models.Model):
    app_name = models.CharField(max_length=255, default='SI-ARSIP SDM BAZNAS')
    app_logo = models.ImageField(upload_to='app_assets/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI

    def __str__(self): 
        return self.app_name

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config