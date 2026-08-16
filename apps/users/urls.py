from django.urls import path
from . import views
from . import employee_views

app_name = 'users'

urlpatterns = [
    path('dashboard/', views.dashboard_index, name='dashboard'),
    path('switch-pov/', views.switch_pov, name='switch_pov'),
    path('profile/', views.profile_view, name='profile'),
    path('app-settings/', views.app_settings_view, name='app_settings'),
    
    # Department & Category Management
    path('app-settings/department/create/', views.department_create, name='department_create'),
    path('app-settings/department/<int:pk>/delete/', views.department_delete, name='department_delete'),
    path('app-settings/category/create/', views.category_create, name='category_create'),
    path('app-settings/category/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('app-settings/category/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('app-settings/test-email-connection/', views.test_email_connection, name='test_email_connection'),
    
    path('management/', views.user_list, name='list'),
    path('management/create/', views.user_create, name='create'),
    path('management/<int:pk>/edit/', views.user_edit, name='edit'),
    path('management/<int:pk>/delete/', views.user_delete, name='delete'),
    
    # Employee Management
    path('employees/', employee_views.employee_list, name='employee_list'),
    path('employees/master/', employee_views.employee_master, name='employee_master'),
    path('employees/create/', employee_views.employee_create, name='employee_create'),
    path('employees/<int:pk>/edit/', employee_views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', employee_views.employee_delete, name='employee_delete'),
    path('employees/<int:pk>/detail/', employee_views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit-master/', employee_views.employee_edit_master, name='employee_edit_master'),
    path('employees/<int:emp_pk>/create-user/', employee_views.employee_create_user, name='employee_create_user'),
    path('employees/<int:emp_pk>/delete-user/', employee_views.employee_delete_user, name='employee_delete_user'),
    path('employees/<int:pk>/position-json/', views.employee_position_json, name='employee_position_json'),
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
    path('wa-health/', views.wa_health_check, name='wa_health'),
]
