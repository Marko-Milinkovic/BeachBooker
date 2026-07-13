import json
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import BeachBar, Reservation, UserRole
from core.services.beach_bar import get_sunbed_map_payload, parse_filter_date
from core.services.categories import (
    CategoryError,
    create_category,
    delete_category,
    serialize_category,
    update_category,
)
from core.services.bundles import (
    BundleError,
    create_bundle,
    list_bundles,
    serialize_bundle,
    set_bundle_active,
    update_bundle,
)
from core.services.bar_settings import (
    SettingsError,
    get_bar_settings_payload,
    update_bar_settings,
)
from core.services.explore import (
    ExploreError,
    amenity_ids_from_querydict,
    parse_price_bound,
    parse_sort,
    search_bars_payload,
)
from core.services.layout import (
    LayoutError,
    get_layout_editor_payload,
    save_bar_layout,
)
from core.services.onboarding import (
    OnboardingError,
    create_owner_bar,
    get_setup_form_payload,
)
from core.services.admin_panel import (
    AdminError,
    create_user,
    delete_user,
    get_overview,
    list_logs,
    list_users,
    update_user,
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


def explore_bars(request):
    try:
        amenity_ids = amenity_ids_from_querydict(request.GET)
        min_price = parse_price_bound(request.GET.get("min_price"), "min_price")
        max_price = parse_price_bound(request.GET.get("max_price"), "max_price")
        sort = parse_sort(request.GET.get("sort"))
    except ExploreError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    filter_date = parse_filter_date(request.GET.get("date"))
    payload = search_bars_payload(
        city=request.GET.get("city", ""),
        filter_date=filter_date,
        amenity_ids=amenity_ids,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return JsonResponse(payload)


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

    bundle_ids = payload.get("bundle_ids") or []
    if not isinstance(bundle_ids, list):
        return JsonResponse(
            {"error": "bundle_ids must be a list.", "code": "invalid_bundles"},
            status=400,
        )
    try:
        bundle_ids = [int(bid) for bid in bundle_ids]
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid bundle selection.", "code": "invalid_bundles"},
            status=400,
        )

    try:
        reservations = book_sunbeds(
            request.user, bar, reservation_date, sunbed_ids, bundle_ids
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
def owner_create_category(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        category = create_category(
            request.owner_bar,
            payload.get("name"),
            payload.get("price"),
            payload.get("description"),
        )
    except CategoryError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse({"ok": True, "category": serialize_category(category)})


@owner_required_json
@require_POST
def owner_update_category(request, category_id):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        category = update_category(
            request.owner_bar,
            category_id,
            payload.get("name"),
            payload.get("price"),
            payload.get("description"),
        )
    except CategoryError as exc:
        status = 404 if exc.code == "not_found" else 400
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse({"ok": True, "category": serialize_category(category)})


@owner_required_json
@require_POST
def owner_delete_category(request, category_id):
    try:
        delete_category(request.owner_bar, category_id)
    except CategoryError as exc:
        status = 404 if exc.code == "not_found" else 400
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse({"ok": True})


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


@owner_required_json
def owner_layout(request):
    if request.method == "GET":
        return JsonResponse(get_layout_editor_payload(request.owner_bar))

    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed.", "code": "method_not_allowed"},
            status=405,
        )

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    cells = payload.get("cells")
    if cells is None:
        return JsonResponse(
            {"error": "cells is required.", "code": "invalid_cells"},
            status=400,
        )

    try:
        layout = save_bar_layout(
            request.owner_bar,
            payload.get("rows"),
            payload.get("cols"),
            cells,
        )
    except LayoutError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse({"ok": True, "layout": layout})


@owner_required_json
def owner_settings(request):
    if request.method == "GET":
        return JsonResponse(get_bar_settings_payload(request.owner_bar))

    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed.", "code": "method_not_allowed"},
            status=405,
        )

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        settings_payload = update_bar_settings(
            request.owner_bar,
            name=payload.get("name"),
            address=payload.get("address"),
            city=payload.get("city"),
            description=payload.get("description"),
            opening_time=payload.get("opening_time"),
            closing_time=payload.get("closing_time"),
            map_url=payload.get("map_url"),
            amenity_ids=payload.get("amenity_ids"),
        )
    except SettingsError as exc:
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=400,
        )

    return JsonResponse({"ok": True, "settings": settings_payload})


