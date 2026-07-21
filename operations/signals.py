from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, VisitService
from .workflow import build_visit_tasks
@receiver(post_save,sender=User)
def profile_for_user(sender,instance,created,**kwargs):
    if created: Profile.objects.create(user=instance)
@receiver(post_save,sender=VisitService)
def copy_sop_tasks(sender,instance,created,**kwargs):
    if created:
        transaction.on_commit(lambda: build_visit_tasks(instance.visit))
