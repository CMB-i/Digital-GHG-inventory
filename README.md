# Digital GHG Inventory

Phase 0 scaffold for the ESG / GHG Data Governance Platform.

## Stack

- Backend: Flask
- Database: PostgreSQL
- Templates: Flask Jinja
- Styling: Tailwind CSS CDN (no Python package required)
- JavaScript: Vanilla JS
- Migrations: Alembic (configured once during Phase 0; `alembic.ini` and `migrations/env.py` are set up manually)
- WSGI server: Waitress (pure Python, works on Mac and Windows)

## Setup

### 1. Clone and create a virtual environment

**Mac / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set `DATABASE_URL` to point to your local PostgreSQL instance, or to a shared dev database if your team has one configured:

```
DATABASE_URL=postgresql://ghg_user:ghg_password@localhost:5432/ghg_inventory
```

### 4. Run database migrations

Migrations are managed with Alembic directly. `alembic.ini` and `migrations/env.py` are configured once during Phase 0 setup and committed to the repo.

```bash
alembic upgrade head
```

Do not use `flask db upgrade` — Flask-Migrate is not used in this project.

### 5. Start the development server

```bash
python run.py
```

The local Flask development server runs on port `5001`.

For a production-style startup using Waitress:

```bash
waitress-serve --call app:create_app
```

Waitress is pure Python and works on both Mac and Windows without additional system dependencies.

## Phase 2 Local Login

Run migrations and seed the development account:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed.py
.venv/bin/python run.py
```

Open `http://localhost:5001/login` and sign in with:

```text
Email: admin@example.com
Password: ChangeMe123!
```

The seed script also grants the dev admin global `access_matrix` permissions with all 11 permission flags enabled.

## File storage (MinIO / local filesystem)

MinIO is used for object storage in production. For local development, choose one of the following:

- **MinIO binary (no Docker):** Download the MinIO binary for your OS from [min.io/download](https://min.io/download) and run it directly. No Docker required.
- **Local filesystem fallback:** For development, a simple local filesystem path can be used instead of MinIO. MinIO is only required in production.

Do not rely on a Docker-based MinIO setup for local development.

## Phase 0 Verification Checklist

- venv is activated and `pip install -r requirements.txt` runs clean with no errors.
- `.env` is configured with a valid `DATABASE_URL` pointing to a reachable PostgreSQL instance.
- `alembic upgrade head` completes without errors.
- `python run.py` starts the Flask development server.
- `/health` returns `{"status": "ok"}`.
- `/db-health` returns `{"database": "connected"}`.
- `/login` page loads successfully.
- `/dashboard` loads.
- `/module/ACCESS/` loads.
- Tailwind styling is visible.
- Module folders exist with `model.py`, `service.py`, and `views.py`.

## Deferred TODOs

- Phase 1: business models, migrations, and service logic.
- Phase 2: authentication and session enforcement.
- Phase 3: configurable Access Matrix permission checks.
- MVP later: full audit log implementation.
