import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from core.models import (
    BeachBar,
    Bundle,
    Reservation,
    ReservationStatus,
    Sunbed,
    SunbedCategory,
    User,
    UserRole,
)
from core.services.beach_bar import get_sunbed_map_payload
from core.services.bundles import (
    BundleError,
    create_bundle,
    list_bundles,
    set_bundle_active,
    update_bundle,
)
from core.services.owner import (
    OwnerAccessError,
    assert_owner_of_bar,
    get_dashboard_overview,
    get_owner_bar,
)
from core.services.pricing import PricingError, update_category_prices
from core.services.reservations import (
    BookingError,
    book_sunbeds,
    cancel_reservation,
    mark_past_reservations_completed,
)


class BookingTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="owner@test.beach",
            password="testpass123",
            first_name="Test",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        cls.guest = User.objects.create_user(
            email="guest@test.beach",
            password="testpass123",
            first_name="Test",
            last_name="Guest",
        )
        cls.other_guest = User.objects.create_user(
            email="other@test.beach",
            password="testpass123",
            first_name="Other",
            last_name="Guest",
        )
        cls.bar = BeachBar.objects.create(
            owner=cls.owner,
            name="Test Beach",
            address="1 Shore Rd",
            city="Budva",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        cls.category = SunbedCategory.objects.create(
            beach_bar=cls.bar,
            name="Standard",
            price=Decimal("25.00"),
        )
        cls.sunbed_a = Sunbed.objects.create(
            beach_bar=cls.bar,
            category=cls.category,
            label="A1",
            grid_row=0,
            grid_col=0,
        )
        cls.sunbed_b = Sunbed.objects.create(
            beach_bar=cls.bar,
            category=cls.category,
            label="A2",
            grid_row=0,
            grid_col=1,
        )
        cls.book_date = date.today() + timedelta(days=14)

    def login_guest(self, client=None):
        client = client or self.client
        client.login(email=self.guest.email, password="testpass123")
        return client

    def api_post(self, client, url, payload=None):
        return client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )


