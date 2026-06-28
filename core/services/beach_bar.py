from datetime import date, timedelta

from django.db.models import Avg, Count, Min

from core.models import BeachBar, Reservation, ReservationStatus, Sunbed

BAR_IMAGES = {
    "Blue Horizon Beach Club": (
        "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=1600&q=80"
    ),
    "Aqua Paradise": (
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1600&q=80"
    ),
}
DEFAULT_BAR_IMAGE = (
    "https://images.unsplash.com/photo-1540541338287-41700207dee6?w=1600&q=80"
)

CATEGORY_CSS = {
    "Premium": ("sb--vip",),
    "Standard": (),
    "Lazy Bag": ("sb--lazy", "sb--shaded"),
    "Cabana": ("sb--cabana", "sb--shaded"),
}


def parse_filter_date(raw):
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def bar_image_url(bar):
    return BAR_IMAGES.get(bar.name, DEFAULT_BAR_IMAGE)


def date_quick_picks(anchor=None, count=5):
    anchor = anchor or date.today()
    picks = []
    for offset in range(count):
        d = anchor + timedelta(days=offset)
        if offset == 0:
            label = "Today"
        elif offset == 1:
            label = "Tomorrow"
        else:
            label = d.strftime("%a %b %d")
        picks.append({"date": d, "label": label})
    return picks


def get_reserved_sunbed_ids(bar, filter_date):
    return set(
        Reservation.objects.filter(
            sunbed__beach_bar=bar,
            reservation_date=filter_date,
            status=ReservationStatus.ACTIVE,
        ).values_list("sunbed_id", flat=True)
    )


def build_sunbed_grid(bar, filter_date):
    reserved_ids = get_reserved_sunbed_ids(bar, filter_date)
    sunbeds = (
        Sunbed.objects.filter(beach_bar=bar)
        .select_related("category")
        .order_by("grid_row", "grid_col")
    )

    rows = {}
    for sunbed in sunbeds:
        is_taken = sunbed.id in reserved_ids
        status_class = "sb--taken" if is_taken else "sb--free"
        category_classes = CATEGORY_CSS.get(sunbed.category.name, ())
        rows.setdefault(sunbed.grid_row, []).append(
            {
                "sunbed": sunbed,
                "label": sunbed.label,
                "category_name": sunbed.category.name,
                "price": sunbed.category.price,
                "is_taken": is_taken,
                "css_classes": " ".join((*category_classes, status_class)),
                "tooltip": f"{sunbed.category.name} · €{sunbed.category.price:.0f}",
            }
        )

    return [rows[row] for row in sorted(rows)]


def serialize_sunbed_grid(grid_rows):
    return [
        [
            {
                "id": cell["sunbed"].id,
                "label": cell["label"],
                "category": cell["category_name"],
                "price": str(cell["price"]),
                "is_taken": cell["is_taken"],
                "css_classes": cell["css_classes"],
            }
            for cell in row
        ]
        for row in grid_rows
    ]


def get_sunbed_map_payload(bar, filter_date=None):
    if filter_date is None:
        filter_date = date.today()

    grid_rows = build_sunbed_grid(bar, filter_date)
    total_spots = Sunbed.objects.filter(beach_bar=bar).count()
    reserved_count = len(get_reserved_sunbed_ids(bar, filter_date))

    return {
        "date": filter_date.isoformat(),
        "free_spots": max(total_spots - reserved_count, 0),
        "total_spots": total_spots,
        "rows": serialize_sunbed_grid(grid_rows),
    }


def get_beach_bar_page_context(bar, filter_date=None):
    if filter_date is None:
        filter_date = date.today()

    stats = BeachBar.objects.filter(pk=bar.pk).annotate(
        min_price=Min("sunbed_categories__price"),
        total_spots=Count("sunbeds", distinct=True),
        avg_rating=Avg("reviews__rating"),
        review_count=Count("reviews", distinct=True),
    ).first()

    reserved_count = len(get_reserved_sunbed_ids(bar, filter_date))
    amenities = [link.amenity.name for link in bar.beachbaramenity_set.select_related("amenity")]
    categories = list(bar.sunbed_categories.order_by("price"))

    return {
        "bar": bar,
        "filter_date": filter_date,
        "today": date.today(),
        "image_url": bar_image_url(bar),
        "amenities": amenities,
        "categories": categories,
        "min_price": stats.min_price,
        "total_spots": stats.total_spots,
        "free_spots": max(stats.total_spots - reserved_count, 0),
        "avg_rating": stats.avg_rating,
        "review_count": stats.review_count,
        "date_quick_picks": date_quick_picks(),
        "grid_rows": build_sunbed_grid(bar, filter_date),
    }
