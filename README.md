# Digital GHG Inventory

Phase 0 scaffold for the ESG / GHG Data Governance Platform.

## Stack

- Backend: Flask
- Database: PostgreSQL
- Templates: Flask Jinja
- Styling: Tailwind CSS CDN
- JavaScript: Vanilla JS
- Migrations: Alembic / Flask-Migrate
- Dev/deploy: Docker Compose

## Setup

Copy the sample environment file:

```bash
cp .env.example .env
```

Run with Docker Compose:

```bash
docker-compose up --build
```

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

For local runs without Docker, set `DATABASE_URL` to a reachable PostgreSQL instance.

## Phase 0 Verification Checklist

- `docker-compose up --build` starts the Flask and PostgreSQL services.
- `/health` returns `{"status": "ok"}`.
- `/db-health` returns `{"database": "connected"}` when PostgreSQL is available.
- `/dashboard` loads.
- `/module/ACCESS/` loads.
- Tailwind styling is visible.
- Module folders exist with `model.py`, `service.py`, and `views.py`.

## Deferred TODOs

- Phase 1: business models, migrations, and service logic.
- Phase 2: authentication and session enforcement.
- Phase 3: configurable role and permission checks.
- MVP later: full audit log implementation.
