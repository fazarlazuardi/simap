from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Employee, User, Department
from .decorators import superadmin_required


def is_pure_superadmin(request):
    if not request.user.is_authenticated:
        return False
    if request.session.get('active_pov'):
        return False
    return getattr(request.user, 'is_superuser', False) or getattr(request.user, 'is_superadmin', False)


@login_required
def employee_master(request):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak mengelola data pegawai.")
        return redirect('users:employee_list')
    employees = Employee.objects.select_related('dept_relation').all().order_by('-created_at')
    users = {
        u.employee_id: u 
        for u in User.objects.filter(employee__isnull=False).select_related('employee')
    }
    
    per_page = int(request.GET.get('per_page', 10))
    paginator = Paginator(employees, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    departments = sorted(Department.objects.all(), key=lambda d: d.rank_order)
    roles = User.ROLE_CHOICES

    return render(request, 'users/employee_master.html', {
        'page_obj': page_obj,
        'employee_list': employee_list,
        'departments': departments,
        'roles': roles,
    })


@login_required
def employee_create_user(request, emp_pk):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak membuat akun.")
        return redirect('users:employee_list')
    emp = get_object_or_404(Employee, pk=emp_pk)
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        role = request.POST.get('role')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' sudah digunakan.")
        else:
            user = User.objects.create_user(username=username, password=password, role=role)
            user.employee = emp
            user.save()
            messages.success(request, f"Akun '{username}' berhasil dibuat untuk {emp.full_name}.")
            
        return redirect(request.META.get('HTTP_REFERER') or 'users:employee_master')
        
    return redirect('users:employee_master')


@login_required
def employee_delete_user(request, emp_pk):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak menghapus akun.")
        return redirect('users:employee_list')
    emp = get_object_or_404(Employee, pk=emp_pk)
    user = User.objects.filter(employee=emp).first()
    
    if request.method == 'POST' and user:
        username = user.username
        user.delete()
        messages.success(request, f"Akun '{username}' berhasil dihapus dari {emp.full_name}.")
        
    return redirect('users:employee_detail', pk=emp.pk)


@login_required
def employee_detail(request, pk):
    emp = get_object_or_404(Employee.objects.select_related('dept_relation'), pk=pk)
    user = User.objects.filter(employee=emp).first()
    roles = User.ROLE_CHOICES

    return render(request, 'users/employee_detail.html', {
        'employee': emp,
        'user_account': user,
        'roles': roles,
    })


@login_required
def employee_edit_master(request, pk):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak mengedit data pegawai.")
        return redirect('users:employee_list')
    emp = get_object_or_404(Employee, pk=pk)
    user = User.objects.filter(employee=emp).first()
    departments = Department.objects.all()
    roles = User.ROLE_CHOICES

    if request.method == 'POST':
        nip = request.POST.get('nip', '').strip()
        
        # Validasi NIP unik
        if Employee.objects.filter(nip=nip).exclude(pk=emp.pk).exists():
            messages.error(request, f"NIP/NIK '{nip}' sudah digunakan oleh pegawai lain.")
            return redirect('users:employee_edit_master', pk=emp.pk)

        emp.nip = nip
        emp.full_name = request.POST.get('full_name', '').strip()
        emp.position = request.POST.get('position', '').strip()
        
        dept_id = request.POST.get('dept_relation')
        emp.dept_relation = Department.objects.get(id=dept_id) if dept_id else None
        
        emp.phone_number = request.POST.get('phone_number', '').strip()
        emp.email = request.POST.get('email', '').strip()
        emp.gender = request.POST.get('gender')

        # Data Diri Pegawai
        if request.FILES.get('photo'):
            emp.photo = request.FILES.get('photo')
        emp.nik_ktp = request.POST.get('nik_ktp', '').strip()
        emp.place_of_birth = request.POST.get('place_of_birth', '').strip()
        emp.date_of_birth = request.POST.get('date_of_birth') or None
        emp.address = request.POST.get('address', '').strip()
        emp.last_education = request.POST.get('last_education', '').strip()

        # Data SK Kepegawaian
        emp.sk_number = request.POST.get('sk_number', '').strip()
        emp.sk_date = request.POST.get('sk_date') or None
        emp.tmt_date = request.POST.get('tmt_date') or None
        emp.employment_status = request.POST.get('employment_status', 'amil_tetap')
        if request.FILES.get('sk_file'):
            emp.sk_file = request.FILES.get('sk_file')

        emp.is_active = request.POST.get('is_active') == 'on'
        emp.save()

        if user:
            new_username = request.POST.get('username', '').strip()
            
            # Validasi Username Unik jika diubah
            if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                messages.error(request, f"Username '{new_username}' sudah digunakan oleh akun lain.")
                return redirect('users:employee_edit_master', pk=emp.pk)
                
            user.username = new_username
            user.email = request.POST.get('email', '').strip()
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.role = request.POST.get('role')
            
            new_password = request.POST.get('password')
            if new_password:
                user.set_password(new_password)
                
            user.is_active_account = request.POST.get('is_active_account') == 'on'
            user.save()

        messages.success(request, f"Data {emp.full_name} berhasil diperbarui.")
        return redirect('users:employee_detail', pk=emp.pk)

    return render(request, 'users/employee_edit_master.html', {
        'employee': emp,
        'user_account': user,
        'departments': departments,
        'roles': roles,
    })


@login_required
def employee_list(request):
    from django.db.models import Q
    bidang = request.GET.get('bidang')
    akun = request.GET.get('akun')
    query = request.GET.get('q', '').strip()

    all_employees = Employee.objects.select_related('dept_relation').all().order_by('-created_at')

    # Total KPI Counters
    total_employees = all_employees.count()
    active_employees = all_employees.filter(is_active=True).count()
    user_emp_ids = set(User.objects.filter(employee__isnull=False).values_list('employee_id', flat=True))
    with_account_count = len(user_emp_ids)
    without_account_count = total_employees - with_account_count

    employees = all_employees

    if query:
        employees = employees.filter(
            Q(nip__icontains=query) |
            Q(full_name__icontains=query) |
            Q(position__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query)
        )

    if bidang:
        employees = employees.filter(dept_relation__id=bidang)
        
    if akun == 'ya':
        employees = employees.filter(pk__in=user_emp_ids)
    elif akun == 'tidak':
        employees = employees.exclude(pk__in=user_emp_ids)

    departments = sorted(Department.objects.all(), key=lambda d: d.rank_order)
    users_map = {
        u.employee_id: u 
        for u in User.objects.filter(employee__isnull=False).select_related('employee')
    }
    
    per_page = int(request.GET.get('per_page', 10))
    paginator = Paginator(employees, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    employee_list_ctx = [(emp, users_map.get(emp.pk)) for emp in page_obj]
    
    return render(request, 'users/employee_list.html', {
        'page_obj': page_obj,
        'employee_list': employee_list_ctx,
        'departments': departments,
        'roles': User.ROLE_CHOICES,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'with_account_count': with_account_count,
        'without_account_count': without_account_count,
        'query': query,
        'filters': {
            'bidang': bidang or '',
            'akun': akun or '',
        },
    })


@login_required
def employee_create(request):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak menambah data pegawai.")
        return redirect('users:employee_list')
    departments = Department.objects.all()
    form_data = {}

    if request.method == 'POST':
        nip = request.POST.get('nip', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        position = request.POST.get('position', '').strip()
        dept_id = request.POST.get('department')
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        gender = request.POST.get('gender', 'L')

        form_data = {
            'nip': nip, 'full_name': full_name, 'position': position,
            'department': dept_id, 'phone_number': phone_number,
            'email': email, 'gender': gender,
        }

        if not nip:
            messages.error(request, "NIP/NIK harus diisi.")
        elif Employee.objects.filter(nip=nip).exists():
            messages.error(request, f"NIP/NIK '{nip}' sudah terdaftar atas nama pegawai lain.")
        else:
            dept = Department.objects.get(id=dept_id) if dept_id else None
            Employee.objects.create(
                nip=nip, full_name=full_name, position=position,
                dept_relation=dept, phone_number=phone_number,
                email=email, gender=gender,
                nik_ktp=request.POST.get('nik_ktp', '').strip(),
                photo=request.FILES.get('photo'),
                place_of_birth=request.POST.get('place_of_birth', '').strip(),
                date_of_birth=request.POST.get('date_of_birth') or None,
                address=request.POST.get('address', '').strip(),
                last_education=request.POST.get('last_education', '').strip(),
                sk_number=request.POST.get('sk_number', '').strip(),
                sk_date=request.POST.get('sk_date') or None,
                tmt_date=request.POST.get('tmt_date') or None,
                employment_status=request.POST.get('employment_status', 'amil_tetap'),
                sk_file=request.FILES.get('sk_file')
            )
            messages.success(request, f"Data pegawai {full_name} berhasil ditambahkan.")
            return redirect('users:employee_list')

    return render(request, 'users/employee_create.html', {
        'departments': departments,
        'form_data': form_data,
        'employment_statuses': Employee.EMPLOYMENT_STATUS_CHOICES,
    })


@login_required
def employee_edit(request, pk):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak mengedit data pegawai.")
        return redirect('users:employee_list')
    emp = get_object_or_404(Employee, pk=pk)
    departments = Department.objects.all()
    
    if request.method == 'POST':
        new_nip = request.POST.get('nip', '').strip()
        
        if not new_nip:
            messages.error(request, "NIP/NIK harus diisi.")
            return redirect('users:employee_edit', pk=emp.pk)
            
        if Employee.objects.filter(nip=new_nip).exclude(pk=emp.pk).exists():
            messages.error(request, f"NIP/NIK '{new_nip}' sudah terdaftar atas nama pegawai lain.")
            return redirect('users:employee_edit', pk=emp.pk)
            
        emp.nip = new_nip
        emp.full_name = request.POST.get('full_name', '').strip()
        emp.position = request.POST.get('position', '').strip()
        
        dept_id = request.POST.get('dept_relation')
        emp.dept_relation = Department.objects.get(id=dept_id) if dept_id else None
        
        emp.phone_number = request.POST.get('phone_number', '').strip()
        emp.email = request.POST.get('email', '').strip()
        emp.gender = request.POST.get('gender')

        # Data Diri Pegawai
        if request.FILES.get('photo'):
            emp.photo = request.FILES.get('photo')
        emp.nik_ktp = request.POST.get('nik_ktp', '').strip()
        emp.place_of_birth = request.POST.get('place_of_birth', '').strip()
        emp.date_of_birth = request.POST.get('date_of_birth') or None
        emp.address = request.POST.get('address', '').strip()
        emp.last_education = request.POST.get('last_education', '').strip()

        # Data SK Kepegawaian
        emp.sk_number = request.POST.get('sk_number', '').strip()
        emp.sk_date = request.POST.get('sk_date') or None
        emp.tmt_date = request.POST.get('tmt_date') or None
        emp.employment_status = request.POST.get('employment_status', 'amil_tetap')
        if request.FILES.get('sk_file'):
            emp.sk_file = request.FILES.get('sk_file')

        emp.is_active = request.POST.get('is_active') == 'on'
        emp.save()
        
        messages.success(request, f"Data pegawai {emp.full_name} berhasil diperbarui.")
        return redirect('users:employee_list')
        
    return render(request, 'users/employee_edit.html', {
        'employee': emp, 
        'departments': departments,
        'employment_statuses': Employee.EMPLOYMENT_STATUS_CHOICES,
    })


@login_required
def employee_delete(request, pk):
    if not is_pure_superadmin(request):
        messages.error(request, "Akses Ditolak: Hanya Superadmin yang berhak menghapus data pegawai.")
        return redirect('users:employee_list')
    if request.method == 'POST':
        emp = get_object_or_404(Employee, pk=pk)
        name = emp.full_name
        user = User.objects.filter(employee=emp).first()
        
        if user:
            user.delete()
        emp.delete()
        
        messages.success(request, f"Data pegawai {name} (beserta akun) telah dihapus.")
        
    return redirect('users:employee_list')