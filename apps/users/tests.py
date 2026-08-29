from django.test import TestCase, Client
from django.urls import reverse
from users.models import Employee, User, Department

class UserModelAndRoleTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Bidang IV (Administrasi & SDM)")
        self.employee = Employee.objects.create(
            nip='198001012018011001',
            full_name='Ahmad Fauzi, S.E.',
            position='Kepala Bidang IV',
            dept_relation=self.dept,
            leadership_type='waka_4'
        )
        self.superadmin = User.objects.create_user(
            username='admin_test',
            password='Password123!',
            role='admin',
            is_superuser=True
        )
        self.waka_user = User.objects.create_user(
            username='waka_test',
            password='Password123!',
            role='pimpinan',
            employee=self.employee
        )

    def test_user_role_properties(self):
        self.assertTrue(self.superadmin.is_superadmin)
        self.assertTrue(self.waka_user.is_waka_4)

    def test_employee_position_json_endpoint(self):
        self.client.force_login(self.superadmin)
        url = reverse('users:employee_position_json', kwargs={'pk': self.employee.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['position'], 'Kepala Bidang IV')
        self.assertEqual(response.json()['full_name'], 'Ahmad Fauzi, S.E.')

    def test_switch_pov_endpoint(self):
        self.client.force_login(self.superadmin)
        url = reverse('users:switch_pov') + '?role=kabid_4'
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('active_pov'), 'kabid_4')

