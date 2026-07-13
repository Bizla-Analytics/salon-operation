from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, VisitService, VisitTask
@receiver(post_save,sender=User)
def profile_for_user(sender,instance,created,**kwargs):
    if created: Profile.objects.create(user=instance)
@receiver(post_save,sender=VisitService)
def copy_sop_tasks(sender,instance,created,**kwargs):
    if created:
        VisitTask.objects.bulk_create([VisitTask(visit_service=instance,source_task=t,sequence=t.sequence,phase=t.phase,task_type=t.task_type,title=t.title,instructions=t.instructions,required=t.required,can_skip=t.can_skip,skip_reason_required=t.skip_reason_required) for t in instance.service.sop_tasks.filter(active=True)])
