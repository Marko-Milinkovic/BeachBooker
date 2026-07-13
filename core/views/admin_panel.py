from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.models import UserRole
from core.services.admin_panel import get_overview, list_logs, list_users

ADMIN_TABS = ("overview", "users", "activity")


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != UserRole.ADMIN or not request.user.is_active:
            return redirect("explore")
        return view_func(request, *args, **kwargs)

    return wrapper


@admin_required
def dashboard(request):
    active_tab = request.GET.get("tab", "overview")
    if active_tab not in ADMIN_TABS:
        active_tab = "overview"

    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()
    action = request.GET.get("action", "").strip()
    date_from = request.GET.get("from", "").strip()
    date_to = request.GET.get("to", "").strip()

    overview = get_overview(request.user)
    users = list_users(request.user, q=q, role=role, status=status)
    logs = list_logs(
        request.user,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )

    return render(
        request,
        "core/admin_panel.html",
        {
            "active_nav": "admin",
            "active_tab": active_tab,
            "overview": overview,
            "users": users,
            "logs": logs,
            "q": q,
            "role_filter": role,
            "status_filter": status,
            "action_filter": action,
            "date_from": date_from,
            "date_to": date_to,
            "roles": (
                UserRole.REGISTERED,
                UserRole.OWNER,
                UserRole.ADMIN,
            ),
        },
    )
