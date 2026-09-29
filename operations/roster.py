from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import BranchDuty


def working_branch(user, day=None):
    """Today's roster overrides the home branch; general managers need explicit cover."""
    if not user.is_authenticated or not user.is_active:
        return None
    profile = getattr(user, "profile", None)
    if not profile or not profile.active:
        return None
    day = day or timezone.localdate()
    duty = BranchDuty.objects.select_related("branch").filter(user=user, date=day).first()
    if duty:
        return duty.branch if duty.status == "WORK" else None
    if profile.role == "GENERAL_MANAGER":
        return None
    return profile.branch


def working_employees(branch, day=None):
    """Eligible employees, excluding leave and another branch's cover."""
    day = day or timezone.localdate()
    if branch is None:
        return User.objects.none()
    duties = BranchDuty.objects.filter(date=day)
    return User.objects.filter(
        profile__role="EMPLOYEE", profile__active=True, is_active=True
    ).filter(
        Q(pk__in=duties.filter(status="WORK", branch=branch).values("user_id"))
        | (Q(profile__branch=branch) & ~Q(pk__in=duties.values("user_id")))
    ).distinct()
