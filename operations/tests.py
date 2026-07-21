from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import VisitCreateForm
from .models import (
    Branch,
    Customer,
    OperationalTask,
    Service,
    ServiceDetail,
    SubService,
    Visit,
    VisitService,
)
from .workflow import build_visit_tasks


class CombinedServiceWorkflowTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code="B1", name="Test Branch")
        self.manager = User.objects.create_user("manager", password="test")
        self.manager.profile.role = "MANAGER"
        self.manager.profile.branch = self.branch
        self.manager.profile.save()
        self.employee = User.objects.create_user("employee", password="test")
        self.employee.profile.role = "EMPLOYEE"
        self.employee.profile.branch = self.branch
        self.employee.profile.save()
        self.customer = Customer.objects.create(name="Test Customer")

        self.consult = SubService.objects.create(code="SUB001", name="Client Consultation")
        self.sanitise = SubService.objects.create(code="SUB025", name="Sanitisation")
        self.work_a = SubService.objects.create(code="SUB100", name="First procedure")
        self.work_b = SubService.objects.create(code="SUB200", name="Second procedure")
        for number, sub_service in enumerate([self.consult, self.sanitise, self.work_a, self.work_b], start=1):
            OperationalTask.objects.create(
                external_id=f"T{number}", sub_service=sub_service, sequence=1, name=sub_service.name
            )
        self.service_a = Service.objects.create(code="S1", name="Service One")
        self.service_b = Service.objects.create(code="S2", name="Service Two")
        ServiceDetail.objects.create(external_id="D1", service=self.service_a, sub_service=self.work_a, sequence=1)
        ServiceDetail.objects.create(external_id="D2", service=self.service_a, sub_service=self.sanitise, sequence=2)
        ServiceDetail.objects.create(external_id="D3", service=self.service_b, sub_service=self.consult, sequence=1)
        ServiceDetail.objects.create(external_id="D4", service=self.service_b, sub_service=self.work_b, sequence=2)

    def create_visit(self):
        visit = Visit.objects.create(
            branch=self.branch, customer=self.customer, status="ASSIGNED", created_by=self.manager
        )
        first = VisitService.objects.create(
            visit=visit, service=self.service_a, order_number=1, employee=self.employee, assigned_by=self.manager
        )
        second = VisitService.objects.create(
            visit=visit, service=self.service_b, order_number=2, employee=self.employee, assigned_by=self.manager
        )
        build_visit_tasks(visit)
        return visit, first, second

    def test_combined_plan_has_one_consultation_first_and_one_sanitisation_last(self):
        visit, first, second = self.create_visit()
        all_tasks = list(visit.services.order_by("order_number").values_list("tasks__title", flat=True))
        self.assertEqual(all_tasks.count("Client Consultation"), 1)
        self.assertEqual(all_tasks.count("Sanitisation"), 1)
        self.assertEqual(first.tasks.first().title, "Client Consultation")
        self.assertEqual(second.tasks.last().title, "Sanitisation")

    def test_employee_cannot_open_second_service_before_first_is_complete(self):
        _, _, second = self.create_visit()
        self.client.force_login(self.employee)
        response = self.client.get(reverse("execute_service", args=[second.pk]))
        self.assertRedirects(response, reverse("employee_dashboard"))

    def test_manager_service_selection_preserves_submitted_order(self):
        form = VisitCreateForm(
            data={
                "customer_name": "Customer",
                "mobile": "",
                "services": [self.service_a.pk, self.service_b.pk],
                "service_order": f"{self.service_b.pk},{self.service_a.pk}",
                "employee": self.employee.pk,
                "chair": "",
            },
            branch=self.branch,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["ordered_services"], [self.service_b, self.service_a])

    def test_manager_sees_searchable_single_service_picker(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("new_visit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="service-search"')
        self.assertContains(response, 'list="service-options-list"')
        self.assertContains(response, 'id="add-service"')
        self.assertContains(response, 'id="selected-services"')

    def test_admin_can_render_service_catalogue(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", "test")
        self.client.force_login(admin)
        response = self.client.get(reverse("service_catalog"), {"service": self.service_a.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Consultation")
        self.assertContains(response, "Sanitisation")
