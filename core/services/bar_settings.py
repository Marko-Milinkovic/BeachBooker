from datetime import datetime, time

from django.db import transaction

from core.models import Amenity, BeachBarAmenity


class SettingsError(Exception):
    def __init__(self, message, code="settings_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_time(raw, field_name):
    if raw is None or str(raw).strip() == "":
        raise SettingsError(f"{field_name} is required.", "invalid_hours")
    text = str(raw).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise SettingsError(f"Invalid {field_name}.", "invalid_hours")


def _clean_text(raw, field_name, required=True, max_length=None):
    if raw is None:
        value = ""
    else:
        value = str(raw).strip()
    if required and not value:
        raise SettingsError(f"{field_name} is required.", f"invalid_{field_name}")
    if max_length is not None and len(value) > max_length:
        raise SettingsError(f"{field_name} is too long.", f"invalid_{field_name}")
    return value


def get_bar_settings_payload(beach_bar):
    selected_ids = set(
        BeachBarAmenity.objects.filter(beach_bar=beach_bar).values_list(
            "amenity_id", flat=True
        )
    )
    amenities = [
        {
            "id": amenity.id,
            "name": amenity.name,
            "selected": amenity.id in selected_ids,
        }
        for amenity in Amenity.objects.order_by("name")
    ]
    return {
        "name": beach_bar.name,
        "address": beach_bar.address,
        "city": beach_bar.city,
        "description": beach_bar.description or "",
        "opening_time": beach_bar.opening_time.strftime("%H:%M"),
        "closing_time": beach_bar.closing_time.strftime("%H:%M"),
        "map_url": beach_bar.map_url or "",
        "amenities": amenities,
    }


@transaction.atomic
def update_bar_settings(
    beach_bar,
    name,
    address,
    city,
    description,
    opening_time,
    closing_time,
    map_url,
    amenity_ids,
):
    name = _clean_text(name, "name", required=True, max_length=120)
    address = _clean_text(address, "address", required=True, max_length=255)
    city = _clean_text(city, "city", required=True, max_length=80)
    description = _clean_text(description, "description", required=False)
    map_url = _clean_text(map_url, "map_url", required=False, max_length=512)

    open_time = _parse_time(opening_time, "opening_time")
    close_time = _parse_time(closing_time, "closing_time")
    if open_time >= close_time:
        raise SettingsError(
            "Opening time must be before closing time.",
            "invalid_hours",
        )

    if amenity_ids is None:
        amenity_ids = []
    if not isinstance(amenity_ids, (list, tuple)):
        raise SettingsError("amenity_ids must be a list.", "invalid_amenities")

    parsed_ids = []
    for item in amenity_ids:
        try:
            parsed_ids.append(int(item))
        except (TypeError, ValueError):
            raise SettingsError("Invalid amenity id.", "invalid_amenities")

    if len(parsed_ids) != len(set(parsed_ids)):
        raise SettingsError("Duplicate amenity id.", "invalid_amenities")

    if parsed_ids:
        found = set(
            Amenity.objects.filter(id__in=parsed_ids).values_list("id", flat=True)
        )
        if found != set(parsed_ids):
            raise SettingsError("Unknown amenity.", "invalid_amenities")

    beach_bar.name = name
    beach_bar.address = address
    beach_bar.city = city
    beach_bar.description = description or None
    beach_bar.opening_time = open_time
    beach_bar.closing_time = close_time
    beach_bar.map_url = map_url or None
    beach_bar.save(
        update_fields=[
            "name",
            "address",
            "city",
            "description",
            "opening_time",
            "closing_time",
            "map_url",
        ]
    )

    BeachBarAmenity.objects.filter(beach_bar=beach_bar).delete()
    BeachBarAmenity.objects.bulk_create(
        [
            BeachBarAmenity(beach_bar=beach_bar, amenity_id=amenity_id)
            for amenity_id in parsed_ids
        ]
    )

    return get_bar_settings_payload(beach_bar)
