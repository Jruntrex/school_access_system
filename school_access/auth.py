"""Two hardcoded roles (see `seed_users` management command): every logged-in
account can see the dashboard, but the CRUD-heavy pages (students, classes,
guard, cards, reports, settings) require the admin account (`is_superuser`).
There is no separate role model/table — Django's built-in `is_superuser`
flag on `auth.User` doubles as the "admin" role.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden


def is_admin_user(user) -> bool:
    return user.is_authenticated and user.is_superuser


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not is_admin_user(request.user):
            return HttpResponseForbidden(
                "Доступ до цієї сторінки має лише адміністратор."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped
