from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Employee, User, Department
from .decorators import superadmin_required


@login_required
@superadmin_required
def employee_master(request):
    employees = Employee.objects.select_related('dept_relation').all().order_by('-created_at')
    users = {
        u.employee_id: u 
        for u in User.objects.filter(employee__isnull=False).select_related('employee')
    }
    
    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(employees, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    employee_list = [(emp, users.get(emp.pk)) for emp in page_obj]
    departments = Department.objects.all()
    roles = User.ROLE_CHOICES

    return render(request, 'users/employee_master.html', {
        'page_obj': page_obj,
        'employee_list': employee_list,
        'departments': departments,
        'roles': roles,
    })


@login_required
@superadmin_required
def employee_create_user(request, emp_pk):
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
            
        return redirect('users:employee_detail', pk=emp.pk)
        
    return redirect('users:employee_list')


@login_required
@superadmin_required
def employee_delete_user(request, emp_pk):
    emp = get_object_or_404(Employee, pk=emp_pk)
    user = User.objects.filter(employee=emp).first()
    
    if request.method == 'POST' and user:
        username = user.username
        user.delete()
        messages.success(request, f"Akun '{username}' berhasil dihapus dari {emp.full_name}.")
        
    return redirect('users:employee_detail', pk=emp.pk)


@login_required
@superadmin_required
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
@superadmin_required
def employee_edit_master(request, pk):
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
@superadmin_required
def employee_list(request):
    bidang = request.GET.get('bidang')
    akun = request.GET.get('akun')

    employees = Employee.objects.select_related('dept_relation').all().order_by('-created_at')

    if bidang:
        employees = employees.filter(dept_relation__id=bidang)
        
    user_emp_ids = User.objects.filter(employee__isnull=False).values_list('employee_id', flat=True)
    if akun == 'ya':
        employees = employees.filter(pk__in=user_emp_ids)
    elif akun == 'tidak':
        employees = employees.exclude(pk__in=user_emp_ids)

    departments = Department.objects.all()
    users_map = {
        u.employee_id: u 
        for u in User.objects.filter(employee__isnull=False).select_related('employee')
    }
    
    per_page = int(request.GET.get('per_page', 25))
    paginator = Paginator(employees, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    employee_list_ctx = [(emp, users_map.get(emp.pk)) for emp in page_obj]
    
    return render(request, 'users/employee_list.html', {
        'page_obj': page_obj,
        'employee_list': employee_list_ctx,
        'departments': departments,
        'filters': {
            'bidang': bidang or '',
            'akun': akun or '',
        },
    })


@login_required
@superadmin_required
def employee_create(request):
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
                email=email, gender=gender
            )
            messages.success(request, f"Data pegawai {full_name} berhasil ditambahkan.")
            return redirect('users:employee_list')

    return render(request, 'users/employee_create.html', {
        'departments': departments,
        'form_data': form_data,
    })


@login_required
@superadmin_required
def employee_edit(request, pk):
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
        emp.is_active = request.POST.get('is_active') == 'on'
        emp.save()
        
        messages.success(request, f"Data pegawai {emp.full_name} berhasil diperbarui.")
        return redirect('users:employee_list')
        
    return render(request, 'users/employee_edit.html', {'employee': emp, 'departments': departments})


@login_required
@superadmin_required
def employee_delete(request, pk):
    if request.method == 'POST':
        emp = get_object_or_404(Employee, pk=pk)
        name = emp.full_name
        user = User.objects.filter(employee=emp).first()
        
        if user:
            user.delete()
        emp.delete()
        
        messages.success(request, f"Data pegawai {name} (beserta akun) telah dihapus.")
        
    return redirect('users:employee_list')