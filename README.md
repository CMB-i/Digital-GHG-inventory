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

### 6. Seed default notification configuration

```bash
flask seed-notifications
```

Notification configuration seeding is now explicit. `create_app()` does not write notification defaults during startup.

### 7. Start the development server

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

This four-state model and its transitions have never changed across the project's visible history. `transition_period` locks the period row (`SELECT ... FOR UPDATE`), and `submit_submission` re-checks the period's status under its own lock on that same row right before its final transition, so a period lock landing mid-submit and a submission racing a period lock can no longer both win.

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
| `scripts/_script_safety.py` | Required safety convention for any new mutating operational script: explicit environment, dry-run support, and confirmed commits. See `scripts/README.md`. |

No `scripts/test_*.py` files are permitted. Real tests belong in `tests/`; manual smoke scripts must use a non-`test_` name and follow the script-safety pattern.

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

The legacy row-level write routes now use the same workbook-assignment boundary as the annual workbook path. `create_draft_submission`, `autosave_submission_values`, proof upload, and submit all reject a site-authorized user who is not assigned to the relevant workbook when the submission is workbook-scoped; genuinely non-workbook submissions keep the older site-permission behavior. Draft creation also validates that `reporting_period_id` belongs to the selected `site_id`, closing the cross-site period/submission mismatch.

`submit_submission` locks the submission row (`SELECT ... FOR UPDATE`) before checking/transitioning its status, and re-checks the reporting period's status under its own lock right before the transition rather than only at the start — so two concurrent submits of the same submission, or a submit racing a concurrent period lock, can no longer both pass their preconditions before either commits. `get_or_create_submission_package` is backed by a real unique constraint (`uq_active_submission_package`) with retry-on-conflict, so two concurrent package-submits for the same site/period/type can no longer create two live packages.

Autosaved values, annual workbook values, and proof uploads now emit audit events through AUDITL (`AUTOSAVE_VALUE`, `SAVE_WORKBOOK_VALUE`, `UPLOAD_PROOF`) with before/after metadata scoped to the field/value/proof, not uploaded file bytes.

Proof uploads enforce both the global upload allowlist and the field contract: uploads are accepted only for `field_type == "file"`, and a field's configured `accepted_mime_types` and `max_file_size_bytes` are enforced server-side. Flask also has a global request-size cap (`MAX_CONTENT_LENGTH` / `MAX_PROOF_UPLOAD_BYTES`). Re-uploading a proof supersedes older active proof rows for the same `(submission_id, field_id)` by soft-deleting them, and normal review/download/reporting reads use deterministic newest-active ordering (`uploaded_at DESC, id DESC`) rather than whichever row the database happens to return first. If metadata persistence fails after a file write, the just-written stored file is removed during rollback cleanup.

### APPROV — approval queue, review, multi-level approval progression

Handles the reviewer-side workflow: queue, package review, approve/reject/request-changes, issue-raising. Approval can be single-level or multi-level, `ANY_ONE` (any assigned approver can act) or `SEQUENTIAL` (approvers act in order) per level.

