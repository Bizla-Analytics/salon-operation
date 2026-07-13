import csv, io
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .forms import *
from .decorators import roles_required

def user_branch(user): return getattr(getattr(user,'profile',None),'branch',None)
@login_required
def dashboard(request):
    p=request.user.profile
    if request.user.is_superuser or p.role=='ADMIN': return redirect('admin_dashboard')
    if p.role=='MANAGER': return redirect('manager_dashboard')
    return redirect('employee_dashboard')

def logout_view(request): logout(request); return redirect('login')

@roles_required('ADMIN')
def admin_dashboard(request):
    return render(request,'operations/admin_dashboard.html',{'branches':Branch.objects.count(),'users':User.objects.count(),'services':Service.objects.count(),'sop_tasks':SOPTask.objects.count()})

@roles_required('ADMIN')
def create_user(request):
    form=UserCreateForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            u=User.objects.create_user(username=form.cleaned_data['username'],password=form.cleaned_data['password'],first_name=form.cleaned_data['first_name'])
            p=u.profile; p.role=form.cleaned_data['role']; p.branch=form.cleaned_data['branch']; p.employee_code=form.cleaned_data['employee_code']; p.job_title=form.cleaned_data['job_title']; p.save()
        messages.success(request,'User created.'); return redirect('create_user')
    return render(request,'operations/form.html',{'form':form,'title':'Add manager or employee'})

CSV_MODELS={'branches':(Branch,['code','name','address','phone','active']), 'services':(Service,['code','name','category','standard_duration_minutes','base_price','active']), 'chairs':(Chair,['branch','code','name','active']), 'sop_tasks':(SOPTask,['service','sequence','phase','task_type','title','instructions','required','can_skip','skip_reason_required','quick_action','active'])}
@roles_required('ADMIN')
def csv_import(request):
    result=[]
    if request.method=='POST' and request.FILES.get('csv_file'):
        kind=request.POST.get('kind'); model,fields=CSV_MODELS[kind]
        text=request.FILES['csv_file'].read().decode('utf-8-sig'); reader=csv.DictReader(io.StringIO(text))
        for n,row in enumerate(reader,2):
            try:
                data={}
                for f in fields:
                    v=(row.get(f) or '').strip()
                    if f in ['active','required','can_skip','skip_reason_required','quick_action']: v=v.lower() in ('1','true','yes','y')
                    if f=='branch': v=Branch.objects.get(code=v)
                    if f=='service': v=Service.objects.get(code=v)
                    data[f]=v
                lookup={'code':data['code']} if 'code' in data else ({'service':data['service'],'sequence':data['sequence']} if kind=='sop_tasks' else {'branch':data['branch'],'code':data['code']})
                model.objects.update_or_create(**lookup,defaults=data); result.append(f'Row {n}: imported')
            except Exception as e: result.append(f'Row {n}: {e}')
    return render(request,'operations/csv_import.html',{'kinds':CSV_MODELS.keys(),'result':result})

@roles_required('MANAGER')
def manager_dashboard(request):
    branch=user_branch(request.user)
    visits=Visit.objects.filter(branch=branch).exclude(status__in=['CLOSED','CANCELLED']).select_related('customer').prefetch_related('services__service','services__employee')
    return render(request,'operations/manager_dashboard.html',{'visits':visits})

@roles_required('MANAGER')
def new_visit(request):
    branch=user_branch(request.user); form=VisitCreateForm(request.POST or None,branch=branch)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            mobile=form.cleaned_data['mobile']; customer=Customer.objects.filter(mobile=mobile).first() if mobile else None
            customer=customer or Customer.objects.create(name=form.cleaned_data['customer_name'],mobile=mobile)
            visit=Visit.objects.create(branch=branch,customer=customer,token_number=form.cleaned_data['token_number'],status='ASSIGNED',created_by=request.user)
            VisitService.objects.create(visit=visit,service=form.cleaned_data['service'],employee=form.cleaned_data['employee'],chair=form.cleaned_data['chair'],assigned_by=request.user)
        messages.success(request,'Service assigned successfully.'); return redirect('manager_dashboard')
    return render(request,'operations/form.html',{'form':form,'title':'Create visit and assign service'})

