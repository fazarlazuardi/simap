from functools import wraps
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def role_required(role_names):
    """
    Decorator for views that checks whether a user has a particular role.
    Superadmin (is_superuser=True) automatically bypasses role checks.
    Also supports active_pov_role from session when Switch POV is active.
    """
    if isinstance(role_names, str):
        role_names = [role_names]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Pengguna tidak terautentikasi.")
            
            # Superadmin bypass
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check session active_pov_role or default user.role
            active_role = request.session.get('active_pov_role', getattr(request.user, 'role', None))
            user_role = getattr(request.user, 'role', None)
            
            if active_role in role_names or user_role in role_names:
                return view_func(request, *args, **kwargs)
            
            raise PermissionDenied("Anda tidak memiliki hak akses ke fitur ini.")
        return _wrapped_view
    return decorator

# Alias untuk backward compatibility
require_role = role_required

def superadmin_required(view_func):
    return role_required(['admin'])(view_func)

def pimpinan_required(view_func):
    return role_required(['pimpinan', 'kabid', 'admin', 'KETUA', 'WAKA'])(view_func)

def sdm_required(view_func):
    return role_required(['staff', 'admin'])(view_func)

def staff_or_kabid_or_pimpinan_required(view_func):
    return role_required(['staff', 'kabid', 'pimpinan', 'admin', 'KETUA', 'WAKA'])(view_func)

