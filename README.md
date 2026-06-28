# BeachBooker

Most beach days do not start relaxed, they start with a race for a strip of sand. **BeachBooker** ends that: a live map of every beach bar, every row, every sunbed. Pick the spot you want before you pack the towel, then book it the way you would book a room on Airbnb. Guests get certainty; owners get one clear place to run the shore.

## Repository layout

| Path | Purpose |
|------|--------|
| `manage.py`, `beachbooker/`, `core/` | Django app (MVT) — backend + templates + static |
| `html_pages/` | Static HTML/CSS prototype (reference for templates) |
| `initial_phases/` | SRS, SSU, specs (`project_structure.txt`, `requirements.txt`) |
| `database/` | SQL schema, coursework templates; deliverables in `database/README/` |
| `context/` | Course slides (architecture, Django vežbe) |

Stack: **Django**, **MySQL**, **AJAX** for dynamic UI (map, booking).

## Local setup (Django)

### First-time clone

```bash
git clone https://github.com/Marko-Milinkovic/BeachBooker.git
cd BeachBooker

python -m venv venv
# Windows (MSYS): venv\bin\python   |   standard Windows: venv\Scripts\python
venv\bin\python -m pip install -r requirements.txt

copy .env.example .env
# Edit .env — set DB_PASSWORD, DB_PORT (e.g. 3308), DB_NAME=beachbooker
```

**MySQL — create database and tables**

1. In MySQL Workbench, create database `beachbooker` (if it does not exist).
2. Import **`database/schema.sql`** (File → Run SQL Script).

**Django migrations**

We keep the canonical schema in `database/schema.sql`. Django models mirror those tables; the first `core` migration must not try to recreate them.

After `schema.sql` is imported:

```bash
venv\bin\python manage.py migrate --fake-initial
venv\bin\python manage.py migrate
```

- `--fake-initial` marks `core.0001_initial` as applied **without** recreating tables from `schema.sql`.
- A normal `migrate` afterwards applies any later migrations (e.g. `core.0002` adds `user.last_login` if your DB was created from an older `schema.sql`).

**`user.last_login` column:** Django’s `core.User` needs a nullable `last_login` field. The current `database/schema.sql` includes it. If you imported an **older** SQL file without that column, `python manage.py migrate` adds it automatically — you do **not** need to re-import `schema.sql`.

If you skip `schema.sql` and use an empty database instead, run:

```bash
venv\bin\python manage.py migrate
```

(Only if you want Django to create all tables from migrations — the team default is **`schema.sql` + `--fake-initial`**.)

**Run the app**

```bash
venv\bin\python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

**Demo data (optional)**

```bash
venv\bin\python manage.py seed_demo
```

Creates sample users (`owner@beachbooker.test`, `guest@beachbooker.test`, `admin@beachbooker.test` / password `demo1234`), two beach bars, sunbeds, and sample reservations. Safe to run more than once.

**Demo login**

- Guest: `guest@beachbooker.test` / `demo1234` — browse, book spots, view/cancel on My Bookings
- Owner: `owner@beachbooker.test` / `demo1234` — owner dashboard (overview, reservations, cancel guest bookings)
- Admin: `admin@beachbooker.test` / `demo1234` — Django admin at `/admin/`

Auth uses Django sessions (cookie-based). Register at `/register/` or log in at `/login/`.

**Booking flow (logged-in guest)**

1. Open a beach bar from Explore, pick a date, tap free spots on the map.
2. Click **Book now** — creates active reservations in the database.
3. **My Bookings** lists active, past (completed), and cancelled reservations.
4. Cancel an active booking from My Bookings; the spot becomes free on the map again.

**Owner dashboard (logged-in owner)**

1. Log in as owner and open **For Owners** (`/owner/`).
2. **Overview** — bookings, revenue, occupancy, and zone fill for a selected date.
3. **Reservations** — all guest bookings for your bar; filter by date and status.
4. **Cancel** an active guest booking; the spot becomes free on the guest map.

**Run tests**

```bash
venv\bin\python manage.py test core
```

**Do not commit `.env`** — only `.env.example` (placeholders).

### After `git pull` (already set up locally)

**Always run this after pulling** — especially when `core/migrations/` has new files:

```bash
git pull
venv\bin\python -m pip install -r requirements.txt   # if requirements.txt changed
venv\bin\python manage.py migrate                      # apply new migrations
venv\bin\python manage.py runserver
```

You do **not** need to re-import `database/schema.sql` for routine updates. Migrations patch the existing database (for example `core.0002_user_last_login_column` adds `user.last_login` when missing).

If a new clone already has BeachBooker tables from `schema.sql` but migrations were never applied, use `migrate --fake-initial` once, then `migrate` (see first-time setup above).

## Viewing the static prototype

Open `html_pages/index.html` in a browser, or:

```bash
python -m http.server 8000 --directory html_pages
```

Then visit `http://localhost:8000/index.html`.

## Team Tropski Bar
Members: Marko Milinkovic, Andrea Ponjavic, Nikola Bajat, Jovan Milinkovic

