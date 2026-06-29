from datetime import date

from django.db import transaction
from django.db.models import Max

from core.models import Reservation, ReservationStatus, Sunbed, SunbedCategory

MIN_ROWS = 1
MAX_ROWS = 12
MIN_COLS = 1
MAX_COLS = 20
DEFAULT_ROWS = 4
DEFAULT_COLS = 10

CATEGORY_LABEL_PREFIX = {
    "Premium": "P",
    "Standard": "S",
    "Lazy Bag": "L",
    "Cabana": "C",
}


class LayoutError(Exception):
    def __init__(self, message, code="layout_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _category_prefix(category_name):
    if category_name in CATEGORY_LABEL_PREFIX:
        return CATEGORY_LABEL_PREFIX[category_name]
    return (category_name[:1] or "S").upper()


def _infer_grid_size(beach_bar):
    stats = Sunbed.objects.filter(beach_bar=beach_bar).aggregate(
        max_row=Max("grid_row"),
        max_col=Max("grid_col"),
    )
    max_row = stats["max_row"]
    max_col = stats["max_col"]
    rows = max((max_row + 1) if max_row is not None else 0, DEFAULT_ROWS)
    cols = max((max_col + 1) if max_col is not None else 0, DEFAULT_COLS)
    return rows, cols


def _categories_for_bar(beach_bar):
    return list(SunbedCategory.objects.filter(beach_bar=beach_bar).order_by("name"))


def _active_reservation_exists(sunbed):
    return Reservation.objects.filter(
        sunbed=sunbed,
        status=ReservationStatus.ACTIVE,
        reservation_date__gte=date.today(),
    ).exists()


def _has_reservation_history(sunbed):
    return Reservation.objects.filter(sunbed=sunbed).exists()


def _assign_labels(beach_bar):
    categories = _categories_for_bar(beach_bar)
    for category in categories:
        prefix = _category_prefix(category.name)
        sunbeds = Sunbed.objects.filter(
            beach_bar=beach_bar,
            category=category,
        ).order_by("grid_row", "grid_col")
        for index, sunbed in enumerate(sunbeds, start=1):
            label = f"{prefix}{index}"
            if sunbed.label != label:
                sunbed.label = label
                sunbed.save(update_fields=["label"])


def get_layout_editor_payload(beach_bar):
    rows, cols = _infer_grid_size(beach_bar)
    categories = _categories_for_bar(beach_bar)
    grid = [[None for _ in range(cols)] for _ in range(rows)]

    sunbeds = Sunbed.objects.filter(beach_bar=beach_bar).select_related("category")
    for sunbed in sunbeds:
        if sunbed.grid_row < rows and sunbed.grid_col < cols:
            grid[sunbed.grid_row][sunbed.grid_col] = {
                "sunbed_id": sunbed.id,
                "category_id": sunbed.category_id,
                "label": sunbed.label,
            }

    return {
        "rows": rows,
        "cols": cols,
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "prefix": _category_prefix(category.name),
            }
            for category in categories
        ],
        "cells": grid,
    }


def _parse_cells(cells, rows, cols):
    if not isinstance(cells, list):
        raise LayoutError("cells must be a list.", "invalid_cells")

    parsed = []
    seen = set()
    for item in cells:
        if not isinstance(item, dict):
            raise LayoutError("Invalid cell entry.", "invalid_cells")
        try:
            row = int(item["row"])
            col = int(item["col"])
            category_id = int(item["category_id"])
        except (KeyError, TypeError, ValueError):
            raise LayoutError("Invalid cell entry.", "invalid_cells")

        if row < 0 or row >= rows or col < 0 or col >= cols:
            raise LayoutError("Cell out of grid bounds.", "invalid_cells")

        position = (row, col)
        if position in seen:
            raise LayoutError("Duplicate cell in layout.", "invalid_cells")
        seen.add(position)

        sunbed_id = item.get("sunbed_id")
        if sunbed_id is not None:
            try:
                sunbed_id = int(sunbed_id)
            except (TypeError, ValueError):
                raise LayoutError("Invalid sunbed id.", "invalid_cells")

        parsed.append(
            {
                "row": row,
                "col": col,
                "category_id": category_id,
                "sunbed_id": sunbed_id,
            }
        )
    return parsed


@transaction.atomic
def save_bar_layout(beach_bar, rows, cols, cells):
    try:
        rows = int(rows)
        cols = int(cols)
    except (TypeError, ValueError):
        raise LayoutError("Invalid grid size.", "invalid_grid")

    if not (MIN_ROWS <= rows <= MAX_ROWS and MIN_COLS <= cols <= MAX_COLS):
        raise LayoutError("Grid size out of allowed range.", "invalid_grid")

    categories = {
        category.id: category
        for category in SunbedCategory.objects.filter(beach_bar=beach_bar)
    }
    if not categories:
        raise LayoutError(
            "Add sunbed categories before editing the layout.",
            "no_categories",
        )

    parsed_cells = _parse_cells(cells, rows, cols)
    for cell in parsed_cells:
        if cell["category_id"] not in categories:
            raise LayoutError("Invalid category for this beach bar.", "invalid_category")

    existing = {
        sunbed.id: sunbed
        for sunbed in Sunbed.objects.filter(beach_bar=beach_bar).select_related(
            "category"
        )
    }
    claimed_ids = set()
    for cell in parsed_cells:
        sunbed_id = cell["sunbed_id"]
        if sunbed_id is None:
            continue
        if sunbed_id in claimed_ids:
            raise LayoutError("Duplicate sunbed in layout.", "invalid_cells")
        sunbed = existing.get(sunbed_id)
        if sunbed is None:
            raise LayoutError("Invalid sunbed for this beach bar.", "invalid_cells")
        claimed_ids.add(sunbed_id)

    for cell in parsed_cells:
        sunbed_id = cell["sunbed_id"]
        if sunbed_id is None:
            continue
        sunbed = existing[sunbed_id]
        if _active_reservation_exists(sunbed) and (
            sunbed.grid_row != cell["row"] or sunbed.grid_col != cell["col"]
        ):
            raise LayoutError(
                f"Spot {sunbed.label} has an active booking and cannot be moved.",
                "has_active_bookings",
            )

    for sunbed_id, sunbed in existing.items():
        if sunbed_id in claimed_ids:
            continue
        if _active_reservation_exists(sunbed):
            raise LayoutError(
                f"Spot {sunbed.label} has an active booking and cannot be removed.",
                "has_active_bookings",
            )
        if _has_reservation_history(sunbed):
            raise LayoutError(
                f"Spot {sunbed.label} has booking history and cannot be removed.",
                "has_booking_history",
            )

    for sunbed_id, sunbed in existing.items():
        if sunbed_id not in claimed_ids:
            sunbed.delete()

    for cell in parsed_cells:
        category = categories[cell["category_id"]]
        sunbed_id = cell["sunbed_id"]
        if sunbed_id is not None:
            sunbed = existing[sunbed_id]
            sunbed.grid_row = cell["row"]
            sunbed.grid_col = cell["col"]
            sunbed.category = category
            sunbed.save(update_fields=["grid_row", "grid_col", "category"])
        else:
            Sunbed.objects.create(
                beach_bar=beach_bar,
                category=category,
                grid_row=cell["row"],
                grid_col=cell["col"],
                label=f"__tmp_{cell['row']}_{cell['col']}",
            )

    _assign_labels(beach_bar)
    return get_layout_editor_payload(beach_bar)
