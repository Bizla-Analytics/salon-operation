from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .roster import working_branch
def roles_required(*roles):
    def dec(view):
        @login_required
        @wraps(view)
        def wrapper(request,*args,**kwargs):
            p=getattr(request.user,'profile',None)
            if request.user.is_superuser:
                return view(request,*args,**kwargs)
            if p and p.active and request.user.is_active:
                if p.role in roles:
                    if "MANAGER" not in roles or working_branch(request.user):
                        return view(request,*args,**kwargs)
                if "MANAGER" in roles and p.role == "GENERAL_MANAGER" and working_branch(request.user):
                    return view(request,*args,**kwargs)
            raise PermissionDenied
        return wrapper
    return dec
