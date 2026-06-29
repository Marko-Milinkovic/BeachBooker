from decimal import Decimal, InvalidOperation

from django.db import transaction

from core.models import SunbedCategory


class PricingError(Exception):
    def __init__(self, message, code="pricing_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_price(raw):
    try:
        price = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise PricingError("Invalid price value.", "invalid_price")
    if price < 0:
        raise PricingError("Price cannot be negative.", "invalid_price")
    return price.quantize(Decimal("0.01"))


@transaction.atomic
def update_category_prices(beach_bar, price_updates):
    if not price_updates:
        raise PricingError("No prices to update.", "no_prices")

    categories = {
        category.id: category
        for category in SunbedCategory.objects.filter(beach_bar=beach_bar)
    }
    if not categories:
        raise PricingError("No categories found for this beach bar.", "no_categories")

    updated = []
    for category_id, raw_price in price_updates.items():
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            raise PricingError("Invalid category.", "invalid_category")

        category = categories.get(category_id)
        if category is None:
            raise PricingError("Invalid category for this beach bar.", "invalid_category")

        category.price = _parse_price(raw_price)
        category.save(update_fields=["price"])
        updated.append(category)

    return updated
