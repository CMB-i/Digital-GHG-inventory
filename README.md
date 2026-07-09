# JSW Digital GHG Inventory

A web application for managing GHG (Greenhouse Gas) emissions data across multiple industrial sites.

The platform covers the full GHG data lifecycle: structured data collection by site operators/SPOCs, workbook-based monthly entry, multi-level approvals, formula-based calculations, audit visibility, and reporting.

Built for JSW Group’s ESG / GHG data governance needs.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 / Flask |
| Database | PostgreSQL |
| ORM | SQLAlchemy via Flask-SQLAlchemy |
| Migrations | Alembic directly, not Flask-Migrate |
| Templates | Jinja2 |
| Styling | Tailwind CSS via CDN, no build step |
| JavaScript | Vanilla JS, no React and no npm |
| WSGI server | Waitress |
| Formula engine | simpleeval |
| Excel export | openpyxl |

---

## Architecture Overview

The platform is split into functional modules under `app/modules/`. Most modules follow the structure:

```text
model.py
service.py
views.py
```

| Module | Purpose |
|---|---|
| `ACCESS` | AccessMatrix — permission source of truth for users, actions, and site scopes |
| `APPROV` | Approval queue, package review, review actions, issue handling, and approval progression |
| `AUDITL` | Audit log for submission state changes |
| `FORMBLD` | Sheet Builder — create, configure, version, and publish GHG data collection sheets |
| `FRMULA` | Formula Builder — calculated field definitions and formula preview |
| `NOTIFY` | Notifications for submission and approval events |
| `PERIOD` | Reporting period management: `OPEN`, `REOPENED`, `SUBMISSION_CLOSED`, `LOCKED` |
| `RPTBLD` | Report Builder — cross-site and cross-period reporting |
| `SITEMST` | Site master — site creation and management |
| `SUBMIT` | SPOC annual workbook runtime — workbook entry, draft save, package submit |
| `USRMGMT` | User management and authentication |
| `VALSET` | Value Set Builder — reference data for dropdown and lookup fields |
| `WFLWBLD` | Approval Path Builder — multi-level workflow and version management |
| `WKBK` | Workbook management — group sheets, assign sites, assign submitters, assign approval path |

---

## Key Design Rules

- **AccessMatrix is the permission source of truth.** Do not use hardcoded roles or archetypes for authorization.
- **WorkbookSite is the authoritative source for workbook-site assignment.** The legacy `form.description["sites"]` field must not be used for runtime routing.
- **WorkbookSiteSubmitter gates SPOC workbook visibility.** A SPOC only sees workbooks they are explicitly assigned to submit for a given site.
- **`Workbook.workflow_id` is the approval path source.** Form-level workflow metadata must not be used for submission routing.
- **WorkbookForm is the source of workbook sheets.** Runtime sheet tabs must come from the selected workbook’s configured sheet list.
- **No manual `ALTER TABLE`.** All schema changes must go through Alembic migrations.
- **Missing or blank values are never treated as zero** in formula calculations.
- **Reports use only approved and locked values.**
- **Soft delete by default.** Most records use an `is_deleted` flag with partial unique indexes. Hard delete is only allowed for assignment join rows where appropriate.

---

## Local Setup

### Prerequisites

- Python 3.10+
- PostgreSQL running locally, or access to a shared development database
- No Docker required

---

### 1. Clone the repository and create a virtual environment

```bash
git clone <repo-url>
cd Digital-GHG-inventory
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://ghg_user:ghg_password@localhost:5432/ghg_inventory
SECRET_KEY=change-me-in-production
FLASK_ENV=development
```

---

### 4. Run database migrations

```bash
alembic upgrade head
```

Do **not** use:

```bash
flask db upgrade
```

Flask-Migrate is not used in this project.

---

### 5. Seed a development admin account

```bash
python scripts/seed.py
```

This creates a development admin user:

```text
Email: admin@example.com
Password: ChangeMe123!
```

The seed script also grants global admin permissions through AccessMatrix.

---

### 6. Start the development server

```bash
python run.py
```

The app runs at:

```text
http://localhost:5001
```

For a production-style startup using Waitress:

```bash
waitress-serve --call app:create_app
```

---

## Health Checks

| URL | Expected response |
|---|---|
| `/health` | `{"status": "ok"}` |
| `/db-health` | `{"database": "connected"}` |

---

## Core Workflows

### Admin Setup

Typical one-time setup per workbook:

1. **Create sites**  
   `/module/SITEMST/`

2. **Create users**  
   `/module/USRMGMT/`

