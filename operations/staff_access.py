from django.contrib.auth.models import User

from .roster import working_branch, working_employees


def resettable_employees(actor):
    """Recovery access follows today's duty, never an employee's old home branch."""
    employees = User.objects.filter(
        profile__role='EMPLOYEE', profile__active=True, is_active=True,
        is_staff=False, is_superuser=False,
    )
    if not actor.is_authenticated or not actor.is_active:
        return employees.none()
    profile = getattr(actor, 'profile', None)
    if not profile or not profile.active:
        return employees.none()
    if actor.is_superuser or profile.role == 'GENERAL_MANAGER':
        return employees
    if profile.role == 'MANAGER':
        branch = working_branch(actor)
        if branch:
            return employees.filter(pk__in=working_employees(branch).values('pk'))
    return employees.none()
