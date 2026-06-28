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
```

- Creates Django’s own tables (`django_migrations`, sessions, etc.).
- Marks `core.0001_initial` as applied **without** running `CREATE TABLE` again.

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

**Do not commit `.env`** — only `.env.example` (placeholders).

### After `git pull` (already set up locally)

```bash
git pull
venv\bin\python -m pip install -r requirements.txt   # if requirements.txt changed
venv\bin\python manage.py migrate                    # apply any new migrations
venv\bin\python manage.py runserver
```

If a new clone already has BeachBooker tables from `schema.sql` but migrations were never applied, use `migrate --fake-initial` once (see first-time setup above), not plain `migrate`.

## Viewing the static prototype

Open `html_pages/index.html` in a browser, or:

```bash
python -m http.server 8000 --directory html_pages
```

Then visit `http://localhost:8000/index.html`.

## Team Tropski Bar
Members: Marko Milinkovic, Andrea Ponjavic, Nikola Bajat, Jovan Milinkovic

