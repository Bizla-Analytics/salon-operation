"""Admin/general-manager-only staff onboarding with private one-time credentials."""
import csv
import io
import logging

from django import forms
from django.contrib import messages
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from .decorators import roles_required
from .forms import BootstrapMixin
from .models import StaffCSVImport
from .staff_imports import (
    MAX_STAFF_UPLOAD, StaffImportProblem, apply_staff_import, credentials_csv,
    expire_staff_imports, stage_staff_import,
)

logger = logging.getLogger(__name__)


class StaffCSVUploadForm(BootstrapMixin, forms.Form):
    csv_file = forms.FileField(label='Staff CSV file', widget=forms.ClearableFileInput(attrs={'accept': '.csv'}))

    def clean_csv_file(self):
        upload = self.cleaned_data['csv_file']
        if not upload.name.lower().endswith('.csv') or upload.size > MAX_STAFF_UPLOAD:
            raise forms.ValidationError('Choose a .csv file no larger than 512 KB.')
        return upload


class StaffCSVConfirmForm(BootstrapMixin, forms.Form):
    actor_password = forms.CharField(label='Your current password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    confirmed = forms.BooleanField(label='I reviewed the branches, roles and pay details and approve creating these new accounts.')

    def __init__(self, *args, actor, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)

    def clean_actor_password(self):
        value = self.cleaned_data['actor_password']
        if not self.actor.check_password(value):
            raise forms.ValidationError('Your current password is incorrect.')
        return value


def staff_directory_url(actor):
    return 'admin_staff' if actor.is_superuser or actor.profile.role == 'ADMIN' else 'general_manager_staff'


@roles_required('ADMIN', 'GENERAL_MANAGER')
@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
def staff_csv_import(request):
    expire_staff_imports()
    form = StaffCSVUploadForm()
    confirm_form = StaffCSVConfirmForm(actor=request.user)
    stage = None
    identifier = request.POST.get('stage') if request.method == 'POST' else request.GET.get('stage')
    if identifier:
        try:
            stage = get_object_or_404(StaffCSVImport, pk=identifier, created_by=request.user)
        except (ValueError, forms.ValidationError):
            return HttpResponseBadRequest('Invalid import reference.')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'validate':
            form = StaffCSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data['csv_file']
                try:
                    stage = stage_staff_import(request.user, upload.name, upload.read(MAX_STAFF_UPLOAD + 1))
                except StaffImportProblem as exc:
                    form.add_error('csv_file', str(exc))
                except DatabaseError:
                    form.add_error('csv_file', 'Staff data is busy. Nothing was created; validate again shortly.')
                else:
                    return redirect(f'{request.path}?stage={stage.pk}')
        elif action == 'confirm' and stage:
            confirm_form = StaffCSVConfirmForm(request.POST, actor=request.user)
            if confirm_form.is_valid():
                try:
                    credentials = apply_staff_import(stage.pk, request.user)
                except StaffImportProblem as exc:
                    messages.error(request, str(exc))
                except DatabaseError:
                    messages.error(request, 'Account creation failed and was rolled back. Nothing was imported; try again shortly.')
                except Exception:
                    logger.error('Staff import failed for operator %s', request.user.pk)
                    messages.error(request, 'Account creation failed and was rolled back. Nothing was imported.')
                else:
                    response = HttpResponse(credentials_csv(credentials), content_type='text/csv; charset=utf-8')
                    response['Content-Disposition'] = 'attachment; filename="staff-login-credentials.csv"'
                    response['X-Content-Type-Options'] = 'nosniff'
                    response['Referrer-Policy'] = 'no-referrer'
                    return response
                stage.refresh_from_db()
        elif action == 'cancel' and stage:
            discarded = StaffCSVImport.objects.filter(pk=stage.pk, created_by=request.user, status='PENDING').update(status='CANCELLED', rows=[])
            messages.info(request, 'Staff preview discarded. No accounts were created.' if discarded
                          else 'This preview is no longer pending. No changes were made.')
            return redirect('staff_csv_import')
        else:
            return HttpResponseBadRequest('Choose validate, confirm or cancel.')
    return render(request, 'operations/staff_csv_import.html', {
        'form': form, 'confirm_form': confirm_form, 'stage': stage,
        'return_to': staff_directory_url(request.user),
        'history': StaffCSVImport.objects.filter(created_by=request.user).defer('rows')[:10],
    })


@roles_required('ADMIN', 'GENERAL_MANAGER')
@never_cache
@require_GET
def staff_csv_template(request):
    output = io.StringIO(newline='')
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['BRANCH', 'NAME', 'PH.NO', 'SECTION', 'EXPERIENCE', 'SALARY'])
    writer.writerow(['REPLACE_WITH_BRANCH_CODE', 'Example Staff', '', 'GENTS ONLY', '3 YEARS', ''])
    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="staff-upload-template.csv"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