@login_required_json
def owner_setup(request):
    if request.user.role != UserRole.OWNER:
        return JsonResponse(
            {"error": "Owner access required.", "code": "forbidden"},
            status=403,
        )

    if request.method == "GET":
        if get_owner_bar(request.user) is not None:
            return JsonResponse(
                {"error": "This account already has a beach bar.", "code": "already_has_bar"},
                status=400,
            )
        return JsonResponse(get_setup_form_payload())

    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed.", "code": "method_not_allowed"},
            status=405,
        )

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"error": "Invalid JSON body.", "code": "invalid_json"},
            status=400,
        )

    try:
        bar = create_owner_bar(
            request.user,
            name=payload.get("name"),
            address=payload.get("address"),
            city=payload.get("city"),
            description=payload.get("description"),
            opening_time=payload.get("opening_time"),
            closing_time=payload.get("closing_time"),
            map_url=payload.get("map_url"),
            amenity_ids=payload.get("amenity_ids"),
        )
    except OnboardingError as exc:
        status = 403 if exc.code == "forbidden" else 400
        return JsonResponse(
            {"error": exc.message, "code": exc.code},
            status=status,
        )

    return JsonResponse(
        {
            "ok": True,
            "bar_id": bar.id,
            "redirect_url": "/owner/?tab=settings",
        }
    )


def admin_required_json(view_func):
    @login_required_json
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != UserRole.ADMIN or not request.user.is_active:
            return JsonResponse(
                {"error": "Admin access required.", "code": "forbidden"},
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def _admin_error_response(exc):
    status = 403 if exc.code in ("forbidden",) else 404 if exc.code == "not_found" else 400
    return JsonResponse({"error": exc.message, "code": exc.code}, status=status)


@admin_required_json
def admin_overview(request):
    if request.method != "GET":
        return JsonResponse(
            {"error": "Method not allowed.", "code": "method_not_allowed"},
            status=405,
        )
    try:
        return JsonResponse(get_overview(request.user))
    except AdminError as exc:
        return _admin_error_response(exc)


@admin_required_json
def admin_users(request):
    if request.method == "GET":
        try:
            users = list_users(
                request.user,
                q=request.GET.get("q", ""),
                role=request.GET.get("role", ""),
                status=request.GET.get("status", ""),
            )
        except AdminError as exc:
            return _admin_error_response(exc)
        return JsonResponse({"count": len(users), "users": users})

    if request.method == "POST":
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse(
                {"error": "Invalid JSON body.", "code": "invalid_json"},
                status=400,
            )
        try:
            user = create_user(
                request.user,
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                email=payload.get("email"),
                password=payload.get("password"),
                role=payload.get("role"),
            )
        except AdminError as exc:
            return _admin_error_response(exc)
        return JsonResponse({"ok": True, "user": user}, status=201)

    return JsonResponse(
        {"error": "Method not allowed.", "code": "method_not_allowed"},
        status=405,
    )


@admin_required_json
def admin_user_detail(request, user_id):
    if request.method == "PATCH":
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse(
                {"error": "Invalid JSON body.", "code": "invalid_json"},
                status=400,
            )
        try:
            user = update_user(
                request.user,
                user_id,
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                email=payload.get("email"),
                role=payload.get("role"),
                password=payload.get("password"),
                is_active=payload.get("is_active"),
            )
        except AdminError as exc:
            return _admin_error_response(exc)
        return JsonResponse({"ok": True, "user": user})

    if request.method == "DELETE":
        try:
            result = delete_user(request.user, user_id)
        except AdminError as exc:
            return _admin_error_response(exc)
        return JsonResponse({"ok": True, **result})

    return JsonResponse(
        {"error": "Method not allowed.", "code": "method_not_allowed"},
        status=405,
    )


@admin_required_json
def admin_logs(request):
    if request.method != "GET":
        return JsonResponse(
            {"error": "Method not allowed.", "code": "method_not_allowed"},
            status=405,
        )
    try:
        logs = list_logs(
            request.user,
            action=request.GET.get("action", ""),
            date_from=request.GET.get("from", ""),
            date_to=request.GET.get("to", ""),
        )
    except AdminError as exc:
        return _admin_error_response(exc)
    return JsonResponse({"count": len(logs), "logs": logs})
