from django.contrib import admin
from .models import Report

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'title', 'created_by', 'created_at')
    search_fields = ('report_number', 'title')
