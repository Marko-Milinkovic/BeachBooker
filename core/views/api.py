import json
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import BeachBar, Reservation, UserRole
from core.services.beach_bar import get_sunbed_map_payload, parse_filter_date
from core.services.bundles import (
    BundleError,
    create_bundle,
    list_bundles,
    serialize_bundle,
    set_bundle_active,
    update_bundle,
)
from core.services.owner import get_owner_bar
from core.services.pricing import PricingError, update_category_prices
from core.services.reservations import (
    BookingError,
    book_sunbeds,
    cancel_reservation,
    parse_booking_date,
    serialize_reservation,
)


def login_required_json(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Authentication required.", "code": "auth_required"},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def owner_required_json(view_func):
    @login_required_json
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != UserRole.OWNER:
            return JsonResponse(
                {"error": "Owner access required.", "code": "forbidden"},
                status=403,
            )
        bar = get_owner_bar(request.user)
        if bar is None:
            return JsonResponse(
                {"error": "No beach bar linked to this account.", "code": "no_bar"},
                status=404,
            )
        request.owner_bar = bar
        return view_func(request, *args, **kwargs)

    return wrapper


def bar_sunbeds(request, bar_id):
    bar = get_object_or_404(BeachBar, pk=bar_id)
    filter_date = parse_filter_date(request.GET.get("date"))
    return JsonResponse(get_sunbed_map_payload(bar, filter_date))


@login_required_json
@require_POST
def book_sunbeds_api(request, bar_id):
    bar = get_object_or_404(BeachBar, pk=bar_id)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    reservation_date = parse_booking_date(payload.get("date"))
    sunbed_ids = payload.get("sunbed_ids") or []
    if not isinstance(sunbed_ids, list):
        return JsonResponse(
            {"error": "sunbed_ids must be a list.", "code": "invalid_spots"},
            status=400,
        )

    try:
        sunbed_ids = [int(sid) for sid in sunbed_ids]
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid spot selection.", "code": "invalid_spots"},
            status=400,
        )

    try:
        reservations = book_sunbeds(
            request.user, bar, reservation_date, sunbed_ids
        )
    except BookingError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "reservations": [serialize_reservation(r) for r in reservations],
        }
    )


@login_required_json
@require_POST
def cancel_reservation_api(request, reservation_id):
    try:
        reservation = cancel_reservation(request.user, reservation_id)
    except BookingError as exc:
        status = 403 if exc.code == "forbidden" else 400
        if exc.code == "not_found":
            status = 404
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse(
        {
            "ok": True,
            "reservation": serialize_reservation(reservation),
        }
    )


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


@owner_required_json
@require_POST
def owner_update_pricing(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    prices = payload.get("prices")
    if not isinstance(prices, list):
        return JsonResponse(
            {"error": "prices must be a list.", "code": "invalid_prices"},
            status=400,
        )

    price_updates = {}
    for item in prices:
        if not isinstance(item, dict):
            return JsonResponse(
                {"error": "Invalid price entry.", "code": "invalid_prices"},
                status=400,
            )
        category_id = item.get("category_id")
        if category_id is None:
            continue
        price_updates[category_id] = item.get("price")

    try:
        categories = update_category_prices(request.owner_bar, price_updates)
    except PricingError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "categories": [
                {
                    "id": category.id,
                    "name": category.name,
                    "price": str(category.price),
                }
                for category in categories
            ],
        }
    )


@owner_required_json
@require_POST
def owner_create_bundle(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        bundle = create_bundle(
            request.owner_bar,
            payload.get("name"),
            payload.get("description"),
            payload.get("price"),
        )
    except BundleError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse({"ok": True, "bundle": serialize_bundle(bundle)})


@owner_required_json
@require_POST
def owner_update_bundle(request, bundle_id):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        bundle = update_bundle(
            request.owner_bar,
            bundle_id,
            payload.get("name"),
            payload.get("description"),
            payload.get("price"),
        )
    except BundleError as exc:
        status = 404 if exc.code == "not_found" else 400
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse({"ok": True, "bundle": serialize_bundle(bundle)})


@owner_required_json
@require_POST
def owner_toggle_bundle(request, bundle_id):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        bundle = set_bundle_active(
            request.owner_bar,
            bundle_id,
            payload.get("is_active", True),
        )
    except BundleError as exc:
        status = 404 if exc.code == "not_found" else 400
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse({"ok": True, "bundle": serialize_bundle(bundle)})
