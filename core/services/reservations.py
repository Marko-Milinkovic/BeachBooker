from datetime import date

from django.db import transaction

from core.models import BeachBar, Reservation, ReservationStatus, Sunbed
from core.services.beach_bar import get_reserved_sunbed_ids, parse_filter_date


class BookingError(Exception):
    def __init__(self, message, code="booking_error"):
        self.message = message
        self.code = code
        super().__init__(message)


@transaction.atomic
def book_sunbeds(user, beach_bar, reservation_date, sunbed_ids):
    if not sunbed_ids:
        raise BookingError("Select at least one spot.", "no_spots")

    unique_ids = list(dict.fromkeys(sunbed_ids))
    sunbeds = list(
        Sunbed.objects.filter(
            id__in=unique_ids,
            beach_bar=beach_bar,
        ).select_related("category")
    )

    if len(sunbeds) != len(unique_ids):
        raise BookingError("Invalid spot selection.", "invalid_spots")

    reserved_ids = get_reserved_sunbed_ids(beach_bar, reservation_date)
    for sunbed in sunbeds:
        if sunbed.id in reserved_ids:
            raise BookingError(
                f"Spot {sunbed.label} is no longer available.",
                "spot_taken",
            )

    reservations = []
    for sunbed in sunbeds:
        existing = Reservation.objects.filter(
            sunbed=sunbed,
            reservation_date=reservation_date,
        ).first()
        if existing:
            if existing.status == ReservationStatus.ACTIVE:
                raise BookingError(
                    f"Spot {sunbed.label} is no longer available.",
                    "spot_taken",
                )
            if existing.status == ReservationStatus.CANCELLED:
                existing.user = user
                existing.status = ReservationStatus.ACTIVE
                existing.price_at_booking = sunbed.category.price
                existing.save(
                    update_fields=["user", "status", "price_at_booking"]
                )
                reservations.append(existing)
                continue
            raise BookingError(
                f"Spot {sunbed.label} is no longer available.",
                "spot_taken",
            )

        reservations.append(
            Reservation.objects.create(
                user=user,
                sunbed=sunbed,
                reservation_date=reservation_date,
                status=ReservationStatus.ACTIVE,
                price_at_booking=sunbed.category.price,
            )
        )
    return reservations


def cancel_reservation(user, reservation_id):
    try:
        reservation = Reservation.objects.select_related(
            "sunbed", "sunbed__beach_bar", "sunbed__beach_bar__owner"
        ).get(pk=reservation_id)
    except Reservation.DoesNotExist:
        raise BookingError("Reservation not found.", "not_found")

    is_guest = reservation.user_id == user.id
    is_bar_owner = reservation.sunbed.beach_bar.owner_id == user.id
    if not (is_guest or is_bar_owner):
        raise BookingError("You cannot cancel this reservation.", "forbidden")

    if reservation.status != ReservationStatus.ACTIVE:
        raise BookingError("Only active reservations can be cancelled.", "not_active")

    reservation.status = ReservationStatus.CANCELLED
    reservation.save(update_fields=["status"])
    return reservation


def mark_past_reservations_completed(user=None):
    queryset = Reservation.objects.filter(
        status=ReservationStatus.ACTIVE,
        reservation_date__lt=date.today(),
    )
    if user is not None:
        queryset = queryset.filter(user=user)
    return queryset.update(status=ReservationStatus.COMPLETED)


def serialize_reservation(reservation):
    bar = reservation.sunbed.beach_bar
    return {
        "id": reservation.id,
        "date": reservation.reservation_date.isoformat(),
        "status": reservation.status,
        "price": str(reservation.price_at_booking),
        "sunbed_id": reservation.sunbed_id,
        "sunbed_label": reservation.sunbed.label,
        "bar_id": bar.id,
        "bar_name": bar.name,
        "bar_city": bar.city,
    }


def parse_booking_date(raw):
    return parse_filter_date(raw)
