from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
def roles_required(*roles):
    def dec(view):
        @login_required
        @wraps(view)
        def wrapper(request,*args,**kwargs):
            p=getattr(request.user,'profile',None)
            if request.user.is_superuser or (p and p.active and p.role in roles): return view(request,*args,**kwargs)
            raise PermissionDenied
        return wrapper
    return dec
