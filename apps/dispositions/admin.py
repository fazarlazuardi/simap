from django.contrib import admin
from .models import Disposition

@admin.register(Disposition)
class DispositionAdmin(admin.ModelAdmin):
    list_display = ('archive', 'sender', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('archive__title', 'archive__archive_number', 'note')
    ordering = ('-created_at',)
