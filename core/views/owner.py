from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.models import UserRole

OWNER_TABS = ("overview", "reservations", "pricing", "bundles")
from core.services.beach_bar import parse_filter_date
from core.services.bundles import list_bundles
from core.services.owner import (
    get_bar_reservations,
    get_dashboard_overview,
    get_owner_bar,
)
from core.services.reservations import get_reservation_line_total


def owner_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != UserRole.OWNER:
            return redirect("explore")
        bar = get_owner_bar(request.user)
        if bar is None:
            return render(
                request,
                "core/owner_no_bar.html",
                {"active_nav": "owner"},
                status=404,
            )
        request.owner_bar = bar
        return view_func(request, *args, **kwargs)

    return wrapper


@owner_required
def dashboard(request):
    filter_date = parse_filter_date(request.GET.get("date"))
    status_filter = request.GET.get("status", "").strip()
    active_tab = request.GET.get("tab", "overview")
    if active_tab not in OWNER_TABS:
        active_tab = "overview"

    overview = get_dashboard_overview(request.owner_bar, filter_date)
    res_filter_date = filter_date if active_tab == "reservations" else None
    reservations = list(
        get_bar_reservations(
            request.owner_bar,
            filter_date=res_filter_date,
            status=status_filter,
        )
    )
    for reservation in reservations:
        reservation.line_total = get_reservation_line_total(reservation)
    categories = list(
        request.owner_bar.sunbed_categories.order_by("price", "name")
    )
    bundles = list_bundles(request.owner_bar)

    return render(
        request,
        "core/owner_dashboard.html",
        {
            "active_nav": "owner",
            "bar": request.owner_bar,
            "filter_date": filter_date,
            "status_filter": status_filter,
            "active_tab": active_tab,
            "overview": overview,
            "reservations": reservations,
            "categories": categories,
            "bundles": bundles,
            "today": filter_date,
        },
    )
