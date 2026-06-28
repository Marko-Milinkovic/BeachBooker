from decimal import Decimal

from django.db.models import Sum

from core.models import BeachBar, Reservation, ReservationStatus, Sunbed, SunbedCategory, User
from core.services.beach_bar import get_reserved_sunbed_ids, parse_filter_date


class OwnerAccessError(Exception):
    def __init__(self, message, code="forbidden"):
        self.message = message
        self.code = code
        super().__init__(message)


def get_owner_bar(user):
    """MVP: one bar per owner — returns the owner's beach bar or None."""
    if not user.is_authenticated:
        return None
    return BeachBar.objects.filter(owner=user).order_by("id").first()


def assert_owner_of_bar(user, beach_bar):
    bar = get_owner_bar(user)
    if bar is None or bar.id != beach_bar.id:
        raise OwnerAccessError("You do not manage this beach bar.")


def user_owns_bar(user, beach_bar):
    return beach_bar.owner_id == user.id


def get_dashboard_overview(beach_bar, filter_date):
    total_spots = Sunbed.objects.filter(beach_bar=beach_bar).count()
    reserved_ids = get_reserved_sunbed_ids(beach_bar, filter_date)
    taken_spots = len(reserved_ids)
    free_spots = max(total_spots - taken_spots, 0)

    active_reservations = Reservation.objects.filter(
        sunbed__beach_bar=beach_bar,
        reservation_date=filter_date,
        status=ReservationStatus.ACTIVE,
    )
    bookings_count = active_reservations.count()
    revenue = active_reservations.aggregate(total=Sum("price_at_booking"))["total"] or Decimal(
        "0"
    )

    occupancy_pct = 0
    if total_spots:
        occupancy_pct = round(taken_spots * 100 / total_spots)

    category_stats = []
    categories = SunbedCategory.objects.filter(beach_bar=beach_bar).order_by("price")
    for category in categories:
        category_sunbed_ids = set(
            Sunbed.objects.filter(beach_bar=beach_bar, category=category).values_list(
                "id", flat=True
            )
        )
        category_taken = len(category_sunbed_ids & reserved_ids)
        category_total = len(category_sunbed_ids)
        category_stats.append(
            {
                "name": category.name,
                "taken": category_taken,
                "total": category_total,
                "pct": round(category_taken * 100 / category_total) if category_total else 0,
            }
        )

    return {
        "date": filter_date.isoformat(),
        "bookings_count": bookings_count,
        "revenue": revenue,
        "occupancy_pct": occupancy_pct,
        "total_spots": total_spots,
        "taken_spots": taken_spots,
        "free_spots": free_spots,
        "category_stats": category_stats,
    }


def get_bar_reservations(beach_bar, filter_date=None, status=""):
    queryset = (
        Reservation.objects.filter(sunbed__beach_bar=beach_bar)
        .select_related("user", "sunbed", "sunbed__category")
        .order_by("-reservation_date", "-created_at")
    )
    if filter_date is not None:
        queryset = queryset.filter(reservation_date=filter_date)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def parse_owner_date(raw):
    return parse_filter_date(raw)