`needs_recalc_review` (set by SUBMIT) is read and displayed here, and **is now checked by the final-approval gate** alongside open, `blocks_approval=True` `Issue` rows — a submission flagged for recalculation review cannot be given final approval until a reviewer either clears the flag (`clear_recalc_review`, once they've confirmed the calculated value is acceptable) or the submitter corrects and resubmits, which recomputes the flag automatically. Intermediate-level approvals in a multi-level chain are unaffected; only the level that actually locks the submission is gated.

Package-level actions (approve/reject a whole package at once) still have no first-class package state — `package.current_level` is derived after the fact as the minimum of member submission levels. But the loop over member submissions is purely additive now: a submission this caller isn't eligible for (different level, or one submitted by the acting user) is recorded as skipped/failed with a reason, inside its own SAVEPOINT, instead of aborting the whole batch and rolling back submissions that already succeeded.

Submission-level `Issue` and cell-level `SubmissionValueIssue` now share the same real enforcement: both have an open→resolved lifecycle (`resolved_by`/`resolved_at`, set via `resolve_issue` / `resolve_package_value_issue`), both carry a `blocks_approval` flag (always set `True` at creation for both — there's no UI path that ever creates or flips it otherwise, on either model), and the final-approval gate checks all three conditions together in one place: no open `Issue` rows, no open `SubmissionValueIssue` rows, and `needs_recalc_review` cleared. Cell issues are raised/resolved from the package review screen (`package_review.js`); the submitter's own read-only view (`annual_workbook.js`) only displays them.

`approve_submission`/`reject_submission`/`request_changes_submission` all lock the submission row before checking/transitioning its status, so two concurrent approvals at an `ANY_ONE` level can no longer both observe the level as still-open and both try to advance/finalize it.

### WKBK — workbook management (group sheets, assign sites, submitters, approval path)

A workbook groups published sheets (`WorkbookForm`), is assigned to sites (`WorkbookSite`), has submitters per site (`WorkbookSiteSubmitter`), and links to an approval path (`Workbook.workflow_id`). Publish readiness requires: ≥1 published sheet, ≥1 assigned site, submitters for every assigned site, and a published approval-path version. This checklist (`check_workbook_readiness`) is real and enforced.

Readiness now revalidates each assigned submitter's actual `submission` permission at that workbook's site via `has_permission()`, not just the existence of a `WorkbookSiteSubmitter` row. An invalid assignment blocks readiness with a specific message naming the user/site that needs fixing.

**WKBK's simplified chain editor (`api_save_site_chain` in `WKBK/views.py`) is currently the only accessible way to configure approval chains.** The standalone Approval Path Builder (WFLWBLD, below) still exists in code, and its service layer (`save_workflow_draft_levels`, `publish_workflow_version`, etc.) is still used internally — WKBK's chain editor calls into it directly rather than duplicating its validation. But WFLWBLD's own UI has been disabled, since multi-level/`SEQUENTIAL` chains aren't needed at the current complexity level. It can be re-enabled by removing the `before_request` block at the top of `WFLWBLD/views.py` (and restoring its nav/dashboard links) if that need arises — see [Consistency Guidelines](#consistency-guidelines).

Deactivating a workbook, or deleting the `Workflow` it points to, now both have dependency checks — `deactivate_workbook` refuses if any in-progress submission (`Draft`/`Submitted`/`Resubmitted`/`Under Review`/`Changes Requested`) still depends on it via the workbook's assigned sheets/sites, and `delete_workflow` (see WFLWBLD below) refuses if an active `Workbook` still points to it. Both raise a clear error instead of silently stranding a submission or workbook.

Permission checks on every WKBK endpoint — including publish and site/submitter assignment — use `@require_permission("form", "manage_forms")`, the same resource type as the Sheet Builder. There is no distinct `"workbook"` permission; anyone with Sheet Builder access has full Workbook admin rights.

### FORMBLD — sheet builder (fields, sections, formulas, publish/versioning)

Fields (`Field`/`FieldVersion`) are properly versioned — publishing a new draft doesn't retroactively change what a live submission sees, because submissions pin to a specific `form_version_id`.

**`FormSection` is now versioned**, the same way fields are — it carries a `form_version_id` (unique per `code` within a version), so editing sections while drafting a new version (rename, reorder, remove) is isolated to the draft and no longer retroactively mutates what's currently live for the *published* version.

Publish readiness for a sheet requires non-empty fields, dropdown fields to have options, and calculated fields to reference a *published* formula version. Field deletion — whether one field omitted from a re-saved draft (`save_form_draft_fields`), or the whole cascade from deleting a sheet (`delete_sheet`) — is blocked up front if any formula still references the field being removed, via `_formulas_referencing_field`'s scan of published formula tokens; the caller gets a clear error naming the blocking formula(s) instead of the field silently disappearing out from under them.

### WFLWBLD — approval path builder (multi-level workflows, versioning)

**This module's UI is currently disabled** — every route under `/module/WFLWBLD/` returns a 404 via a `before_request` hook at the top of `WFLWBLD/views.py`, so visiting it directly 404s instead of loading the builder. This isn't a bug: it's an intentional, easily-reversible switch-off, since WKBK's simplified chain editor is the only configuration surface needed at present. The model and service layers below are untouched and fully live — WKBK, SUBMIT, APPROV, NOTIFY, and FORMBLD all still call into them directly.

The real, validated writer for workflow levels/approvers (`save_workflow_draft_levels`): requires a valid `approval_mode`, ≥1 approver per level, active/existing users, real sites for site-scoped approvers, and unique sequence numbers for `SEQUENTIAL` mode. Publishing requires ≥1 level, ≥1 approver per level, all active, unique sequence numbers where relevant.

**`get_eligible_level_approvers` now filters on `is_active` as well as `is_deleted`**, matching the check `publish_workflow_version` already applies at publish time — if every approver at a level is later deactivated, that level is correctly treated as having no eligible approver instead of silently matching deactivated users.

`update_details` (the workflow-detail edit endpoint) no longer reads or writes `form.description["workflow_id"]` / `["sites"]` — the legacy write path that fed the standalone builder's "Covered Sites" checkbox has been removed (it only ever updates `Workflow.name` now). Site-eligibility routing runs exclusively through `WorkbookSite`, which this never affected either way; the checkbox UI itself still exists in `workflow_builder.js`, but since the module's UI is fully disabled (see above), it's unreachable and its data no longer goes anywhere.

The WKBK per-site chain editor no longer soft-deletes shared `WorkflowLevel` rows simply because one site's submitted level list omits them. It replaces only that site's `WorkflowLevelApprover.scope_site_id` assignments, leaving levels and other sites' approver assignments intact.

`delete_workflow` now refuses to delete a `Workflow` that an active `Workbook` still points to via `workflow_id`, raising a clear error instead of silently stranding that workbook.

### FRMULA — formula definitions and evaluation

Formula delete (`delete_formula`) mirrors the Field-delete guard in the other direction: it blocks if any live calculated field's `field_config["formula_version_id"]` still points at one of the formula's versions, scanning every version a field could hold (not just its current one), and asks the caller to repoint or edit those fields first.

Formulas are versioned and validated against currently-active field/value-set codes at publish time, using `simpleeval`. Value-set tokens are resolved through `get_active_approved_value_set_version()`, so formula publication validates against the active Approved value-set version rather than trusting `ValueSet.current_version_id` if that points at a draft or superseded version. There is no re-validation when a field a published formula references is later renamed or soft-deleted, and FORMBLD's own "delete fields not present in a re-saved sheet" logic (this is literally what a field rename looks like under the hood) does not check formula references before deleting. How this manifests, once it happens, is inconsistent — SUBMIT alone has four different behaviors ranging from fully silent to a specific error message, depending on which of its five calculated-field code paths hits it first (see [Consistency Guidelines](#consistency-guidelines)).

The client-side formula evaluator (`static/js/formula_runtime.js`) is a materially narrower grammar than the backend's (no unary minus, no exponent), and its `SUM_MONTHS` implementation is still a literal no-op internally — it can only ever see one row's values client-side, so it can't compute a real cross-month sum. Rather than trying to fake that computation in the browser, every call site now checks `FormulaRuntime.usesAggregate(expression)` first and shows an explicit "preview unavailable" message instead of a number: the Formula Builder's live preview (`formula_builder.js`) and the inline recalculation run during data entry (`form_renderer.js`, used by `spoc_entry`) both do this consistently. The real value is still computed correctly server-side at save/submit time.

`Formula.context` (`"field"` / `"report"`, default `"field"`) lets the same `Formula`/`FormulaVersion` tables and the same `evaluate_formula()` serve two different callers instead of forking either. `publish_formula_version`'s token-validation branches on it: `"field"` behavior is completely unchanged (tokens checked against `Field.field_code` scoped to `form_id`, plus active `ValueSetEntry.entry_code`). `"report"` validates every token against a fixed canonical metric vocabulary (`REPORT_CONTEXT_METRIC_KEYS` in `FRMULA/service.py`) plus any token matching `{group_id}__{metric_key}` — accepted by shape only here, since FRMULA has no notion of a report template or its row groups; confirming a referenced `group_id` actually exists on a given template is RPTBLD's job (`pivot_report_data`), not FRMULA's. `evaluate_formula()` itself needed no changes for this — it already just takes an expression string and a flat `names` dict, regardless of what a "row" or "group" means to the caller. See Consistency Guidelines below and the RPTBLD section for how this is consumed. The Formula Builder page (`formula_builder.js`/`formula_builder.html`) is context-aware the same way: opened with `?context=report&report_template_id=<id>` (RPTBLD's "Add computed column" round trip, see below), its palette is populated from the canonical metric vocabulary plus that template's currently-configured row groups instead of a form's fields, and its Value Sets tab is hidden — valset codes aren't valid `"report"`-context tokens.

### VALSET — value sets (reference data for dropdowns/lookups)

Draft → Submitted → Approved lifecycle. `reject_value_set_version` blocks self-rejection (`submitted_by == user_id`); `approve_value_set_version` now has an equivalent self-approval check, covering both routes that can reach it — `/publish` (gated by `manage_forms`, the same permission that lets you create the draft) and `/approve` (gated by a distinct `approve` permission). Since `/publish` can approve a version straight from `Draft` (before it's ever been through `/submit`, when `submitted_by` is still unset), the check falls back to `created_by` in that case so a draft's own author can't self-approve through either route.

The active Approved version is resolved by `get_active_approved_value_set_version()`: `status == "Approved"`, `effective_to IS NULL`, newest version/id wins. FRMULA publish validation and SUBMIT runtime calculation snapshots both use this resolver, so draft/current-pointer drift cannot feed formula validation or runtime calculations.

### PERIOD — reporting period lifecycle

See [Reporting Period Statuses](#reporting-period-statuses) above. Four states, stable across the project's entire history. `transition_period` locks the row and `submit_submission` re-checks the period's status under that same lock immediately before its own final transition, closing the race between an admin locking a period and a submission mid-commit in the same window.

### SITEMST — site master

Straightforward CRUD for sites.

### RPTBLD — cross-site/period reporting

Filters submissions to `Approved` + `is_locked=True` before reporting, correctly matching the "reports use only approved and locked values" rule (see [Key Design Rules](#key-design-rules)). Its site/permission-scoping logic (`list_report_templates`, `_get_user_allowed_sites`) now calls the shared `get_user_permissions()` instead of hand-rolling its own `AccessMatrix` query — the same fix NOTIFY's `resolve_recipients` got (see NOTIFY below) — so a user with a blanket "all entities" permission grant is no longer silently excluded from reports they should be able to see. Template read/export and mutation routes also use resource-aware scoped checks: global report grants still work, and site-scoped grants can create/update/delete templates for their own site without opening access to other sites.

`get_missing_submissions` batch-fetches workbook-assignment and existing-submission data up front (two queries total, keyed by set) instead of running two queries per (period, form) pair inside a doubly-nested loop — the same fix applied to SUBMIT's `get_spoc_sheets_buckets` and APPROV's `get_approver_queue`, which had the same O(n×m) pattern.

`pivot_report_data()` sits alongside `generate_report_data()`, not in place of it — the flat, per-field-per-submission query stays the query of record (`export_report_to_excel`'s flat "Report Data" sheet and any other flat-row consumer are unaffected), and `pivot_report_data` reuses its output rather than re-querying submissions. `ReportTemplate.config_json` can now additionally hold `row_groups` (site groupings with a subtotal label and an `is_reference_base`/`include_in_grand_total` flag each — exactly one group per template may be the reference base), `metric_aliases` (per-site, per-canonical-metric field mappings, `field_id`-keyed rather than code-string-keyed so a mapping survives a field rename — a deliberate departure from `FormulaVersion.tokens`'s own code-string pattern, which is the fragility FORMBLD's "delete fields not present in a re-saved sheet" gap already demonstrates elsewhere), and `computed_columns` (one entry per report-level formula column, each pointing at a `context="report"` `Formula` by `formula_id`). `export_report_to_excel` grows an additional "Report Data (Pivot)" sheet, built from `pivot_report_data`, whenever `row_groups` is configured — the original flat sheet is untouched either way.

`AppConfig` (a key/value table that sat completely unreferenced since it was added) now has its first real reader: `get_emission_factor_version()`. This is display/documentation only — it is never wired into `evaluate_formula`'s `names` dict or any other computation. The source workbook this feature was modeled on treats its emission-factor cells as reference footnotes, not active formula inputs (no formula in that workbook actually multiplies by the emission factor; Scope-1/2 values arrive already computed from upstream), so this stays a footnote-only value here too.

### AUDITL — audit log

Records status changes and resolves human-readable entity descriptions for the audit trail. The `access_matrix` entity-description branch now correctly reads `scope_site_id` (the real field on `AccessMatrix`), producing a proper "User: ..., Site: ..." (or "Scope: Global") description instead of falling back to a generic "Access Matrix Record #123" label.

### NOTIFY — notifications (in-app, desktop, email, WhatsApp)

Multi-channel routing with per-user preferences. **`resolve_recipients`'s role-based and dynamic (`site_admins`) recipient resolution now calls the shared `get_user_permissions()` / `has_permission()`** instead of hand-rolling its own `AccessMatrix` query, matching the RPTBLD permission-resolver remediation (see [Consistency Guidelines](#consistency-guidelines)) — so a user with a blanket "all entities" grant is no longer silently skipped as a notification recipient.

Email/WhatsApp delivery attempts are persisted as `Notification` rows with `channel == "email"` / `"whatsapp"`. Their outcome is stored in `delivery_status` (`"sent"` or `"failed"`) and `delivery_error`; in-app and desktop rows default to `"sent"` because they are database inserts rather than external-provider sends.

### ACCESS — AccessMatrix, the permission source of truth

`get_user_permissions()` / `has_permission()` correctly OR in `entity_type == "all"` alongside a specific entity type — this is the correct, complete implementation and the one every module should call (see [Key Design Rules](#key-design-rules)). `ACCESS/views.py` is now the sole, canonical user CRUD UI (create/edit/password/toggle-active) — the duplicate that used to live in `USRMGMT/views.py` was confirmed unreachable from any nav link, dashboard card, or cross-reference, and has been removed. Both call the same `USRMGMT/service.py` functions underneath; ACCESS's blueprint additionally handles permission assignment (`/assign`, `/assign-matrix`), which USRMGMT never had.

`count_global_user_managers(exclude_user_id=None)` is the shared helper for "how many active users currently resolve global `can_manage_users`" — it counts via `get_user_permissions()` per user rather than a raw `AccessMatrix` column scan, so an `entity_type == "all"` wildcard grant is correctly counted as admin access. Both zero-global-admin guards below (`upsert_access_row` here, and `USRMGMT.can_deactivate_user`) call this one function, so they can't quietly disagree with each other. `upsert_access_row` — the single write path both `/assign` and `/assign-matrix` (via `save_permission_matrix`, which calls it once per entity type) funnel through — now blocks a global `user`/`all`-entity save that would revoke `can_manage_users` from a user who currently holds it, if `count_global_user_managers` (excluding that user) is `0`. This closes the loophole where the last admin's access could be zeroed out through the permission matrix even though deactivating that same user outright was already blocked — a site-scoped grant never counts toward or is blocked by this check, only `scope_type == "global"`.

Active AccessMatrix rows are uniqueness-scoped by user, scope, entity type, and entity id. The migration soft-deletes duplicate active rows before adding the partial unique index, and `upsert_access_row()` resolves all matching active rows in newest-updated order, soft-deletes duplicates, and applies the update/revoke to the survivor. This means revoking a permission can no longer update one duplicate while another active duplicate silently preserves access.

The wildcard `entity_type == "all"` grant is now a first-class row in the ACCESS matrix UI/API, not just a runtime behavior. It appears as "All Entities", supports the same permission flags, and can be created, edited, or revoked through the canonical ACCESS screen.

Creating a user through ACCESS/USRMGMT now emits a `USER_CREATED` audit event after the user row is flushed. The payload is the non-sensitive user snapshot (`id`, `full_name`, `email`, `phone`, `is_active`) and does not include temporary passwords, password hashes, or reset material.

`toggle_active` is now gated by `@require_permission("user", "manage_users")`, matching every other admin action on this blueprint (create/edit/password/assign/assign-matrix) — it previously accepted the weaker `("edit", "delete")` grant, a mismatch with an action that flips whether an account can log in at all. `access_matrix.html`'s toggle-active button, its "Reset password" menu item, and the row's action-cell/menu-toggle wrappers around them were updated to gate on `perm_manage_users` alone, so what's visible in the UI now matches what the backend actually allows. One consequence, left as-is here: `can_edit` / `can_delete` on the `"user"` entity_type are not consumed by any route or permission check anywhere in the app today — a known inert-permission-flag observation, not something fixed in this change.

### USRMGMT — user management and auth

Password hashing uses bcrypt. Session handling correctly clears the session before setting a new user on login. `USRMGMT/views.py` now holds only `auth_bp` (`/login`, `/logout`) — its own user CRUD blueprint (`bp`: index/create/edit/password/toggle-active, plus `users.html`) was removed as the unreachable duplicate of ACCESS's (see ACCESS above); `USRMGMT/service.py` is untouched and still the shared implementation both ACCESS and the login flow call into.

Post-login `next` redirects are allowed only when `is_safe_internal_path()` confirms a relative, same-origin application path: no scheme, no netloc, no protocol-relative `//`, no backslash-normalization tricks, no encoded external variants, and no CR/LF characters. Unsafe values fall back to `default_landing_url(user)`.

Password reset OTPs are rate-limited and locked after repeated failed verification attempts. A locked/expired/wrong OTP uses the same generic error text, and issuing a new OTP invalidates older unused ones and starts with a clean attempt counter. Successful password reset increments `User.session_version`; `current_user()` compares it with `session["user_session_version"]`, so existing logged-in sessions for that user are invalidated. The reset form also posts `confirm_password`, and the server checks it against `new_password` before consuming the OTP or changing the password.

`can_deactivate_user` now resolves through ACCESS's `get_user_permissions()` / `count_global_user_managers()` instead of hand-rolling its own raw `AccessMatrix` join/filter — the same anti-pattern class Consistency Guideline #3 flags (RPTBLD, and until recently NOTIFY) — so it can never quietly disagree with the equivalent guard on the permission-matrix side (see ACCESS above). Semantics are unchanged: a user who isn't currently active, or doesn't currently hold global `can_manage_users`, can always be deactivated; one who does can only be deactivated if at least one other active user still retains it. `set_user_active` also now refuses self-deactivation outright (`user_id == actor_id`) as its very first check, before `can_deactivate_user` or anything else runs — an admin can no longer lock themselves out even while other admins remain.

---

## Key Design Rules

These are enforced (or intended to be enforced) throughout the codebase. Violations should be flagged in code review.

- **AccessMatrix is the permission source of truth.** Call `has_permission()` / `get_user_permissions()` from the `ACCESS` module for every authorization check. Do not hand-roll a narrower `AccessMatrix` query and do not use hardcoded roles — see [Known Gaps](#known-gaps) for where this is currently violated.
- **Every state-changing request needs CSRF.** Application-wide CSRF validation covers `POST`, `PUT`, `PATCH`, and `DELETE` with a session token rendered into the page as `<meta name="csrf-token">` and sent by `static/js/csrf.js` as `X-CSRFToken` for same-origin fetch mutations. There are no route or blueprint exemptions.
- **`WorkbookSite` is the authoritative source for workbook-site assignment.** The legacy `form.description["sites"]` field must never be read for runtime routing (it is still, unfortunately, actively *written* by one dead-end UI — see the WFLWBLD module notes and [Known Gaps](#known-gaps)).
- **`WorkbookSiteSubmitter` gates submitter workbook visibility, with no AccessMatrix fallback.** Seeing/submitting a workbook at a site requires both an AccessMatrix `submission` grant at that site *and* an explicit `WorkbookSiteSubmitter` row for that workbook/site — AccessMatrix access alone is never enough. `WorkbookSiteSubmitter` is a deliberate, explicit assignment ("this exact person submits this exact workbook"), not a permission proxy. When a user has the AccessMatrix grant but no `WorkbookSiteSubmitter` row, this is surfaced explicitly (`needs_submitter_assignment` from `get_annual_workbook_options` / `get_spoc_sheets_buckets`) rather than left as an unexplained empty state.
- **`Workbook.workflow_id` is the approval path source.** Form-level workflow metadata (`form.description["workflow_id"]`) must never be used for submission routing — it is also still actively written by the same dead-end UI noted above, but never read for routing.
- **`WorkbookForm` is the source of workbook sheets.** Runtime sheet tabs must come from the selected workbook's configured sheet list.
- **No manual `ALTER TABLE`.** All schema changes must go through Alembic migrations, and the migration chain must remain linear with a single head (see [Known Gaps](#known-gaps) — this isn't mechanically enforced yet).
- **Missing or blank values are never treated as zero** in formula calculations. The formula evaluator excludes blank/missing values from evaluation inputs rather than coercing them.
- **Calculated values on a non-locked submission are not fully pinned to their `form_version`'s formula — this is a deliberate, narrow exception, not a pattern to extend.** `Submission.form_version_id` never changes after creation, but a calculated field's `field_config.formula_version_id` is a live, in-place edit (unlike the `Formula` row itself, which is never edited in place once published — see FRMULA above). When that live formula reference changes to a genuinely different `Formula`, `recalc_or_flag_submissions_for_formula_swap` (`SUBMIT/service.py`) recalculates every Draft/Submitted/Resubmitted/Under Review/Changes Requested submission on that sheet against the *current* live formula, not the formula that was live when each row was entered. Only raw input values, and calculated values on submissions already `Approved` + `is_locked=True`, are truly immutable — locked submissions are never silently recomputed; they're flagged `needs_recalc_review` instead, gated by the existing final-approval check. Do not generalize this "recompute against current state" behavior to any other versioned entity (`Form`, `Workflow`, `ValueSet`) — those remain fully pinned to their version at all times.
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

   `Formula` is a second, deliberate instance of this same rule, not a special case: `context` (`"field"` / `"report"`) lets FORMBLD's calculated fields and RPTBLD's computed report columns share one `Formula`/`FormulaVersion` schema and one `evaluate_formula()`, with only `publish_formula_version`'s token-validation step branching per context. **The `context` branch in `publish_formula_version` is not dead code or an accidental fork — it is the whole point.** Don't "simplify" it back down to a single validation path, and don't add a third caller without extending that same branch rather than writing a parallel validator. RPTBLD's own Formula Builder round trip (`reports.js` → `/module/FRMULA/?context=report&report_template_id=...` → `formula_builder.js`) is the UI-reuse half of this: it navigates to FRMULA's existing page rather than forking its contenteditable chip engine into `reports.js`, the same way WKBK's chain editor reuses WFLWBLD's backend instead of reimplementing it.

5. **Shared vocabularies that already exist — extend these, don't fork them:**
   - **Submission status** — `STATUS_DRAFT` / `STATUS_SUBMITTED` / `STATUS_RESUBMITTED` / `STATUS_UNDER_REVIEW` / `STATUS_CHANGES_REQUESTED` / `STATUS_APPROVED` / `STATUS_REJECTED`, plus the `EDITABLE_SUBMISSION_STATUSES` / `REVIEWABLE_STATUSES` groupings and `SUBMISSION_STATUS_LABELS`, all defined once in `app/common/submission_status.py` and imported by both `SUBMIT/service.py` and `APPROV/service.py`. `PERIOD` and `VALSET` have their own, separate status lifecycles and are not part of this vocabulary — don't fold them in.
   - **Calculated-field status** — `calc_status` (`"ok"` / `"error"` / `"pending"`), defined in `SUBMIT/service.py`. This is the canonical vocabulary produced by the shared `resolve_calculated_fields` resolver (used by both the persisted and preview paths) for "can this calculated field's value be trusted right now." The annual sheet-result path (`_compose_sheet_results`) still has its own, different vocabulary (`not_configured`/`needs_input`/`calculated`/`error`/`partial`) since it resolves a structurally different value shape — new code resolving ordinary per-row calculated fields should use `calc_status`'s vocabulary, not invent a third. `partial` means a `SUM_MONTHS`-style FY aggregate computed from whatever months are present (`blank_policy` defaults to allowing this; an explicit `blank_policy: "strict"` on the field still blocks and returns `needs_input` instead). `calculated` means literally every month is present — the two never overlap. This partial-computation behavior is specific to cross-month aggregation in `_compose_sheet_results`; `resolve_calculated_fields` (row-level formulas like `Total = A * B`) is untouched and still returns `pending` for a missing same-row operand, since that genuinely can't be computed at all, partially or otherwise.
   - **Cell state** — `CELL_STATE_BLANK_EDITABLE` / `_DRAFT_FILLED` / `_SUBMITTED` / `_APPROVED_LOCKED` / `_CHANGES_REQUESTED` / `_LATE_ENTRY`, defined in `SUBMIT/service.py`. This is the canonical per-value lifecycle state. The frontend (`static/js/workbook_sheet.js`) reads its display colors from one shared `CELL_STATE_META` map (also used by the reviewer legend) — if you add a cell state, add it there and nowhere else.

---

## Known Gaps

Honest, short list of things known to be wrong or unfinished today. If you fix one of these, delete it from this list in the same change.

- **"SPOC" and "Submitter" (and "Approver" and "Reviewer") coexist in the codebase.** See [Terminology](#terminology) below — user-facing copy mostly says Submitter/Reviewer, but module names, JS filenames, CSS classes, and some newer admin-facing strings still say SPOC/Approver.
- **`Field.current_version_id` means something different from every sibling `current_version_id`** in the app (see [Consistency Guidelines](#consistency-guidelines)). Harmless today since nothing reads it, but a landmine for anyone who assumes it follows the app-wide convention.
- **There is no single "correct" default for which group a `%` Contribution/Variation computed column divides against.** The real source workbook this feature was modeled on always divided its `% Contribution`/`Variation` columns by the Core group's subtotal, even for non-Core rows — that was a hardcoded assumption in a spreadsheet formula, not a deliberate design decision. This system doesn't reproduce that assumption as a default; instead, which group's subtotal a `pct_of_group`/`variation_from_group_avg`-style computed column references is an explicit, per-formula choice, made by whichever `{group_id}__{metric_key}` token the formula's author picks when building it in FRMULA. Don't assume "divide by the reference-base group" is the intended behavior when reading or writing one of these formulas — read the actual token.
- **`metric_aliases` keyed by a computed column's own `id` (rather than a canonical metric key) is a deliberate per-site override escape hatch, not an inconsistency.** It exists because the real source workbook had specific sites (referred to during development as the PNP/MELT case) that sourced a value like Energy Intensity directly from upstream instead of it being computed from other cells. `pivot_report_data` honors an override entry over formula evaluation for that site/column and marks the cell `"source": "override"` (vs `"computed"`) precisely so this is visible at every layer above it — in the API response, the Excel export's cell, and the preview table — rather than silently indistinguishable from a normal computed value. This phase (4) doesn't expose UI for authoring override entries — they can currently only arrive via a template's `config_json` written directly or carried over from an earlier config — so it renders correctly wherever it already exists but isn't yet editable from the drawer.
- **RPTBLD's "Add computed column" round trip to FRMULA requires the report template to already be saved.** Unlike FORMBLD (whose Form/Field rows are persisted before its own "Open Formula Builder" button is ever reachable), RPTBLD's create-template drawer holds every panel — General/Scoping/Forms/Sites/Row Groups/Metric Aliasing — in browser memory only until a single final save. Building a computed column's formula means navigating away to a different page, so "Add Computed Column" stays disabled until the template has a real id: a brand-new template must be saved once (row groups and metric aliases included, computed columns still empty) before its computed columns can be added via the FRMULA round trip. This is the reason `create_report_template`/`update_report_template` gained no new "draft" concept in this phase — the existing create-then-edit flow was reused rather than inventing incremental autosave.
- **Three calculated-result tests still encode the superseded three-decimal expectation.** The stale assertions are `round(0.026 * 47.3, 3)`-style checks that fail by about `0.0002` now that calculated fields are expected to use four-decimal precision (`1.2298`). This is unrelated to the security/correctness remediation batches and still needs a separate precision-policy cleanup.
- **Two data-cleanup migrations have not been exercised against real data yet.** The proof-document active-uniqueness migration (`e1f2a3b4c5d6`) and AccessMatrix active-uniqueness migration (`f6a7b8c9d0e2`) are written to soft-delete duplicate active rows before adding partial unique indexes, but they still need staging-first verification before production.

---

## Terminology

"SPOC" (Single Point of Contact) and "Submitter" refer to the same role: the person who enters monthly data for a site. "Approver" and "Reviewer" refer to the same role: the person who reviews and approves/rejects submissions. User-facing copy was swept from SPOC/Approver to Submitter/Reviewer in one pass, but the rename didn't reach everywhere:

- **Says Submitter/Reviewer:** most current user-facing UI copy.
- **Still says SPOC/Approver:** the `SUBMIT` module's internal name, `static/js/spoc_entry.js`, `static/js/spoc_sheets.js`, the `.approver-submission-review` CSS class, `human_sheet_label`'s helper naming, and some newer NOTIFY admin-facing notification-config strings (added after the rename, but written using the old terms).

**Submitter / Reviewer is the intended long-term direction for all new user-facing copy.** Internal identifiers (module names, file names, CSS classes) are not required to be renamed retroactively — do not do a mechanical rename of those as a side effect of unrelated work, since `SUBMIT`/`APPROV` are load-bearing module names referenced throughout routing and permissions.
