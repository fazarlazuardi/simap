from django.contrib import admin
from .models import SPPD

@admin.register(SPPD)
class SPPDAdmin(admin.ModelAdmin):
    list_display = ('sppd_number', 'destination', 'departure_date', 'return_date', 'created_by')
    search_fields = ('sppd_number', 'destination')
