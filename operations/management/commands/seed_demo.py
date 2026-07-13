from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from operations.models import *
class Command(BaseCommand):
    help='Create demo branch, users, service, SOP and feedback questions'
    def handle(self,*args,**kwargs):
        b,_=Branch.objects.get_or_create(code='BR001',defaults={'name':'Main Salon'})
        Chair.objects.get_or_create(branch=b,code='C01',defaults={'name':'Chair 1'})
        for username,role,name in [('admin','ADMIN','Administrator'),('manager','MANAGER','Branch Manager'),('stylist','EMPLOYEE','Hair Stylist')]:
            u,_=User.objects.get_or_create(username=username,defaults={'first_name':name}); u.set_password('Admin@123'); u.is_staff=(role=='ADMIN'); u.is_superuser=(role=='ADMIN'); u.save(); p=u.profile; p.role=role; p.branch=b; p.job_title=name; p.save()
        s,_=Service.objects.get_or_create(code='HAIRCUT',defaults={'name':'Haircut & Styling','category':'Hair','standard_duration_minutes':45,'base_price':500})
        tasks=[
        (10,'BEFORE','SERVICE','Escort customer to chair',True,False),(20,'BEFORE','CONSULT','Consult customer and confirm requested style',True,False),(30,'BEFORE','TOWEL','Allocate clean towel and cape',True,False),(40,'BEFORE','HYGIENE','Confirm tools are cleaned and sanitized',True,False),(50,'DURING','SERVICE','Pre-cut hair wash',False,True),(60,'DURING','SERVICE','Hair cutting',True,False),(70,'DURING','SERVICE','Post-cut wash if needed',False,True),(80,'FINISHING','SERVICE','Drying and styling',True,False),(90,'FINISHING','QUALITY','Show result and confirm customer satisfaction',True,False),(100,'FINISHING','RECOMMEND','Record observed concern or optional recommendation',False,True),(110,'AFTER','HYGIENE','Clean and sanitize used tools and workstation',True,False),(120,'AFTER','TOWEL','Send used towel/cape to laundry allocation',True,False)]
        for seq,phase,typ,title,req,skip in tasks: SOPTask.objects.update_or_create(service=s,sequence=seq,defaults={'phase':phase,'task_type':typ,'title':title,'required':req,'can_skip':skip,'skip_reason_required':skip})
        qs=['How satisfied are you with the final result?','How professionally did the employee handle your service?','How comfortable and clean was the experience?','How well did the employee understand your requirement?','How likely are you to visit us again?']
        for i,q in enumerate(qs,1): FeedbackQuestion.objects.get_or_create(text=q,defaults={'sequence':i*10})
        self.stdout.write(self.style.SUCCESS('Demo created. Password for demo users: Admin@123'))
