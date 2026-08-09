from django.contrib import admin
from .models import Agenda

@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
    list_display = ('title', 'scheduled_at', 'created_by', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'scheduled_at', 'created_at')
    search_fields = ('title', 'description', 'archive__archive_number')
    ordering = ('scheduled_at',)