@roles_required('MANAGER')
def verify_service(request,pk):
    vs=get_object_or_404(VisitService,pk=pk,visit__branch=user_branch(request.user))
    form=VerifyForm(request.POST or None,initial={'manager_notes':vs.manager_notes})
    if request.method=='POST' and form.is_valid():
        if vs.tasks.filter(required=True).exclude(status='COMPLETED').exists():
            messages.error(request,'Required tasks are not completed.'); return redirect('verify_service',pk=pk)
        vs.status='VERIFIED'; vs.manager_notes=form.cleaned_data['manager_notes']; vs.verified_at=timezone.now(); vs.save()
        if not vs.visit.services.exclude(status='VERIFIED').exists(): vs.visit.status='VERIFIED'; vs.visit.save(update_fields=['status'])
        messages.success(request,'Service verified.'); return redirect('manager_dashboard')
    return render(request,'operations/verify.html',{'vs':vs,'form':form})

@roles_required('MANAGER')
def add_invoice(request,visit_id):
    visit=get_object_or_404(Visit,pk=visit_id,branch=user_branch(request.user)); form=InvoiceForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        inv=form.save(commit=False); inv.visit=visit; inv.entered_by=request.user; inv.save(); visit.status='INVOICED'; visit.save(update_fields=['status']); fb,_=Feedback.objects.get_or_create(visit=visit)
        return render(request,'operations/feedback_link.html',{'feedback':fb})
    return render(request,'operations/form.html',{'form':form,'title':'Enter invoice'})

@roles_required('EMPLOYEE')
def employee_dashboard(request):
    jobs=VisitService.objects.filter(employee=request.user,status__in=['ASSIGNED','IN_PROGRESS','PAUSED']).select_related('visit__customer','service','chair')
    return render(request,'operations/employee_dashboard.html',{'jobs':jobs})

@roles_required('EMPLOYEE')
def execute_service(request,pk):
    vs=get_object_or_404(VisitService,pk=pk,employee=request.user)
    current=vs.tasks.exclude(status__in=['COMPLETED','SKIPPED']).first()
    return render(request,'operations/execute.html',{'vs':vs,'current':current,'tasks':vs.tasks.all()})

@roles_required('EMPLOYEE')
@require_POST
def task_action(request,pk,action):
    task=get_object_or_404(VisitTask,pk=pk,visit_service__employee=request.user); vs=task.visit_service
    now=timezone.now(); note=request.POST.get('note','').strip(); reason=request.POST.get('skip_reason','').strip()
    if action=='start':
        task.status='IN_PROGRESS'; task.started_at=task.started_at or now
        if vs.status=='ASSIGNED': vs.status='IN_PROGRESS'; vs.started_at=vs.started_at or now; vs.visit.status='IN_PROGRESS'; vs.visit.save(update_fields=['status'])
    elif action=='complete':
        task.status='COMPLETED'; task.started_at=task.started_at or now; task.completed_at=now
    elif action=='skip':
        if not task.can_skip: messages.error(request,'This task cannot be skipped.'); return redirect('execute_service',pk=vs.pk)
        if task.skip_reason_required and not reason: messages.error(request,'Please give a short skip reason.'); return redirect('execute_service',pk=vs.pk)
        task.status='SKIPPED'; task.skip_reason=reason; task.completed_at=now
    task.note=note; task.performed_by=request.user; task.save(); vs.save()
    return redirect('execute_service',pk=vs.pk)

@roles_required('EMPLOYEE')
@require_POST
def finish_service(request,pk):
    vs=get_object_or_404(VisitService,pk=pk,employee=request.user)
    if vs.tasks.exclude(status__in=['COMPLETED','SKIPPED']).exists(): messages.error(request,'Complete or skip the remaining tasks first.')
    else:
        vs.status='EMPLOYEE_DONE'; vs.employee_completed_at=timezone.now(); vs.employee_notes=request.POST.get('employee_notes',''); vs.save(); vs.visit.status='EMPLOYEE_DONE'; vs.visit.save(update_fields=['status']); messages.success(request,'Submitted to manager.')
    return redirect('employee_dashboard')

def feedback_form(request,token):
    fb=get_object_or_404(Feedback,public_token=token)
    questions=FeedbackQuestion.objects.filter(active=True)
    if request.method=='POST' and not fb.submitted_at:
        with transaction.atomic():
            for q in questions:
                r=int(request.POST.get(f'q_{q.id}',0))
                if r not in range(1,6): messages.error(request,'Please answer all five questions.'); return render(request,'operations/feedback.html',{'feedback':fb,'questions':questions})
                FeedbackAnswer.objects.update_or_create(feedback=fb,question=q,defaults={'rating':r})
            fb.suggestion=request.POST.get('suggestion',''); fb.submitted_at=timezone.now(); fb.save(); fb.visit.status='CLOSED'; fb.visit.closed_at=timezone.now(); fb.visit.save(update_fields=['status','closed_at'])
        return render(request,'operations/feedback_thanks.html')
    return render(request,'operations/feedback.html',{'feedback':fb,'questions':questions})
