# Digital GHG Inventory

A web application for managing GHG (Greenhouse Gas) emissions data across multiple industrial sites. It covers the full data lifecycle: structured monthly data collection by site operators, workbook-based entry with formula-driven calculated fields, multi-level approvals, audit visibility, and cross-site/period reporting. Built for JSW Group's ESG / GHG data governance needs.

This README is the single source of truth for the project. There is no separate agent-instructions file (CLAUDE.md was removed — see [Known Gaps](#known-gaps) if you're looking for it).

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

## Local Setup

### Prerequisites

- Python 3.10+
- PostgreSQL running locally, or access to a shared development database
- No Docker required

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

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

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

### 4. Run database migrations

```bash
alembic upgrade head
```

Do **not** use `flask db upgrade` — Flask-Migrate is not installed in this project; migrations are plain Alembic.

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

### 6. Start the development server

```bash
python run.py
```

The app runs at `http://localhost:5001`.

For a production-style startup using Waitress:

```bash
waitress-serve --call app:create_app
```

### Health Checks

| URL | Expected response |
|---|---|
| `/health` | `{"status": "ok"}` |
| `/db-health` | `{"database": "connected"}` |

### Financial Year Model

The platform uses April–March financial years:

```python
FY_MONTH_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
```

Example: `FY 2024 = April 2024 – March 2025`. This has been stable and unchanged across the entire visible project history.

### Reporting Period Statuses

| Status | Submitter can enter data | Reviewer can act |
|---|---:|---:|
| `OPEN` | Yes | No |
| `REOPENED` | Yes | No |
| `SUBMISSION_CLOSED` | No | No |
| `LOCKED` | No | No |

This four-state model and its transitions have never changed across the project's visible history. There is no row locking on period transitions against in-flight submissions — see [Known Gaps](#known-gaps).

### Adding a Migration

```bash
alembic revision --autogenerate -m "describe_the_change"
alembic upgrade head
```

Always inspect the generated migration before running it. The migration chain must remain linear, with a single Alembic head. Run `python scripts/check_alembic_heads.py` before pushing a new migration — it exits non-zero if the chain has forked (there's no CI wired up yet to run this automatically; see [Known Gaps](#known-gaps)).

### Development Scripts

| Script | Purpose |
|---|---|
| `scripts/seed.py` | Seeds a development admin account and global AccessMatrix permissions |

### Running Tests

```bash
pytest
```

Tests run against a real, dedicated Postgres database — never the dev database. SQLite isn't an option here since the models use Postgres-specific features (JSONB, partial unique indexes). The test database is created automatically (name derived from `DATABASE_URL` with `_test` appended, or set `TEST_DATABASE_URL` explicitly) and its schema is built via `db.create_all()`, not Alembic — for a fresh test database the current models *are* the schema.

Isolation between tests is **not** savepoint/rollback-based. Service functions throughout this codebase call `db.session.commit()` themselves (not just at the top level), which a rollback harness would have to intercept every one of. Instead, `tests/conftest.py` provides factory fixtures (`make_user`, `make_site`, `make_access_grant`, `make_form`, `make_workflow`, `make_workbook`, `make_submission`, etc.) that create real rows with real commits and delete them again in teardown — the same throwaway-fixture-plus-cleanup pattern used for every manual verification in this project's history, just reusable now instead of hand-rolled per script. If you add a new fixture that creates rows, make sure whatever creates them also gets cleaned up (the existing fixtures are the reference for how).

New features should come with tests going forward — this is a lightweight expectation, not a formal policy. `tests/` is organized by risk area, roughly in the priority order the suite was built in: calc_status/formula recalculation, permission scoping, then regression coverage for specific past bugs. Add to whichever file matches, or start a new one for a new area.

### Module Prefix Reference

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
| `/module/SUBMIT/` | Submitter data-entry runtime |
| `/module/USRMGMT/` | User management |
| `/module/VALSET/` | Value Set Builder |
| `/module/WFLWBLD/` | Approval Path Builder |
| `/workbooks/` | Workbook management |

---

## Module Reference

Each module lives under `app/modules/<NAME>/` with `model.py` / `service.py` / `views.py`. This section describes what each module actually does today, including known rough edges — not an aspirational design doc.

### SUBMIT — data entry and package submission

Handles draft entry, autosave, formula recalculation, and submission of monthly workbook data. Raw data entry and calculated-field correctness are decoupled: a submission goes through as long as all *raw* required fields are filled, even if a calculated field's formula errors. When a calculated field errors at submit time, `submission.needs_recalc_review` is set `True` and surfaced to reviewers, and now blocks final approval until a reviewer clears it or the submitter corrects and resubmits (see APPROV below).

Every calculated field carries an explicit `calc_status` (`ok` / `error` / `pending`) instead of a blank value meaning nothing more than "not computed yet." All per-row calculated-field resolution goes through one shared function, `resolve_calculated_fields`, used by both the persisted path (`recalculate_submission_formulas`) and the preview path (`_compute_preview_calculated_values`). The annual "sheet result" aggregate path (`_compose_sheet_results`) has a fundamentally different value shape (monthly-series arrays feeding `SUM_MONTHS`, not scalar field values) and its own status vocabulary, so it isn't merged into the same function — but it reuses the same dependency-ordering/cycle-detection helper. Dependency chains between calculated fields are resolved via topological ordering of each formula's `formula_version.tokens`, not a hardcoded pass count, so a chain resolves correctly in a single pass regardless of field display order or chain depth. A field left over after topological ordering is a genuine circular dependency (A depends on B, B depends on A) and is classified `error` ("circular formula dependency...") rather than being silently stuck at `pending` forever. See [Consistency Guidelines](#consistency-guidelines) and [Known Gaps](#known-gaps).

Site/workbook visibility for a submitter requires **both** an AccessMatrix `submission` grant at that site **and** an explicit `WorkbookSiteSubmitter` row for that specific workbook/site — there is no fallback either way, by design: `WorkbookSiteSubmitter` is a deliberate, explicit assignment ("this exact person submits this exact workbook"), and AccessMatrix site permission alone is never sufficient on its own. A user with AccessMatrix access but no `WorkbookSiteSubmitter` row for that site gets an empty dashboard/workbook list, but `get_annual_workbook_options` and `get_spoc_sheets_buckets` both flag this case explicitly (`needs_submitter_assignment` in their JSON response, surfaced in the UI as "you haven't been assigned as a submitter yet — contact your admin") so it reads distinctly from having no access at all.

There is no row locking anywhere in this module. Two concurrent submits of the same submission (double-click, retry, two package-submits racing) can both pass their preconditions before either commits.

### APPROV — approval queue, review, multi-level approval progression

Handles the reviewer-side workflow: queue, package review, approve/reject/request-changes, issue-raising. Approval can be single-level or multi-level, `ANY_ONE` (any assigned approver can act) or `SEQUENTIAL` (approvers act in order) per level.

`needs_recalc_review` (set by SUBMIT) is read and displayed here, and **is now checked by the final-approval gate** alongside open, `blocks_approval=True` `Issue` rows — a submission flagged for recalculation review cannot be given final approval until a reviewer either clears the flag (`clear_recalc_review`, once they've confirmed the calculated value is acceptable) or the submitter corrects and resubmits, which recomputes the flag automatically. Intermediate-level approvals in a multi-level chain are unaffected; only the level that actually locks the submission is gated.

Package-level actions (approve/reject a whole package at once) are a thin loop over submission-level actions with no first-class package state — `package.current_level` is derived after the fact as the minimum of member submission levels. If a package's member submissions have heterogeneous eligibility (different levels, or one submitted by the acting user), `approve_package` can abort partway through with no partial-success handling.

Submission-level `Issue` and cell-level `SubmissionValueIssue` now share the same real enforcement: both have an open→resolved lifecycle (`resolved_by`/`resolved_at`, set via `resolve_issue` / `resolve_package_value_issue`), both carry a `blocks_approval` flag (always set `True` at creation for both — there's no UI path that ever creates or flips it otherwise, on either model), and the final-approval gate checks all three conditions together in one place: no open `Issue` rows, no open `SubmissionValueIssue` rows, and `needs_recalc_review` cleared. Cell issues are raised/resolved from the package review screen (`package_review.js`); the submitter's own read-only view (`annual_workbook.js`) only displays them.

No row locking here either — concurrent approvals at an `ANY_ONE` level can double-advance a level or double-notify.

### WKBK — workbook management (group sheets, assign sites, submitters, approval path)

A workbook groups published sheets (`WorkbookForm`), is assigned to sites (`WorkbookSite`), has submitters per site (`WorkbookSiteSubmitter`), and links to an approval path (`Workbook.workflow_id`). Publish readiness requires: ≥1 published sheet, ≥1 assigned site, submitters for every assigned site, and a published approval-path version. This checklist (`check_workbook_readiness`) is real and enforced.

**WKBK's simplified chain editor (`api_save_site_chain` in `WKBK/views.py`) is currently the only accessible way to configure approval chains.** The standalone Approval Path Builder (WFLWBLD, below) still exists in code, and its service layer (`save_workflow_draft_levels`, `publish_workflow_version`, etc.) is still used internally — WKBK's chain editor calls into it directly rather than duplicating its validation. But WFLWBLD's own UI has been disabled, since multi-level/`SEQUENTIAL` chains aren't needed at the current complexity level. It can be re-enabled by removing the `before_request` block at the top of `WFLWBLD/views.py` (and restoring its nav/dashboard links) if that need arises — see [Consistency Guidelines](#consistency-guidelines).

Deactivating a workbook, or deleting the `Workflow` it points to, now both have dependency checks — `deactivate_workbook` refuses if any in-progress submission (`Draft`/`Submitted`/`Resubmitted`/`Under Review`/`Changes Requested`) still depends on it via the workbook's assigned sheets/sites, and `delete_workflow` (see WFLWBLD below) refuses if an active `Workbook` still points to it. Both raise a clear error instead of silently stranding a submission or workbook.

Permission checks on every WKBK endpoint — including publish and site/submitter assignment — use `@require_permission("form", "manage_forms")`, the same resource type as the Sheet Builder. There is no distinct `"workbook"` permission; anyone with Sheet Builder access has full Workbook admin rights.

### FORMBLD — sheet builder (fields, sections, formulas, publish/versioning)

Fields (`Field`/`FieldVersion`) are properly versioned — publishing a new draft doesn't retroactively change what a live submission sees, because submissions pin to a specific `form_version_id`.

**`FormSection` is now versioned**, the same way fields are — it carries a `form_version_id` (unique per `code` within a version), so editing sections while drafting a new version (rename, reorder, remove) is isolated to the draft and no longer retroactively mutates what's currently live for the *published* version.

Publish readiness for a sheet requires non-empty fields, dropdown fields to have options, and calculated fields to reference a *published* formula version. There is no check, at field-deletion time, for whether a formula still references the field being deleted — a formula can be published against a field, and that field can later be soft-deleted with no warning, breaking the formula silently at evaluation time.

### WFLWBLD — approval path builder (multi-level workflows, versioning)

**This module's UI is currently disabled** — every route under `/module/WFLWBLD/` returns a 404 via a `before_request` hook at the top of `WFLWBLD/views.py`, so visiting it directly 404s instead of loading the builder. This isn't a bug: it's an intentional, easily-reversible switch-off, since WKBK's simplified chain editor is the only configuration surface needed at present. The model and service layers below are untouched and fully live — WKBK, SUBMIT, APPROV, NOTIFY, and FORMBLD all still call into them directly.

The real, validated writer for workflow levels/approvers (`save_workflow_draft_levels`): requires a valid `approval_mode`, ≥1 approver per level, active/existing users, real sites for site-scoped approvers, and unique sequence numbers for `SEQUENTIAL` mode. Publishing requires ≥1 level, ≥1 approver per level, all active, unique sequence numbers where relevant.

**`get_eligible_level_approvers` now filters on `is_active` as well as `is_deleted`**, matching the check `publish_workflow_version` already applies at publish time — if every approver at a level is later deactivated, that level is correctly treated as having no eligible approver instead of silently matching deactivated users.

`update_details` (the workflow-detail edit endpoint) no longer reads or writes `form.description["workflow_id"]` / `["sites"]` — the legacy write path that fed the standalone builder's "Covered Sites" checkbox has been removed (it only ever updates `Workflow.name` now). Site-eligibility routing runs exclusively through `WorkbookSite`, which this never affected either way; the checkbox UI itself still exists in `workflow_builder.js`, but since the module's UI is fully disabled (see above), it's unreachable and its data no longer goes anywhere.

`delete_workflow` now refuses to delete a `Workflow` that an active `Workbook` still points to via `workflow_id`, raising a clear error instead of silently stranding that workbook.

### FRMULA — formula definitions and evaluation

Formulas are versioned and validated against currently-active field/value-set codes at publish time, using `simpleeval`. There is no re-validation when a field a published formula references is later renamed or soft-deleted, and FORMBLD's own "delete fields not present in a re-saved sheet" logic (this is literally what a field rename looks like under the hood) does not check formula references before deleting. How this manifests, once it happens, is inconsistent — SUBMIT alone has four different behaviors ranging from fully silent to a specific error message, depending on which of its five calculated-field code paths hits it first (see [Consistency Guidelines](#consistency-guidelines)).

The client-side formula evaluator (`static/js/formula_runtime.js`) is a materially narrower grammar than the backend's (no unary minus, no exponent), and its `SUM_MONTHS` implementation is still a literal no-op internally — it can only ever see one row's values client-side, so it can't compute a real cross-month sum. Rather than trying to fake that computation in the browser, every call site now checks `FormulaRuntime.usesAggregate(expression)` first and shows an explicit "preview unavailable" message instead of a number: the Formula Builder's live preview (`formula_builder.js`) and the inline recalculation run during data entry (`form_renderer.js`, used by `spoc_entry`) both do this consistently. The real value is still computed correctly server-side at save/submit time.

### VALSET — value sets (reference data for dropdowns/lookups)

Draft → Submitted → Approved lifecycle. `reject_value_set_version` blocks self-rejection (`submitted_by == user_id`); `approve_value_set_version` now has an equivalent self-approval check, covering both routes that can reach it — `/publish` (gated by `manage_forms`, the same permission that lets you create the draft) and `/approve` (gated by a distinct `approve` permission). Since `/publish` can approve a version straight from `Draft` (before it's ever been through `/submit`, when `submitted_by` is still unset), the check falls back to `created_by` in that case so a draft's own author can't self-approve through either route.

### PERIOD — reporting period lifecycle

See [Reporting Period Statuses](#reporting-period-statuses) above. Four states, stable across the project's entire history. Transitions have no row locking against in-flight submissions — a period can be locked by an admin in the same window a submission is mid-commit, with no atomicity between the two.

### SITEMST — site master

Straightforward CRUD for sites.

### RPTBLD — cross-site/period reporting

Filters submissions to `Approved` + `is_locked=True` before reporting, correctly matching the "reports use only approved and locked values" rule (see [Key Design Rules](#key-design-rules)). Its site/permission-scoping logic (`list_report_templates`, `_get_user_allowed_sites`) now calls the shared `get_user_permissions()` instead of hand-rolling its own `AccessMatrix` query — the same fix NOTIFY's `resolve_recipients` got (see NOTIFY below) — so a user with a blanket "all entities" permission grant is no longer silently excluded from reports they should be able to see.

`get_missing_submissions` runs two queries inside a doubly-nested loop over periods × forms — a real O(n×m) query explosion that will get slower as sites/forms grow. Not yet a problem at current scale.

### AUDITL — audit log

Records status changes and resolves human-readable entity descriptions for the audit trail. The `access_matrix` entity-description branch now correctly reads `scope_site_id` (the real field on `AccessMatrix`), producing a proper "User: ..., Site: ..." (or "Scope: Global") description instead of falling back to a generic "Access Matrix Record #123" label.

### NOTIFY — notifications (in-app, desktop, email, WhatsApp)

Multi-channel routing with per-user preferences. **`resolve_recipients`'s role-based and dynamic (`site_admins`) recipient resolution now calls the shared `get_user_permissions()` / `has_permission()`** instead of hand-rolling its own `AccessMatrix` query — the same bug pattern RPTBLD still has (see [Consistency Guidelines](#consistency-guidelines)) — so a user with a blanket "all entities" grant is no longer silently skipped as a notification recipient.

Email/WhatsApp delivery failures are caught and only printed to console — no persisted record exists for a failed email/WhatsApp send, so a failure is invisible to everyone, including the intended recipient and any admin.

### ACCESS — AccessMatrix, the permission source of truth

`get_user_permissions()` / `has_permission()` correctly OR in `entity_type == "all"` alongside a specific entity type — this is the correct, complete implementation and the one every module should call (see [Key Design Rules](#key-design-rules)). `ACCESS/views.py` is now the sole, canonical user CRUD UI (create/edit/password/toggle-active) — the duplicate that used to live in `USRMGMT/views.py` was confirmed unreachable from any nav link, dashboard card, or cross-reference, and has been removed. Both call the same `USRMGMT/service.py` functions underneath; ACCESS's blueprint additionally handles permission assignment (`/assign`, `/assign-matrix`), which USRMGMT never had.

### USRMGMT — user management and auth

Password hashing uses bcrypt. Session handling correctly clears the session before setting a new user on login. `USRMGMT/views.py` now holds only `auth_bp` (`/login`, `/logout`) — its own user CRUD blueprint (`bp`: index/create/edit/password/toggle-active, plus `users.html`) was removed as the unreachable duplicate of ACCESS's (see ACCESS above); `USRMGMT/service.py` is untouched and still the shared implementation both ACCESS and the login flow call into.

---

## Key Design Rules

These are enforced (or intended to be enforced) throughout the codebase. Violations should be flagged in code review.

- **AccessMatrix is the permission source of truth.** Call `has_permission()` / `get_user_permissions()` from the `ACCESS` module for every authorization check. Do not hand-roll a narrower `AccessMatrix` query and do not use hardcoded roles — see [Known Gaps](#known-gaps) for where this is currently violated.
- **`WorkbookSite` is the authoritative source for workbook-site assignment.** The legacy `form.description["sites"]` field must never be read for runtime routing (it is still, unfortunately, actively *written* by one dead-end UI — see the WFLWBLD module notes and [Known Gaps](#known-gaps)).
- **`WorkbookSiteSubmitter` gates submitter workbook visibility, with no AccessMatrix fallback.** Seeing/submitting a workbook at a site requires both an AccessMatrix `submission` grant at that site *and* an explicit `WorkbookSiteSubmitter` row for that workbook/site — AccessMatrix access alone is never enough. `WorkbookSiteSubmitter` is a deliberate, explicit assignment ("this exact person submits this exact workbook"), not a permission proxy. When a user has the AccessMatrix grant but no `WorkbookSiteSubmitter` row, this is surfaced explicitly (`needs_submitter_assignment` from `get_annual_workbook_options` / `get_spoc_sheets_buckets`) rather than left as an unexplained empty state.
- **`Workbook.workflow_id` is the approval path source.** Form-level workflow metadata (`form.description["workflow_id"]`) must never be used for submission routing — it is also still actively written by the same dead-end UI noted above, but never read for routing.
- **`WorkbookForm` is the source of workbook sheets.** Runtime sheet tabs must come from the selected workbook's configured sheet list.
- **No manual `ALTER TABLE`.** All schema changes must go through Alembic migrations, and the migration chain must remain linear with a single head (see [Known Gaps](#known-gaps) — this isn't mechanically enforced yet).
- **Missing or blank values are never treated as zero** in formula calculations. The formula evaluator excludes blank/missing values from evaluation inputs rather than coercing them.
- **Reports use only approved and locked values.** RPTBLD's report query filters on `status == "Approved"` and `is_locked == True`.
- **Soft delete by default.** Most records use an `is_deleted` flag with partial unique indexes. Hard delete is only allowed for assignment join rows where appropriate.
- **No hardcoded site names, form names, GHG categories, workflow labels, or role names in business logic.**
- **No React, no npm, no build pipeline. Tailwind CSS stays CDN-based. No Docker requirement for local dev. No Flask-Migrate.**

---

## Consistency Guidelines

Added to prevent the kind of drift documented in [Known Gaps](#known-gaps) from recurring.

1. **Check `app/common/` before adding a new constant.** Before introducing a new status enum, permission check, or date-math constant (FY boundaries, period math, etc.), check whether one already exists in `app/common/` or in a sibling module. Extend or import the existing one instead of writing a parallel copy.

2. **`current_version_id` always means "the currently published version," app-wide.** `Form.current_version_id`, `Workflow.current_version_id`, `ValueSet.current_version_id`, and `Formula.current_version_id` are all set only at publish time. `Field.current_version_id` is the one exception — it's set on every draft save, published or not, which is inconsistent with every sibling field of the same name. This is believed to be drift from multiple contributors, not intentional. It's currently harmless (nothing reads `Field.current_version_id` today), but any new code must follow the app-wide convention ("currently published"), not `Field`'s current behavior. Fixing `Field` itself is low priority since nothing depends on it, but don't copy its pattern.

3. **Never reimplement `AccessMatrix` scoping logic.** Always call `has_permission()` / `get_user_permissions()` from `ACCESS`. Two modules (RPTBLD and, until recently, NOTIFY) independently hand-rolled their own narrower version of this query and both got it wrong the same way (missing the `entity_type == "all"` wildcard) — see [Known Gaps](#known-gaps).

4. **One validated backend can serve more than one UI — never fork the validation logic between them.** WKBK's per-workbook chain editor calls into WFLWBLD's validated service functions (`save_workflow_draft_levels`'s helpers, via `save_site_chain_levels`) rather than re-implementing its own weaker rules. Right now this is less about two live UIs sharing a backend and more about one: the standalone WFLWBLD Approval Path Builder's own UI is currently disabled (see the WKBK module section above), so WKBK's chain editor is the only interface to this backend today. The rule still applies going forward — if the standalone UI is re-enabled, or another simplified UI is added later, it must call the same validated functions rather than duplicating them.

5. **Shared vocabularies that already exist — extend these, don't fork them:**
   - **Submission status** — string literals (`"Draft"`, `"Submitted"`, `"Resubmitted"`, `"Under Review"`, `"Changes Requested"`, `"Approved"`, `"Rejected"`) defined independently in both `SUBMIT/service.py` and `APPROV/service.py`. There is no shared enum yet (see [Known Gaps](#known-gaps)) — until there is, keep any new status string consistent with both existing tuples rather than inventing a new casing convention.
   - **Calculated-field status** — `calc_status` (`"ok"` / `"error"` / `"pending"`), defined in `SUBMIT/service.py`. This is the canonical vocabulary produced by the shared `resolve_calculated_fields` resolver (used by both the persisted and preview paths) for "can this calculated field's value be trusted right now." The annual sheet-result path (`_compose_sheet_results`) still has its own, different vocabulary (`not_configured`/`needs_input`/`calculated`/`error`) since it resolves a structurally different value shape — new code resolving ordinary per-row calculated fields should use `calc_status`'s vocabulary, not invent a third.
   - **Cell state** — `CELL_STATE_BLANK_EDITABLE` / `_DRAFT_FILLED` / `_SUBMITTED` / `_APPROVED_LOCKED` / `_CHANGES_REQUESTED` / `_LATE_ENTRY`, defined in `SUBMIT/service.py`. This is the canonical per-value lifecycle state. The frontend (`static/js/workbook_sheet.js`) maintains its own color maps for this vocabulary — if you add or rename a cell state, update every color map in that file, not just one (see [Known Gaps](#known-gaps)).

---

## Known Gaps

Honest, short list of things known to be wrong or unfinished today. If you fix one of these, delete it from this list in the same change.

- **No shared submission-status enum.** `SUBMIT` and `APPROV` each define their own status string tuples independently; `PERIOD` and `VALSET` use yet other casing conventions for their own separate lifecycles.
- **"SPOC" and "Submitter" (and "Approver" and "Reviewer") coexist in the codebase.** See [Terminology](#terminology) below — user-facing copy mostly says Submitter/Reviewer, but module names, JS filenames, CSS classes, and some newer admin-facing strings still say SPOC/Approver.
- **No row locking anywhere in SUBMIT, APPROV, or PERIOD.** Concurrent submits, concurrent `ANY_ONE`-level approvals, and period-lock-during-in-flight-submission races are all possible.
- **`Field.current_version_id` means something different from every sibling `current_version_id`** in the app (see [Consistency Guidelines](#consistency-guidelines)). Harmless today since nothing reads it, but a landmine for anyone who assumes it follows the app-wide convention.

---

## Terminology

"SPOC" (Single Point of Contact) and "Submitter" refer to the same role: the person who enters monthly data for a site. "Approver" and "Reviewer" refer to the same role: the person who reviews and approves/rejects submissions. User-facing copy was swept from SPOC/Approver to Submitter/Reviewer in one pass, but the rename didn't reach everywhere:

- **Says Submitter/Reviewer:** most current user-facing UI copy.
- **Still says SPOC/Approver:** the `SUBMIT` module's internal name, `static/js/spoc_entry.js`, `static/js/spoc_sheets.js`, the `.approver-submission-review` CSS class, `human_sheet_label`'s helper naming, and some newer NOTIFY admin-facing notification-config strings (added after the rename, but written using the old terms).

**Submitter / Reviewer is the intended long-term direction for all new user-facing copy.** Internal identifiers (module names, file names, CSS classes) are not required to be renamed retroactively — do not do a mechanical rename of those as a side effect of unrelated work, since `SUBMIT`/`APPROV` are load-bearing module names referenced throughout routing and permissions.
