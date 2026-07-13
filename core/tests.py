import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from core.models import (
    Amenity,
    BeachBar,
    BeachBarAmenity,
    Bundle,
    Reservation,
    ReservationBundle,
    ReservationStatus,
    Review,
    Sunbed,
    SunbedCategory,
    User,
    UserRole,
)
from core.services.beach_bar import get_sunbed_map_payload
from core.services.categories import (
    CategoryError,
    create_category,
    delete_category,
    list_categories,
    update_category,
)
from core.services.bundles import (
    BundleError,
    create_bundle,
    list_active_bundles,
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
from core.services.bar_settings import (
    SettingsError,
    get_bar_settings_payload,
    update_bar_settings,
)
from core.services.onboarding import (
    DEFAULT_CATEGORIES,
    OnboardingError,
    create_owner_bar,
    get_setup_form_payload,
)
from core.services.explore import (
    ExploreError,
    amenity_ids_from_querydict,
    list_amenities,
    parse_amenity_ids,
    parse_price_bound,
    parse_sort,
    search_bars,
    search_bars_payload,
    serialize_bar,
    filters_active,
    DEFAULT_UNFILTERED_LIMIT,
)
from core.services.layout import (
    LayoutError,
    get_layout_editor_payload,
    save_bar_layout,
)
from core.services.pricing import PricingError, update_category_prices
from core.services.reservations import (
    BookingError,
    book_sunbeds,
    cancel_reservation,
    get_reservation_line_total,
    mark_past_reservations_completed,
    serialize_reservation,
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
        self.assertContains(response, "Categories &amp; pricing")
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

    def test_owner_without_bar_sees_setup_form(self):
        owner_no_bar = User.objects.create_user(
            email="nobars@test.beach",
            password="testpass123",
            first_name="No",
            last_name="Bar",
            role=UserRole.OWNER,
        )
        self.client.login(email=owner_no_bar.email, password="testpass123")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your beach bar")
        self.assertContains(response, reverse("api_owner_setup"))
        self.assertContains(response, 'id="bar-setup-form"')


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


class CategoryServiceTests(BookingTestMixin, TestCase):
    def test_create_and_list_categories(self):
        category = create_category(self.bar, "VIP", "45.00", "Front row")
        self.assertEqual(category.name, "VIP")
        self.assertEqual(category.price, Decimal("45.00"))
        self.assertEqual(category.description, "Front row")
        names = [c.name for c in list_categories(self.bar)]
        self.assertIn("VIP", names)
        self.assertIn("Standard", names)

    def test_update_category(self):
        updated = update_category(
            self.bar,
            self.category.id,
            "Premium Standard",
            "28.50",
            "Renamed zone",
        )
        self.assertEqual(updated.name, "Premium Standard")
        self.assertEqual(updated.price, Decimal("28.50"))
        self.assertEqual(updated.description, "Renamed zone")

    def test_delete_empty_category(self):
        extra = create_category(self.bar, "Cabana", "80.00", None)
        delete_category(self.bar, extra.id)
        self.assertFalse(SunbedCategory.objects.filter(pk=extra.id).exists())

    def test_delete_rejects_category_with_sunbeds(self):
        with self.assertRaises(CategoryError) as ctx:
            delete_category(self.bar, self.category.id)
        self.assertEqual(ctx.exception.code, "has_sunbeds")

    def test_duplicate_name_rejected(self):
        with self.assertRaises(CategoryError) as ctx:
            create_category(self.bar, "standard", "20.00", None)
        self.assertEqual(ctx.exception.code, "duplicate_name")

    def test_update_duplicate_name_rejected(self):
        other = create_category(self.bar, "Lazy Bag", "18.00", None)
        with self.assertRaises(CategoryError) as ctx:
            update_category(self.bar, other.id, "Standard", "18.00", None)
        self.assertEqual(ctx.exception.code, "duplicate_name")

    def test_create_rejects_invalid_price(self):
        with self.assertRaises(CategoryError) as ctx:
            create_category(self.bar, "Budget", "-5", None)
        self.assertEqual(ctx.exception.code, "invalid_price")

    def test_create_rejects_empty_name(self):
        with self.assertRaises(CategoryError) as ctx:
            create_category(self.bar, "  ", "10.00", None)
        self.assertEqual(ctx.exception.code, "invalid_name")


class CategoryApiTests(BookingTestMixin, TestCase):
    def test_owner_can_create_category(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_create_category"),
            {
                "name": "Cabana",
                "description": "Private shade",
                "price": "90.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["category"]["name"], "Cabana")
        self.assertTrue(
            SunbedCategory.objects.filter(
                beach_bar=self.bar, name="Cabana"
            ).exists()
        )

    def test_owner_can_update_and_delete_category(self):
        category = create_category(self.bar, "Budget", "12.00", None)
        self.client.login(email=self.owner.email, password="testpass123")
        update_response = self.api_post(
            self.client,
            reverse("api_owner_update_category", args=[category.id]),
            {"name": "Economy", "description": "Back row", "price": "14.00"},
        )
        self.assertEqual(update_response.status_code, 200)
        category.refresh_from_db()
        self.assertEqual(category.name, "Economy")
        self.assertEqual(category.price, Decimal("14.00"))

        delete_response = self.api_post(
            self.client,
            reverse("api_owner_delete_category", args=[category.id]),
            {},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(SunbedCategory.objects.filter(pk=category.id).exists())

    def test_delete_category_with_sunbeds_returns_400(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_delete_category", args=[self.category.id]),
            {},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "has_sunbeds")

    def test_owner_cannot_update_other_bars_category(self):
        other_owner = User.objects.create_user(
            email="other-owner4@test.beach",
            password="testpass123",
            first_name="Other",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        other_bar = BeachBar.objects.create(
            owner=other_owner,
            name="Other Beach 4",
            address="4 Shore Rd",
            city="Kotor",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        other_category = SunbedCategory.objects.create(
            beach_bar=other_bar,
            name="Other Zone",
            price=Decimal("10.00"),
        )
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_update_category", args=[other_category.id]),
            {"name": "Hacked", "description": "", "price": "1.00"},
        )
        self.assertEqual(response.status_code, 404)

    def test_guest_cannot_create_category(self):
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_owner_create_category"),
            {"name": "VIP", "price": "50.00"},
        )
        self.assertEqual(response.status_code, 403)


class CategoryIntegrationTests(BookingTestMixin, TestCase):
    def test_new_category_appears_in_layout_palette(self):
        cabana = create_category(self.bar, "Cabana", "75.00", "Shaded")
        payload = get_layout_editor_payload(self.bar)
        names = {item["name"] for item in payload["categories"]}
        self.assertIn("Cabana", names)
        self.assertIn(cabana.id, {item["id"] for item in payload["categories"]})

    def test_custom_category_gets_layout_prefix(self):
        bar_table = create_category(self.bar, "Bar table", "40.00", None)
        payload = get_layout_editor_payload(self.bar)
        by_id = {item["id"]: item for item in payload["categories"]}
        self.assertEqual(by_id[bar_table.id]["prefix"], "B")

    def test_renamed_category_keeps_sunbed_labels_until_layout_save(self):
        update_category(self.bar, self.category.id, "Economy", "22.00", None)
        self.sunbed_a.refresh_from_db()
        self.assertEqual(self.sunbed_a.label, "A1")

        save_bar_layout(
            self.bar,
            rows=4,
            cols=10,
            cells=[
                {
                    "row": self.sunbed_a.grid_row,
                    "col": self.sunbed_a.grid_col,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": self.sunbed_b.grid_row,
                    "col": self.sunbed_b.grid_col,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
            ],
        )
        self.sunbed_a.refresh_from_db()
        self.assertEqual(self.sunbed_a.label, "E1")

    def test_new_booking_uses_category_price_after_crud_update(self):
        cabana = create_category(self.bar, "Cabana", "99.00", None)
        Sunbed.objects.create(
            beach_bar=self.bar,
            category=cabana,
            label="C1",
            grid_row=1,
            grid_col=0,
        )
        cabana_sunbed = Sunbed.objects.get(category=cabana)
        reservation = book_sunbeds(
            self.guest, self.bar, self.book_date, [cabana_sunbed.id]
        )[0]
        self.assertEqual(reservation.price_at_booking, Decimal("99.00"))

    def test_map_api_reflects_new_category_price(self):
        cabana = create_category(self.bar, "Cabana", "88.00", None)
        Sunbed.objects.create(
            beach_bar=self.bar,
            category=cabana,
            label="C1",
            grid_row=1,
            grid_col=0,
        )
        cabana_sunbed = Sunbed.objects.get(category=cabana)
        payload = get_sunbed_map_payload(self.bar, self.book_date)
        prices = {
            cell["price"]
            for row in payload["rows"]
            for cell in row
            if cell.get("id") == cabana_sunbed.id
        }
        self.assertEqual(prices, {"88.00"})

    def test_pricing_tab_shows_category_crud_ui(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "pricing"},
        )
        self.assertContains(response, "Categories &amp; pricing")
        self.assertContains(response, "new-category-btn")
        self.assertContains(response, reverse("api_owner_create_category"))
        self.assertContains(response, "category-form")


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
        self.assertContains(response, "new-category-btn")

    def test_owner_bundles_tab_lists_existing_bundle(self):
        create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "bundles"},
        )
        self.assertContains(response, "Drinks Package")
        self.assertContains(response, "new-bundle-btn")


class BundleBookingServiceTests(BookingTestMixin, TestCase):
    def setUp(self):
        self.drinks = create_bundle(self.bar, "Drinks", "Two drinks", "8.00")
        self.parking = create_bundle(self.bar, "Parking", "Nearby", "5.00")

    def test_list_active_bundles_excludes_inactive(self):
        set_bundle_active(self.bar, self.parking.id, False)
        active = list(list_active_bundles(self.bar))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, self.drinks.id)

    def test_book_with_bundle_attaches_to_first_reservation_only(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id, self.sunbed_b.id],
            bundle_ids=[self.drinks.id],
        )
        self.assertEqual(len(reservations), 2)
        self.assertEqual(
            ReservationBundle.objects.filter(reservation=reservations[0]).count(),
            1,
        )
        self.assertEqual(
            ReservationBundle.objects.filter(reservation=reservations[1]).count(),
            0,
        )

    def test_book_snapshots_bundle_price(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[self.drinks.id],
        )
        row = ReservationBundle.objects.get(reservation=reservations[0])
        self.assertEqual(row.price_at_booking, Decimal("8.00"))

        update_bundle(self.bar, self.drinks.id, "Drinks", "Two drinks", "10.00")
        row.refresh_from_db()
        self.assertEqual(row.price_at_booking, Decimal("8.00"))

    def test_serialize_reservation_includes_bundle_totals(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[self.drinks.id, self.parking.id],
        )
        payload = serialize_reservation(reservations[0])
        self.assertEqual(payload["bundle_total"], "13.00")
        self.assertEqual(payload["line_total"], "38.00")
        self.assertEqual(len(payload["bundles"]), 2)

    def test_get_reservation_line_total(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[self.parking.id],
        )
        self.assertEqual(get_reservation_line_total(reservations[0]), Decimal("30.00"))

    def test_book_rejects_inactive_bundle(self):
        set_bundle_active(self.bar, self.drinks.id, False)
        with self.assertRaises(BookingError) as ctx:
            book_sunbeds(
                self.guest,
                self.bar,
                self.book_date,
                [self.sunbed_a.id],
                bundle_ids=[self.drinks.id],
            )
        self.assertEqual(ctx.exception.code, "inactive_bundle")

    def test_book_rejects_foreign_bundle(self):
        other_owner = User.objects.create_user(
            email="other-owner4@test.beach",
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
        foreign = create_bundle(other_bar, "Foreign", None, "4.00")
        with self.assertRaises(BookingError) as ctx:
            book_sunbeds(
                self.guest,
                self.bar,
                self.book_date,
                [self.sunbed_a.id],
                bundle_ids=[foreign.id],
            )
        self.assertEqual(ctx.exception.code, "invalid_bundle")

    def test_rebook_cancelled_spot_replaces_bundles(self):
        reservations = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[self.drinks.id],
        )
        cancel_reservation(self.guest, reservations[0].id)
        rebound = book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[self.parking.id],
        )[0]
        rows = ReservationBundle.objects.filter(reservation=rebound)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().bundle_id, self.parking.id)


