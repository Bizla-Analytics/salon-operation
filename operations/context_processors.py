from .roster import working_branch


def acting_branch(request):
    user = request.user
    profile = getattr(user, "profile", None) if user.is_authenticated else None
    if profile and profile.role == "GENERAL_MANAGER":
        return {"acting_branch": working_branch(user)}
    return {"acting_branch": None}
