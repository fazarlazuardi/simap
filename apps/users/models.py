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

    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="No. WhatsApp / Telepon")
    email = models.EmailField(blank=True, null=True, verbose_name="Alamat Email")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='L', verbose_name="Jenis Kelamin")
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
    def phone(self):
        """Property alias untuk phone_number agar notifikasi WA kompatibel di semua modul."""
        return self.phone_number

    @property
    def current_department(self):
        """Mengembalikan departemen aktif (jika sedang jadi Plt, gunakan departemen Plt)."""
        if self.is_acting_role and self.acting_in_department:
            return self.acting_in_department
        return self.dept_relation

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

    class Meta:
        app_label = 'users'  # <--- WAJIB DITAMBAHKAN DI SINI

    def __str__(self): 
        return f"{self.username} ({self.get_role_display()})"

    @property
    def avatar_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        name_str = (self.get_full_name() or self.username).replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={name_str}&background=046C4E&color=fff&size=128&bold=true"


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