from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class TimeStamped(models.Model):
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: abstract=True

class Branch(TimeStamped):
    code=models.CharField(max_length=20,unique=True); name=models.CharField(max_length=120); address=models.TextField(blank=True); phone=models.CharField(max_length=30,blank=True); active=models.BooleanField(default=True)
    def __str__(self): return f'{self.code} - {self.name}'

class Profile(TimeStamped):
    ROLE_CHOICES=[('ADMIN','Admin'),('MANAGER','Manager'),('EMPLOYEE','Employee')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile'); role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='EMPLOYEE'); branch=models.ForeignKey(Branch,on_delete=models.PROTECT,null=True,blank=True); employee_code=models.CharField(max_length=30,blank=True); job_title=models.CharField(max_length=80,blank=True); mobile=models.CharField(max_length=30,blank=True); active=models.BooleanField(default=True)
    def __str__(self): return f'{self.user.username} ({self.role})'

class Chair(TimeStamped):
    branch=models.ForeignKey(Branch,on_delete=models.CASCADE,related_name='chairs'); code=models.CharField(max_length=20); name=models.CharField(max_length=80); active=models.BooleanField(default=True)
    class Meta: unique_together=('branch','code')
    def __str__(self): return f'{self.branch.code} - {self.name}'

class Service(TimeStamped):
    code=models.CharField(max_length=30,unique=True); name=models.CharField(max_length=120); category=models.CharField(max_length=80,blank=True); standard_duration_minutes=models.PositiveIntegerField(default=30); base_price=models.DecimalField(max_digits=10,decimal_places=2,default=0); active=models.BooleanField(default=True)
    def __str__(self): return f'{self.code} - {self.name}'

class SOPTask(TimeStamped):
    PHASES=[('BEFORE','Before service'),('DURING','During service'),('FINISHING','Finishing'),('AFTER','After service')]
    TYPES=[('SERVICE','Service step'),('CONSULT','Consultation'),('HYGIENE','Cleaning / sanitization'),('TOWEL','Towel / laundry'),('QUALITY','Quality check'),('RECOMMEND','Recommendation')]
    service=models.ForeignKey(Service,on_delete=models.CASCADE,related_name='sop_tasks'); sequence=models.PositiveIntegerField(default=10); phase=models.CharField(max_length=20,choices=PHASES,default='DURING'); task_type=models.CharField(max_length=20,choices=TYPES,default='SERVICE'); title=models.CharField(max_length=160); instructions=models.TextField(blank=True); required=models.BooleanField(default=True); can_skip=models.BooleanField(default=False); skip_reason_required=models.BooleanField(default=True); quick_action=models.BooleanField(default=True); active=models.BooleanField(default=True)
    class Meta: ordering=['sequence','id']; unique_together=('service','sequence')
    def __str__(self): return f'{self.service.name} #{self.sequence} {self.title}'

class Customer(TimeStamped):
    name=models.CharField(max_length=120); mobile=models.CharField(max_length=30,blank=True,db_index=True); email=models.EmailField(blank=True); notes=models.TextField(blank=True)
    def __str__(self): return self.name

class Visit(TimeStamped):
    STATUS=[('WAITING','Waiting'),('ASSIGNED','Assigned'),('IN_PROGRESS','In progress'),('EMPLOYEE_DONE','Employee completed'),('VERIFIED','Manager verified'),('INVOICED','Invoiced'),('CLOSED','Closed'),('CANCELLED','Cancelled')]
    branch=models.ForeignKey(Branch,on_delete=models.PROTECT,related_name='visits'); customer=models.ForeignKey(Customer,on_delete=models.PROTECT,related_name='visits'); token_number=models.CharField(max_length=20,blank=True); status=models.CharField(max_length=30,choices=STATUS,default='WAITING'); created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='visits_created'); closed_at=models.DateTimeField(null=True,blank=True)
    def __str__(self): return f'Visit {self.id} - {self.customer.name}'

