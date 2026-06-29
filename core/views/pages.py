from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Min
from django.shortcuts import get_object_or_404, render

from core.models import BeachBar, Reservation, ReservationStatus
from core.services.beach_bar import (
    bar_image_url,
    get_beach_bar_page_context,
    parse_filter_date,
)
from core.services.reservations import (
    get_reservation_line_total,
    mark_past_reservations_completed,
)


def get_explore_bars(city="", filter_date=None):
    if filter_date is None:
        filter_date = date.today()

    bars = BeachBar.objects.annotate(
        min_price=Min("sunbed_categories__price"),
        total_spots=Count("sunbeds", distinct=True),
        avg_rating=Avg("reviews__rating"),
    ).order_by("name")

    if city:
        bars = bars.filter(city__icontains=city)

    result = []
    for bar in bars.distinct():
        reserved = (
            Reservation.objects.filter(
                sunbed__beach_bar=bar,
                reservation_date=filter_date,
                status=ReservationStatus.ACTIVE,
            )
            .values("sunbed_id")
            .distinct()
            .count()
        )
        bar.free_spots = max(bar.total_spots - reserved, 0)
        bar.image_url = bar_image_url(bar)
        result.append(bar)
    return result, filter_date


def index(request):
    return render(request, "core/index.html", {"active_nav": "home"})


def explore(request):
    city = request.GET.get("city", "").strip()
    filter_date = parse_filter_date(request.GET.get("date"))
    bars, filter_date = get_explore_bars(city, filter_date)
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