class BundleBookingApiTests(BookingTestMixin, TestCase):
    def setUp(self):
        self.drinks = create_bundle(self.bar, "Drinks", "Two drinks", "8.00")

    def test_book_with_bundles_via_api(self):
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
                "bundle_ids": [self.drinks.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        reservation = data["reservations"][0]
        self.assertEqual(reservation["bundle_total"], "8.00")
        self.assertEqual(reservation["line_total"], "33.00")
        self.assertEqual(reservation["bundles"][0]["name"], "Drinks")

    def test_book_rejects_inactive_bundle_via_api(self):
        set_bundle_active(self.bar, self.drinks.id, False)
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
                "bundle_ids": [self.drinks.id],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "inactive_bundle")

    def test_book_without_bundles_still_works(self):
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        reservation = response.json()["reservations"][0]
        self.assertEqual(reservation["bundle_total"], "0.00")
        self.assertEqual(reservation["line_total"], "25.00")
        self.assertEqual(reservation["bundles"], [])


class BeachBarBundleUiTests(BookingTestMixin, TestCase):
    def test_beach_bar_shows_active_bundles(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        response = self.client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(response, "Drinks Package")
        self.assertContains(response, "bundle-addons")
        self.assertContains(response, f'data-bundle-id="{drinks.id}"')
        self.assertContains(response, "sum-extras")

    def test_beach_bar_hides_inactive_bundles(self):
        create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        parking = create_bundle(self.bar, "Parking", "Nearby", "5.00")
        set_bundle_active(self.bar, parking.id, False)
        response = self.client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(response, "Drinks Package")
        self.assertNotContains(response, ">Parking<")

    def test_beach_bar_without_bundles_omits_addon_section(self):
        response = self.client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertNotContains(response, "bundle-addons")


class MyBookingsBundleTests(BookingTestMixin, TestCase):
    def test_my_bookings_shows_bundle_lines_and_total(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[drinks.id],
        )
        self.login_guest()
        response = self.client.get(reverse("my_reservations"))
        self.assertContains(response, "Drinks Package")
        self.assertContains(response, "&euro;33")

    def test_my_bookings_without_bundles_shows_spot_price_only(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.login_guest()
        response = self.client.get(reverse("my_reservations"))
        self.assertContains(response, "&euro;25")
        self.assertNotContains(response, "Drinks Package")


class OwnerBundleRevenueTests(BookingTestMixin, TestCase):
    def test_overview_revenue_includes_bundle_add_ons(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[drinks.id],
        )
        overview = get_dashboard_overview(self.bar, self.book_date)
        self.assertEqual(overview["revenue"], Decimal("33.00"))

    def test_owner_reservations_tab_shows_line_total_with_bundle(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id],
            bundle_ids=[drinks.id],
        )
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(response, "guest@test.beach")
        self.assertContains(response, "&euro;33")


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
        self.assertContains(page, reverse("api_owner_update_category", args=[self.category.id]))
        self.assertContains(page, "&euro;25.00")

        response = self.api_post(
            self.client,
            reverse("api_owner_update_category", args=[self.category.id]),
            {
                "name": "Standard",
                "description": "",
                "price": "33.50",
            },
        )
        self.assertEqual(response.status_code, 200)

        page_after = self.client.get(
            reverse("owner_dashboard"),
            {"tab": "pricing"},
        )
        self.assertContains(page_after, "&euro;33.50")
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
        self.assertContains(response, 'id="category-form"')


class Slice7FlowTests(BookingTestMixin, TestCase):
    def test_guest_bundle_booking_flow_end_to_end(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        guest_client = Client(HTTP_HOST="127.0.0.1")
        guest_client.login(email=self.guest.email, password="testpass123")

        beach_page = guest_client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(beach_page, "Drinks Package")
        self.assertContains(beach_page, f'data-bundle-id="{drinks.id}"')

        book_response = self.api_post(
            guest_client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
                "bundle_ids": [drinks.id],
            },
        )
        self.assertEqual(book_response.status_code, 200)
        self.assertEqual(book_response.json()["reservations"][0]["line_total"], "33.00")

        my_bookings = guest_client.get(reverse("my_reservations"))
        self.assertContains(my_bookings, "Drinks Package")
        self.assertContains(my_bookings, "&euro;33")

        owner_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")
        owner_page = owner_client.get(
            reverse("owner_dashboard"),
            {
                "tab": "reservations",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(owner_page, "&euro;33")
        overview = owner_client.get(
            reverse("owner_dashboard"),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(overview, "&euro;33")

    def test_multi_spot_booking_charges_bundles_once(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id, self.sunbed_b.id],
                "bundle_ids": [drinks.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        reservations = response.json()["reservations"]
        self.assertEqual(reservations[0]["bundle_total"], "8.00")
        self.assertEqual(reservations[0]["line_total"], "33.00")
        self.assertEqual(reservations[1]["bundle_total"], "0.00")
        self.assertEqual(reservations[1]["line_total"], "25.00")

        overview = get_dashboard_overview(self.bar, self.book_date)
        self.assertEqual(overview["revenue"], Decimal("58.00"))

    def test_deactivated_bundle_hidden_and_rejected(self):
        drinks = create_bundle(self.bar, "Drinks Package", "Two drinks", "8.00")
        set_bundle_active(self.bar, drinks.id, False)

        page = self.client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertNotContains(page, "Drinks Package")

        self.login_guest()
        response = self.api_post(
            self.client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
                "bundle_ids": [drinks.id],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "inactive_bundle")


class LayoutServiceTests(BookingTestMixin, TestCase):
    def test_get_layout_payload_includes_existing_sunbed(self):
        payload = get_layout_editor_payload(self.bar)
        self.assertGreaterEqual(payload["rows"], 1)
        self.assertGreaterEqual(payload["cols"], 1)
        cell = payload["cells"][self.sunbed_a.grid_row][self.sunbed_a.grid_col]
        self.assertIsNotNone(cell)
        self.assertEqual(cell["sunbed_id"], self.sunbed_a.id)
        self.assertEqual(cell["label"], "A1")

    def test_save_adds_sunbed_on_empty_cell(self):
        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": 0,
                    "col": 0,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": 0,
                    "col": 1,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
                {"row": 1, "col": 0, "category_id": self.category.id},
            ],
        )
        self.assertEqual(Sunbed.objects.filter(beach_bar=self.bar).count(), 3)
        new_bed = Sunbed.objects.get(beach_bar=self.bar, grid_row=1, grid_col=0)
        self.assertTrue(new_bed.label.startswith("S"))

    def test_save_blocks_removing_active_booking(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            )
        self.assertEqual(ctx.exception.code, "has_active_bookings")

    def test_save_blocks_moving_active_booking(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[
                    {
                        "row": 1,
                        "col": 0,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_a.id,
                    },
                ],
            )
        self.assertEqual(ctx.exception.code, "has_active_bookings")


class LayoutApiTests(BookingTestMixin, TestCase):
    def test_owner_can_get_layout(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.get(reverse("api_owner_layout"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rows", data)
        self.assertIn("cols", data)
        self.assertIn("categories", data)
        self.assertIn("cells", data)

    def test_owner_save_layout_round_trip(self):
        self.client.login(email=self.owner.email, password="testpass123")
        payload = {
            "rows": 2,
            "cols": 2,
            "cells": [
                {
                    "row": 0,
                    "col": 0,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": 0,
                    "col": 1,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
                {"row": 1, "col": 0, "category_id": self.category.id},
            ],
        }
        response = self.api_post(self.client, reverse("api_owner_layout"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        layout = response.json()["layout"]
        self.assertIsNotNone(layout["cells"][1][0])
        self.assertEqual(Sunbed.objects.filter(beach_bar=self.bar).count(), 3)

    def test_guest_cannot_access_layout_api(self):
        self.login_guest()
        response = self.client.get(reverse("api_owner_layout"))
        self.assertEqual(response.status_code, 403)

    def test_save_blocks_active_booking_via_api(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_layout"),
            {
                "rows": 2,
                "cols": 2,
                "cells": [
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "has_active_bookings")


class LayoutUiTests(BookingTestMixin, TestCase):
    def test_layout_tab_renders_editor(self):
        self.client.login(email=self.owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"), {"tab": "layout"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="tab-layout"')
        self.assertContains(page, reverse("api_owner_layout"))
        self.assertContains(page, 'id="le-grid"')
        self.assertContains(page, 'id="le-save"')
        self.assertContains(page, "/static/core/js/layout_editor.js")

    def test_sidebar_includes_layout_link(self):
        self.client.login(email=self.owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"))
        self.assertContains(page, 'data-tab="layout"')
        self.assertContains(page, "Layout")


class LayoutIntegrationTests(BookingTestMixin, TestCase):
    def test_saved_layout_appears_on_guest_map(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        guest_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")

        save_response = self.api_post(
            owner_client,
            reverse("api_owner_layout"),
            {
                "rows": 2,
                "cols": 2,
                "cells": [
                    {
                        "row": 0,
                        "col": 0,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_a.id,
                    },
                    {"row": 0, "col": 1, "category_id": self.category.id},
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        new_label = save_response.json()["layout"]["cells"][0][1]["label"]

        map_data = guest_client.get(
            f"{reverse('api_bar_sunbeds', args=[self.bar.id])}?date={self.book_date.isoformat()}"
        ).json()
        map_labels = {
            cell.get("label")
            for row in map_data["rows"]
            for cell in row
            if cell
        }
        self.assertIn(new_label, map_labels)
        self.assertNotIn(self.sunbed_b.label, map_labels)

        beach_page = guest_client.get(
            reverse("beach_bar", args=[self.bar.id]),
            {"date": self.book_date.isoformat()},
        )
        self.assertContains(beach_page, new_label)


class LayoutEdgeCaseTests(BookingTestMixin, TestCase):
    def test_save_first_layout_on_empty_bar(self):
        empty_bar = BeachBar.objects.create(
            owner=self.owner,
            name="Empty Shore",
            address="2 Sand Ln",
            city="Ulcinj",
            opening_time=time(9, 0),
            closing_time=time(18, 0),
        )
        category = SunbedCategory.objects.create(
            beach_bar=empty_bar,
            name="Standard",
            price=Decimal("10.00"),
        )
        payload = save_bar_layout(
            empty_bar,
            rows=2,
            cols=2,
            cells=[
                {"row": 0, "col": 0, "category_id": category.id},
                {"row": 1, "col": 1, "category_id": category.id},
            ],
        )
        self.assertEqual(Sunbed.objects.filter(beach_bar=empty_bar).count(), 2)
        self.assertIsNotNone(payload["cells"][0][0])
        self.assertIsNotNone(payload["cells"][1][1])

    def test_edit_preserves_price_at_booking_on_existing_reservation(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        reservation = Reservation.objects.get(sunbed=self.sunbed_a)
        original_price = reservation.price_at_booking

        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": 0,
                    "col": 0,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": 0,
                    "col": 1,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
            ],
        )
        update_category_prices(self.bar, {self.category.id: "99.00"})
        reservation.refresh_from_db()
        self.assertEqual(reservation.price_at_booking, original_price)

    def test_cannot_remove_sunbed_with_booking_history(self):
        reservations = book_sunbeds(
            self.guest, self.bar, self.book_date, [self.sunbed_a.id]
        )
        cancel_reservation(self.guest, reservations[0].id)
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            )
        self.assertEqual(ctx.exception.code, "has_booking_history")


class Slice8FlowTests(BookingTestMixin, TestCase):
    def test_owner_layout_booking_guard_flow(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        guest_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")

        save_response = self.api_post(
            owner_client,
            reverse("api_owner_layout"),
            {
                "rows": 2,
                "cols": 2,
                "cells": [
                    {
                        "row": 0,
                        "col": 0,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_a.id,
                    },
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        labels = {
            cell["label"]
            for row in save_response.json()["layout"]["cells"]
            for cell in row
            if cell
        }
        self.assertEqual(len(labels), 2)

        guest_client.login(email=self.guest.email, password="testpass123")
        book_response = self.api_post(
            guest_client,
            reverse("api_book_sunbeds", args=[self.bar.id]),
            {
                "date": self.book_date.isoformat(),
                "sunbed_ids": [self.sunbed_a.id],
            },
        )
        self.assertEqual(book_response.status_code, 200)

        blocked = self.api_post(
            owner_client,
            reverse("api_owner_layout"),
            {
                "rows": 2,
                "cols": 2,
                "cells": [
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            },
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.json()["code"], "has_active_bookings")

        cancel_reservation(self.guest, book_response.json()["reservations"][0]["id"])
        still_blocked = self.api_post(
            owner_client,
            reverse("api_owner_layout"),
            {
                "rows": 2,
                "cols": 2,
                "cells": [
                    {
                        "row": 0,
                        "col": 1,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_b.id,
                    },
                ],
            },
        )
        self.assertEqual(still_blocked.status_code, 400)
        self.assertEqual(still_blocked.json()["code"], "has_booking_history")

    def test_layout_dashboard_payload_matches_api(self):
        self.client.login(email=self.owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"), {"tab": "layout"})
        self.assertContains(page, reverse("api_owner_layout"))
        api_data = self.client.get(reverse("api_owner_layout")).json()
        self.assertGreaterEqual(api_data["rows"], 1)
        self.assertIn(self.category.name, str(api_data["categories"]))


class LayoutRiskTests(BookingTestMixin, TestCase):
    """Guards against regressions on validation, relabeling, and booking edge cases."""

    def test_can_change_category_on_active_booked_spot_at_same_cell(self):
        premium = SunbedCategory.objects.create(
            beach_bar=self.bar,
            name="Premium",
            price=Decimal("40.00"),
        )
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        reservation = Reservation.objects.get(sunbed=self.sunbed_a)

        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": self.sunbed_a.grid_row,
                    "col": self.sunbed_a.grid_col,
                    "category_id": premium.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": self.sunbed_b.grid_row,
                    "col": self.sunbed_b.grid_col,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
            ],
        )

        self.sunbed_a.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.sunbed_a.category_id, premium.id)
        self.assertEqual(reservation.sunbed_id, self.sunbed_a.id)
        self.assertEqual(reservation.status, ReservationStatus.ACTIVE)

    def test_relabel_assigns_unique_labels_per_category(self):
        premium = SunbedCategory.objects.create(
            beach_bar=self.bar,
            name="Premium",
            price=Decimal("40.00"),
        )
        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": 0,
                    "col": 0,
                    "category_id": premium.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": 0,
                    "col": 1,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
                {"row": 1, "col": 0, "category_id": premium.id},
            ],
        )
        labels = list(
            Sunbed.objects.filter(beach_bar=self.bar).values_list("label", flat=True)
        )
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("P1", labels)
        self.assertIn("P2", labels)
        self.assertIn("S1", labels)

    def test_rejects_duplicate_cell_position(self):
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[
                    {"row": 0, "col": 0, "category_id": self.category.id},
                    {"row": 0, "col": 0, "category_id": self.category.id},
                ],
            )
        self.assertEqual(ctx.exception.code, "invalid_cells")

    def test_rejects_cell_outside_grid_bounds(self):
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[{"row": 2, "col": 0, "category_id": self.category.id}],
            )
        self.assertEqual(ctx.exception.code, "invalid_cells")

    def test_rejects_invalid_grid_size(self):
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=13,
                cols=10,
                cells=[{"row": 0, "col": 0, "category_id": self.category.id}],
            )
        self.assertEqual(ctx.exception.code, "invalid_grid")

    def test_rejects_foreign_category_id(self):
        other_bar = BeachBar.objects.create(
            owner=self.owner,
            name="Other Bar",
            address="9 Pier",
            city="Kotor",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        foreign_category = SunbedCategory.objects.create(
            beach_bar=other_bar,
            name="Standard",
            price=Decimal("20.00"),
        )
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[{"row": 0, "col": 0, "category_id": foreign_category.id}],
            )
        self.assertEqual(ctx.exception.code, "invalid_category")

    def test_rejects_duplicate_sunbed_id_in_payload(self):
        with self.assertRaises(LayoutError) as ctx:
            save_bar_layout(
                self.bar,
                rows=2,
                cols=2,
                cells=[
                    {
                        "row": 0,
                        "col": 0,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_a.id,
                    },
                    {
                        "row": 1,
                        "col": 0,
                        "category_id": self.category.id,
                        "sunbed_id": self.sunbed_a.id,
                    },
                ],
            )
        self.assertEqual(ctx.exception.code, "invalid_cells")

    def test_save_empty_cells_removes_unbooked_sunbeds(self):
        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": 0,
                    "col": 0,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
            ],
        )
        self.assertFalse(Sunbed.objects.filter(id=self.sunbed_b.id).exists())
        self.assertTrue(Sunbed.objects.filter(id=self.sunbed_a.id).exists())

    def test_layout_api_rejects_invalid_json(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.post(
            reverse("api_owner_layout"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_layout_api_rejects_missing_cells(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_layout"),
            {"rows": 2, "cols": 2},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_cells")

    def test_active_booking_still_bookable_after_layout_relabel(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        reservation = Reservation.objects.get(sunbed=self.sunbed_a)
        original_sunbed_id = reservation.sunbed_id

        save_bar_layout(
            self.bar,
            rows=2,
            cols=2,
            cells=[
                {
                    "row": 0,
                    "col": 0,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_a.id,
                },
                {
                    "row": 0,
                    "col": 1,
                    "category_id": self.category.id,
                    "sunbed_id": self.sunbed_b.id,
                },
            ],
        )

        reservation.refresh_from_db()
        self.sunbed_a.refresh_from_db()
        self.assertEqual(reservation.sunbed_id, original_sunbed_id)
        self.assertEqual(self.sunbed_a.label, "S1")

        map_data = get_sunbed_map_payload(self.bar, self.book_date)
        booked = [
            cell
            for row in map_data["rows"]
            for cell in row
            if cell and cell.get("id") == self.sunbed_a.id
        ]
        self.assertEqual(len(booked), 1)
        self.assertTrue(booked[0]["is_taken"])


class ExploreTestMixin(BookingTestMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        cls.wifi = Amenity.objects.create(name="Wi-Fi")
        cls.showers = Amenity.objects.create(name="Showers")
        BeachBarAmenity.objects.create(beach_bar=cls.bar, amenity=cls.parking)
        BeachBarAmenity.objects.create(beach_bar=cls.bar, amenity=cls.wifi)

        cls.other_bar = BeachBar.objects.create(
            owner=cls.owner,
            name="Aqua Cove",
            address="2 Pier",
            city="Bar",
            opening_time=time(9, 0),
            closing_time=time(19, 0),
        )
        cls.other_category = SunbedCategory.objects.create(
            beach_bar=cls.other_bar,
            name="Standard",
            price=Decimal("12.00"),
        )
        cls.other_sunbed = Sunbed.objects.create(
            beach_bar=cls.other_bar,
            category=cls.other_category,
            label="A1",
            grid_row=0,
            grid_col=0,
        )
        BeachBarAmenity.objects.create(beach_bar=cls.other_bar, amenity=cls.parking)

        cls.empty_bar = BeachBar.objects.create(
            owner=cls.owner,
            name="Bare Shore",
            address="3 Sand",
            city="Ulcinj",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
        )


class ExploreServiceTests(ExploreTestMixin, TestCase):
    def test_list_amenities_sorted_by_name(self):
        names = [item["name"] for item in list_amenities()]
        self.assertEqual(names, sorted(names))
        self.assertIn("Parking", names)

    def test_search_filters_by_city(self):
        bars = search_bars(city="Budva", filter_date=self.book_date)
        names = {bar.name for bar in bars}
        self.assertIn(self.bar.name, names)
        self.assertNotIn(self.other_bar.name, names)

    def test_search_amenity_and_requires_all_selected(self):
        both = search_bars(
            filter_date=self.book_date,
            amenity_ids=[self.parking.id, self.wifi.id],
        )
        names = {bar.name for bar in both}
        self.assertIn(self.bar.name, names)
        self.assertNotIn(self.other_bar.name, names)

        parking_only = search_bars(
            filter_date=self.book_date,
            amenity_ids=[self.parking.id],
        )
        parking_names = {bar.name for bar in parking_only}
        self.assertIn(self.bar.name, parking_names)
        self.assertIn(self.other_bar.name, parking_names)

    def test_search_filters_by_min_and_max_price(self):
        cheap = search_bars(
            filter_date=self.book_date,
            max_price=Decimal("15.00"),
        )
        cheap_names = {bar.name for bar in cheap}
        self.assertIn(self.other_bar.name, cheap_names)
        self.assertNotIn(self.bar.name, cheap_names)

        expensive = search_bars(
            filter_date=self.book_date,
            min_price=Decimal("20.00"),
        )
        expensive_names = {bar.name for bar in expensive}
        self.assertIn(self.bar.name, expensive_names)
        self.assertNotIn(self.other_bar.name, expensive_names)

    def test_search_sort_by_price_asc(self):
        bars = search_bars(filter_date=self.book_date, sort="price_asc")
        priced = [bar for bar in bars if bar.min_price is not None]
        prices = [bar.min_price for bar in priced]
        self.assertEqual(prices, sorted(prices))

    def test_search_sort_by_rating_desc(self):
        Review.objects.create(
            user=self.guest,
            beach_bar=self.other_bar,
            rating=5,
            review_text="Great",
        )
        Review.objects.create(
            user=self.guest,
            beach_bar=self.bar,
            rating=3,
            review_text="Ok",
        )
        bars = search_bars(filter_date=self.book_date, sort="rating_desc")
        rated = [bar for bar in bars if bar.avg_rating is not None]
        self.assertGreaterEqual(rated[0].avg_rating, rated[1].avg_rating)

    def test_free_spots_reflect_active_bookings(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])
        bars = search_bars(city="Budva", filter_date=self.book_date)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].free_spots, 1)

    def test_zero_free_spots_still_listed(self):
        book_sunbeds(
            self.guest,
            self.bar,
            self.book_date,
            [self.sunbed_a.id, self.sunbed_b.id],
        )
        bars = search_bars(city="Budva", filter_date=self.book_date)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].free_spots, 0)

    def test_serialize_bar_payload_shape(self):
        bars = search_bars(city="Budva", filter_date=self.book_date)
        payload = serialize_bar(bars[0], self.book_date)
        self.assertEqual(payload["id"], self.bar.id)
        self.assertEqual(payload["name"], self.bar.name)
        self.assertEqual(payload["city"], self.bar.city)
        self.assertEqual(payload["min_price"], "25.00")
        self.assertEqual(payload["free_spots"], 2)
        self.assertIn(f"/bars/{self.bar.id}/", payload["url"])
        self.assertIn(self.book_date.isoformat(), payload["url"])

    def test_parse_helpers_reject_invalid_input(self):
        with self.assertRaises(ExploreError) as ctx:
            parse_amenity_ids("x")
        self.assertEqual(ctx.exception.code, "invalid_amenities")

        with self.assertRaises(ExploreError) as ctx:
            parse_price_bound("-1", "min_price")
        self.assertEqual(ctx.exception.code, "invalid_price")

        with self.assertRaises(ExploreError) as ctx:
            parse_sort("popular")
        self.assertEqual(ctx.exception.code, "invalid_sort")

    def test_amenity_ids_from_querydict_supports_csv_and_list(self):
        from django.http import QueryDict

        csv_q = QueryDict(f"amenity_ids={self.parking.id},{self.wifi.id}")
        self.assertEqual(
            amenity_ids_from_querydict(csv_q),
            [self.parking.id, self.wifi.id],
        )
        list_q = QueryDict(mutable=True)
        list_q.setlist("amenity_ids", [str(self.parking.id), str(self.wifi.id)])
        self.assertEqual(
            amenity_ids_from_querydict(list_q),
            [self.parking.id, self.wifi.id],
        )


class ExploreApiTests(ExploreTestMixin, TestCase):
    def test_explore_api_returns_bars(self):
        response = self.client.get(reverse("api_explore_bars"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("bars", data)
        self.assertIn("date", data)
        self.assertGreaterEqual(data["count"], 2)

    def test_explore_api_filters_city(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"city": "Budva"},
        )
        data = response.json()
        names = {bar["name"] for bar in data["bars"]}
        self.assertEqual(names, {self.bar.name})

    def test_explore_api_filters_amenities_and(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"amenity_ids": f"{self.parking.id},{self.wifi.id}"},
        )
        names = {bar["name"] for bar in response.json()["bars"]}
        self.assertIn(self.bar.name, names)
        self.assertNotIn(self.other_bar.name, names)

    def test_explore_api_filters_price(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"max_price": "15"},
        )
        names = {bar["name"] for bar in response.json()["bars"]}
        self.assertIn(self.other_bar.name, names)
        self.assertNotIn(self.bar.name, names)

    def test_explore_api_sort_price_asc(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"sort": "price_asc"},
        )
        priced = [
            Decimal(bar["min_price"])
            for bar in response.json()["bars"]
            if bar["min_price"] is not None
        ]
        self.assertEqual(priced, sorted(priced))

    def test_explore_api_rejects_invalid_price(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"min_price": "nope"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_price")

    def test_explore_api_rejects_invalid_sort(self):
        response = self.client.get(
            reverse("api_explore_bars"),
            {"sort": "popular"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_sort")

    def test_explore_api_public_no_auth_required(self):
        response = self.client.get(reverse("api_explore_bars"))
        self.assertEqual(response.status_code, 200)


class ExploreUiTests(ExploreTestMixin, TestCase):
    def test_explore_page_renders_filters_and_script(self):
        response = self.client.get(reverse("explore"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="explore-app"')
        self.assertContains(response, reverse("api_explore_bars"))
        self.assertContains(response, 'id="price-min"')
        self.assertContains(response, 'id="price-max"')
        self.assertContains(response, 'id="explore-sort"')
        self.assertContains(response, "/static/core/js/explore.js")
        self.assertContains(response, "Parking")
        self.assertContains(response, "Wi-Fi")

    def test_explore_page_server_renders_city_filter(self):
        response = self.client.get(reverse("explore"), {"city": "Budva"})
        self.assertContains(response, self.bar.name)
        self.assertNotContains(response, self.other_bar.name)

    def test_explore_page_server_renders_amenity_selection(self):
        response = self.client.get(
            reverse("explore"),
            {"amenity_ids": [self.parking.id, self.wifi.id]},
        )
        self.assertContains(response, self.bar.name)
        self.assertNotContains(response, self.other_bar.name)
        self.assertContains(
            response,
            f'value="{self.wifi.id}"',
        )
        self.assertContains(response, "checked")


class ExploreEdgeCaseTests(ExploreTestMixin, TestCase):
    def test_bar_without_categories_excluded_from_price_filter(self):
        bars = search_bars(
            filter_date=self.book_date,
            min_price=Decimal("1.00"),
        )
        names = {bar.name for bar in bars}
        self.assertNotIn(self.empty_bar.name, names)

        all_bars = search_bars(filter_date=self.book_date)
        all_names = {bar.name for bar in all_bars}
        self.assertIn(self.empty_bar.name, all_names)
        empty = next(bar for bar in all_bars if bar.id == self.empty_bar.id)
        self.assertIsNone(empty.min_price)

    def test_bar_without_amenities_fails_amenity_filter(self):
        bars = search_bars(
            filter_date=self.book_date,
            amenity_ids=[self.parking.id],
        )
        names = {bar.name for bar in bars}
        self.assertNotIn(self.empty_bar.name, names)

    def test_unknown_amenity_id_returns_empty(self):
        bars = search_bars(
            filter_date=self.book_date,
            amenity_ids=[999999],
        )
        self.assertEqual(bars, [])

    def test_invalid_date_falls_back_to_today_in_payload(self):
        payload = search_bars_payload(city="Budva", filter_date=None)
        self.assertEqual(payload["date"], date.today().isoformat())


class Slice9FlowTests(ExploreTestMixin, TestCase):
    def test_explore_filter_flow_city_amenity_and_date(self):
        book_sunbeds(self.guest, self.bar, self.book_date, [self.sunbed_a.id])

        response = self.client.get(
            reverse("api_explore_bars"),
            {
                "city": "Budva",
                "amenity_ids": f"{self.parking.id},{self.wifi.id}",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        bar = data["bars"][0]
        self.assertEqual(bar["name"], self.bar.name)
        self.assertEqual(bar["free_spots"], 1)
        self.assertEqual(bar["min_price"], "25.00")

        page = self.client.get(
            reverse("explore"),
            {
                "city": "Budva",
                "amenity_ids": f"{self.parking.id},{self.wifi.id}",
                "date": self.book_date.isoformat(),
            },
        )
        self.assertContains(page, self.bar.name)
        self.assertContains(page, "1 spot")
        self.assertNotContains(page, self.other_bar.name)

    def test_explore_price_sort_flow_matches_page_and_api(self):
        api_response = self.client.get(
            reverse("api_explore_bars"),
            {"sort": "price_asc"},
        )
        api_names = [
            bar["name"]
            for bar in api_response.json()["bars"]
            if bar["min_price"] is not None
        ]

        page = self.client.get(reverse("explore"), {"sort": "price_asc"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'value="price_asc"')
        body = page.content.decode()
        first = body.find(api_names[0])
        second = body.find(api_names[1])
        self.assertNotEqual(first, -1)
        self.assertNotEqual(second, -1)
        self.assertLess(first, second)

    def test_explore_dashboard_payload_includes_api_hook(self):
        page = self.client.get(reverse("explore"))
        self.assertContains(page, 'data-api-url="')
        self.assertContains(page, reverse("api_explore_bars"))
        self.assertContains(page, 'id="explore-apply"')
        self.assertContains(page, 'id="explore-clear"')


class BarSettingsServiceTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        cls.wifi = Amenity.objects.create(name="Wi-Fi")
        BeachBarAmenity.objects.create(beach_bar=cls.bar, amenity=cls.parking)

    def test_get_settings_payload_includes_amenities(self):
        payload = get_bar_settings_payload(self.bar)
        self.assertEqual(payload["name"], self.bar.name)
        self.assertEqual(payload["opening_time"], "08:00")
        amenities = {item["id"]: item["selected"] for item in payload["amenities"]}
        self.assertTrue(amenities[self.parking.id])
        self.assertFalse(amenities[self.wifi.id])

    def test_update_bar_fields_and_amenities(self):
        payload = update_bar_settings(
            self.bar,
            name="New Horizon",
            address="2 Shore Rd",
            city="Kotor",
            description="Updated description",
            opening_time="09:30",
            closing_time="21:00",
            map_url="https://maps.example.com/bar",
            amenity_ids=[self.wifi.id],
        )
        self.bar.refresh_from_db()
        self.assertEqual(self.bar.name, "New Horizon")
        self.assertEqual(self.bar.city, "Kotor")
        self.assertEqual(self.bar.opening_time.strftime("%H:%M"), "09:30")
        self.assertEqual(self.bar.map_url, "https://maps.example.com/bar")
        linked = set(
            BeachBarAmenity.objects.filter(beach_bar=self.bar).values_list(
                "amenity_id", flat=True
            )
        )
        self.assertEqual(linked, {self.wifi.id})
        selected = {
            item["id"] for item in payload["amenities"] if item["selected"]
        }
        self.assertEqual(selected, {self.wifi.id})

    def test_rejects_empty_name(self):
        with self.assertRaises(SettingsError) as ctx:
            update_bar_settings(
                self.bar,
                name="   ",
                address=self.bar.address,
                city=self.bar.city,
                description="",
                opening_time="08:00",
                closing_time="20:00",
                map_url="",
                amenity_ids=[],
            )
        self.assertEqual(ctx.exception.code, "invalid_name")

    def test_rejects_opening_not_before_closing(self):
        with self.assertRaises(SettingsError) as ctx:
            update_bar_settings(
                self.bar,
                name=self.bar.name,
                address=self.bar.address,
                city=self.bar.city,
                description="",
                opening_time="20:00",
                closing_time="08:00",
                map_url="",
                amenity_ids=[],
            )
        self.assertEqual(ctx.exception.code, "invalid_hours")

    def test_rejects_unknown_amenity(self):
        with self.assertRaises(SettingsError) as ctx:
            update_bar_settings(
                self.bar,
                name=self.bar.name,
                address=self.bar.address,
                city=self.bar.city,
                description="",
                opening_time="08:00",
                closing_time="20:00",
                map_url="",
                amenity_ids=[999999],
            )
        self.assertEqual(ctx.exception.code, "invalid_amenities")

    def test_clear_all_amenities(self):
        update_bar_settings(
            self.bar,
            name=self.bar.name,
            address=self.bar.address,
            city=self.bar.city,
            description="",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[],
        )
        self.assertFalse(
            BeachBarAmenity.objects.filter(beach_bar=self.bar).exists()
        )


class BarSettingsApiTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")

    def test_owner_can_get_and_save_settings(self):
        self.client.login(email=self.owner.email, password="testpass123")
        get_response = self.client.get(reverse("api_owner_settings"))
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["name"], self.bar.name)

        post_response = self.api_post(
            self.client,
            reverse("api_owner_settings"),
            {
                "name": "API Horizon",
                "address": "3 Shore",
                "city": "Budva",
                "description": "From API",
                "opening_time": "07:00",
                "closing_time": "19:00",
                "map_url": "",
                "amenity_ids": [self.parking.id],
            },
        )
        self.assertEqual(post_response.status_code, 200)
        self.assertTrue(post_response.json()["ok"])
        self.bar.refresh_from_db()
        self.assertEqual(self.bar.name, "API Horizon")
        self.assertEqual(self.bar.opening_time.strftime("%H:%M"), "07:00")

    def test_guest_cannot_access_settings_api(self):
        self.login_guest()
        response = self.client.get(reverse("api_owner_settings"))
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_returns_400(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.client.post(
            reverse("api_owner_settings"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_validation_error_returns_400(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_settings"),
            {
                "name": "",
                "address": "x",
                "city": "y",
                "description": "",
                "opening_time": "08:00",
                "closing_time": "20:00",
                "map_url": "",
                "amenity_ids": [],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_name")


class BarSettingsUiTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        BeachBarAmenity.objects.create(beach_bar=cls.bar, amenity=cls.parking)

    def test_settings_tab_renders_form(self):
        self.client.login(email=self.owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"), {"tab": "settings"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="tab-settings"')
        self.assertContains(page, reverse("api_owner_settings"))
        self.assertContains(page, 'id="bar-settings-form"')
        self.assertContains(page, 'id="save-settings-btn"')
        self.assertContains(page, "/static/core/js/bar_settings.js")
        self.assertContains(page, self.bar.name)
        self.assertContains(page, "Parking")
        self.assertContains(page, 'data-tab="settings"')


class BarSettingsIntegrationTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        cls.wifi = Amenity.objects.create(name="Wi-Fi")

    def test_saved_settings_appear_on_guest_page_and_explore(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            owner_client,
            reverse("api_owner_settings"),
            {
                "name": "Guest Visible Bar",
                "address": "9 Coast",
                "city": "Tivat",
                "description": "Sunny cove",
                "opening_time": "10:00",
                "closing_time": "18:00",
                "map_url": "https://maps.example.com/tivat",
                "amenity_ids": [self.wifi.id],
            },
        )
        self.assertEqual(response.status_code, 200)

        guest_page = self.client.get(reverse("beach_bar", args=[self.bar.id]))
        self.assertContains(guest_page, "Guest Visible Bar")
        self.assertContains(guest_page, "Sunny cove")
        self.assertContains(guest_page, "10:00")
        self.assertContains(guest_page, "18:00")
        self.assertContains(guest_page, "Wi-Fi")
        self.assertContains(guest_page, "Open in Maps")
        self.assertNotContains(guest_page, "Parking")

        explore = self.client.get(
            reverse("api_explore_bars"),
            {"city": "Tivat", "amenity_ids": str(self.wifi.id)},
        )
        names = {bar["name"] for bar in explore.json()["bars"]}
        self.assertIn("Guest Visible Bar", names)


class BarSettingsEdgeCaseTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        BeachBarAmenity.objects.create(beach_bar=cls.bar, amenity=cls.parking)

    def test_blank_description_and_map_url_allowed(self):
        update_bar_settings(
            self.bar,
            name=self.bar.name,
            address=self.bar.address,
            city=self.bar.city,
            description="   ",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[self.parking.id],
        )
        self.bar.refresh_from_db()
        self.assertIsNone(self.bar.description)
        self.assertIsNone(self.bar.map_url)

    def test_cleared_amenities_hide_from_guest_and_explore_filter(self):
        update_bar_settings(
            self.bar,
            name=self.bar.name,
            address=self.bar.address,
            city=self.bar.city,
            description="Still here",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[],
        )
        guest_page = self.client.get(reverse("beach_bar", args=[self.bar.id]))
        self.assertNotContains(guest_page, "Parking")

        explore = self.client.get(
            reverse("api_explore_bars"),
            {"amenity_ids": str(self.parking.id)},
        )
        names = {bar["name"] for bar in explore.json()["bars"]}
        self.assertNotIn(self.bar.name, names)


class Slice10FlowTests(BookingTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parking = Amenity.objects.create(name="Parking")
        cls.wifi = Amenity.objects.create(name="Wi-Fi")

    def test_owner_settings_flow_end_to_end(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")

        page = owner_client.get(reverse("owner_dashboard"), {"tab": "settings"})
        self.assertContains(page, reverse("api_owner_settings"))
        self.assertContains(page, 'id="bar-name"')

        save = self.api_post(
            owner_client,
            reverse("api_owner_settings"),
            {
                "name": "Flow Beach",
                "address": "1 Flow",
                "city": "Ulcinj",
                "description": "Flow desc",
                "opening_time": "09:00",
                "closing_time": "17:00",
                "map_url": "https://maps.example.com/flow",
                "amenity_ids": [self.parking.id, self.wifi.id],
            },
        )
        self.assertEqual(save.status_code, 200)

        page_after = owner_client.get(
            reverse("owner_dashboard"), {"tab": "settings"}
        )
        self.assertContains(page_after, "Flow Beach")
        self.assertContains(page_after, "Ulcinj")
        self.assertContains(page_after, 'value="09:00"')

        guest = self.client.get(reverse("beach_bar", args=[self.bar.id]))
        self.assertContains(guest, "Flow Beach")
        self.assertContains(guest, "Parking")
        self.assertContains(guest, "Wi-Fi")

        explore = self.client.get(
            reverse("api_explore_bars"),
            {
                "city": "Ulcinj",
                "amenity_ids": f"{self.parking.id},{self.wifi.id}",
            },
        )
        self.assertEqual(explore.json()["count"], 1)
        self.assertEqual(explore.json()["bars"][0]["name"], "Flow Beach")


class Slice11FlowTests(BookingTestMixin, TestCase):
    def test_owner_category_crud_flow_end_to_end(self):
        owner_client = Client(HTTP_HOST="127.0.0.1")
        owner_client.login(email=self.owner.email, password="testpass123")

        page = owner_client.get(reverse("owner_dashboard"), {"tab": "pricing"})
        self.assertContains(page, reverse("api_owner_create_category"))
        self.assertContains(page, "new-category-btn")

        create = self.api_post(
            owner_client,
            reverse("api_owner_create_category"),
            {
                "name": "Cabana",
                "description": "Private shade",
                "price": "95.00",
            },
        )
        self.assertEqual(create.status_code, 200)
        cabana_id = create.json()["category"]["id"]

        layout_payload = get_layout_editor_payload(self.bar)
        self.assertIn("Cabana", {c["name"] for c in layout_payload["categories"]})

        update = self.api_post(
            owner_client,
            reverse("api_owner_update_category", args=[cabana_id]),
            {
                "name": "Premium Cabana",
                "description": "Front cabana",
                "price": "110.00",
            },
        )
        self.assertEqual(update.status_code, 200)

        standard_update = self.api_post(
            owner_client,
            reverse("api_owner_update_category", args=[self.category.id]),
            {
                "name": "Standard",
                "description": "",
                "price": "30.00",
            },
        )
        self.assertEqual(standard_update.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.price, Decimal("30.00"))

        page_after = owner_client.get(reverse("owner_dashboard"), {"tab": "pricing"})
        self.assertContains(page_after, "Premium Cabana")
        self.assertContains(page_after, "110.00")
        self.assertContains(page_after, "30.00")

        blocked = self.api_post(
            owner_client,
            reverse("api_owner_delete_category", args=[self.category.id]),
            {},
        )
        self.assertEqual(blocked.status_code, 400)

        delete = self.api_post(
            owner_client,
            reverse("api_owner_delete_category", args=[cabana_id]),
            {},
        )
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(SunbedCategory.objects.filter(pk=cabana_id).exists())


class OnboardingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="newowner@test.beach",
            password="testpass123",
            first_name="New",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        cls.parking = Amenity.objects.create(name="Parking")

    def test_create_owner_bar_seeds_default_categories(self):
        bar = create_owner_bar(
            self.owner,
            name="Fresh Beach",
            address="1 New Rd",
            city="Budva",
            description="Brand new",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[self.parking.id],
        )
        self.assertEqual(bar.owner_id, self.owner.id)
        self.assertEqual(bar.name, "Fresh Beach")
        categories = list(
            SunbedCategory.objects.filter(beach_bar=bar).order_by("name")
        )
        self.assertEqual(len(categories), 2)
        names = {category.name: category.price for category in categories}
        self.assertEqual(names["Premium"], Decimal("25.00"))
        self.assertEqual(names["Standard"], Decimal("15.00"))
        self.assertTrue(
            BeachBarAmenity.objects.filter(
                beach_bar=bar, amenity=self.parking
            ).exists()
        )
        self.assertEqual(Sunbed.objects.filter(beach_bar=bar).count(), 0)

    def test_second_create_blocked(self):
        create_owner_bar(
            self.owner,
            name="First Bar",
            address="1 Rd",
            city="Bar",
            description="",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[],
        )
        with self.assertRaises(OnboardingError) as ctx:
            create_owner_bar(
                self.owner,
                name="Second Bar",
                address="2 Rd",
                city="Bar",
                description="",
                opening_time="08:00",
                closing_time="20:00",
                map_url="",
                amenity_ids=[],
            )
        self.assertEqual(ctx.exception.code, "already_has_bar")

    def test_rejects_empty_name(self):
        with self.assertRaises(OnboardingError) as ctx:
            create_owner_bar(
                self.owner,
                name="  ",
                address="1 Rd",
                city="Bar",
                description="",
                opening_time="08:00",
                closing_time="20:00",
                map_url="",
                amenity_ids=[],
            )
        self.assertEqual(ctx.exception.code, "invalid_name")

    def test_rejects_invalid_hours(self):
        with self.assertRaises(OnboardingError) as ctx:
            create_owner_bar(
                self.owner,
                name="Hours Bar",
                address="1 Rd",
                city="Bar",
                description="",
                opening_time="20:00",
                closing_time="08:00",
                map_url="",
                amenity_ids=[],
            )
        self.assertEqual(ctx.exception.code, "invalid_hours")

    def test_empty_amenities_allowed(self):
        bar = create_owner_bar(
            self.owner,
            name="No Amenity Bar",
            address="1 Rd",
            city="Bar",
            description="",
            opening_time="08:00",
            closing_time="20:00",
            map_url="",
            amenity_ids=[],
        )
        self.assertFalse(BeachBarAmenity.objects.filter(beach_bar=bar).exists())

    def test_setup_form_payload_lists_amenities(self):
        payload = get_setup_form_payload()
        self.assertEqual(payload["opening_time"], "08:00")
        names = [item["name"] for item in payload["amenities"]]
        self.assertIn("Parking", names)


class OnboardingApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="setupowner@test.beach",
            password="testpass123",
            first_name="Setup",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        cls.guest = User.objects.create_user(
            email="setupguest@test.beach",
            password="testpass123",
            first_name="Setup",
            last_name="Guest",
        )
        cls.parking = Amenity.objects.create(name="Parking")

    def api_post(self, client, url, payload=None):
        return client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def test_owner_can_create_bar_via_api(self):
        self.client.login(email=self.owner.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_setup"),
            {
                "name": "API Beach",
                "address": "9 Coast",
                "city": "Tivat",
                "description": "Created via API",
                "opening_time": "09:00",
                "closing_time": "19:00",
                "map_url": "",
                "amenity_ids": [self.parking.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("bar_id", data)
        self.assertEqual(data["redirect_url"], "/owner/?tab=settings")
        bar = BeachBar.objects.get(id=data["bar_id"])
        self.assertEqual(bar.owner_id, self.owner.id)
        self.assertEqual(
            SunbedCategory.objects.filter(beach_bar=bar).count(),
            len(DEFAULT_CATEGORIES),
        )

    def test_second_setup_returns_400(self):
        self.client.login(email=self.owner.email, password="testpass123")
        payload = {
            "name": "Only Bar",
            "address": "1 Rd",
            "city": "Bar",
            "description": "",
            "opening_time": "08:00",
            "closing_time": "20:00",
            "map_url": "",
            "amenity_ids": [],
        }
        first = self.api_post(self.client, reverse("api_owner_setup"), payload)
        self.assertEqual(first.status_code, 200)
        second = self.api_post(self.client, reverse("api_owner_setup"), payload)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "already_has_bar")

    def test_guest_cannot_setup(self):
        self.client.login(email=self.guest.email, password="testpass123")
        response = self.api_post(
            self.client,
            reverse("api_owner_setup"),
            {
                "name": "Nope",
                "address": "1",
                "city": "X",
                "description": "",
                "opening_time": "08:00",
                "closing_time": "20:00",
                "map_url": "",
                "amenity_ids": [],
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_gets_401(self):
        response = self.api_post(self.client, reverse("api_owner_setup"), {})
        self.assertEqual(response.status_code, 401)


class OnboardingUiTests(TestCase):
    def test_owner_login_redirects_to_setup_when_no_bar(self):
        owner = User.objects.create_user(
            email="loginowner@test.beach",
            password="testpass123",
            first_name="Login",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        response = self.client.post(
            reverse("login"),
            {"email": owner.email, "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("owner_dashboard"))
        setup_page = self.client.get(response.url)
        self.assertContains(setup_page, "Create your beach bar")

    def test_owner_login_with_next_honors_next(self):
        owner = User.objects.create_user(
            email="nextowner@test.beach",
            password="testpass123",
            first_name="Next",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        response = self.client.post(
            reverse("login"),
            {
                "email": owner.email,
                "password": "testpass123",
                "next": "/explore/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/explore/")

    def test_setup_page_renders_for_owner_without_bar(self):
        owner = User.objects.create_user(
            email="uiowner@test.beach",
            password="testpass123",
            first_name="Ui",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        Amenity.objects.create(name="Wi-Fi")
        self.client.login(email=owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="bar-setup-form"')
        self.assertContains(page, reverse("api_owner_setup"))
        self.assertContains(page, "/static/core/js/bar_setup.js")
        self.assertContains(page, "Wi-Fi")
        self.assertContains(page, "Standard and Premium")

    def test_owner_with_bar_sees_dashboard_not_setup(self):
        owner = User.objects.create_user(
            email="hasbar@test.beach",
            password="testpass123",
            first_name="Has",
            last_name="Bar",
            role=UserRole.OWNER,
        )
        BeachBar.objects.create(
            owner=owner,
            name="Existing",
            address="1",
            city="Budva",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        self.client.login(email=owner.email, password="testpass123")
        page = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="tab-overview"')
        self.assertNotContains(page, 'id="bar-setup-form"')


class Slice13FlowTests(TestCase):
    def api_post(self, client, url, payload=None):
        return client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def test_register_owner_create_bar_reaches_dashboard_tabs(self):
        Amenity.objects.create(name="Parking")
        register = self.client.post(
            reverse("register"),
            {
                "first_name": "Reg",
                "last_name": "Owner",
                "email": "regowner@test.beach",
                "password": "testpass123",
                "role": UserRole.OWNER,
                "terms": "on",
            },
        )
        self.assertEqual(register.status_code, 302)
        self.assertEqual(register.url, reverse("owner_dashboard"))

        setup_page = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(setup_page.status_code, 200)
        self.assertContains(setup_page, "Create your beach bar")

        create = self.api_post(
            self.client,
            reverse("api_owner_setup"),
            {
                "name": "Registered Beach",
                "address": "5 Coast",
                "city": "Budva",
                "description": "From register flow",
                "opening_time": "08:00",
                "closing_time": "20:00",
                "map_url": "https://maps.example.com/reg",
                "amenity_ids": [],
            },
        )
        self.assertEqual(create.status_code, 200)
        bar_id = create.json()["bar_id"]

        settings_page = self.client.get(
            reverse("owner_dashboard"), {"tab": "settings"}
        )
        self.assertContains(settings_page, "Registered Beach")
        self.assertContains(settings_page, "Budva")

        pricing_page = self.client.get(
            reverse("owner_dashboard"), {"tab": "pricing"}
        )
        self.assertContains(pricing_page, "Standard")
        self.assertContains(pricing_page, "Premium")
        self.assertContains(pricing_page, "15.00")
        self.assertContains(pricing_page, "25.00")

        layout_page = self.client.get(
            reverse("owner_dashboard"), {"tab": "layout"}
        )
        self.assertContains(layout_page, 'id="tab-layout"')
        self.assertContains(layout_page, reverse("api_owner_layout"))

        guest_page = self.client.get(reverse("beach_bar", args=[bar_id]))
        self.assertContains(guest_page, "Registered Beach")
        self.assertContains(guest_page, "From register flow")


class BarImageUrlTests(TestCase):
    def test_bar_image_url_prefers_stored_field(self):
        from core.services.beach_bar import bar_image_url

        owner = User.objects.create_user(
            email="imgowner@test.beach",
            password="testpass123",
            first_name="Img",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        custom_url = "https://images.example.com/custom-beach.jpg"
        bar = BeachBar.objects.create(
            owner=owner,
            name="Custom Image Bar",
            address="1 Shore",
            city="Budva",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
            image_url=custom_url,
        )
        self.assertEqual(bar_image_url(bar), custom_url)


class SeedBulkTests(TestCase):
    def test_seed_bulk_creates_bars_with_unique_images(self):
        from django.core.management import call_command

        call_command("seed_bulk", bars=5, seed=7)
        bulk_bars = BeachBar.objects.filter(
            owner__email__regex=r"^owner\d{3}@beachbooker\.test$"
        )
        self.assertEqual(bulk_bars.count(), 5)
        image_urls = set(bulk_bars.values_list("image_url", flat=True))
        self.assertEqual(len(image_urls), 5)
        self.assertTrue(all(url for url in image_urls))

    def test_seed_bulk_is_idempotent(self):
        from django.core.management import call_command

        call_command("seed_bulk", bars=4, seed=11)
        call_command("seed_bulk", bars=4, seed=11)
        bulk_bars = BeachBar.objects.filter(
            owner__email__regex=r"^owner\d{3}@beachbooker\.test$"
        )
        self.assertEqual(bulk_bars.count(), 4)

    def test_clear_bulk_removes_bulk_data_only(self):
        from django.core.management import call_command

        call_command("seed_demo")
        call_command("seed_bulk", bars=3, seed=3)
        demo_count_before = BeachBar.objects.filter(
            name__in=["Riccardo Beach Bar", "Porto Skver Beach"]
        ).count()
        self.assertEqual(demo_count_before, 2)

        call_command("seed_bulk", clear_bulk=True)

        self.assertEqual(
            BeachBar.objects.filter(
                owner__email__regex=r"^owner\d{3}@beachbooker\.test$"
            ).count(),
            0,
        )
        self.assertEqual(
            BeachBar.objects.filter(
                name__in=["Riccardo Beach Bar", "Porto Skver Beach"]
            ).count(),
            2,
        )
        self.assertTrue(
            User.objects.filter(email="owner@beachbooker.test").exists()
        )

    def test_search_bars_returns_bulk_cities(self):
        from django.core.management import call_command

        call_command("seed_bulk", bars=10, seed=5)
        payload = search_bars_payload(city="Budva")
        self.assertGreaterEqual(payload["count"], 1)
        for bar in payload["bars"]:
            self.assertTrue(bar["image_url"])

    def test_unfiltered_search_limits_to_eighteen(self):
        from django.core.management import call_command

        call_command("seed_bulk", bars=30, seed=9)
        bars = search_bars()
        self.assertEqual(len(bars), DEFAULT_UNFILTERED_LIMIT)
        filtered = search_bars(city="Budva")
        self.assertGreater(len(filtered), 0)
