from .roster import working_branch


def acting_branch(request):
    user = request.user
    profile = getattr(user, "profile", None) if user.is_authenticated else None
    context = {'can_manage_records': bool(user.is_authenticated and user.is_staff and (
        user.is_superuser or user.has_module_perms('operations')
    )), 'acting_branch': None}
    if profile and profile.role == "GENERAL_MANAGER":
        context['acting_branch'] = working_branch(user)
    return context
