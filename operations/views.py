import csv, io
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .forms import *
from .decorators import roles_required
from .workflow import CONSULTATION_CODE, SANITISATION_CODE, build_visit_tasks, rebuild_service_tasks

def user_branch(user): return getattr(getattr(user,'profile',None),'branch',None)

def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    return JsonResponse({'status':'ok','django':'connected','postgresql':'connected'})

def with_progress(queryset):
    return queryset.annotate(
        task_total=Count('tasks',distinct=True),
        task_done=Count('tasks',filter=Q(tasks__status__in=['COMPLETED','SKIPPED']),distinct=True),
    )
@login_required
def dashboard(request):
    p=request.user.profile
    if request.user.is_superuser or p.role=='ADMIN': return redirect('admin_dashboard')
    if p.role=='MANAGER': return redirect('manager_dashboard')
    return redirect('employee_dashboard')

def logout_view(request): logout(request); return redirect('login')

@roles_required('ADMIN')
def admin_dashboard(request):
    return render(request,'operations/admin_dashboard.html',{'branches':Branch.objects.count(),'users':User.objects.count(),'services':Service.objects.count(),'sop_tasks':OperationalTask.objects.count()})


@roles_required('ADMIN')
def admin_reports(request):
    """Business-wide operational reporting without exposing edit controls."""
    visits = Visit.objects.all()
    task_summary = VisitTask.objects.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED')),
        skipped=Count('id', filter=Q(status='SKIPPED')),
        labour_minutes=Sum('active_labour_minutes'),
        passive_minutes=Sum('passive_time_minutes'),
    )
    summary = {
        'visits': visits.count(),
        'active_visits': visits.filter(status__in=['WAITING', 'ASSIGNED', 'IN_PROGRESS', 'EMPLOYEE_DONE']).count(),
        'completed_visits': visits.filter(status__in=['VERIFIED', 'INVOICED', 'CLOSED']).count(),
        'customers': Customer.objects.count(),
        'invoices': Invoice.objects.count(),
        'revenue': Invoice.objects.aggregate(total=Sum('amount'))['total'] or 0,
        'feedback_requests': Feedback.objects.count(),
        'feedback_submitted': Feedback.objects.filter(submitted_at__isnull=False).count(),
        'feedback_average': FeedbackAnswer.objects.aggregate(value=Avg('rating'))['value'],
    }
    task_summary = {key: value or 0 for key, value in task_summary.items()}

    branch_rows = list(
        Branch.objects.annotate(
            visit_count=Count('visits', distinct=True),
            active_visit_count=Count(
                'visits',
                filter=Q(visits__status__in=['WAITING', 'ASSIGNED', 'IN_PROGRESS', 'EMPLOYEE_DONE']),
                distinct=True,
            ),
            invoice_count=Count('visits__invoice', distinct=True),
            revenue=Sum('visits__invoice__amount'),
        ).order_by('name')
    )
    branch_feedback = {
        row['feedback__visit__branch_id']: row['average']
        for row in FeedbackAnswer.objects.values('feedback__visit__branch_id').annotate(average=Avg('rating'))
    }
    for branch in branch_rows:
        branch.revenue = branch.revenue or 0
        branch.feedback_average = branch_feedback.get(branch.pk)

    service_rows = Service.objects.annotate(
        visit_count=Count('visitservice', distinct=True),
        completed_count=Count(
            'visitservice',
            filter=Q(visitservice__status__in=['EMPLOYEE_DONE', 'VERIFIED']),
            distinct=True,
        ),
        labour_minutes=Sum('visitservice__tasks__active_labour_minutes'),
        passive_minutes=Sum('visitservice__tasks__passive_time_minutes'),
    ).order_by('-visit_count', 'name')
    status_rows = visits.values('status').annotate(total=Count('id')).order_by('status')
    rating_rows = FeedbackAnswer.objects.values('rating').annotate(total=Count('id')).order_by('rating')
    recent_feedback = Feedback.objects.filter(submitted_at__isnull=False).select_related(
        'visit__customer', 'visit__branch'
    ).prefetch_related('answers').order_by('-submitted_at')[:10]
    for feedback in recent_feedback:
        ratings = [answer.rating for answer in feedback.answers.all()]
        feedback.average_rating = sum(ratings) / len(ratings) if ratings else None

    return render(request, 'operations/admin_reports.html', {
        'summary': summary,
        'task_summary': task_summary,
        'branch_rows': branch_rows,
        'service_rows': service_rows,
        'status_rows': status_rows,
        'rating_rows': rating_rows,
        'recent_feedback': recent_feedback,
    })