class VisitService(TimeStamped):
    STATUS=[('ASSIGNED','Assigned'),('IN_PROGRESS','In progress'),('PAUSED','Paused'),('EMPLOYEE_DONE','Employee completed'),('VERIFIED','Manager verified'),('CANCELLED','Cancelled')]
    visit=models.ForeignKey(Visit,on_delete=models.CASCADE,related_name='services'); service=models.ForeignKey(Service,on_delete=models.PROTECT); employee=models.ForeignKey(User,on_delete=models.PROTECT,related_name='assigned_services'); chair=models.ForeignKey(Chair,on_delete=models.SET_NULL,null=True,blank=True); assigned_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='service_assignments'); status=models.CharField(max_length=30,choices=STATUS,default='ASSIGNED'); assigned_at=models.DateTimeField(default=timezone.now); started_at=models.DateTimeField(null=True,blank=True); employee_completed_at=models.DateTimeField(null=True,blank=True); verified_at=models.DateTimeField(null=True,blank=True); employee_notes=models.TextField(blank=True); manager_notes=models.TextField(blank=True)
    def __str__(self): return f'{self.visit.customer.name} - {self.service.name}'
    @property
    def progress_percent(self):
        total=self.tasks.count(); done=self.tasks.filter(status__in=['COMPLETED','SKIPPED']).count(); return int(done*100/total) if total else 0

class VisitTask(TimeStamped):
    STATUS=[('PENDING','Pending'),('IN_PROGRESS','In progress'),('COMPLETED','Completed'),('SKIPPED','Skipped')]
    visit_service=models.ForeignKey(VisitService,on_delete=models.CASCADE,related_name='tasks'); source_task=models.ForeignKey(SOPTask,on_delete=models.SET_NULL,null=True,blank=True); sequence=models.PositiveIntegerField(); phase=models.CharField(max_length=20,choices=SOPTask.PHASES); task_type=models.CharField(max_length=20,choices=SOPTask.TYPES); title=models.CharField(max_length=160); instructions=models.TextField(blank=True); required=models.BooleanField(default=True); can_skip=models.BooleanField(default=False); skip_reason_required=models.BooleanField(default=True); status=models.CharField(max_length=20,choices=STATUS,default='PENDING'); started_at=models.DateTimeField(null=True,blank=True); completed_at=models.DateTimeField(null=True,blank=True); skip_reason=models.CharField(max_length=250,blank=True); note=models.TextField(blank=True); performed_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    class Meta: ordering=['sequence','id']; unique_together=('visit_service','sequence')
    def __str__(self): return self.title

class Invoice(TimeStamped):
    visit=models.OneToOneField(Visit,on_delete=models.CASCADE,related_name='invoice'); invoice_number=models.CharField(max_length=50,unique=True); amount=models.DecimalField(max_digits=10,decimal_places=2,default=0); payment_method=models.CharField(max_length=50,blank=True); entered_by=models.ForeignKey(User,on_delete=models.PROTECT)
    def __str__(self): return self.invoice_number

class FeedbackQuestion(TimeStamped):
    text=models.CharField(max_length=220); sequence=models.PositiveIntegerField(default=10); active=models.BooleanField(default=True)
    class Meta: ordering=['sequence','id']
    def __str__(self): return self.text

class Feedback(TimeStamped):
    visit=models.OneToOneField(Visit,on_delete=models.CASCADE,related_name='feedback'); public_token=models.UUIDField(default=uuid.uuid4,unique=True,editable=False); suggestion=models.TextField(blank=True); submitted_at=models.DateTimeField(null=True,blank=True)
    def __str__(self): return f'Feedback {self.visit_id}'

class FeedbackAnswer(models.Model):
    feedback=models.ForeignKey(Feedback,on_delete=models.CASCADE,related_name='answers'); question=models.ForeignKey(FeedbackQuestion,on_delete=models.PROTECT); rating=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])
    class Meta: unique_together=('feedback','question')
