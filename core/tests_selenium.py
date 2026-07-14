"""Selenium WebDriver UI tests for BeachBooker.

Requires Google Chrome. Selenium 4 downloads a matching ChromeDriver automatically.

Run (from project root, with venv active and .env / MySQL configured):

    python manage.py test core.tests_selenium

Watch the browser (headed mode):

    set SELENIUM_HEADLESS=0
    python manage.py test core.tests_selenium

Django unit tests (no browser):

    python manage.py test core.tests
"""

from __future__ import annotations

import os
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from core.models import (
    Bundle,
    BeachBar,
    Reservation,
    ReservationStatus,
    Sunbed,
    SunbedCategory,
    User,
    UserRole,
)

PASSWORD = "testpass123"
DEFAULT_WAIT = 12


def _headless_enabled() -> bool:
    raw = os.environ.get("SELENIUM_HEADLESS", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class SeleniumBase(StaticLiveServerTestCase):
    """Shared Chrome browser + per-test fixtures for UI tests.

    LiveServerTestCase resets the DB between tests, so fixtures belong in setUp().
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        if _headless_enabled():
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,900")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.browser = webdriver.Chrome(options=options)
        cls.browser.implicitly_wait(1)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def dismiss_alerts(self):
        for _ in range(5):
            try:
                alert = self.browser.switch_to.alert
                alert.accept()
            except Exception:
                break

    def setUp(self):
        self.wait = WebDriverWait(self.browser, DEFAULT_WAIT)
        self.dismiss_alerts()
        try:
            self.browser.delete_all_cookies()
        except Exception:
            self.dismiss_alerts()
            self.browser.delete_all_cookies()

        self.owner = User.objects.create_user(
            email="owner.selenium@test.beach",
            password=PASSWORD,
            first_name="Sel",
            last_name="Owner",
            role=UserRole.OWNER,
        )
        self.guest = User.objects.create_user(
            email="guest.selenium@test.beach",
            password=PASSWORD,
            first_name="Sel",
            last_name="Guest",
            role=UserRole.REGISTERED,
        )
        self.admin = User.objects.create_user(
            email="admin.selenium@test.beach",
            password=PASSWORD,
            first_name="Sel",
            last_name="Admin",
            role=UserRole.ADMIN,
        )
        self.bar = BeachBar.objects.create(
            owner=self.owner,
            name="Selenium Cove",
            address="1 Test Shore",
            city="Budva",
            description="Fixture bar for WebDriver tests.",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )
        self.other_bar = BeachBar.objects.create(
            owner=self.owner,
            name="Other Bay",
            address="9 Quiet Rd",
            city="Kotor",
            opening_time=time(9, 0),
            closing_time=time(19, 0),
        )
        self.category = SunbedCategory.objects.create(
            beach_bar=self.bar,
            name="Standard",
            price=Decimal("25.00"),
        )
        SunbedCategory.objects.create(
            beach_bar=self.other_bar,
            name="Standard",
            price=Decimal("40.00"),
        )
        self.sunbed_a = Sunbed.objects.create(
            beach_bar=self.bar,
            category=self.category,
            label="A1",
            grid_row=0,
            grid_col=0,
        )
        self.sunbed_b = Sunbed.objects.create(
            beach_bar=self.bar,
            category=self.category,
            label="A2",
            grid_row=0,
            grid_col=1,
        )
        Bundle.objects.create(
            beach_bar=self.bar,
            name="Parking Pass",
            description="Day parking",
            price=Decimal("5.00"),
            is_active=True,
        )

    def tearDown(self):
        self.dismiss_alerts()
        try:
            self.browser.get("about:blank")
        except Exception:
            self.dismiss_alerts()
        super().tearDown()

    def url(self, name, *args, **kwargs):
        path = reverse(name, args=args, kwargs=kwargs)
        return f"{self.live_server_url}{path}"

    def open(self, name, *args, **kwargs):
        self.browser.get(self.url(name, *args, **kwargs))

    def login_via_ui(self, email, password=PASSWORD, *, expect_success=True):
        self.dismiss_alerts()
        self.open("login")
        email_input = self.browser.find_element(By.NAME, "email")
        email_input.clear()
        email_input.send_keys(email)
        password_input = self.browser.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(password)
        self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        if expect_success:
            WebDriverWait(self.browser, DEFAULT_WAIT).until(
                lambda driver: "/login" not in driver.current_url
            )

    def wait_for_text(self, text, timeout=DEFAULT_WAIT):
        WebDriverWait(self.browser, timeout).until(
            EC.text_to_be_present_in_element((By.TAG_NAME, "body"), text)
        )

    def wait_css(self, selector, timeout=DEFAULT_WAIT):
        return WebDriverWait(self.browser, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def wait_clickable(self, selector, timeout=DEFAULT_WAIT):
        return WebDriverWait(self.browser, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )

    def set_date_input(self, element, iso_date):
        self.browser.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            element,
            iso_date,
        )


class AuthSeleniumTests(SeleniumBase):
    def test_01_login_success_guest_lands_on_explore(self):
        self.login_via_ui(self.guest.email)
        self.wait_for_text("Explore")
        self.assertIn("/explore", self.browser.current_url)
        self.assertIn("Sel", self.browser.page_source)

    def test_02_login_failure_shows_error(self):
        self.login_via_ui(self.guest.email, password="wrong-password", expect_success=False)
        self.wait_for_text("Invalid email or password.")
        self.assertIn("/login", self.browser.current_url)

    def test_03_register_beach_goer_success(self):
        self.open("register")
        self.browser.find_element(By.NAME, "first_name").send_keys("Nova")
        self.browser.find_element(By.NAME, "last_name").send_keys("Guest")
        self.browser.find_element(By.NAME, "email").send_keys("nova.selenium@test.beach")
        self.browser.find_element(By.NAME, "password").send_keys(PASSWORD)
        self.browser.find_element(By.NAME, "password_confirm").send_keys(PASSWORD)
        Select(self.browser.find_element(By.NAME, "role")).select_by_value("registered")
        self.browser.find_element(By.NAME, "terms").click()
        self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait_for_text("Explore")
        self.assertIn("/explore", self.browser.current_url)
        self.assertTrue(
            User.objects.filter(email="nova.selenium@test.beach").exists()
        )

    def test_04_register_password_mismatch_stays_on_form(self):
        self.open("register")
        self.browser.find_element(By.NAME, "first_name").send_keys("Bad")
        self.browser.find_element(By.NAME, "last_name").send_keys("Match")
        self.browser.find_element(By.NAME, "email").send_keys("badmatch.selenium@test.beach")
        self.browser.find_element(By.NAME, "password").send_keys(PASSWORD)
        self.browser.find_element(By.NAME, "password_confirm").send_keys("different99")
        Select(self.browser.find_element(By.NAME, "role")).select_by_value("registered")
        self.browser.find_element(By.NAME, "terms").click()
        self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait_for_text("Password confirmation does not match.")
        self.assertIn("/register", self.browser.current_url)

    def test_05_logout_returns_to_public_nav(self):
        self.login_via_ui(self.guest.email)
        self.wait_for_text("Log out")
        self.browser.find_element(By.LINK_TEXT, "Log out").click()
        self.wait_clickable("a[href*='login']")
        self.assertIn("Log in", self.browser.find_element(By.CSS_SELECTOR, ".nav__right").text)
        self.assertNotIn("Log out", self.browser.page_source)


class ExploreSeleniumTests(SeleniumBase):
    def test_06_explore_lists_fixture_bars(self):
        self.open("explore")
        self.wait_for_text("Selenium Cove")
        self.assertIn("Other Bay", self.browser.page_source)
        self.assertIn("beach bar", self.browser.page_source.lower())

    def test_07_explore_filter_by_city(self):
        self.open("explore")
        self.wait_css("#filter-loc")
        city = self.browser.find_element(By.ID, "filter-loc")
        city.clear()
        city.send_keys("Budva")
        self.browser.find_element(By.ID, "explore-apply").click()
        self.wait_for_text("Selenium Cove")
        try:
            WebDriverWait(self.browser, 5).until_not(
                EC.text_to_be_present_in_element((By.ID, "explore-results"), "Other Bay")
            )
        except TimeoutException:
            self.fail("City filter did not hide Other Bay")

    def test_08_explore_price_filter(self):
        self.open("explore")
        self.wait_css("#price-max")
        price_max = self.browser.find_element(By.ID, "price-max")
        price_max.clear()
        price_max.send_keys("30")
        self.browser.find_element(By.ID, "explore-apply").click()
        self.wait_for_text("Selenium Cove")
        try:
            WebDriverWait(self.browser, 5).until_not(
                EC.text_to_be_present_in_element((By.ID, "explore-results"), "Other Bay")
            )
        except TimeoutException:
            self.fail("Price filter did not hide higher-priced Other Bay")

    def test_09_explore_clear_filters(self):
        self.open("explore")
        self.wait_css("#filter-loc")
        city = self.browser.find_element(By.ID, "filter-loc")
        city.clear()
        city.send_keys("Budva")
        self.browser.find_element(By.ID, "explore-apply").click()
        self.wait_for_text("Selenium Cove")
        self.browser.find_element(By.ID, "explore-clear").click()
        self.wait_for_text("Other Bay")

    def test_10_open_bar_detail_from_explore(self):
        self.open("explore")
        self.wait_for_text("Selenium Cove")
        self.browser.find_element(By.PARTIAL_LINK_TEXT, "Selenium Cove").click()
        self.wait_for_text("Selenium Cove")
        self.assertIn(f"/bars/{self.bar.id}/", self.browser.current_url)
        self.wait_css("#beach-bar-booking")
        self.wait_css("#reserve-btn")


class BookingSeleniumTests(SeleniumBase):
    def test_11_guest_book_sunbed_lands_on_my_reservations(self):
        self.login_via_ui(self.guest.email)
        self.wait_for_text("Explore")
        self.browser.get(f"{self.live_server_url}/bars/{self.bar.id}/")
        root = self.wait_css("#beach-bar-booking")
        self.assertEqual(root.get_attribute("data-is-authenticated"), "true")
        spot = self.wait_clickable(".sb--clickable")
        spot.click()
        WebDriverWait(self.browser, DEFAULT_WAIT).until(
            lambda driver: driver.find_element(By.ID, "sum-bed").text != "0"
        )
        reserve = self.wait_clickable("#reserve-btn")
        reserve.click()
        try:
            WebDriverWait(self.browser, DEFAULT_WAIT).until(
                EC.url_contains("/my-reservations")
            )
        except TimeoutException:
            self.dismiss_alerts()
            self.fail(
                f"Booking did not redirect; url={self.browser.current_url!r} "
                f"body snippet={self.browser.page_source[:400]!r}"
            )
        self.assertTrue(
            Reservation.objects.filter(
                user=self.guest,
                status=ReservationStatus.ACTIVE,
            ).exists()
        )

    def test_12_my_reservations_active_tab_shows_booking(self):
        Reservation.objects.create(
            user=self.guest,
            sunbed=self.sunbed_a,
            reservation_date=date.today() + timedelta(days=1),
            status=ReservationStatus.ACTIVE,
            price_at_booking=Decimal("25.00"),
        )
        self.login_via_ui(self.guest.email)
        self.open("my_reservations")
        self.wait.until(EC.url_contains("/my-reservations"))
        active_tab = self.wait_css("button[data-tab='active']")
        self.wait_for_text("Selenium Cove")
        self.assertIn("on", active_tab.get_attribute("class"))
        self.assertIn("Active", self.browser.find_element(By.ID, "tab-active").text)

    def test_13_cancel_booking_moves_to_cancelled_tab(self):
        Reservation.objects.create(
            user=self.guest,
            sunbed=self.sunbed_b,
            reservation_date=date.today() + timedelta(days=2),
            status=ReservationStatus.ACTIVE,
            price_at_booking=Decimal("25.00"),
        )
        self.login_via_ui(self.guest.email)
        self.open("my_reservations")
        cancel_btn = self.wait_clickable(".cancel-reservation")
        cancel_btn.click()
        alert = self.wait.until(EC.alert_is_present())
        alert.accept()
        WebDriverWait(self.browser, DEFAULT_WAIT).until(
            lambda driver: Reservation.objects.filter(
                user=self.guest,
                sunbed_id=self.sunbed_b.id,
                status=ReservationStatus.CANCELLED,
            ).exists()
        )
        self.wait_clickable("button[data-tab='cancelled']").click()
        self.wait_for_text("Selenium Cove")
        cancelled_panel = self.browser.find_element(By.ID, "tab-cancelled")
        self.assertNotEqual(cancelled_panel.value_of_css_property("display"), "none")

    def test_14_unauthenticated_book_redirects_to_login(self):
        self.browser.get(f"{self.live_server_url}/bars/{self.bar.id}/")
        spot = self.wait_clickable(".sb--clickable")
        spot.click()
        self.wait_clickable("#reserve-btn").click()
        self.wait_for_text("Log in")
        self.assertIn("/login", self.browser.current_url)


class OwnerSeleniumTests(SeleniumBase):
    def test_15_owner_overview_shows_bar_and_date(self):
        self.login_via_ui(self.owner.email)
        self.wait_for_text("Selenium Cove")
        self.assertIn("/owner", self.browser.current_url)
        self.wait_css("#overview-date")
        self.assertIn("Bookings", self.browser.page_source)

    def test_16_owner_overview_apply_date_filter(self):
        self.login_via_ui(self.owner.email)
        self.wait_css("#overview-date")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        date_input = self.browser.find_element(By.ID, "overview-date")
        self.set_date_input(date_input, tomorrow)
        self.assertEqual(date_input.get_attribute("value"), tomorrow)
        self.browser.execute_script(
            "arguments[0].closest('form').submit();", date_input
        )
        WebDriverWait(self.browser, DEFAULT_WAIT).until(
            EC.url_contains(f"date={tomorrow}")
        )
        self.assertEqual(
            self.browser.find_element(By.ID, "overview-date").get_attribute("value"),
            tomorrow,
        )

    def test_17_owner_reservations_tab_loads(self):
        self.login_via_ui(self.owner.email)
        self.wait_for_text("Selenium Cove")
        self.browser.find_element(By.CSS_SELECTOR, "a[data-tab='reservations']").click()
        self.wait_for_text("Reservations")
        self.assertIn("tab=reservations", self.browser.current_url)
        self.wait_css("#tab-reservations")

    def test_18_owner_pricing_tab_shows_category(self):
        self.login_via_ui(self.owner.email)
        self.browser.find_element(By.CSS_SELECTOR, "a[data-tab='pricing']").click()
        self.wait_for_text("Standard")
        self.assertIn("tab=pricing", self.browser.current_url)
        self.wait_css("#category-list")
        self.assertIn("25", self.browser.page_source)

    def test_19_owner_bundles_and_settings_tabs(self):
        self.login_via_ui(self.owner.email)
        self.browser.find_element(By.CSS_SELECTOR, "a[data-tab='bundles']").click()
        self.wait_for_text("Parking Pass")
        self.assertIn("tab=bundles", self.browser.current_url)

        self.browser.find_element(By.CSS_SELECTOR, "a[data-tab='settings']").click()
        self.wait_css("#bar-settings-form")
        name_input = self.browser.find_element(By.ID, "bar-name")
        self.assertEqual(name_input.get_attribute("value"), "Selenium Cove")
        name_input.clear()
        name_input.send_keys("Selenium Cove Updated")
        self.browser.find_element(By.ID, "save-settings-btn").click()
        alert = self.wait.until(EC.alert_is_present())
        self.assertIn("saved", alert.text.lower())
        alert.accept()
        self.bar.refresh_from_db()
        self.assertEqual(self.bar.name, "Selenium Cove Updated")


class AdminSeleniumTests(SeleniumBase):
    def test_20_admin_panel_overview_and_users(self):
        self.login_via_ui(self.admin.email)
        self.wait_for_text("System overview")
        self.assertIn("/admin-panel", self.browser.current_url)
        self.assertIn("Beach bars", self.browser.page_source)

        self.browser.find_element(By.LINK_TEXT, "Users").click()
        self.wait_for_text("User accounts")
        self.assertIn("tab=users", self.browser.current_url)
        self.wait_for_text("guest.selenium@test.beach")
