"""
URL configuration for SIMAP project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('users:dashboard'), name='root_redirect'),
    path('admin/', admin.site.urls),
    
    path('auth/', include('authentication.urls')),
    path('users/', include('users.urls')),
    path('archives/', include('archives.urls')),
    path('dispositions/', include('dispositions.urls')),
    path('agendas/', include('agendas.urls')),
    path('notifications/', include('notifications.urls')),
    path('reports/', include('reports.urls')),
    path('audit/', include('audit_logs.urls')),
    path('sppd/', include('sppd_service.urls')),
    path('surat-tugas/', include('surat_tugas.urls', namespace='surat_tugas')),
    path('rapat-internal/', include('internal_meetings.urls', namespace='internal_meetings')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
