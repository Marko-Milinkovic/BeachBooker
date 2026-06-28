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

```bash
python -m venv venv
# Windows (MSYS): venv\bin\python   |   standard Windows: venv\Scripts\python
venv\bin\python -m pip install -r requirements.txt
copy .env.example .env
# Edit .env — set DB_PASSWORD and DB_PORT (default 3308)
venv\bin\python manage.py migrate
venv\bin\python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Import `database/schema.sql` in MySQL Workbench before using BeachBooker tables.

**Do not commit `.env`** — only `.env.example` (placeholders).

## Viewing the static prototype

Open `html_pages/index.html` in a browser, or:

```bash
python -m http.server 8000 --directory html_pages
```

Then visit `http://localhost:8000/index.html`.

## Team Tropski Bar
Members: Marko Milinkovic, Andrea Ponjavic, Nikola Bajat, Jovan Milinkovic
