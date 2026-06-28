from datetime import date

from django.db.models import Avg, Count, Min
from django.shortcuts import get_object_or_404, render

from core.models import BeachBar, Reservation, ReservationStatus

BAR_IMAGES = {
    "Blue Horizon Beach Club": (
        "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=500&q=80"
    ),
    "Aqua Paradise": (
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=500&q=80"
    ),
}
DEFAULT_BAR_IMAGE = (
    "https://images.unsplash.com/photo-1540541338287-41700207dee6?w=500&q=80"
)


def _parse_explore_date(raw):
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


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
        bar.image_url = BAR_IMAGES.get(bar.name, DEFAULT_BAR_IMAGE)
        result.append(bar)
    return result, filter_date


def index(request):
    return render(request, "core/index.html", {"active_nav": "home"})


def explore(request):
    city = request.GET.get("city", "").strip()
    filter_date = _parse_explore_date(request.GET.get("date"))
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
    return render(
        request,
        "core/beach_bar_stub.html",
        {"active_nav": "explore", "bar": bar},
    )
