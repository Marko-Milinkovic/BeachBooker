from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.models import BeachBar, Reservation, ReservationStatus
from core.services.beach_bar import (
    get_beach_bar_page_context,
    parse_filter_date,
)
from core.services.explore import (
    ExploreError,
    amenity_ids_from_querydict,
    list_amenities,
    parse_price_bound,
    parse_sort,
    search_bars,
)
from core.services.reservations import (
    get_reservation_line_total,
    mark_past_reservations_completed,
)


def index(request):
    return render(request, "core/index.html", {"active_nav": "home"})


def explore(request):
    city = request.GET.get("city", "").strip()
    filter_date = parse_filter_date(request.GET.get("date"))
    amenity_ids = []
    min_price = None
    max_price = None
    sort = "name"
    try:
        amenity_ids = amenity_ids_from_querydict(request.GET)
        min_price = parse_price_bound(request.GET.get("min_price"), "min_price")
        max_price = parse_price_bound(request.GET.get("max_price"), "max_price")
        sort = parse_sort(request.GET.get("sort"))
    except ExploreError:
        amenity_ids = []
        min_price = None
        max_price = None
        sort = "name"

    bars = search_bars(
        city=city,
        filter_date=filter_date,
        amenity_ids=amenity_ids,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    amenities = list_amenities()
    selected_amenities = set(amenity_ids)

    return render(
        request,
        "core/explore.html",
        {
            "active_nav": "explore",
            "bars": bars,
            "filter_date": filter_date,
            "city": city,
            "bar_count": len(bars),
            "today": date.today(),
            "amenities": amenities,
            "selected_amenities": selected_amenities,
            "min_price": request.GET.get("min_price", ""),
            "max_price": request.GET.get("max_price", ""),
            "sort": sort,
        },
    )


def beach_bar(request, bar_id):
    bar = get_object_or_404(BeachBar, pk=bar_id)
    filter_date = parse_filter_date(request.GET.get("date"))
    context = get_beach_bar_page_context(bar, filter_date)
    context["active_nav"] = "explore"

    category_names = {c.name for c in context["categories"]}
    context["show_premium_legend"] = "Premium" in category_names
    context["show_lazy_legend"] = "Lazy Bag" in category_names
    context["show_cabana_legend"] = "Cabana" in category_names
    context["show_shade_legend"] = bool(
        category_names.intersection({"Lazy Bag", "Cabana"})
    )

    return render(request, "core/beach_bar.html", context)


@login_required
def my_reservations(request):
    mark_past_reservations_completed(user=request.user)
    reservations = (
        Reservation.objects.filter(user=request.user)
        .select_related("sunbed", "sunbed__beach_bar", "sunbed__category")
        .prefetch_related("reservationbundle_set__bundle")
        .order_by("-reservation_date", "-created_at")
    )
    today = date.today()

    def with_line_totals(items):
        for reservation in items:
            reservation.line_total = get_reservation_line_total(reservation)
        return items

    return render(
        request,
        "core/my_reservations.html",
        {
            "active_nav": "bookings",
            "active_reservations": with_line_totals(
                [
                    r
                    for r in reservations
                    if r.status == ReservationStatus.ACTIVE
                    and r.reservation_date >= today
                ]
            ),
            "past_reservations": with_line_totals(
                [r for r in reservations if r.status == ReservationStatus.COMPLETED]
            ),
            "cancelled_reservations": with_line_totals(
                [r for r in reservations if r.status == ReservationStatus.CANCELLED]
            ),
        },
    )
