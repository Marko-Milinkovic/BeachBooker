from decimal import Decimal, InvalidOperation

from django.db import transaction

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
