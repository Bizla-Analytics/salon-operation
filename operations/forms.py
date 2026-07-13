from django import forms
from django.contrib.auth.models import User
from .models import *
class BootstrapMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for f in self.fields.values():
            if isinstance(f.widget,(forms.CheckboxInput,forms.RadioSelect)): continue
            f.widget.attrs['class']='form-control'
class VisitCreateForm(BootstrapMixin,forms.Form):
    customer_name=forms.CharField(max_length=120); mobile=forms.CharField(max_length=30,required=False); service=forms.ModelChoiceField(queryset=Service.objects.filter(active=True)); employee=forms.ModelChoiceField(queryset=User.objects.none()); chair=forms.ModelChoiceField(queryset=Chair.objects.none(),required=False)
    def __init__(self,*args,branch=None,**kwargs):
        super().__init__(*args,**kwargs)
        if branch:
            self.fields['employee'].queryset=User.objects.filter(profile__branch=branch,profile__role='EMPLOYEE',profile__active=True,is_active=True)
            self.fields['chair'].queryset=Chair.objects.filter(branch=branch,active=True)
class TaskActionForm(BootstrapMixin,forms.Form):
    note=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':2})); skip_reason=forms.CharField(required=False,max_length=250)
class VerifyForm(BootstrapMixin,forms.Form):
    manager_notes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':3}))
class InvoiceForm(BootstrapMixin,forms.ModelForm):
    class Meta: model=Invoice; fields=['invoice_number','payment_method']
class UserCreateForm(BootstrapMixin,forms.Form):
    username=forms.CharField(); first_name=forms.CharField(); password=forms.CharField(widget=forms.PasswordInput); role=forms.ChoiceField(choices=Profile.ROLE_CHOICES); branch=forms.ModelChoiceField(queryset=Branch.objects.filter(active=True)); employee_code=forms.CharField(required=False); job_title=forms.CharField(required=False)
