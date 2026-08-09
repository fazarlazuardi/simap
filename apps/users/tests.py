from django.test import TestCase
from django.urls import reverse

from users.models import Employee, User


class EmployeePositionAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='secret123')
        self.employee = Employee.objects.create(
            nip='198001012018011001',
            full_name='Budi Santoso',
            position='Waka II',
        )

    def test_employee_position_json_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('users:employee_position_json', kwargs={'pk': self.employee.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['position'], 'Waka II')
        self.assertEqual(response.json()['full_name'], 'Budi Santoso')
