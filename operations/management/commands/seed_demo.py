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
        (10,'BEFORE','CONSULT','Consult customer and confirm requested style',True,False),
        (20,'BEFORE','HYGIENE','Confirm tools are cleaned and sanitized',True,False),
        (30,'DURING','SERVICE','Complete haircut and styling',True,False),
        (40,'FINISHING','QUALITY','Show result and confirm customer satisfaction',True,False),
        (50,'AFTER','HYGIENE','Clean tools and workstation',True,False)]
        for seq,phase,typ,title,req,skip in tasks: SOPTask.objects.update_or_create(service=s,sequence=seq,defaults={'phase':phase,'task_type':typ,'title':title,'required':req,'can_skip':skip,'skip_reason_required':skip})
        SOPTask.objects.filter(service=s).exclude(sequence__in=[t[0] for t in tasks]).delete()
        qs=[
            'അന്തിമ ഫലത്തിൽ നിങ്ങൾ എത്രത്തോളം തൃപ്തനാണ്?\nHow satisfied are you with the final result?',
            'ഞങ്ങളുടെ ജീവനക്കാരൻ എത്രത്തോളം പ്രൊഫഷണലായാണ് സേവനം നൽകിയത്?\nHow professionally did the employee handle your service?',
            'ഞങ്ങളുടെ കേന്ദ്രത്തിലെ ശുചിത്വവും അന്തരീക്ഷവും നിങ്ങൾക്ക് എത്രത്തോളം സുഖകരമായിരുന്നു?\nHow comfortable and clean was your experience?',
            'നിങ്ങളുടെ ആവശ്യങ്ങൾ ഞങ്ങളുടെ ജീവനക്കാരൻ എത്രത്തോളം കൃത്യമായി മനസ്സിലാക്കി?\nHow well did the employee understand your requirements?',
            'വീണ്ടും ഞങ്ങളെ സന്ദർശിക്കാൻ നിങ്ങൾക്ക് എത്രത്തോളം സാധ്യതയുണ്ട്?\nHow likely are you to visit us again?',
        ]
        for i,q in enumerate(qs,1): FeedbackQuestion.objects.update_or_create(sequence=i*10,defaults={'text':q,'active':True})
        self.stdout.write(self.style.SUCCESS('Demo created. Password for demo users: Admin@123'))
