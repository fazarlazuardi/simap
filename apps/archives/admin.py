from django.contrib import admin
from .models import Category, Archive

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Archive)
class ArchiveAdmin(admin.ModelAdmin):
    list_display = ('archive_number', 'title', 'archive_type', 'category', 'uploaded_by', 'status', 'created_at')
    list_filter = ('archive_type', 'category', 'status', 'created_at')
    search_fields = ('archive_number', 'title', 'sender', 'receiver', 'description')  # Diperbaiki di sini
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)