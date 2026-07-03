from decimal import Decimal

from django.db import transaction

from core.models import Amenity, BeachBar, BeachBarAmenity, SunbedCategory, UserRole
from core.services.bar_settings import SettingsError, _clean_text, _parse_time
from core.services.owner import get_owner_bar

DEFAULT_CATEGORIES = (
    ("Standard", Decimal("15.00")),
    ("Premium", Decimal("25.00")),
)


class OnboardingError(Exception):
    def __init__(self, message, code="onboarding_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def get_setup_form_payload():
    amenities = [
        {"id": amenity.id, "name": amenity.name, "selected": False}
        for amenity in Amenity.objects.order_by("name")
    ]
    return {
        "name": "",
        "address": "",
        "city": "",
        "description": "",
        "opening_time": "08:00",
        "closing_time": "20:00",
        "map_url": "",
        "amenities": amenities,
    }


@transaction.atomic
def create_owner_bar(
    owner,
    name,
    address,
    city,
    description,
    opening_time,
    closing_time,
    map_url,
    amenity_ids,
):
    if owner.role != UserRole.OWNER:
        raise OnboardingError("Owner access required.", "forbidden")

    if get_owner_bar(owner) is not None:
        raise OnboardingError(
            "This account already has a beach bar.",
            "already_has_bar",
        )

    try:
        name = _clean_text(name, "name", required=True, max_length=120)
        address = _clean_text(address, "address", required=True, max_length=255)
        city = _clean_text(city, "city", required=True, max_length=80)
        description = _clean_text(description, "description", required=False)
        map_url = _clean_text(map_url, "map_url", required=False, max_length=512)
        open_time = _parse_time(opening_time, "opening_time")
        close_time = _parse_time(closing_time, "closing_time")
    except SettingsError as exc:
        raise OnboardingError(exc.message, exc.code) from exc

    if open_time >= close_time:
        raise OnboardingError(
            "Opening time must be before closing time.",
            "invalid_hours",
        )

    if amenity_ids is None:
        amenity_ids = []
    if not isinstance(amenity_ids, (list, tuple)):
        raise OnboardingError("amenity_ids must be a list.", "invalid_amenities")

    parsed_ids = []
    for item in amenity_ids:
        try:
            parsed_ids.append(int(item))
        except (TypeError, ValueError):
            raise OnboardingError("Invalid amenity id.", "invalid_amenities")

    if len(parsed_ids) != len(set(parsed_ids)):
        raise OnboardingError("Duplicate amenity id.", "invalid_amenities")

    if parsed_ids:
        found = set(
            Amenity.objects.filter(id__in=parsed_ids).values_list("id", flat=True)
        )
        if found != set(parsed_ids):
            raise OnboardingError("Unknown amenity.", "invalid_amenities")

    bar = BeachBar.objects.create(
        owner=owner,
        name=name,
        address=address,
        city=city,
        description=description or None,
        opening_time=open_time,
        closing_time=close_time,
        map_url=map_url or None,
    )

    BeachBarAmenity.objects.bulk_create(
        [
            BeachBarAmenity(beach_bar=bar, amenity_id=amenity_id)
            for amenity_id in parsed_ids
        ]
    )

    for category_name, price in DEFAULT_CATEGORIES:
        SunbedCategory.objects.create(
            beach_bar=bar,
            name=category_name,
            price=price,
        )

    return bar
