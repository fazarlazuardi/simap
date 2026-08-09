from django.contrib import admin
from .models import SuratTugas
from .forms import SuratTugasForm  # Impor form yang baru dibuat

@admin.register(SuratTugas)
class SuratTugasAdmin(admin.ModelAdmin):
    form = SuratTugasForm  # Masukkan form custom di sini
    
    list_display = (
        'nomor_surat_display', 
        'tentang_truncated', 
        'tanggal_mulai', 
        'lokasi_tujuan', 
        'created_at'
    )
    list_filter = ('tanggal_mulai', 'created_at')
    search_fields = ('nomor_surat', 'tentang', 'lokasi_tujuan')
    filter_horizontal = ('pegawai_ditugaskan',)
    autocomplete_fields = ('disposition', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Informasi Surat', {
            'fields': ('nomor_surat', 'tentang', 'disposition')
        }),
        ('Waktu & Tempat', {
            'fields': ('hari_kegiatan', 'tanggal_mulai', 'lokasi_tujuan')
        }),
        ('Pegawai & Penandatangan', {
            'fields': ('pegawai_ditugaskan', 'pilihan_penandatangan', 'pejabat_penandatangan', 'jabatan_penandatangan')
        }),
        ('Metadata Sistem', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def nomor_surat_display(self, obj):
        return obj.nomor_surat or "(Draft)"
    nomor_surat_display.short_description = 'Nomor Surat'

    def tentang_truncated(self, obj):
        return obj.tentang[:50] + "..." if len(obj.tentang) > 50 else obj.tentang
    tentang_truncated.short_description = 'Tentang'

    def delete_model(self, request, obj):
        try:
            from sppd_service.models import SPPD
            SPPD.objects.filter(surat_tugas=obj).update(surat_tugas=None)
        except Exception:
            pass
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        try:
            from sppd_service.models import SPPD
            SPPD.objects.filter(surat_tugas__in=queryset).update(surat_tugas=None)
        except Exception:
            pass
        super().delete_queryset(request, queryset)