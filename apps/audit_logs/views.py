from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import AuditLog

@login_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user').all().order_by('-created_at')
    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(logs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'audit_logs/list.html', {'page_obj': page_obj, 'logs': page_obj})
