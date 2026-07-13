from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, F, Min
from django.urls import reverse

from core.models import Amenity, BeachBar, Reservation, ReservationStatus
from core.services.beach_bar import bar_image_url, parse_filter_date

SORT_NAME = "name"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_RATING_DESC = "rating_desc"
VALID_SORTS = {SORT_NAME, SORT_PRICE_ASC, SORT_PRICE_DESC, SORT_RATING_DESC}
DEFAULT_UNFILTERED_LIMIT = 18


class ExploreError(Exception):
    def __init__(self, message, code="explore_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def list_amenities():
    return list(Amenity.objects.order_by("name").values("id", "name"))


def parse_amenity_ids(raw_ids):
    if raw_ids is None or raw_ids == "":
        return []
    if isinstance(raw_ids, str):
        parts = [part.strip() for part in raw_ids.split(",") if part.strip()]
    elif isinstance(raw_ids, (list, tuple)):
        parts = list(raw_ids)
    else:
        raise ExploreError("Invalid amenity filter.", "invalid_amenities")

    amenity_ids = []
    for part in parts:
        try:
            amenity_ids.append(int(part))
        except (TypeError, ValueError):
            raise ExploreError("Invalid amenity filter.", "invalid_amenities")
    return amenity_ids


def amenity_ids_from_querydict(querydict):
    values = querydict.getlist("amenity_ids")
    if not values:
        return []
    if len(values) == 1:
        return parse_amenity_ids(values[0])
    return parse_amenity_ids(values)


def parse_price_bound(raw, field_name):
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ExploreError(f"Invalid {field_name}.", "invalid_price")
    if value < 0:
        raise ExploreError(f"Invalid {field_name}.", "invalid_price")
    return value


def parse_sort(raw):
    if not raw:
        return SORT_NAME
    sort = str(raw).strip()
    if sort not in VALID_SORTS:
        raise ExploreError("Invalid sort option.", "invalid_sort")
    return sort


def filters_active(city="", amenity_ids=None, min_price=None, max_price=None):
    return bool((city or "").strip()) or bool(amenity_ids) or min_price is not None or max_price is not None


def _free_spots_for_bar(bar, filter_date):
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
    total = bar.total_spots or 0
    return max(total - reserved, 0)


def serialize_bar(bar, filter_date):
    min_price = bar.min_price
    avg_rating = bar.avg_rating
    free_spots = getattr(bar, "free_spots", None)
    if free_spots is None:
        free_spots = _free_spots_for_bar(bar, filter_date)
    image_url = getattr(bar, "image_url", None) or bar_image_url(bar)
    return {
        "id": bar.id,
        "name": bar.name,
        "city": bar.city,
        "image_url": image_url,
        "min_price": str(min_price) if min_price is not None else None,
        "free_spots": free_spots,
        "avg_rating": f"{avg_rating:.1f}" if avg_rating is not None else None,
        "url": f"{reverse('beach_bar', args=[bar.id])}?date={filter_date.isoformat()}",
    }


def search_bars(
    city="",
    filter_date=None,
    amenity_ids=None,
    min_price=None,
    max_price=None,
    sort=SORT_NAME,
):
    filter_date = filter_date or parse_filter_date(None)
    amenity_ids = amenity_ids or []
    city = (city or "").strip()

    bars = BeachBar.objects.annotate(
        min_price=Min("sunbed_categories__price"),
        total_spots=Count("sunbeds", distinct=True),
        avg_rating=Avg("reviews__rating"),
    )

    if city:
        bars = bars.filter(city__icontains=city)

    for amenity_id in amenity_ids:
        bars = bars.filter(beachbaramenity__amenity_id=amenity_id)

    if min_price is not None:
        bars = bars.filter(min_price__gte=min_price)
    if max_price is not None:
        bars = bars.filter(min_price__lte=max_price)

    if sort == SORT_PRICE_ASC:
        bars = bars.order_by(F("min_price").asc(nulls_last=True), "name")
    elif sort == SORT_PRICE_DESC:
        bars = bars.order_by(F("min_price").desc(nulls_last=True), "name")
    elif sort == SORT_RATING_DESC:
        bars = bars.order_by(F("avg_rating").desc(nulls_last=True), "name")
    else:
        bars = bars.order_by("name")

    result = []
    for bar in bars.distinct():
        bar.free_spots = _free_spots_for_bar(bar, filter_date)
        bar.image_url = bar_image_url(bar)
        result.append(bar)

    if not filters_active(city, amenity_ids, min_price, max_price):
        result = result[:DEFAULT_UNFILTERED_LIMIT]

    return result


def search_bars_payload(
    city="",
    filter_date=None,
    amenity_ids=None,
    min_price=None,
    max_price=None,
    sort=SORT_NAME,
):
    filter_date = filter_date or parse_filter_date(None)
    bars = search_bars(
        city=city,
        filter_date=filter_date,
        amenity_ids=amenity_ids,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    serialized = [serialize_bar(bar, filter_date) for bar in bars]
    return {
        "date": filter_date.isoformat(),
        "count": len(serialized),
        "bars": serialized,
    }
