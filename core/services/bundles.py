from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum

from core.models import Bundle


class BundleError(Exception):
    def __init__(self, message, code="bundle_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_price(raw):
    try:
        price = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise BundleError("Invalid price value.", "invalid_price")
    if price < 0:
        raise BundleError("Price cannot be negative.", "invalid_price")
    return price.quantize(Decimal("0.01"))


def list_bundles(beach_bar):
    return Bundle.objects.filter(beach_bar=beach_bar).order_by("name")


def list_active_bundles(beach_bar):
    return Bundle.objects.filter(beach_bar=beach_bar, is_active=True).order_by("name")


def resolve_booking_bundles(beach_bar, bundle_ids):
    if not bundle_ids:
        return []

    try:
        unique_ids = list(dict.fromkeys(int(bundle_id) for bundle_id in bundle_ids))
    except (TypeError, ValueError):
        raise BundleError("Invalid bundle selection.", "invalid_bundle")

    bundles = list(
        Bundle.objects.filter(beach_bar=beach_bar, id__in=unique_ids).order_by("name")
    )
    if len(bundles) != len(unique_ids):
        raise BundleError("Invalid bundle selection.", "invalid_bundle")

    inactive = [bundle.name for bundle in bundles if not bundle.is_active]
    if inactive:
        raise BundleError(
            f"Bundle {inactive[0]} is not available.",
            "inactive_bundle",
        )
    return bundles


def attach_bundles_to_reservation(reservation, bundles):
    from core.models import ReservationBundle

    reservation.reservationbundle_set.all().delete()
    for bundle in bundles:
        ReservationBundle.objects.create(
            reservation=reservation,
            bundle=bundle,
            price_at_booking=bundle.price,
        )


def get_reservation_bundle_total(reservation):
    from core.models import ReservationBundle

    total = ReservationBundle.objects.filter(reservation=reservation).aggregate(
        total=Sum("price_at_booking")
    )["total"]
    return total or Decimal("0.00")


def serialize_reservation_bundles(reservation):
    from core.models import ReservationBundle

    rows = ReservationBundle.objects.filter(reservation=reservation).select_related(
        "bundle"
    )
    return [
        {
            "id": row.bundle_id,
            "name": row.bundle.name,
            "price": str(row.price_at_booking),
        }
        for row in rows
    ]


def get_owner_bundle(beach_bar, bundle_id):
    try:
        return Bundle.objects.get(pk=bundle_id, beach_bar=beach_bar)
    except Bundle.DoesNotExist:
        raise BundleError("Bundle not found.", "not_found")


@transaction.atomic
def create_bundle(beach_bar, name, description, price):
    name = (name or "").strip()
    if not name:
        raise BundleError("Bundle name is required.", "invalid_name")
    description = (description or "").strip() or None
    return Bundle.objects.create(
        beach_bar=beach_bar,
        name=name,
        description=description,
        price=_parse_price(price),
        is_active=True,
    )


@transaction.atomic
def update_bundle(beach_bar, bundle_id, name, description, price):
    bundle = get_owner_bundle(beach_bar, bundle_id)
    name = (name or "").strip()
    if not name:
        raise BundleError("Bundle name is required.", "invalid_name")
    bundle.name = name
    bundle.description = (description or "").strip() or None
    bundle.price = _parse_price(price)
    bundle.save(update_fields=["name", "description", "price"])
    return bundle


@transaction.atomic
def set_bundle_active(beach_bar, bundle_id, is_active):
    bundle = get_owner_bundle(beach_bar, bundle_id)
    bundle.is_active = bool(is_active)
    bundle.save(update_fields=["is_active"])
    return bundle


def serialize_bundle(bundle):
    return {
        "id": bundle.id,
        "name": bundle.name,
        "description": bundle.description or "",
        "price": str(bundle.price),
        "is_active": bundle.is_active,
    }
