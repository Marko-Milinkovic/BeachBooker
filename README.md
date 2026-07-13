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

**Prerequisites (must exist on the machine before Cursor/agents can finish setup):**
- Git, Python 3.11+ (3.13 is fine)
- MySQL Server running locally (Workbench optional but handy)
- Your MySQL root (or other) password and port — fill these into `.env`; nobody else knows them

### First-time clone (line by line)

1. **Clone the repo**
   ```bash
   git clone https://github.com/Marko-Milinkovic/BeachBooker.git
   cd BeachBooker
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   ```
   - Windows (PowerShell / cmd): `venv\Scripts\activate`
   - Windows (MSYS/Git Bash): `source venv/Scripts/activate` or use `venv\Scripts\python.exe` directly
   - macOS / Linux: `source venv/bin/activate`

3. **Install dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```
   (Use the venv’s `python` after activate. On this team’s Windows machines, `py manage.py …` only works if that interpreter also has Django installed.)

4. **Create `.env` from the example**
   ```bash
   # Windows
   copy .env.example .env
   # macOS / Linux
   # cp .env.example .env
   ```
   Edit `.env` and set at least:
   - `DB_PASSWORD=` *(your local MySQL password)*
   - `DB_PORT=` *(e.g. `3308` or `3306`)*
   - `DB_NAME=beachbooker`
   - `DB_USER=root` *(or your MySQL user)*
   - `DB_HOST=127.0.0.1`
   - Optionally change `SECRET_KEY`

5. **MySQL — create database and tables**
   1. Start MySQL.
   2. Create database `beachbooker` if it does not exist  
      (Workbench: create schema, or CLI: `CREATE DATABASE beachbooker CHARACTER SET utf8mb4;`).
   3. Import **`database/schema.sql`** (Workbench: File → Run SQL Script).  
      Current `schema.sql` already includes `user.is_active`, `user.last_login`, `beach_bar.image_url`, and `admin_action_log`.

6. **Apply Django migrations**
   ```bash
   python manage.py migrate --fake-initial
   python manage.py migrate
   ```
   - `--fake-initial` marks `core.0001_initial` as applied **without** recreating tables already created by `schema.sql`.
   - The following `migrate` applies any newer migrations if your DB predates them.

   If you use an **empty** database and skip `schema.sql`:
   ```bash
   python manage.py migrate
   ```

7. **Seed demo + bulk data (recommended for a full Explore demo)**
   ```bash
   python manage.py seed_demo
   python manage.py seed_bulk --bars 100
   ```
   Optional: `python manage.py seed_bulk --refresh-images` re-assigns local bar photos from `core/static/core/images/bars/`.

8. **Run the server**
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/`.

### Can a teammate paste this README into Cursor and get a working app?

**Mostly yes**, if they (or Cursor) follow steps 1–8 in order. Cursor can create the venv, install deps, copy `.env.example`, run migrate/seed/runserver.

**They / Cursor still need human input for:**
- MySQL already installed and running
- Real `DB_PASSWORD` / `DB_PORT` in `.env` (not committed; only `.env.example` is in the repo)

Without MySQL credentials, setup stops at step 4–5. With a correct `.env` + `schema.sql` imported, the rest is automated.

### Bar images (works on every teammate’s machine)

- **116 beach photos are committed** under `core/static/core/images/bars/` — they come with `git clone`; nobody needs to re-download them.
- Each bulk bar stores a **site-relative** URL such as `/static/core/images/bars/pexels-….jpg` in `beach_bar.image_url`.
- Django serves those files from the repo via `STATICFILES_DIRS` (`core/static/`). Paths are not absolute (`D:\…`) and not machine-specific, so cards load the same after clone + `seed_bulk` (or `--refresh-images`).
- Demo bars (Riccardo Beach Bar, Porto Skver Beach) still use external Unsplash URLs from `seed_demo`.

```bash
python manage.py seed_bulk --refresh-images   # re-assign local photos to bulk bars
python manage.py seed_bulk --clear-bulk       # remove bulk bars/owners only
```

Bulk owner accounts: `owner001@beachbooker.test` … `owner100@beachbooker.test` / `demo1234`. Reviewer pool: `guest001@…` … `guest020@…`.

### Demo login

- Guest: `guest@beachbooker.test` / `demo1234` — browse, book spots, view/cancel on My Bookings
- Owner: `owner@beachbooker.test` / `demo1234` — owner dashboard (overview, reservations, cancel guest bookings)
- Admin: `admin@beachbooker.test` / `demo1234` — BeachBooker Admin at `/admin-panel/` (users + activity log); Django `/admin/` remains as backup

### Owner onboarding

1. Register with role **Beach bar owner** (or log in as an owner with no bar).
2. You are taken to **Create your beach bar** — name, address, city, hours, optional description/Maps link/amenities.
3. On create, Standard (€15) and Premium (€25) categories are seeded; no sunbeds yet (use Layout).
4. You land on **Settings**; Categories & pricing, Layout, Bundles, and Reservations are available immediately.

Auth uses Django sessions (cookie-based). Register at `/register/` or log in at `/login/`.

**Explore filters**

1. Open **Explore** (`/explore/`) — beach bar cards load with free spots for the selected date.
2. Filter by **city**, **date**, **price range** (min category price), and **amenities** (bar must have all selected).
3. **Sort** by name, price, or rating. Apply updates results via AJAX (`GET /api/explore/bars/`) without a full page reload; the URL query string stays in sync for refresh/share.
4. Clear all resets filters. Without JavaScript, the same filters still work via normal form GET.

**Booking flow (logged-in guest)**

1. Open a beach bar from Explore, pick a date, tap free spots on the map.
2. Optionally select **add-on bundles** (e.g. drinks, parking) in the booking panel.
3. Click **Book now** — creates active reservations in the database (`reservation_bundle` stores add-on price snapshots).
4. **My Bookings** lists active, past (completed), and cancelled reservations with spot + add-on totals.
5. Cancel an active booking from My Bookings; the spot becomes free on the map again.

**Owner dashboard (logged-in owner)**

1. Log in as owner and open **For Owners** (`/owner/`). New owners without a bar first complete **Create your beach bar**.
2. **Overview** — bookings, revenue, occupancy, and zone fill for a selected date.
3. **Reservations** — all guest bookings for your bar; filter by date and status.
4. **Cancel** an active guest booking; the spot becomes free on the guest map.
5. **Categories & pricing** — create, edit, and delete sunbed categories (name, optional description, price). New bookings snapshot the current rate. Categories with sunbeds on the layout cannot be deleted.
6. **Bundles** — create, edit, and enable/disable add-on bundles; guests select them when booking.
7. **Layout** — paint the beach grid (rows × columns), place sunbeds by category, and save. Spot labels (e.g. S1, P2) are assigned automatically on save. You cannot remove or move a sunbed that has an active future booking; sunbeds with any past reservation history cannot be deleted from the layout.
8. **Settings** — edit public name, address, city, description, opening hours, optional Maps link, and amenity toggles. Changes appear on the guest beach bar page and in Explore filters.

**Layout editor manual check**

1. Owner → **Layout** — grid loads with existing sunbeds (Riccardo Beach Bar after `seed_demo`).
2. Paint cells, **Save layout** — hard refresh (`Ctrl+Shift+R`) — layout persists.
3. Guest beach bar map shows updated spots and labels.
4. Book a spot → owner tries to erase that cell — blocked with an error message.
5. After cancel, the spot still cannot be erased (booking history); only spots with no reservations can be removed.

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

