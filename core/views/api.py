import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import BeachBar, Reservation
from core.services.beach_bar import get_sunbed_map_payload, parse_filter_date
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