class ReservationServiceTests(BookingTestMixin, TestCase):
    def test_book_free_spot(self):
        reservations = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )
        self.assertEqual(len(reservations), 1)
        reservation = reservations[0]
        self.assertEqual(reservation.user_id, self.guest.id)
        self.assertEqual(reservation.status, ReservationStatus.ACTIVE)
        self.assertEqual(reservation.price_at_booking, Decimal("25.00"))

    def test_book_multiple_spots_atomic(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id, self.sunbed_b.id],
        )
        self.assertEqual(len(reservations), 2)

    def test_reject_taken_spot(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        with self.assertRaises(BookingError) as ctx:
            book_sunbeds(self.other_guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.assertEqual(ctx.exception.code, "spot_taken")

    def test_cancel_reservation(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        cancelled = cancel_reservation(self.guest, reservation.id)
        self.assertEqual(cancelled.status, ReservationStatus.CANCELLED)

    def test_rebook_cancelled_spot_reactivates_row(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        cancel_reservation(self.guest, reservation.id)
        rebound = book_sunbeds(
            self.other_guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.assertEqual(rebound.id, reservation.id)
        self.assertEqual(rebound.user_id, self.other_guest.id)
        self.assertEqual(rebound.status, ReservationStatus.ACTIVE)

    def test_mark_past_reservations_completed(self):
        past_date = date.today() - timedelta(days=3)
        reservation = Reservation.objects.create(
            user=self.guest,
            sunbed=self.sunbed_b,
            reservation_date=past_date,
            status=ReservationStatus.ACTIVE,
            price_at_booking=Decimal("25.00"),
        )
        updated = mark_past_reservations_completed(user=self.guest)
        self.assertEqual(updated, 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.COMPLETED)


class BookingApiTests(BookingTestMixin, TestCase):
    def test_book_requires_login(self):
        url = reverse("api_book_sunbeds", args=[self.bar.id])
        response = self.api_post(
            self.client,
            url,
            {"date": self.book_date.isoformat(), "sunbed_ids": [self.sunbed_a.id]},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "auth_required")

    def test_book_success(self):
        self.login_guest()
        url = reverse("api_book_sunbeds", args=[self.bar.id])
        response = self.api_post(
            self.client,
            url,
            {"date": self.book_date.isoformat(), "sunbed_ids": [self.sunbed_a.id]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["reservations"]), 1)
        self.assertEqual(data["reservations"][0]["sunbed_label"], "A1")

    def test_book_taken_spot_returns_400(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.login_guest(self.client)
        self.client.logout()
        self.client.login(email=self.other_guest.email, password="testpass123")
        url = reverse("api_book_sunbeds", args=[self.bar.id])
        response = self.api_post(
            self.client,
            url,
            {"date": self.book_date.isoformat(), "sunbed_ids": [self.sunbed_a.id]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "spot_taken")

    def test_cancel_requires_login(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        url = reverse("api_cancel_reservation", args=[reservation.id])
        response = self.api_post(self.client, url)
        self.assertEqual(response.status_code, 401)

    def test_cancel_forbidden_for_other_user(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.client.login(email=self.other_guest.email, password="testpass123")
        url = reverse("api_cancel_reservation", args=[reservation.id])
        response = self.api_post(self.client, url)
        self.assertEqual(response.status_code, 403)

    def test_cancel_success(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.login_guest()
        url = reverse("api_cancel_reservation", args=[reservation.id])
        response = self.api_post(self.client, url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["reservation"]["status"], ReservationStatus.CANCELLED
        )


class MyReservationsPageTests(BookingTestMixin, TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("my_reservations"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_shows_active_booking(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.login_guest()
        response = self.client.get(reverse("my_reservations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Beach")
        self.assertContains(response, "Spot A1")
        self.assertContains(response, "cancel-reservation")

    def test_marks_past_bookings_completed_on_visit(self):
        past_date = date.today() - timedelta(days=2)
        Reservation.objects.create(
            user=self.guest,
            sunbed=self.sunbed_a,
            reservation_date=past_date,
            status=ReservationStatus.ACTIVE,
            price_at_booking=Decimal("25.00"),
        )
        self.login_guest()
        response = self.client.get(reverse("my_reservations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed")
        self.assertNotContains(response, 'data-reservation-id')


class BookingIntegrationTests(BookingTestMixin, TestCase):
    def test_login_book_list_cancel_map_free(self):
        client = Client(HTTP_HOST="127.0.0.1")
        client.login(email=self.guest.email, password="testpass123")

        book_url = reverse("api_book_sunbeds", args=[self.bar.id])
        book_response = self.api_post(
            client,
            book_url,
            {"date": self.book_date.isoformat(), "sunbed_ids": [self.sunbed_a.id]},
        )
        self.assertEqual(book_response.status_code, 200)
        reservation_id = book_response.json()["reservations"][0]["id"]

        bookings_response = client.get(reverse("my_reservations"))
        self.assertContains(bookings_response, "Test Beach")
        self.assertContains(bookings_response, f'data-reservation-id="{reservation_id}"')

        sunbeds_url = reverse("api_bar_sunbeds", args=[self.bar.id])
        map_before_cancel = client.get(
            f"{sunbeds_url}?date={self.book_date.isoformat()}"
        ).json()
        taken = [
            cell
            for row in map_before_cancel["rows"]
            for cell in row
            if cell["id"] == self.sunbed_a.id
        ]
        self.assertTrue(taken[0]["is_taken"])

        cancel_url = reverse("api_cancel_reservation", args=[reservation_id])
        cancel_response = self.api_post(client, cancel_url)
        self.assertEqual(cancel_response.status_code, 200)

        bookings_after = client.get(reverse("my_reservations"))
        self.assertContains(bookings_after, "Cancelled")

        map_after_cancel = client.get(
            f"{sunbeds_url}?date={self.book_date.isoformat()}"
        ).json()
        free = [
            cell
            for row in map_after_cancel["rows"]
            for cell in row
            if cell["id"] == self.sunbed_a.id
        ]
        self.assertFalse(free[0]["is_taken"])

    def test_beach_bar_page_has_book_data_attrs_when_logged_in(self):
        self.login_guest()
        response = self.client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-book-url')
        self.assertContains(response, 'data-bookings-url')
        self.assertContains(response, 'data-is-authenticated="true"')


class OwnerDashboardAccessTests(BookingTestMixin, TestCase):
    def test_non_owner_redirects_to_explore(self):
        self.login_guest()
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("explore"))

    def test_owner_sees_dashboard(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Beach")
        self.assertContains(response, "Overview")
        self.assertContains(response, "Reservations")
        self.assertContains(response, "Pricing")
        self.assertContains(response, "Bundles")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class OwnerServiceTests(BookingTestMixin, TestCase):
    def test_get_owner_bar_returns_bar(self):
        self.assertEqual(get_owner_bar(self.owner), self.bar)

    def test_get_owner_bar_returns_none_for_guest(self):
        self.assertIsNone(get_owner_bar(self.guest))

    def test_assert_owner_of_bar_passes_for_owner(self):
        assert_owner_of_bar(self.owner, self.bar)

    def test_assert_owner_of_bar_raises_for_other_owner(self):
        other_owner = User.objects.create_user(
            email="other-owner@test.beach",
            password="testpass123",
            first_name="Other",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        with self.assertRaises(OwnerAccessError):
            assert_owner_of_bar(other_owner, self.bar)

    def test_owner_without_bar_gets_404(self):
        owner_no_bar = User.objects.create_user(
            email="nobars@test.beach",
            password="testpass123",
            first_name="No",
            last_name="Bar",
            role=UserRole.OWNER,
        )
        self.client.login(email=owner_no_bar.email, password="testpass123")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 404)


class OwnerOverviewTests(BookingTestMixin, TestCase):
    def test_overview_stats_match_db(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        overview = get_dashboard_overview(self.bar, self.book_date)
        self.assertEqual(overview["bookings_count"], 1)
        self.assertEqual(overview["taken_spots"], 1)
        self.assertEqual(overview["free_spots"], 1)
        self.assertEqual(overview["occupancy_pct"], 50)
        self.assertEqual(overview["revenue"], Decimal("25.00"))

    def test_overview_page_shows_stats(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(response, "50%")
        self.assertContains(response, "Bookings")


class OwnerReservationsTests(BookingTestMixin, TestCase):
    def setUp(self):
        self.reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]

    def test_reservations_tab_lists_booking(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(response, "guest@test.beach")
        self.assertContains(response, "A1")

    def test_reservations_filtered_by_date(self):
        other_date = self.book_date + timedelta(days=3)
        book_sunbeds(self.guest, self.bar, other_date, [self.sunbed_b.id])
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(response, "A1")
        self.assertNotContains(response, ">A2<")


class OwnerCancelTests(BookingTestMixin, TestCase):
    def test_owner_can_cancel_guest_reservation_via_api(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_cancel_reservation", args=[reservation.id]),
        )
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CANCELLED)

    def test_owner_cannot_cancel_other_bars_reservation(self):
        other_owner = User.objects.create_user(
            email="other-owner2@test.beach",
            password="testpass123",
            first_name="Other",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        other_bar = BeachBar.objects.create(
            owner=other_owner,
            name="Other Beach",
            address="2 Shore Rd",
            city="Kotor",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        other_category = SunbedCategory.objects.create(
            beach_bar=other_bar,
            name="Standard",
            price=Decimal("20.00"),
        )
        other_sunbed = Sunbed.objects.create(
            beach_bar=other_bar,
            category=other_category,
            label="B1",
            grid_row=0,
            grid_col=0,
        )
        reservation = book_sunbeds(
            self.guest, other_bar, self.book_date, [other_sunbed.id]
        )[0]
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_cancel_reservation", args=[reservation.id]),
        )
        self.assertEqual(response.status_code, 403)


class OwnerDashboardIntegrationTests(BookingTestMixin, TestCase):
    def test_owner_overview_cancel_and_map_free(self):
        client = Client(HTTP_HOST="127.0.0.1")
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        client.login(email=self.owner.email, password="testpass123")

        overview = client.get(
            reverse("owner_dashboard"),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(overview, "Test Beach")

        cancel_response = self.api_post(
            client,
            reverse("api_cancel_reservation", args=[reservation.id]),
        )
        self.assertEqual(cancel_response.status_code, 200)

        sunbeds_url = reverse("api_bar_sunbeds", args=[self.bar.id])
        map_data = client.get(
            f"{sunbeds_url}?date={self.book_date.isoformat()}"
        ).json()
        free = [
            cell
            for row in map_data["rows"]
            for cell in row
            if cell["id"] == self.sunbed_a.id
        ]
        self.assertFalse(free[0]["is_taken"])


class OwnerManualParityTests(BookingTestMixin, TestCase):
    """Covers manual checklist items not asserted elsewhere."""

    def test_overview_zero_stats_when_no_bookings(self):
        overview = get_dashboard_overview(self.bar, self.book_date)
        self.assertEqual(overview["bookings_count"], 0)
        self.assertEqual(overview["revenue"], Decimal("0"))
        self.assertEqual(overview["occupancy_pct"], 0)
        self.assertEqual(overview["free_spots"], 2)

        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(response, "spots booked")
        self.assertContains(response, "<strong>0</strong> of <strong>2</strong>")

    def test_overview_category_breakdown_on_page(self):
        premium = SunbedCategory.objects.create(
            beach_bar=self.bar,
            name="Premium",
            price=Decimal("40.00"),
        )
        Sunbed.objects.create(
            beach_bar=self.bar,
            category=premium,
            label="P1",
            grid_row=1,
            grid_col=0,
        )
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])

        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(response, "Standard")
        self.assertContains(response, "Premium")
        self.assertContains(response, "1 / 2")
        self.assertContains(response, "0 / 1")

    def test_overview_taken_spots_matches_guest_map_api(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        overview = get_dashboard_overview(self.bar, self.book_date)
        map_payload = get_sunbed_map_payload(self.bar, self.book_date)
        map_taken = sum(
            1
            for row in map_payload["rows"]
            for cell in row
            if cell["is_taken"]
        )
        self.assertEqual(overview["taken_spots"], map_taken)
        self.assertEqual(overview["free_spots"], map_payload["free_spots"])

    def test_date_filter_changes_overview_counts(self):
        other_date = self.book_date + timedelta(days=1)
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        book_sunbeds(self.guest, self.bar, other_date, [self.sunbed_a.id, self.sunbed_b.id])

        day_one = get_dashboard_overview(self.bar, self.book_date)
        day_two = get_dashboard_overview(self.bar, other_date)
        self.assertEqual(day_one["bookings_count"], 1)
        self.assertEqual(day_two["bookings_count"], 2)

    def test_reservations_status_filter_cancelled(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        cancel_reservation(self.guest, reservation.id)
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_b.id])

        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
                "status": "cancelled",
            },
        )
        self.assertContains(response, "A1")
        self.assertNotContains(response, ">A2<")
        self.assertContains(response, "Cancelled")

    def test_reservations_active_shows_cancel_button(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
                "status": "active",
            },
        )
        self.assertContains(response, "owner-cancel-reservation")
        self.assertContains(response, f'data-reservation-id="{reservation.id}"')

    def test_guest_cancel_still_works_after_owner_cancel_change(self):
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_cancel_reservation", args=[reservation.id]),
        )
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CANCELLED)
class PricingServiceTests(BookingTestMixin, TestCase):
    def test_update_category_prices(self):
        updated = update_category_prices(self.bar, {self.category.id: "30.50"})
        self.assertEqual(len(updated), 1)
        self.category.refresh_from_db()
        self.assertEqual(self.category.price, Decimal("30.50"))

    def test_update_rejects_invalid_category(self):
        with self.assertRaises(PricingError) as ctx:
            update_category_prices(self.bar, {99999: "10.00"})
        self.assertEqual(ctx.exception.code, "invalid_category")

    def test_update_rejects_negative_price(self):
        with self.assertRaises(PricingError) as ctx:
            update_category_prices(self.bar, {self.category.id: "-1"})
        self.assertEqual(ctx.exception.code, "invalid_price")

    def test_update_rejects_empty_updates(self):
        with self.assertRaises(PricingError) as ctx:
            update_category_prices(self.bar, {})
        self.assertEqual(ctx.exception.code, "no_prices")


class PricingApiTests(BookingTestMixin, TestCase):
    def test_owner_can_update_pricing_via_api(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_pricing"),
            {"prices": [{"category_id": self.category.id, "price": "32.00"}]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.category.refresh_from_db()
        self.assertEqual(self.category.price, Decimal("32.00"))

    def test_guest_cannot_update_pricing(self):
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_owner_pricing"),
            {"prices": [{"category_id": self.category.id, "price": "32.00"}]},
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_returns_400(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.post(
            reverse("api_owner_pricing"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class BundleServiceTests(BookingTestMixin, TestCase):
    def test_create_and_list_bundles(self):
        bundle = create_bundle(self.bar, "Drinks", "Soft drinks", "8.00")
        self.assertEqual(bundle.name, "Drinks")
        self.assertEqual(bundle.price, Decimal("8.00"))
        self.assertTrue(bundle.is_active)
        bundles = list_bundles(self.bar)
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].id, bundle.id)

    def test_update_bundle(self):
        bundle = create_bundle(self.bar, "Parking", None, "5.00")
        updated = update_bundle(
            self.bar, bundle.id, "VIP Parking", "Near entrance", "7.50"
        )
        self.assertEqual(updated.name, "VIP Parking")
        self.assertEqual(updated.description, "Near entrance")
        self.assertEqual(updated.price, Decimal("7.50"))

    def test_set_bundle_active(self):
        bundle = create_bundle(self.bar, "Towels", None, "3.00")
        toggled = set_bundle_active(self.bar, bundle.id, False)
        self.assertFalse(toggled.is_active)

    def test_create_rejects_empty_name(self):
        with self.assertRaises(BundleError) as ctx:
            create_bundle(self.bar, "  ", None, "5.00")
        self.assertEqual(ctx.exception.code, "invalid_name")


class BundleApiTests(BookingTestMixin, TestCase):
    def test_owner_can_create_bundle(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_create_bundle"),
            {
                "name": "Drinks Package",
                "description": "Two drinks",
                "price": "8.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["bundle"]["name"], "Drinks Package")
        self.assertTrue(
            Bundle.objects.filter(
                beach_bar=self.bar, name="Drinks Package"
            ).exists()
        )

    def test_owner_can_update_and_toggle_bundle(self):
        bundle = create_bundle(self.bar, "Parking", None, "5.00")
        self.client.login(email=self.owner.email, password="testpass123")
        update_response = self.api_post(
            self.client,
            reverse("api_owner_update_bundle", args=[bundle.id]),
            {"name": "Parking Plus", "description": "", "price": "6.00"},
        )
        self.assertEqual(update_response.status_code, 200)
        bundle.refresh_from_db()
        self.assertEqual(bundle.name, "Parking Plus")
        self.assertEqual(bundle.price, Decimal("6.00"))

        toggle_response = self.api_post(
            self.client,
            reverse("api_owner_toggle_bundle", args=[bundle.id]),
            {"is_active": False},
        )
        self.assertEqual(toggle_response.status_code, 200)
        bundle.refresh_from_db()
        self.assertFalse(bundle.is_active)

    def test_owner_cannot_update_other_bars_bundle(self):
        other_owner = User.objects.create_user(
            email="other-owner3@test.beach",
            password="testpass123",
            first_name="Other",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        other_bar = BeachBar.objects.create(
            owner=other_owner,
            name="Other Beach",
            address="2 Shore Rd",
            city="Kotor",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        other_bundle = create_bundle(other_bar, "Other Bundle", None, "4.00")
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_update_bundle", args=[other_bundle.id]),
            {"name": "Hacked", "description": "", "price": "1.00"},
        )
        self.assertEqual(response.status_code, 404)

    def test_guest_cannot_create_bundle(self):
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_owner_create_bundle"),
            {"name": "Drinks", "price": "8.00"},
        )
        self.assertEqual(response.status_code, 403)


class PricingIntegrationTests(BookingTestMixin, TestCase):
    def test_new_booking_uses_updated_category_price(self):
        update_category_prices(self.bar, {self.category.id: "40.00"})
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )[0]
        self.assertEqual(reservation.price_at_booking, Decimal("40.00"))

    def test_map_api_reflects_updated_price(self):
        update_category_prices(self.bar, {self.category.id: "35.00"})
        payload = get_sunbed_map_payload(self.bar, self.book_date)
        prices = {
            cell["price"]
            for row in payload["rows"]
            for cell in row
            if cell.get("id") == self.sunbed_a.id
        }
        self.assertEqual(prices, {"35.00"})

    def test_owner_pricing_tab_shows_categories(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "pricing"},
        )
        self.assertContains(response, "Standard")
        self.assertContains(response, "save-pricing-btn")

    def test_owner_bundles_tab_lists_existing_bundle(self):
        create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(response, "Drinks Package")
        self.assertContains(response, "new-bundle-btn")


class Slice6FlowTests(BookingTestMixin, TestCase):
    """Chained HTTP flows for owner pricing/bundles (dashboard.js payload shapes)."""

    def test_owner_pricing_flow_reaches_guest_booking(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        guest_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")

        pricing_response = self.api_post(
            owner_client,
            reverse("api_owner_pricing"),
            {
                "prices": [
                    {"category_id": self.category.id, "price": "45.00"},
                ],
            },
        )
        self.assertEqual(pricing_response.status_code, 200)
        self.assertTrue(pricing_response.json()["ok"])

        guest_client.login(email=self.guest.email, password="testpass123")
        sunbeds_url = reverse("api_bar_sunbeds", args=[self.bar.id])
        map_data = guest_client.get(
            f"{sunbeds_url}?date={self.book_date.isoformat()}"
        ).json()
        map_prices = {
            cell["price"]
            for row in map_data["rows"]
            for cell in row
            if cell.get("id") == self.sunbed_a.id
        }
        self.assertEqual(map_prices, {"45.00"})

        beach_bar_page = guest_client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertEqual(beach_bar_page.status_code, 200)
        self.assertContains(beach_bar_page, "from &euro;45")
        self.assertContains(beach_bar_page, "&euro;45 / spot")

        book_response = self.api_post(
            guest_client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {"date": self.book_date.isoformat(), "sunbed_ids": [self.sunbed_a.id]},
        )
        self.assertEqual(book_response.status_code, 200)
        book_data = book_response.json()
        self.assertEqual(book_data["reservations"][0]["price"], "45.00")

        reservation_id = book_data["reservations"][0]["id"]
        my_bookings = guest_client.get(reverse("my_reservations"))
        self.assertContains(my_bookings, "&euro;45")

        owner_reservations = owner_client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(owner_reservations, "guest@test.beach")
        self.assertContains(owner_reservations, "&euro;45")
        self.assertContains(
            owner_reservations, f'data-reservation-id="{reservation_id}"'
        )

    def test_pricing_dashboard_payload_matches_saved_api(self):
        self.client.login(email=self.owner.email, password="testpass123")
        page = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "pricing"},
        )
        self.assertContains(page, reverse("api_owner_pricing"))
        self.assertContains(
            page, f'data-category-id="{self.category.id}"'
        )
        self.assertContains(page, 'value="25.00"')

        response = self.api_post(
            self.client,
            reverse("api_owner_pricing"),
            {
                "prices": [
                    {"category_id": self.category.id, "price": "33.50"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)

        page_after = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "pricing"},
        )
        self.assertContains(page_after, 'value="33.50"')
        self.category.refresh_from_db()
        self.assertEqual(self.category.price, Decimal("33.50"))

    def test_owner_bundle_create_flow_shows_on_dashboard(self):
        self.client.login(email=self.owner.email, password="testpass123")
        create_response = self.api_post(
            self.client,
            reverse("api_owner_create_bundle"),
            {
                "name": "Sunscreen Kit",
                "description": "SPF 50",
                "price": "12.00",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        bundle_id = create_response.json()["bundle"]["id"]

        dashboard = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(dashboard, "Sunscreen Kit")
        self.assertContains(dashboard, "SPF 50")
        self.assertContains(dashboard, "&euro;12")
        self.assertContains(
            dashboard,
            reverse("api_owner_update_bundle", args=[bundle_id]),
        )
        self.assertContains(
            dashboard,
            reverse("api_owner_toggle_bundle", args=[bundle_id]),
        )
        self.assertContains(dashboard, reverse("api_owner_create_bundle"))

    def test_owner_bundle_update_flow_reflects_on_dashboard(self):
        bundle = create_bundle(self.bar, "Towel Rental", "Fresh towel", "4.00")
        self.client.login(email=self.owner.email, password="testpass123")
        update_response = self.api_post(
            self.client,
            reverse("api_owner_update_bundle", args=[bundle.id]),
            {
                "name": "Premium Towel",
                "description": "Large towel",
                "price": "6.50",
            },
        )
        self.assertEqual(update_response.status_code, 200)

        dashboard = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(dashboard, "Premium Towel")
        self.assertContains(dashboard, "Large towel")
        self.assertContains(dashboard, "&euro;7")
        self.assertNotContains(dashboard, "Towel Rental")

    def test_owner_bundle_toggle_flow_reflects_on_dashboard(self):
        bundle = create_bundle(self.bar, "Locker", "Secure storage", "3.00")
        self.client.login(email=self.owner.email, password="testpass123")

        toggle_response = self.api_post(
            self.client,
            reverse("api_owner_toggle_bundle", args=[bundle.id]),
            {"is_active": False},
        )
        self.assertEqual(toggle_response.status_code, 200)

        dashboard = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(dashboard, "Locker")
        self.assertContains(dashboard, "bundle-row--off")
        bundle.refresh_from_db()
        self.assertFalse(bundle.is_active)

        reactivate = self.api_post(
            self.client,
            reverse("api_owner_toggle_bundle", args=[bundle.id]),
            {"is_active": True},
        )
        self.assertEqual(reactivate.status_code, 200)

        dashboard_active = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(dashboard_active, "Locker")
        self.assertNotContains(dashboard_active, "bundle-row--off")
        bundle.refresh_from_db()
        self.assertTrue(bundle.is_active)

    def test_dashboard_loads_owner_pricing_and_bundle_scripts(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertContains(response, "/static/core/js/dashboard.js")
        self.assertContains(response, 'id="tab-pricing"')
        self.assertContains(response, 'id="tab-bundles"')
        self.assertContains(response, 'id="bundle-form"')
        self.assertContains(response, 'id="save-pricing-btn"')
