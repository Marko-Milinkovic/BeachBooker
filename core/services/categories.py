from decimal import Decimal, InvalidOperation

from django.db import transaction
from core.models import Sunbed, SunbedCategory


class CategoryError(Exception):
    def __init__(self, message, code="category_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_price(raw):
    try:
        price = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise CategoryError("Invalid price value.", "invalid_price")
    if price < 0:
        raise CategoryError("Price cannot be negative.", "invalid_price")
    return price.quantize(Decimal("0.01"))


def _clean_name(raw):
    name = (raw or "").strip()
    if not name:
        raise CategoryError("Category name is required.", "invalid_name")
    if len(name) > 80:
        raise CategoryError("Category name is too long.", "invalid_name")
    return name


def list_categories(beach_bar):
    return SunbedCategory.objects.filter(beach_bar=beach_bar).order_by("price", "name")


def get_owner_category(beach_bar, category_id):
    try:
        return SunbedCategory.objects.get(pk=category_id, beach_bar=beach_bar)
    except SunbedCategory.DoesNotExist:
        raise CategoryError("Category not found.", "not_found")


def _duplicate_name_exists(beach_bar, name, exclude_id=None):
    queryset = SunbedCategory.objects.filter(beach_bar=beach_bar).filter(
        name__iexact=name
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset.exists()


def serialize_category(category):
    return {
        "id": category.id,
        "name": category.name,
        "price": str(category.price),
        "description": category.description or "",
        "sunbed_count": Sunbed.objects.filter(category=category).count(),
    }


@transaction.atomic
def create_category(beach_bar, name, price, description=None):
    name = _clean_name(name)
    if _duplicate_name_exists(beach_bar, name):
        raise CategoryError(
            "A category with this name already exists.",
            "duplicate_name",
        )
    description = (description or "").strip() or None
    if description and len(description) > 255:
        raise CategoryError("Description is too long.", "invalid_description")

    category = SunbedCategory.objects.create(
        beach_bar=beach_bar,
        name=name,
        price=_parse_price(price),
        description=description,
    )
    return category


@transaction.atomic
def update_category(beach_bar, category_id, name, price, description=None):
    category = get_owner_category(beach_bar, category_id)
    name = _clean_name(name)
    if _duplicate_name_exists(beach_bar, name, exclude_id=category.id):
        raise CategoryError(
            "A category with this name already exists.",
            "duplicate_name",
        )
    description = (description or "").strip() or None
    if description and len(description) > 255:
        raise CategoryError("Description is too long.", "invalid_description")

    category.name = name
    category.price = _parse_price(price)
    category.description = description
    category.save(update_fields=["name", "price", "description"])
    return category


@transaction.atomic
def delete_category(beach_bar, category_id):
    category = get_owner_category(beach_bar, category_id)
    if Sunbed.objects.filter(category=category).exists():
        raise CategoryError(
            f"Category {category.name} has sunbeds on the layout and cannot be deleted.",
            "has_sunbeds",
        )
    category.delete()