3. **Grant permissions**  
   `/module/ACCESS/`  
   Assign AccessMatrix rows per user and per site scope.

4. **Build sheets**  
   `/module/FORMBLD/`  
   Define sheet fields, sections, formulas, validations, and value-set-backed dropdowns.

5. **Create workbook**  
   `/workbooks/`  
   Group published sheets into a workbook.

6. **Assign sites to workbook**  
   Workbook detail → Sites tab.

7. **Assign submitters**  
   Workbook detail → Sites tab → add submitters per site.

8. **Assign approval path**  
   Workbook detail → Approval Path tab → link a published approval path.

9. **Publish workbook**  
   Readiness requires:
   - At least one published sheet
   - At least one assigned site
   - Submitters assigned for all workbook sites
   - A published/live approval path

---

### SPOC Data Entry

1. Navigate to **My Workbooks**.
2. Only assigned workbook-site combinations are visible.
3. Open a workbook and choose the financial year.
4. Select a sheet tab and enter monthly values.
5. Save draft values.
6. Submit the monthly workbook package.
7. Submitted packages enter the configured approval workflow.

---

### Approver Review

1. Navigate to **Approval Queue**.
2. Open a submitted package.
3. Review workbook sheets, monthly values, issues, and audit log.
4. Approve, request changes, or reject at each approval level.
5. Final approval locks the data for reporting.

---

### Reporting

Reports are built through:

```text
/module/RPTBLD/
```

Reporting uses only approved and locked values.

---

## Financial Year Model

The platform uses April–March financial years.

```python
FY_MONTH_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
```

Example:

```text
FY 2024 = April 2024 – March 2025
```

---

## Reporting Period Statuses

| Status | SPOC can enter data | Approver can act |
|---|---:|---:|
| `OPEN` | Yes | No |
| `REOPENED` | Yes | No |
| `SUBMISSION_CLOSED` | No | No |
| `LOCKED` | No | No |

---

## Development Scripts

| Script | Purpose |
|---|---|
| `scripts/seed.py` | Seeds a development admin account and global AccessMatrix permissions |
| `scripts/seed_jaigarh_workbook.py` | Seeds the Jaigarh FY25-26 GHG workbook (4 sheets: Cargo, Electricity, Fuel Consumption + GRI Summary; formulas, Excel data). Run after `seed.py`. Use `--verify-only` to re-check totals. |
| `scripts/dev_purge_test_data.py` | **Development only** — hard-deletes test/demo data by name pattern. Requires `FLASK_ENV=development`. Run with `--dry-run` first. |

---

## Adding a Migration

Create a migration:

```bash
alembic revision --autogenerate -m "describe_the_change"
```

Apply migrations:

```bash
alembic upgrade head
```

Always inspect the generated migration before running it.

The migration chain must remain linear, with a single Alembic head.

---

## Project Constraints

The following constraints are enforced throughout the codebase. Violations should be flagged in code review.

- No hardcoded site names, form names, GHG categories, workflow labels, or role names in business logic.
- No `form.description["sites"]` or `form.description["workflow_id"]` for runtime routing.
- Use `WorkbookSite` for workbook-site assignment.
- Use `WorkbookSiteSubmitter` for SPOC workbook visibility.
- Use `Workbook.workflow_id` for approval path routing.
- Use `WorkbookForm` for the workbook sheet list.
- No `ALTER TABLE` outside Alembic migrations.
- No React, no npm, and no build pipeline.
- Tailwind CSS must remain CDN-based.
- No Docker requirement for local development.
- No Flask-Migrate.
- AccessMatrix must gate privileged actions.
- Missing or blank values must not be coerced to zero in formula logic.
- Reports must use approved and locked values only.

---

## Module Prefix Reference

| URL prefix | Module |
|---|---|
| `/login`, `/logout` | `USRMGMT` authentication |
| `/module/ACCESS/` | AccessMatrix management |
| `/module/APPROV/` | Approval queue and package review |
| `/module/FORMBLD/` | Sheet Builder |
| `/module/FRMULA/` | Formula Builder |
| `/module/NOTIFY/` | Notifications |
| `/module/PERIOD/` | Reporting periods |
| `/module/RPTBLD/` | Report Builder |
| `/module/SITEMST/` | Site management |
| `/module/SUBMIT/` | SPOC annual workbook runtime |
| `/module/USRMGMT/` | User management |
| `/module/VALSET/` | Value Set Builder |
| `/module/WFLWBLD/` | Approval Path Builder |
| `/workbooks/` | Workbook management |
```

