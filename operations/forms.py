from django import forms
from django.contrib.auth.models import User
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.db.models import Q

from .models import Branch, Chair, Invoice, Profile, Service, Visit, VisitService


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            field.widget.attrs["class"] = "form-control"


class VisitCreateForm(BootstrapMixin, forms.Form):
    customer_name = forms.CharField(max_length=120)
    mobile = forms.CharField(
        max_length=10,
        required=False,
        help_text="Optional. Enter exactly 10 digits when provided.",
    )
    invoice_number = forms.CharField(
        required=False,
        disabled=True,
        label="Invoice number",
        help_text="Available after every service has been verified.",
        widget=forms.TextInput(attrs={"placeholder": "Available after verification"}),
    )

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()
        if mobile and (not mobile.isdigit() or len(mobile) != 10):
            raise forms.ValidationError("Enter a valid 10-digit mobile number.")
        return mobile


class CompleteInvoiceForm(VisitCreateForm):
    invoice_number = forms.CharField(max_length=50, required=True)

    def clean_invoice_number(self):
        value = self.cleaned_data["invoice_number"].strip()
        if Invoice.objects.filter(invoice_number=value, status="COMPLETED").exists():
            raise forms.ValidationError("This invoice number is already in use.")
        return value


class VisitServiceAssignmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = VisitService
        fields = ["order_number", "service", "employee", "chair"]

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        current_service = self.instance.service_id if self.instance.pk else None
        current_employee = self.instance.employee_id if self.instance.pk else None
        current_chair = self.instance.chair_id if self.instance.pk else None
        self.fields["service"].queryset = Service.objects.filter(Q(active=True) | Q(pk=current_service)).distinct()
        self.fields["employee"].queryset = User.objects.filter(
            Q(pk=current_employee) | Q(
                profile__branch=branch,
                profile__role="EMPLOYEE",
                profile__active=True,
                is_active=True,
            )
        ).distinct()
        self.fields["chair"].queryset = Chair.objects.filter(
            Q(pk=current_chair) | Q(branch=branch, active=True)
        ).distinct()
        if self.instance.pk and self.instance.status != "ASSIGNED":
            for field in self.fields.values():
                field.disabled = True


class BaseVisitServiceFormSet(BaseInlineFormSet):
    def __init__(self, *args, branch=None, **kwargs):
        self.branch = branch
        super().__init__(*args, **kwargs)
        for form in self.forms:
            if form.instance.pk and form.instance.status != "ASSIGNED":
                form.fields["DELETE"].disabled = True

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["branch"] = self.branch
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("service")
        ]
        if not active:
            raise forms.ValidationError("Add at least one service to the visit.")
        order_numbers = [form.cleaned_data["order_number"] for form in active]
        if len(order_numbers) != len(set(order_numbers)):
            raise forms.ValidationError("Every active service must have a unique order number.")
        locked_orders = [
            form.instance.order_number for form in active
            if form.instance.pk and form.instance.status != "ASSIGNED"
        ]
        if locked_orders:
            locked_prefix_end = max(locked_orders)
            editable_orders = [
                form.cleaned_data["order_number"] for form in active
                if not form.instance.pk or form.instance.status == "ASSIGNED"
            ]
            if any(order <= locked_prefix_end for order in editable_orders):
                raise forms.ValidationError(
                    "Upcoming services must remain after every started or completed service."
                )


VisitServiceFormSet = inlineformset_factory(
    Visit,
    VisitService,
    form=VisitServiceAssignmentForm,
    formset=BaseVisitServiceFormSet,
    fields=["order_number", "service", "employee", "chair"],
    extra=0,
    can_delete=True,
)


class CancelAndReassignForm(BootstrapMixin, forms.Form):
    cancellation_reason = forms.CharField(max_length=250, widget=forms.Textarea(attrs={"rows": 3}))
    employee = forms.ModelChoiceField(queryset=User.objects.none())
    chair = forms.ModelChoiceField(queryset=Chair.objects.none(), required=False)

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = User.objects.filter(
            profile__branch=branch, profile__role="EMPLOYEE", profile__active=True, is_active=True
        )
        self.fields["chair"].queryset = Chair.objects.filter(branch=branch, active=True)


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
