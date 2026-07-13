from django.contrib import admin
from .models import *
@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin): list_display=('code','name','active'); search_fields=('code','name')
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin): list_display=('user','role','branch','employee_code','active'); list_filter=('role','branch','active')
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin): list_display=('code','name','category','standard_duration_minutes','base_price','active'); search_fields=('code','name'); list_filter=('active','category')
class SOPInline(admin.TabularInline): model=SOPTask; extra=0
ServiceAdmin.inlines=[SOPInline]
@admin.register(SOPTask)
class SOPTaskAdmin(admin.ModelAdmin): list_display=('service','sequence','phase','task_type','title','required','can_skip','active'); list_filter=('service','phase','task_type','active')
admin.site.register([Chair,Customer,Visit,VisitService,VisitTask,Invoice,FeedbackQuestion,Feedback,FeedbackAnswer])
admin.site.site_header='Salon Operations Administration'
