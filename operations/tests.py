from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import InvoiceForm, VisitCreateForm
from .models import (
    Branch,
    Customer,
    Feedback,
    FeedbackQuestion,
    Invoice,
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

    def test_combined_plan_has_one_sanitisation_then_one_consultation(self):
        visit, first, second = self.create_visit()
        all_tasks = list(visit.services.order_by("order_number").values_list("tasks__title", flat=True))
        self.assertEqual(all_tasks.count("Client Consultation"), 1)
        self.assertEqual(all_tasks.count("Sanitisation"), 1)
        self.assertEqual(
            list(first.tasks.order_by("sequence").values_list("title", flat=True)),
            ["Sanitisation", "Client Consultation", "First procedure"],
        )
        self.assertEqual(
            list(second.tasks.order_by("sequence").values_list("title", flat=True)),
            ["Second procedure"],
        )

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
        self.assertContains(response, 'id="add-service-first"')
        self.assertContains(response, 'id="add-service"')
        self.assertContains(response, 'id="selected-services"')

    def test_manager_can_reorder_services_and_rebuild_pending_plan(self):
        visit, first, second = self.create_visit()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("edit_visit_services", args=[visit.pk]),
            {
                "services": [self.service_a.pk, self.service_b.pk],
                "service_order": f"{self.service_b.pk},{self.service_a.pk}",
                "employee": self.employee.pk,
                "chair": "",
            },
        )
        self.assertRedirects(response, reverse("manager_dashboard"))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(second.order_number, 1)
        self.assertEqual(first.order_number, 2)
        self.assertEqual(
            list(second.tasks.order_by("sequence").values_list("title", flat=True)),
            ["Sanitisation", "Client Consultation", "Second procedure"],
        )
        self.assertEqual(
            list(first.tasks.order_by("sequence").values_list("title", flat=True)),
            ["First procedure"],
        )

    def test_manager_cannot_reorder_after_work_starts(self):
        visit, first, _ = self.create_visit()
        task = first.tasks.first()
        task.status = "IN_PROGRESS"
        task.save(update_fields=["status"])
        self.client.force_login(self.manager)
        response = self.client.get(reverse("edit_visit_services", args=[visit.pk]))
        self.assertRedirects(response, reverse("manager_dashboard"))

    def test_other_branch_manager_cannot_edit_visit(self):
        visit, _, _ = self.create_visit()
        other_branch = Branch.objects.create(code="B2", name="Other Branch")
        other_manager = User.objects.create_user("other-manager", password="test")
        other_manager.profile.role = "MANAGER"
        other_manager.profile.branch = other_branch
        other_manager.profile.save()
        self.client.force_login(other_manager)
        response = self.client.get(reverse("edit_visit_services", args=[visit.pk]))
        self.assertEqual(response.status_code, 404)

    def test_admin_can_render_service_catalogue(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", "test")
        self.client.force_login(admin)
        response = self.client.get(reverse("service_catalog"), {"service": self.service_a.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Consultation")
        self.assertContains(response, "Sanitisation")

    def test_invoice_form_does_not_request_payment_method(self):
        form = InvoiceForm()
        self.assertEqual(list(form.fields), ["invoice_number"])

    def test_combined_visit_creates_one_invoice_and_one_feedback_request(self):
        visit, first, second = self.create_visit()
        first.status = second.status = "VERIFIED"
        first.save(update_fields=["status"])
        second.save(update_fields=["status"])
        visit.status = "VERIFIED"
        visit.save(update_fields=["status"])
        self.client.force_login(self.manager)

        dashboard = self.client.get(reverse("manager_dashboard"))
        self.assertContains(dashboard, "Complete combined invoice", count=1)

        invoice_url = reverse("add_invoice", args=[visit.pk])
        response = self.client.post(invoice_url, {"invoice_number": "INV-COMBINED-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invoice.objects.filter(visit=visit).count(), 1)
        self.assertEqual(Feedback.objects.filter(visit=visit).count(), 1)
        self.assertEqual(
            Invoice.objects.get(visit=visit).amount,
            self.service_a.base_price + self.service_b.base_price,
        )

        response = self.client.post(invoice_url, {"invoice_number": "INV-COMBINED-2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invoice.objects.filter(visit=visit).count(), 1)
        self.assertEqual(Feedback.objects.filter(visit=visit).count(), 1)

    def test_default_feedback_questions_are_bilingual(self):
        questions = list(FeedbackQuestion.objects.filter(active=True).order_by("sequence"))
        self.assertEqual(len(questions), 5)
        self.assertTrue(all("\n" in question.text for question in questions))
        self.assertEqual(
            questions[0].text,
            "അന്തിമ ഫലത്തിൽ നിങ്ങൾ എത്രത്തോളം തൃപ്തനാണ്?\n"
            "How satisfied are you with the final result?",
        )