@roles_required('ADMIN')
def admin_visits(request):
    """Searchable, read-only visit cards for administrators."""
    query = request.GET.get('q', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    service_id = request.GET.get('service', '').strip()
    status = request.GET.get('status', '').strip()
    service_queryset = with_progress(
        VisitService.objects.select_related('service', 'employee', 'chair').prefetch_related(
            Prefetch(
                'tasks',
                queryset=VisitTask.objects.only(
                    'visit_service_id',
                    'status',
                    'started_at',
                    'completed_at',
                ),
            )
        )
    ).order_by('order_number', 'id')
    visits = Visit.objects.select_related('branch', 'customer', 'invoice', 'feedback').prefetch_related(
        Prefetch('services', queryset=service_queryset)
    )
    if query:
        search = (
            Q(customer__name__icontains=query)
            | Q(customer__mobile__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(token_number__icontains=query)
            | Q(services__service__name__icontains=query)
            | Q(services__service__code__icontains=query)
            | Q(services__employee__username__icontains=query)
            | Q(services__employee__first_name__icontains=query)
            | Q(invoice__invoice_number__icontains=query)
        )
        if query.isdigit():
            search |= Q(pk=int(query))
        visits = visits.filter(search)
    if branch_id.isdigit():
        visits = visits.filter(branch_id=int(branch_id))
    if service_id.isdigit():
        visits = visits.filter(services__service_id=int(service_id))
    valid_statuses = {choice[0] for choice in Visit.STATUS}
    if status in valid_statuses:
        visits = visits.filter(status=status)
    visits = visits.annotate(
        task_total=Count('services__tasks', distinct=True),
        task_done=Count(
            'services__tasks',
            filter=Q(services__tasks__status__in=['COMPLETED', 'SKIPPED']),
            distinct=True,
        ),
        feedback_average=Avg('feedback__answers__rating'),
    ).distinct().order_by('-created_at', '-id')
    page = Paginator(visits, 20).get_page(request.GET.get('page'))
    for visit in page.object_list:
        visit.admin_progress = int(visit.task_done * 100 / visit.task_total) if visit.task_total else 0
        visit_services = list(visit.services.all())
        total_seconds = sum(
            max((task.completed_at - task.started_at).total_seconds(), 0)
            for item in visit_services
            if item.status in ['EMPLOYEE_DONE', 'VERIFIED']
            for task in item.tasks.all()
            if task.status == 'COMPLETED' and task.started_at and task.completed_at
        )
        total_minutes = int((total_seconds / 60) + 0.5)
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            visit.total_task_time = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        elif hours:
            visit.total_task_time = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            visit.total_task_time = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return render(request, 'operations/admin_visits.html', {
        'page': page,
        'branches': Branch.objects.order_by('name'),
        'service_options': Service.objects.order_by('name'),
        'status_options': Visit.STATUS,
        'filters': {'q': query, 'branch': branch_id, 'service': service_id, 'status': status},
    })

@roles_required('ADMIN')
def service_catalog(request):
    form=ServiceLookupForm(request.GET or None)
    selected=None; sections=[]; totals={'labour':0,'passive':0,'equipment':0,'utility':0}
    if form.is_valid():
        selected=form.cleaned_data['service']
        mapped=list(selected.service_details.filter(active=True,sub_service__active=True).select_related('sub_service').order_by('sequence','id'))
        ordered=[]
        consultation=SubService.objects.filter(code=CONSULTATION_CODE,active=True).first()
        sanitisation=SubService.objects.filter(code=SANITISATION_CODE,active=True).first()
        if sanitisation: ordered.append((sanitisation,True))
        if consultation: ordered.append((consultation,True))
        ordered.extend((detail.sub_service,detail.mandatory) for detail in mapped if detail.sub_service.code not in [CONSULTATION_CODE,SANITISATION_CODE])
        for sub_service,mandatory in ordered:
            task_rows=[]
            for task in sub_service.tasks.filter(active=True).order_by('sequence','id'):
                inventory=list(task.inventory_requirements.filter(active=True,service=selected).select_related('inventory'))
                equipment=list(task.equipment_requirements.filter(active=True).select_related('equipment'))
                totals['labour']+=task.active_labour_minutes; totals['passive']+=task.passive_time_minutes
                totals['equipment']+=sum(item.equipment_usage_minutes for item in equipment)
                totals['utility']+=sum(item.utility_minutes for item in equipment)
                task_rows.append({'task':task,'inventory':inventory,'equipment':equipment})
            sections.append({'sub_service':sub_service,'mandatory':mandatory,'tasks':task_rows})
    return render(request,'operations/service_catalog.html',{'form':form,'selected':selected,'sections':sections,'totals':totals})

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
    # Prefetch in the visit's authoritative execution order.  Do not rely on
    # implicit model ordering after progress annotations/grouping because the
    # manager must see the same sequence used to build the employee task plan.
    services=(with_progress(
        VisitService.objects.select_related('service','employee','chair')
    ).order_by('visit_id','order_number','id'))
    visits=(Visit.objects.filter(branch=branch).exclude(status__in=['CLOSED','CANCELLED'])
            .select_related('customer')
            .prefetch_related(Prefetch('services',queryset=services),'invoice')
            .order_by('created_at','id'))
    for visit in visits:
        active_services = [item for item in visit.services.all() if item.status != 'CANCELLED']
        visit.can_verify_all = bool(active_services) and all(
            item.status in ['EMPLOYEE_DONE', 'VERIFIED'] for item in active_services
        ) and any(item.status == 'EMPLOYEE_DONE' for item in active_services)
    return render(request,'operations/manager_dashboard.html',{'visits':visits})

@roles_required('MANAGER')
def new_visit(request):
    branch=user_branch(request.user); form=VisitCreateForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            mobile=form.cleaned_data['mobile']; customer=Customer.objects.filter(mobile=mobile).first() if mobile else None
            if customer:
                if customer.name != form.cleaned_data['customer_name']:
                    customer.name = form.cleaned_data['customer_name']
                    customer.save(update_fields=['name', 'updated_at'])
            else:
                customer=Customer.objects.create(name=form.cleaned_data['customer_name'],mobile=mobile)
            visit=Visit.objects.create(branch=branch,customer=customer,status='WAITING',created_by=request.user)
        messages.success(request,'Customer details saved. Now add and assign the services.')
        return redirect('edit_visit_services', visit_id=visit.pk)
    return render(request,'operations/visit_form.html',{'form':form,'title':'Create service visit'})

@roles_required('MANAGER')
def edit_visit_services(request, visit_id):
    branch = user_branch(request.user)
    visit = get_object_or_404(Visit, pk=visit_id, branch=branch)
    if visit.status in ['VERIFIED', 'INVOICED', 'CLOSED', 'CANCELLED']:
        messages.error(request, "Assignments cannot be changed after visit verification.")
        return redirect("manager_dashboard")

    formset = VisitServiceFormSet(
        request.POST or None,
        instance=visit,
        branch=branch,
        queryset=visit.services.exclude(status='CANCELLED').order_by('order_number', 'id'),
        prefix='services',
    )
    # A brand-new visit starts with one convenient assignment row. Existing
    # visits never receive an unsolicited blank row when reopened.
    if request.method == 'GET' and not visit.services.exists():
        formset.extra = 1
    if request.method == "POST" and formset.is_valid():
        with transaction.atomic():
            changed_service_ids = set()
            for form in formset.forms:
                if not form.cleaned_data:
                    continue
                instance = form.instance
                if form.cleaned_data.get('DELETE'):
                    if instance.pk and instance.status == 'ASSIGNED':
                        instance.delete()
                    continue
                if not form.cleaned_data.get('service'):
                    continue
                is_new = not instance.pk
                service_changed = is_new or 'service' in form.changed_data
                item = form.save(commit=False)
                item.visit = visit
                item.assigned_by = request.user
                if is_new or any(name in form.changed_data for name in ['employee', 'chair']):
                    item.assigned_at = timezone.now()
                item.save()
                if service_changed:
                    changed_service_ids.add(item.pk)
            active = visit.services.exclude(status='CANCELLED')
            has_started_history = VisitTask.objects.filter(visit_service__visit=visit).exclude(status='PENDING').exists()
            if not has_started_history:
                build_visit_tasks(visit)
            else:
                for item in active.filter(pk__in=changed_service_ids):
                    rebuild_service_tasks(item)
            visit.status = 'ASSIGNED' if not active.exclude(status='ASSIGNED').exists() else visit.status
            visit.save(update_fields=['status'])
        messages.success(request, "Upcoming service order and assignments updated.")
        return redirect("manager_dashboard")

    return render(
        request,
        "operations/service_assignments.html",
        {
            "formset": formset,
            "title": f"Assign services for {visit.customer.name}",
            "visit": visit,
        },
    )


@roles_required('MANAGER')
def verify_service(request,pk):
    vs=get_object_or_404(VisitService.objects.select_related('visit__customer','service').prefetch_related('tasks'),pk=pk,visit__branch=user_branch(request.user))
    form=VerifyForm(request.POST or None,initial={'manager_notes':vs.manager_notes})
    if request.method=='POST' and form.is_valid():
        if vs.tasks.filter(required=True).exclude(status='COMPLETED').exists():
            messages.error(request,'Required tasks are not completed.'); return redirect('verify_service',pk=pk)
        vs.status='VERIFIED'; vs.manager_notes=form.cleaned_data['manager_notes']; vs.verified_at=timezone.now(); vs.save()
        if not vs.visit.services.exclude(status='CANCELLED').exclude(status='VERIFIED').exists(): vs.visit.status='VERIFIED'; vs.visit.save(update_fields=['status'])
        messages.success(request,'Service verified.'); return redirect('manager_dashboard')
    return render(request,'operations/verify.html',{'vs':vs,'form':form})


@roles_required('MANAGER')
def verify_visit(request, visit_id):
    visit = get_object_or_404(
        Visit.objects.select_related('customer').prefetch_related(
            Prefetch(
                'services',
                queryset=VisitService.objects.select_related('service', 'employee', 'chair')
                .prefetch_related('tasks').order_by('order_number', 'id'),
            )
        ),
        pk=visit_id,
        branch=user_branch(request.user),
    )
    if visit.status in ['INVOICED', 'CLOSED', 'CANCELLED']:
        messages.error(request, 'This visit can no longer be verified.')
        return redirect('manager_dashboard')
    active_services = [item for item in visit.services.all() if item.status != 'CANCELLED']
    if request.method == 'POST':
        with transaction.atomic():
            locked_visit = Visit.objects.select_for_update().get(pk=visit.pk)
            services = list(
                locked_visit.services.select_for_update().exclude(status='CANCELLED').order_by('order_number', 'id')
            )
            unfinished = [item for item in services if item.status not in ['EMPLOYEE_DONE', 'VERIFIED']]
            incomplete_tasks = VisitTask.objects.filter(
                visit_service__in=services, required=True
            ).exclude(status='COMPLETED')
            if not services or unfinished or incomplete_tasks.exists():
                messages.error(request, 'Every active service and required task must be completed before Verify all.')
                return redirect('verify_visit', visit_id=visit.pk)
            now = timezone.now()
            for item in services:
                item.manager_notes = request.POST.get(f'manager_notes_{item.pk}', '').strip()
                item.status = 'VERIFIED'
                item.verified_at = item.verified_at or now
                item.verified_by = request.user
                item.save(update_fields=['manager_notes', 'status', 'verified_at', 'verified_by', 'updated_at'])
            locked_visit.status = 'VERIFIED'
            locked_visit.save(update_fields=['status'])
        messages.success(request, 'All services verified. The invoice can now be added.')
        return redirect('manager_dashboard')
    return render(request, 'operations/verify_visit.html', {'visit': visit, 'services': active_services})


@roles_required('MANAGER')
def cancel_and_reassign_service(request, pk):
    branch = user_branch(request.user)
    service = get_object_or_404(
        VisitService.objects.select_related('visit__customer', 'service'), pk=pk, visit__branch=branch
    )
    if service.status not in ['ASSIGNED', 'IN_PROGRESS', 'PAUSED']:
        messages.error(request, 'Only an upcoming or active service can be cancelled and reassigned.')
        return redirect('manager_dashboard')
    form = CancelAndReassignForm(
        request.POST or None,
        branch=branch,
        initial={'employee': service.employee_id, 'chair': service.chair_id},
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            old = VisitService.objects.select_for_update().get(pk=service.pk)
            if old.status not in ['ASSIGNED', 'IN_PROGRESS', 'PAUSED']:
                messages.error(request, 'This service can no longer be reassigned.')
                return redirect('manager_dashboard')
            now = timezone.now()
            old.status = 'CANCELLED'
            old.cancelled_at = now
            old.cancelled_by = request.user
            old.cancellation_reason = form.cleaned_data['cancellation_reason']
            old.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
            old.tasks.filter(status__in=['PENDING', 'IN_PROGRESS']).update(status='CANCELLED', completed_at=now)
            replacement = VisitService.objects.create(
                visit=old.visit,
                service=old.service,
                order_number=old.order_number,
                employee=form.cleaned_data['employee'],
                chair=form.cleaned_data['chair'],
                assigned_by=request.user,
                replaces=old,
            )
            completed_opening_types = set(VisitTask.objects.filter(
                visit_service__visit=old.visit,
                task_type__in=['HYGIENE', 'CONSULT'],
                status__in=['COMPLETED', 'SKIPPED'],
            ).values_list('task_type', flat=True))
            rebuild_service_tasks(
                replacement,
                include_sanitisation=old.order_number == 1 and 'HYGIENE' not in completed_opening_types,
                include_consultation=old.order_number == 1 and 'CONSULT' not in completed_opening_types,
            )
            old.visit.status = 'ASSIGNED'
            old.visit.save(update_fields=['status'])
        messages.success(request, 'The original service was cancelled and a replacement was assigned.')
        return redirect('manager_dashboard')
    return render(request, 'operations/form.html', {
        'form': form,
        'title': f'Cancel and reassign {service.service.name}',
        'form_note': 'The original task history will be preserved. A cancellation reason is required.',
    })

@roles_required('MANAGER')
def add_invoice(request,visit_id):
    visit=get_object_or_404(Visit,pk=visit_id,branch=user_branch(request.user))
    existing = Invoice.objects.filter(visit=visit).first()
    if existing and existing.status == 'COMPLETED':
        feedback, _ = Feedback.objects.get_or_create(visit=visit)
        messages.info(request, "This combined visit already has one completed invoice.")
        return redirect('manager_dashboard')
    if not visit.is_invoice_ready:
        messages.error(request,'Verify every service in the order before creating the invoice.')
        return redirect('manager_dashboard')
    form=CompleteInvoiceForm(request.POST or None, initial={
        'customer_name': visit.customer.name,
        'mobile': visit.customer.mobile,
        'invoice_number': existing.invoice_number if existing else '',
    })
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked = Visit.objects.select_for_update().get(pk=visit.pk)
            customer = locked.customer
            customer.name = form.cleaned_data['customer_name']
            customer.mobile = form.cleaned_data['mobile']
            customer.save(update_fields=['name', 'mobile', 'updated_at'])
            total=sum((item.service.base_price for item in locked.services.exclude(status='CANCELLED').select_related('service')),start=0)
            inv = existing or Invoice(visit=locked, entered_by=request.user)
            inv.invoice_number = form.cleaned_data['invoice_number']
            inv.amount = total
            inv.status = 'COMPLETED'
            inv.completed_at = timezone.now()
            inv.save()
            locked.status='INVOICED'; locked.save(update_fields=['status'])
            Feedback.objects.get_or_create(visit=locked)
        messages.success(request, 'Invoice completed. Feedback can now be collected.')
        return redirect('manager_dashboard')
    total=sum((item.service.base_price for item in visit.services.exclude(status='CANCELLED').select_related('service')),start=0)
    return render(request,'operations/invoice_form.html',{'form':form,'visit':visit,'total':total})


def _save_feedback(request, feedback, questions):
    for question in questions:
        try:
            rating = int(request.POST.get(f'q_{question.id}', 0))
        except (TypeError, ValueError):
            rating = 0
        if rating not in range(1, 6):
            return False
        FeedbackAnswer.objects.update_or_create(
            feedback=feedback, question=question, defaults={'rating': rating}
        )
    feedback.suggestion=request.POST.get('suggestion','').strip()
    feedback.submitted_at=timezone.now()
    feedback.save(update_fields=['suggestion', 'submitted_at', 'updated_at'])
    feedback.visit.status='CLOSED'
    feedback.visit.closed_at=timezone.now()
    feedback.visit.save(update_fields=['status','closed_at'])
    return True


@roles_required('MANAGER')
def collect_feedback(request, visit_id):
    visit = get_object_or_404(Visit, pk=visit_id, branch=user_branch(request.user), status='INVOICED')
    feedback, _ = Feedback.objects.get_or_create(visit=visit)
    questions = FeedbackQuestion.objects.filter(active=True)
    if request.method == 'POST':
        with transaction.atomic():
            if not _save_feedback(request, feedback, questions):
                messages.error(request, 'Please answer every feedback question.')
            else:
                messages.success(request, 'Feedback saved and the visit was closed.')
                return redirect('manager_dashboard')
    return render(request, 'operations/feedback.html', {
        'feedback': feedback, 'questions': questions, 'manager_collection': True
    })

@roles_required('EMPLOYEE')
def employee_dashboard(request):
    jobs=(with_progress(VisitService.objects.filter(
        employee=request.user,
        status__in=['ASSIGNED','IN_PROGRESS','PAUSED'],
    )).select_related('visit__customer','service','chair')
        .order_by('visit__created_at','visit_id','order_number','id'))
    return render(request,'operations/employee_dashboard.html',{'jobs':jobs})

@roles_required('EMPLOYEE')
def execute_service(request,pk):
    vs=get_object_or_404(VisitService,pk=pk,employee=request.user,status__in=['ASSIGNED','IN_PROGRESS','PAUSED'])
    if vs.visit.services.filter(order_number__lt=vs.order_number).exclude(status__in=['EMPLOYEE_DONE','VERIFIED','CANCELLED']).exists():
        messages.error(request,'Complete the earlier service in this visit first.')
        return redirect('employee_dashboard')
    current=vs.tasks.exclude(status__in=['COMPLETED','SKIPPED']).first()
    return render(request,'operations/execute.html',{'vs':vs,'current':current,'tasks':vs.tasks.all()})

@roles_required('EMPLOYEE')
@require_POST
def task_action(request,pk,action):
    task=get_object_or_404(VisitTask,pk=pk,visit_service__employee=request.user,visit_service__status__in=['ASSIGNED','IN_PROGRESS','PAUSED']); vs=task.visit_service
    if vs.visit.services.filter(order_number__lt=vs.order_number).exclude(status__in=['EMPLOYEE_DONE','VERIFIED','CANCELLED']).exists():
        messages.error(request,'Complete the earlier service in this visit first.'); return redirect('employee_dashboard')
    now=timezone.now(); note=request.POST.get('note','').strip()
    reason_choice=request.POST.get('skip_reason_choice','').strip()
    reason_other=request.POST.get('skip_reason_other','').strip()
    reason=reason_other if reason_choice=='OTHER' else reason_choice
    if action=='start':
        if task.status!='PENDING': return redirect('execute_service',pk=vs.pk)
        task.status='IN_PROGRESS'; task.started_at=task.started_at or now
        if vs.status=='ASSIGNED': vs.status='IN_PROGRESS'; vs.started_at=vs.started_at or now; vs.visit.status='IN_PROGRESS'; vs.visit.save(update_fields=['status'])
    elif action=='complete':
        if task.status!='IN_PROGRESS':
            messages.error(request,'Start the task before completing it.'); return redirect('execute_service',pk=vs.pk)
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
    vs=get_object_or_404(VisitService,pk=pk,employee=request.user,status__in=['ASSIGNED','IN_PROGRESS','PAUSED'])
    if vs.tasks.exclude(status__in=['COMPLETED','SKIPPED']).exists(): messages.error(request,'Complete or skip the remaining tasks first.')
    else:
        vs.status='EMPLOYEE_DONE'; vs.employee_completed_at=timezone.now(); vs.employee_notes=request.POST.get('employee_notes',''); vs.save()
        if not vs.visit.services.exclude(status__in=['EMPLOYEE_DONE','VERIFIED','CANCELLED']).exists():
            vs.visit.status='EMPLOYEE_DONE'; vs.visit.save(update_fields=['status'])
        messages.success(request,'Submitted to manager.')
    return redirect('employee_dashboard')

def feedback_form(request,token):
    fb=get_object_or_404(Feedback,public_token=token)
    questions=FeedbackQuestion.objects.filter(active=True)
    if request.method=='POST' and not fb.submitted_at:
        with transaction.atomic():
            if not _save_feedback(request, fb, questions):
                messages.error(request,'Please answer all five questions.')
                return render(request,'operations/feedback.html',{'feedback':fb,'questions':questions})
        return render(request,'operations/feedback_thanks.html')
    return render(request,'operations/feedback.html',{'feedback':fb,'questions':questions})
