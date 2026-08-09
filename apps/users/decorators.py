from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def role_required(role_names):
    """
    Decorator for views that checks whether a user has a particular role.
    """
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.role in role_names:
            return True
        raise PermissionDenied
    return user_passes_test(check_role)

def superadmin_required(view_func):
    return role_required(['admin'])(view_func)

def pimpinan_required(view_func):
    return role_required(['pimpinan', 'kabid', 'admin'])(view_func)

def sdm_required(view_func):
    return role_required(['staff', 'admin'])(view_func)

def staff_or_kabid_or_pimpinan_required(view_func):
    return role_required(['staff', 'kabid', 'pimpinan', 'admin'])(view_func)
