from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Employee, SystemSetting, Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('nip', 'full_name', 'position', 'dept_relation', 'phone_number', 'is_active')
    list_filter = ('dept_relation', 'gender', 'is_active')
    search_fields = ('nip', 'full_name', 'email')
    ordering = ('nip',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'employee', 'is_staff', 'is_active_account')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active_account')
    fieldsets = UserAdmin.fieldsets + (
        ('Informasi Tambahan', {'fields': ('role', 'employee', 'is_active_account')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informasi Tambahan', {'fields': ('role', 'employee', 'is_active_account')}),
    )

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
