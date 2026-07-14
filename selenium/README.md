# Selenium WebDriver tests — BeachBooker

This folder holds **course materials** (PDFs, example zip, chat notes).  
The **actual automated UI tests** live in the Django app:

```text
core/tests_selenium.py
```

Scope for this phase (as agreed): **Django unit tests** (`core/tests.py`) + **Selenium WebDriver** only.  
Selenium IDE is **not** used.

---

## Prerequisites

1. Normal Django setup working (`.env`, MySQL, migrations) — same as `runserver`.
2. **Google Chrome** installed.
3. Dependencies installed (includes `selenium`):

```powershell
python -m pip install -r requirements.txt
```

Selenium 4 downloads a matching **ChromeDriver** automatically — you do **not** need to install `chromedriver.exe` by hand.

You do **not** need `runserver` running. Tests start their own temporary LiveServer.

Cursor / VS Code: use the integrated terminal; no Selenium plugin is required.

---

## What the 20 tests cover

| # | Class | Test method | What it checks |
|---|--------|-------------|----------------|
| 1 | `AuthSeleniumTests` | `test_01_login_success_guest_lands_on_explore` | Guest logs in → Explore |
| 2 | | `test_02_login_failure_shows_error` | Wrong password → error on login |
| 3 | | `test_03_register_beach_goer_success` | Register beach-goer → Explore |
| 4 | | `test_04_register_password_mismatch_stays_on_form` | Mismatched passwords → validation |
| 5 | | `test_05_logout_returns_to_public_nav` | Log out → “Log in” in nav |
| 6 | `ExploreSeleniumTests` | `test_06_explore_lists_fixture_bars` | Explore lists fixture bars |
| 7 | | `test_07_explore_filter_by_city` | City filter (Budva) |
| 8 | | `test_08_explore_price_filter` | Max price filter |
| 9 | | `test_09_explore_clear_filters` | Clear filters restores results |
| 10 | | `test_10_open_bar_detail_from_explore` | Open bar detail from a card |
| 11 | `BookingSeleniumTests` | `test_11_guest_book_sunbed_lands_on_my_reservations` | Click spot → Book → My Bookings |
| 12 | | `test_12_my_reservations_active_tab_shows_booking` | Active tab shows a booking |
| 13 | | `test_13_cancel_booking_moves_to_cancelled_tab` | Cancel → Cancelled tab |
| 14 | | `test_14_unauthenticated_book_redirects_to_login` | Guest Book → login redirect |
| 15 | `OwnerSeleniumTests` | `test_15_owner_overview_shows_bar_and_date` | Owner Overview loads |
| 16 | | `test_16_owner_overview_apply_date_filter` | Overview date Apply |
| 17 | | `test_17_owner_reservations_tab_loads` | Reservations tab |
| 18 | | `test_18_owner_pricing_tab_shows_category` | Pricing / categories tab |
| 19 | | `test_19_owner_bundles_and_settings_tabs` | Bundles + save settings |
| 20 | `AdminSeleniumTests` | `test_20_admin_panel_overview_and_users` | Admin overview + Users |

Each test uses its **own fixture data** (not your seeded demo DB). You will see names like **Selenium Cove**, not necessarily Riccardo.

---

## How to run — whole suite (batch)

From the **project root** (`beach_booker/`):

```powershell
python manage.py test core.tests_selenium
```

**Headless (default):** Chrome runs in the background — faster, less flicker.  
**Headed (watch the browser):**

```powershell
$env:SELENIUM_HEADLESS="0"
python manage.py test core.tests_selenium
```

Expect roughly **~2 minutes** for all 20 and a final line like:

```text
Ran 20 tests in …
OK
```

Yes — they look **fast**. That is normal. Selenium clicks as quickly as the browser allows; it is not a slow demo recording unless you add artificial pauses.

---

## How to run — one class

```powershell
python manage.py test core.tests_selenium.AuthSeleniumTests
python manage.py test core.tests_selenium.ExploreSeleniumTests
python manage.py test core.tests_selenium.BookingSeleniumTests
python manage.py test core.tests_selenium.OwnerSeleniumTests
python manage.py test core.tests_selenium.AdminSeleniumTests
```

---

## How to run — one test

Pattern:

```text
python manage.py test core.tests_selenium.<ClassName>.<test_method>
```

Examples:

```powershell
python manage.py test core.tests_selenium.AuthSeleniumTests.test_01_login_success_guest_lands_on_explore

python manage.py test core.tests_selenium.BookingSeleniumTests.test_11_guest_book_sunbed_lands_on_my_reservations

python manage.py test core.tests_selenium.OwnerSeleniumTests.test_15_owner_overview_shows_bar_and_date
```

Use headed mode (`$env:SELENIUM_HEADLESS="0"`) when learning — one test is much easier to follow than the full suite.

---

## What you should expect to see

| Mode | What happens |
|------|----------------|
| **Headless (default)** | Little or no Chrome window; dots `.` in the terminal as tests pass; ends with `OK`. |
| **Headed** | Chrome opens, pages flash (login, explore, book, owner, …), then close. Hard to “read” when running all 20 — run **one** test if you want to watch. |
| **Pass** | `OK` and exit code 0. |
| **Fail** | Traceback with the failing assertion / timeout; often the last page Chrome was on. |

Related **unit** tests (no browser):

```powershell
python manage.py test core.tests
```

Everything (units + Selenium):

```powershell
python manage.py test core
```

---

## Materials in this folder

| File | Role |
|------|------|
| `Uputstvo_za_predaju_testiranja_2026.pdf` | Submission instructions (IDE waived for our team — WebDriver + Django units only) |
| `PSI_Vezbe09_Testiranje_Django_aplikacija.pdf` | Course slides on Django / Selenium testing |
| `django_project.zip` | Sample cinema project (pattern reference) |
| `example usage.txt` | Short WebDriver login snippet from the team chat |

More setup notes also live in the root **README.md** under **Selenium WebDriver (UI tests)**.
