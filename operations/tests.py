from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import InvoiceForm, VisitCreateForm, VisitEditForm
from .models import (
    Branch,
    Customer,
    Feedback,
    FeedbackAnswer,
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

    def test_manager_sees_old_phone_compatible_service_picker(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("new_visit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="service-search"')
        self.assertContains(response, 'id="service-select"')
        self.assertNotContains(response, "<datalist")
        self.assertContains(response, "works on older company phones")
        self.assertContains(response, 'id="add-service-first"')
        self.assertContains(response, 'id="add-service"')
        self.assertContains(response, 'id="selected-services"')
        self.assertContains(response, 'class="mobile-signout"')

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

        dashboard = self.client.get(reverse("manager_dashboard"))
        displayed_visit = next(item for item in dashboard.context["visits"] if item.pk == visit.pk)
        displayed_services = list(displayed_visit.services.all())
        self.assertEqual([item.pk for item in displayed_services], [second.pk, first.pk])
        self.assertEqual([item.order_number for item in displayed_services], [1, 2])

    def test_visit_edit_form_prefills_existing_assignment_and_order(self):
        visit, _, _ = self.create_visit()

        # This is how the view constructs the form on a GET request.
        form = VisitEditForm(None, visit=visit, branch=self.branch)

        self.assertEqual(
            [int(value) for value in form["services"].value()],
            [self.service_a.pk, self.service_b.pk],
        )
        self.assertEqual(
            form["service_order"].value(),
            f"{self.service_a.pk},{self.service_b.pk}",
        )
        self.assertEqual(form["employee"].value(), self.employee.pk)

    def test_edit_page_contains_previous_services_in_execution_order(self):
        visit, _, _ = self.create_visit()
        self.client.force_login(self.manager)

        response = self.client.get(reverse("edit_visit_services", args=[visit.pk]))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(
            [int(value) for value in form["services"].value()],
            [self.service_a.pk, self.service_b.pk],
        )
        self.assertEqual(
            form["service_order"].value(),
            f"{self.service_a.pk},{self.service_b.pk}",
        )

    def test_reassignment_preserves_existing_services_and_order(self):
        visit, first, second = self.create_visit()
        replacement = User.objects.create_user("replacement", password="test")
        replacement.profile.role = "EMPLOYEE"
        replacement.profile.branch = self.branch
        replacement.profile.save()
        original_ids = [first.pk, second.pk]
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("edit_visit_services", args=[visit.pk]),
            {
                "services": [self.service_a.pk, self.service_b.pk],
                "service_order": f"{self.service_a.pk},{self.service_b.pk}",
                "employee": replacement.pk,
                "chair": "",
            },
        )

        self.assertRedirects(response, reverse("manager_dashboard"))
        assignments = list(visit.services.order_by("order_number", "id"))
        self.assertEqual([item.pk for item in assignments], original_ids)
        self.assertEqual(
            [item.service_id for item in assignments],
            [self.service_a.pk, self.service_b.pk],
        )
        self.assertEqual([item.order_number for item in assignments], [1, 2])
        self.assertTrue(all(item.employee_id == replacement.pk for item in assignments))

        self.client.force_login(replacement)
        response = self.client.get(reverse("employee_dashboard"))
        jobs = list(response.context["jobs"])
        self.assertEqual([job.pk for job in jobs], original_ids)
        self.assertEqual([job.order_number for job in jobs], [1, 2])

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

    def test_admin_visit_explorer_searches_and_filters_visit_cards(self):
        visit, _, _ = self.create_visit()
        admin = User.objects.create_superuser("visit-admin", "visit-admin@example.com", "test")
        self.client.force_login(admin)

        response = self.client.get(reverse("admin_visits"), {
            "q": self.customer.name,
            "branch": self.branch.pk,
            "service": self.service_a.pk,
            "status": "ASSIGNED",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertContains(response, self.customer.name)
        self.assertContains(response, f"Visit #{visit.pk}")
        self.assertContains(response, self.service_a.name)
        self.assertContains(response, "Apply filters")

    def test_admin_reports_include_revenue_tasks_and_feedback(self):
        visit, _, _ = self.create_visit()
        Invoice.objects.create(
            visit=visit,
            invoice_number="REPORT-1",
            amount=Decimal("250.00"),
            entered_by=self.manager,
        )
        feedback = Feedback.objects.create(visit=visit, submitted_at=timezone.now(), suggestion="Great visit")
        question = FeedbackQuestion.objects.filter(active=True).first()
        FeedbackAnswer.objects.create(feedback=feedback, question=question, rating=5)
        admin = User.objects.create_superuser("report-admin", "report-admin@example.com", "test")
        self.client.force_login(admin)

        response = self.client.get(reverse("admin_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["visits"], 1)
        self.assertEqual(response.context["summary"]["revenue"], Decimal("250.00"))
        self.assertEqual(response.context["summary"]["feedback_average"], 5)
        self.assertContains(response, "Branch performance")
        self.assertContains(response, "Service performance")
        self.assertContains(response, "Great visit")

    def test_visit_related_labels_include_customer_and_visit(self):
        visit, first, _ = self.create_visit()
        feedback = Feedback.objects.create(visit=visit)
        question = FeedbackQuestion.objects.filter(active=True).first()
        answer = FeedbackAnswer.objects.create(feedback=feedback, question=question, rating=4)

        self.assertIn(self.customer.name, str(visit))
        self.assertIn(self.customer.name, str(first))
        self.assertIn(self.customer.name, str(first.tasks.first()))
        self.assertIn(self.customer.name, str(feedback))
        self.assertIn(self.customer.name, str(answer))
        self.assertIn(f"Visit #{visit.pk}", str(feedback))

        admin = User.objects.create_superuser("records-admin", "records-admin@example.com", "test")
        self.client.force_login(admin)
        feedback_page = self.client.get(reverse("admin:operations_feedback_changelist"))
        answer_page = self.client.get(reverse("admin:operations_feedbackanswer_changelist"))
        self.assertContains(feedback_page, self.customer.name)
        self.assertContains(feedback_page, f"Visit #{visit.pk}")
        self.assertContains(answer_page, self.customer.name)

    def test_manager_cannot_open_admin_reports_or_visit_explorer(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("admin_reports")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_visits")).status_code, 403)

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
