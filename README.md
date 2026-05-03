# BeachBooker

Most beach days do not start relaxed — they start with a race for a strip of sand. **BeachBooker** ends that: a live map of every beach bar, every row, every sunbed. Pick the spot you want before you pack the towel, then book it the way you would book a room on Airbnb. Guests get certainty; owners get one clear place to run the shore.

## Repository layout

| Path | Purpose |
|------|--------|
| `prototype/` | Static HTML/CSS mockup prototype of main screens |
| `specs/` | Requirements, target Django layout, and related notes |

Planned backend stack: **Django**, **MySQL**, and **AJAX** for dynamic UI. The intended project tree is described in `specs/project_structure.txt`. Python dependencies are pinned in `specs/requirements.txt` until a Django project exists at the repository root.

## Viewing the prototype

You can download the project as a ZIP from GitHub (green button **Code** → **Download ZIP**), extract it, and open `prototype/index.html` in your browser.

If you have the repository cloned locally, open `prototype/index.html` in a browser, or from the repo root serve the folder locally, for example:

```bash
python -m http.server 8000 --directory prototype
```

Then visit `http://localhost:8000/index.html`.

## Local configuration (later)

When the Django app is added, use a `.env` file for secrets and database settings (see `.gitignore`). Commit only a `.env.example` with placeholder keys and no real passwords.
