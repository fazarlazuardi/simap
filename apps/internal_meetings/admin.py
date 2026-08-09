from django.contrib import admin
from .models import InternalMeeting


@admin.register(InternalMeeting)
class InternalMeetingAdmin(admin.ModelAdmin):
    list_display = (
        'meeting_number', 'title', 'meeting_type', 'scheduled_at',
        'location', 'get_pimpinan_display', 'status', 'created_by'
    )
    list_filter = ('meeting_type', 'status', 'scheduled_at', 'created_at')
    search_fields = (
        'meeting_number', 'title', 'location', 'agenda_topics',
        'notulensi_summary', 'notulensi_decision'
    )
    ordering = ('-scheduled_at',)
    filter_horizontal = ('leaders', 'participants')
    readonly_fields = ('meeting_number', 'created_at', 'updated_at')

    fieldsets = (
        ('Informasi Utama Rapat', {
            'fields': (
                'meeting_number', 'title', 'meeting_type', 'scheduled_at',
                'location', 'status', 'created_by'
            )
        }),
        ('Pimpinan & Peserta Rapat', {
            'fields': ('leader', 'leaders', 'participants')
        }),
        ('Agenda & Lampiran', {
            'fields': ('agenda_topics', 'attachment')
        }),
        ('Notulensi & Risalah Rapat', {
            'fields': (
                'notulensi_summary', 'notulensi_decision', 'notulensi_action_items',
                'notulis', 'notulensi_file', 'notulensi_created_at'
            )
        }),
        ('Metadata Sistem', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_pimpinan_display(self, obj):
        return obj.leader_names_display
    get_pimpinan_display.short_description = "Pimpinan Rapat"

    def has_module_permission(self, request):
        return True

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return True

    def has_delete_permission(self, request, obj=None):
        return True
