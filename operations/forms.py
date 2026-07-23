from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Branch, Chair, Invoice, Profile, Service


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            field.widget.attrs["class"] = "form-control"


class VisitCreateForm(BootstrapMixin, forms.Form):
    customer_name = forms.CharField(max_length=120)
    mobile = forms.CharField(max_length=30, required=False)
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select services in the order they should be completed.",
    )
    service_order = forms.CharField(widget=forms.HiddenInput, required=False)
    employee = forms.ModelChoiceField(queryset=User.objects.none())
    chair = forms.ModelChoiceField(queryset=Chair.objects.none(), required=False)

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["services"].queryset = Service.objects.filter(active=True)
        if branch:
            self.fields["employee"].queryset = User.objects.filter(
                profile__branch=branch,
                profile__role="EMPLOYEE",
                profile__active=True,
                is_active=True,
            )
            self.fields["chair"].queryset = Chair.objects.filter(branch=branch, active=True)

    def clean(self):
        cleaned = super().clean()
        selected = list(cleaned.get("services") or [])
        selected_by_id = {service.pk: service for service in selected}
        raw_order = cleaned.get("service_order", "")
        try:
            ordered_ids = [int(value) for value in raw_order.split(",") if value]
        except ValueError:
            ordered_ids = []
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(selected_by_id):
            ordered_ids = [service.pk for service in selected]
        cleaned["ordered_services"] = [selected_by_id[service_id] for service_id in ordered_ids]
        return cleaned


class VisitEditForm(VisitCreateForm):
    customer_name = None
    mobile = None

    def __init__(self, *args, visit=None, branch=None, **kwargs):
        self.visit = visit
        if visit and not args and "initial" not in kwargs:
            visit_services = list(visit.services.order_by("order_number", "id"))
            kwargs["initial"] = {
                "services": [item.service_id for item in visit_services],
                "service_order": ",".join(str(item.service_id) for item in visit_services),
                "employee": visit_services[0].employee_id if visit_services else None,
                "chair": visit_services[0].chair_id if visit_services else None,
            }
        super().__init__(*args, branch=branch, **kwargs)
        if visit:
            current_service_ids = visit.services.values_list("service_id", flat=True)
            self.fields["services"].queryset = Service.objects.filter(
                Q(active=True) | Q(pk__in=current_service_ids)
            ).distinct()


class ServiceLookupForm(BootstrapMixin, forms.Form):
    service = forms.ModelChoiceField(queryset=Service.objects.filter(active=True), empty_label="Select a service")


class TaskActionForm(BootstrapMixin, forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    skip_reason = forms.CharField(required=False, max_length=250)


class VerifyForm(BootstrapMixin, forms.Form):
    manager_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class InvoiceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_number"]


class UserCreateForm(BootstrapMixin, forms.Form):
    username = forms.CharField()
    first_name = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES)
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(active=True))
    employee_code = forms.CharField(required=False)
    job_title = forms.CharField(required=False)
