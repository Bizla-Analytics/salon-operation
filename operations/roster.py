from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models import BranchDuty, VisitService


def employee_services(user):
    """Current work plus own carried-over home/previous-cover assignments.

    Home membership or a historical duty authorizes only the employee's own
    older assignment, not general branch records. Leave still blocks execution.
    """
    branch = working_branch(user)
    if branch is None:
        return VisitService.objects.none()
    previous_cover = BranchDuty.objects.filter(
        user=user, status='WORK', branch_id=OuterRef('visit__branch_id'),
        date=OuterRef('assigned_at__date'), date__lt=timezone.localdate(),
    )
    return VisitService.objects.filter(
        employee=user, status__in=['ASSIGNED', 'IN_PROGRESS', 'PAUSED'],
    ).exclude(visit__status__in=['CLOSED', 'INVOICED', 'CANCELLED']).annotate(
        historical_cover=Exists(previous_cover),
    ).filter(
        Q(visit__branch=branch) | Q(historical_cover=True)
        | Q(visit__branch=user.profile.branch, assigned_at__date__lt=timezone.localdate())
    )


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
