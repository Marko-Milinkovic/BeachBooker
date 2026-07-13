from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum

from core.models import (
    BeachBar,
    Bundle,
    Reservation,
    ReservationBundle,
    ReservationStatus,
    Sunbed,
    SunbedCategory,
)
from core.services.beach_bar import get_reserved_sunbed_ids, parse_filter_date

ZONE_STYLES = (
    ("amber", "var(--amber)"),
    ("green", "var(--green)"),
    ("purple", "#7C3AED"),
    ("rose", "var(--rose)"),
    ("teal", "var(--teal)"),
)
ADDON_STYLES = (
    ("teal", "var(--teal)"),
    ("amber", "var(--amber)"),
    ("purple", "#7C3AED"),
    ("green", "var(--green)"),
    ("rose", "var(--rose)"),
)


class OwnerAccessError(Exception):
    def __init__(self, message, code="forbidden"):
        self.message = message
        self.code = code
        super().__init__(message)


DEMO_SHOWCASE_BAR = "Riccardo Beach Bar"


def get_owner_bar(user):
    """Return the owner's primary beach bar, or None.

    MVP still assumes one active bar in the UI. When an owner has several,
    prefer the demo showcase bar, then the bar with the most sunbeds.
    """
    if not user.is_authenticated:
        return None
    bars = BeachBar.objects.filter(owner=user)
    showcase = bars.filter(name=DEMO_SHOWCASE_BAR).first()
    if showcase is not None:
        return showcase
    return bars.annotate(sunbed_count=Count("sunbeds")).order_by(
        "-sunbed_count", "id"
    ).first()


def assert_owner_of_bar(user, beach_bar):
    if not user.is_authenticated or beach_bar.owner_id != user.id:
        raise OwnerAccessError("You do not manage this beach bar.")


def user_owns_bar(user, beach_bar):
    return beach_bar.owner_id == user.id


def _pct_change(current, baseline):
    """Return percent change, or None when baseline is zero."""
    if baseline is None:
        return None
    baseline = Decimal(baseline) if not isinstance(baseline, Decimal) else baseline
    current = Decimal(current) if not isinstance(current, Decimal) else current
    if baseline == 0:
        return None
    return round(float((current - baseline) * 100 / baseline))


def _trend_entry(current, yesterday, last_week):
    return {
        "vs_yesterday_pct": _pct_change(current, yesterday),
        "vs_last_week_pct": _pct_change(current, last_week),
        "yesterday_value": yesterday,
        "last_week_value": last_week,
    }


def _day_snapshot(beach_bar, filter_date):
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
    spot_revenue = active_reservations.aggregate(
        total=Sum("price_at_booking")
    )["total"] or Decimal("0")
    reservation_bundle_qs = ReservationBundle.objects.filter(
        reservation__in=active_reservations
    )
    bundle_revenue = reservation_bundle_qs.aggregate(
        total=Sum("price_at_booking")
    )["total"] or Decimal("0")
    revenue = spot_revenue + bundle_revenue

    occupancy_pct = 0
    if total_spots:
        occupancy_pct = round(taken_spots * 100 / total_spots)

    category_stats = []
    category_revenue = []
    categories = SunbedCategory.objects.filter(beach_bar=beach_bar).order_by("price")
    max_zone_revenue = Decimal("0")
    zone_rows = []
    for index, category in enumerate(categories):
        dot, color = ZONE_STYLES[index % len(ZONE_STYLES)]
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
                "dot": dot,
                "color": color,
            }
        )
        zone_rev = active_reservations.filter(sunbed__category=category).aggregate(
            total=Sum("price_at_booking")
        )["total"] or Decimal("0")
        zone_rows.append(
            {
                "name": category.name,
                "revenue": zone_rev,
                "dot": dot,
                "color": color,
            }
        )
        if zone_rev > max_zone_revenue:
            max_zone_revenue = zone_rev

    for row in zone_rows:
        pct = 0
        if max_zone_revenue:
            pct = round(float(row["revenue"] * 100 / max_zone_revenue))
        category_revenue.append({**row, "pct": pct})

    bundle_stats = []
    bundles = Bundle.objects.filter(beach_bar=beach_bar).order_by("name")
    for index, bundle in enumerate(bundles):
        dot, color = ADDON_STYLES[index % len(ADDON_STYLES)]
        sold_rows = reservation_bundle_qs.filter(bundle=bundle)
        sold = sold_rows.count()
        sold_revenue = sold_rows.aggregate(total=Sum("price_at_booking"))[
            "total"
        ] or Decimal("0")
        if sold or bundle.is_active:
            bundle_stats.append(
                {
                    "name": bundle.name,
                    "sold": sold,
                    "revenue": sold_revenue,
                    "dot": dot,
                    "color": color,
                }
            )

    circumference = 327  # 2 * pi * 52, matches prototype SVG ring
    ring_offset = round(circumference * (100 - occupancy_pct) / 100)

    return {
        "date": filter_date.isoformat(),
        "bookings_count": bookings_count,
        "revenue": revenue,
        "spot_revenue": spot_revenue,
        "bundle_revenue_total": bundle_revenue,
        "occupancy_pct": occupancy_pct,
        "total_spots": total_spots,
        "taken_spots": taken_spots,
        "free_spots": free_spots,
        "category_stats": category_stats,
        "category_revenue": category_revenue,
        "bundle_stats": bundle_stats,
        "ring_circumference": circumference,
        "ring_dashoffset": ring_offset,
        "has_bookings": bookings_count > 0,
    }


def get_dashboard_overview(beach_bar, filter_date):
    overview = _day_snapshot(beach_bar, filter_date)
    yesterday = _day_snapshot(beach_bar, filter_date - timedelta(days=1))
    last_week = _day_snapshot(beach_bar, filter_date - timedelta(days=7))

    overview["trends"] = {
        "bookings_count": _trend_entry(
            overview["bookings_count"],
            yesterday["bookings_count"],
            last_week["bookings_count"],
        ),
        "revenue": _trend_entry(
            overview["revenue"],
            yesterday["revenue"],
            last_week["revenue"],
        ),
        "occupancy_pct": _trend_entry(
            overview["occupancy_pct"],
            yesterday["occupancy_pct"],
            last_week["occupancy_pct"],
        ),
        "free_spots": _trend_entry(
            overview["free_spots"],
            yesterday["free_spots"],
            last_week["free_spots"],
        ),
    }
    return overview


def get_bar_reservations(beach_bar, filter_date=None, status=""):
    queryset = (
        Reservation.objects.filter(sunbed__beach_bar=beach_bar)
        .select_related("user", "sunbed", "sunbed__category")
        .prefetch_related("reservationbundle_set__bundle")
        .order_by("-reservation_date", "-created_at")
    )
    if filter_date is not None:
        queryset = queryset.filter(reservation_date=filter_date)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def parse_owner_date(raw):
    return parse_filter_date(raw)
