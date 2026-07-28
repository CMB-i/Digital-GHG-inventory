from app.modules.FORMBLD.model import Field, FieldVersion
from app.modules.WKBK.model import WorkbookForm


NUMERIC_FIELD_TYPES = {"integer", "number", "decimal", "float", "numeric"}


def is_formula_compatible_field(field_version):
    field_type = (field_version.field_type or "").strip().lower()
    config = field_version.field_config or {}
    configured_type = str(
        config.get("result_type")
        or config.get("value_type")
        or config.get("data_type")
        or ""
    ).lower()
    return (
        field_type in NUMERIC_FIELD_TYPES
        or field_type == "calculated"
        or configured_type in NUMERIC_FIELD_TYPES
        or config.get("is_numeric") is True
    )


def get_formula_compatible_fields(form_version_id):
    if not form_version_id:
        return []

    rows = (
        FieldVersion.query.with_entities(FieldVersion, Field)
        .join(Field, Field.id == FieldVersion.field_id)
        .filter(
            FieldVersion.form_version_id == form_version_id,
            FieldVersion.is_deleted.is_(False),
            Field.is_deleted.is_(False),
        )
        .order_by(Field.display_order.asc(), Field.id.asc())
        .all()
    )
    return [
        {
            "field_id": field_version.field_id,
            "field_version_id": field_version.id,
            "field_code": field.field_code,
            "field_name": field_version.field_name,
            "field_type": field_version.field_type,
        }
        for field_version, field in rows
        if is_formula_compatible_field(field_version)
    ]


import re
from datetime import datetime, timezone
from app.database import db
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion, FormSection
from app.modules.FRMULA.model import FormulaVersion

MOCK_FY_START_YEAR = 2026
MOCK_FY_MONTHS = (
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December"),
    (1, "January"),
    (2, "February"),
    (3, "March"),
)

ALLOWED_SECTION_LAYOUT_TYPES = {"monthly_table", "annual_table", "reference_table"}
ALLOWED_FIELD_FREQUENCIES = {"monthly", "annual", "static"}


def local_dropdown_options(field_config):
    options = (field_config or {}).get("options")
    if not isinstance(options, list):
        return []

    normalized = []
    for option in options:
        if isinstance(option, dict):
            value = (
                option.get("entry_label")
                or option.get("label")
                or option.get("name")
                or option.get("entry_code")
                or option.get("code")
                or option.get("value")
            )
        else:
            value = option
        if value is not None and str(value).strip():
            normalized.append(str(value).strip())
    return normalized

def list_forms():
    return Form.query.filter_by(is_deleted=False).all()

def get_form(form_id):
    return Form.query.filter_by(id=form_id, is_deleted=False).one_or_none()

def get_form_by_code(code):
    return Form.query.filter_by(code=code, is_deleted=False).one_or_none()

def create_form(name, code, description, user_id):
    if not name or not name.strip():
        raise ValueError("Form name is required.")
    if not code or not code.strip():
        raise ValueError("Form code is required.")
        
    existing = get_form_by_code(code)
    if existing:
        raise ValueError(f"Form with code '{code}' already exists.")
        
    form = Form(
        name=name.strip(),
        code=code.strip(),
        description=description,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(form)
    db.session.flush()
    
    version = FormVersion(
        form_id=form.id,
        version_number=1,
        status="Draft",
        created_by=user_id
    )
    db.session.add(version)
    db.session.flush()

    return form

def _formulas_referencing_field(field):
    """
    Returns every Formula whose currently-published FormulaVersion references
    field.field_code in its tokens. tokens is a raw JSON dict with no FK to
    Field (see FRMULA.model.FormulaVersion), so this has to be an
    application-level scan rather than something the database can enforce.

    Scoped to formulas built for the same form as the field (or legacy
    formulas with no form_id recorded), mirroring publish_formula_version's
    own scoping in FRMULA/service.py -- field_code is only unique per-form,
    so an unscoped check could false-positive on an unrelated field
    elsewhere that happens to share the same code.
    """
    from app.modules.FRMULA.model import Formula, FormulaVersion

    referencing = []
    formulas = Formula.query.filter(
        Formula.is_deleted == False,
        Formula.current_version_id.isnot(None),
    ).filter(
        db.or_(Formula.form_id == field.form_id, Formula.form_id.is_(None))
    ).all()
    for formula in formulas:
        # FormulaVersion has no is_deleted column (unlike Formula) -- only
        # id lookup applies here.
        version = FormulaVersion.query.filter_by(id=formula.current_version_id).one_or_none()
        if version and field.field_code in (version.tokens or {}):
            referencing.append(formula)
    return referencing

def _blocked_field_removal_message(prefix, blocked_fields_with_formulas):
    parts = []
    for field_code, formulas in blocked_fields_with_formulas:
        names = ", ".join(f"'{formula.name}' ({formula.code})" for formula in formulas)
        parts.append(f"'{field_code}' is referenced by formula(s) {names}")
    return f"{prefix}: " + "; ".join(parts) + ". Unpublish or edit the formula(s) first."

def delete_sheet(form_id, user_id, reason):
    """
    A sheet can now only ever be attached to the workbook it was created in
    -- "Reuse existing sheet" (which let one sheet be attached to more than
    one Workbook via WorkbookForm) has been removed. Sheets reused before
    that removal may still have more than one live WorkbookForm row, so
    deletion detaches from every one of them, not just one.

    Like Period's delete, this blocks on a Submission of ANY status, not just
    in-progress -- RPTBLD may read historical Approved/Locked submissions by
    form, so old approved data still isn't safe to remove out from under it.
    Submission has no workbook_id column at all (uq_active_submission scopes
    it only by site_id/form_id/reporting_period_id), so this one check is
    already sufficient regardless of how many workbooks reference the sheet
    -- no separate per-workbook submission check is needed.
    """
    form = Form.query.filter_by(id=form_id, is_deleted=False).one_or_none()
    if not form:
        raise ValueError("Sheet not found.")

    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A delete reason is required.")

    from app.modules.SUBMIT.model import Submission
    submission_count = Submission.query.filter_by(form_id=form_id, is_deleted=False).count()
    if submission_count > 0:
        raise ValueError(
            f"Cannot delete sheet: {submission_count} submission(s) of any "
            "status still reference it."
        )

    # This cascades to soft-delete every active field on the sheet below, via
    # a code path completely separate from save_form_draft_fields (no draft
    # payload involved) -- so it needs a published-formula-reference guard
    # up front, checked before any mutation, same as that path. But unlike
    # save_form_draft_fields (where the sheet survives and a sibling
    # formula's need for the field is a real external dependency),
    # _formulas_referencing_field's Formula.form_id == field.form_id branch
    # can only ever return formulas that belong to THIS sheet -- formulas
    # are strictly sheet-scoped (see publish_formula_version's own
    # per-form field-code cross-check), so a same-sheet formula is being
    # deleted along with everything else here, not a genuine dependency,
    # and must never block the sheet's own deletion. Only the legacy
    # form_id-is-None case is excluded from that filtering: those formulas
    # validate against every active field system-wide (see
    # publish_formula_version's unscoped fallback), so one could still be
    # the live formula for a same-named field on a different, still-existing
    # sheet -- that ambiguity means it must keep blocking, same as before.
    active_fields = Field.query.filter_by(form_id=form_id, is_deleted=False).all()
    blocked = []
    for f in active_fields:
        referencing_formulas = [
            formula for formula in _formulas_referencing_field(f)
            if formula.form_id != form_id
        ]
        if referencing_formulas:
            blocked.append((f.field_code, referencing_formulas))
    if blocked:
        raise ValueError(_blocked_field_removal_message("Cannot delete sheet", blocked))

    now = datetime.now(timezone.utc)

    # Detach from every workbook that currently references it -- normally at
    # most one now, but legacy sheets attached via the removed reuse flow may
    # still have more than one live WorkbookForm row.
    from app.modules.WKBK.model import WorkbookForm
    for wf in WorkbookForm.query.filter_by(form_id=form_id).all():
        db.session.delete(wf)

    form.is_deleted = True
    form.deleted_by = user_id
    form.deleted_at = now
    form.delete_reason = reason

    # Cascade to this sheet's own fields, same soft-delete pattern
    # save_form_draft_fields already uses -- just applied to every active
    # field at once instead of one draft-save payload at a time.
    for f in active_fields:
        f.is_deleted = True
        f.deleted_by = user_id
        f.deleted_at = now
        f.delete_reason = "Sheet deleted"

    return form

def get_form_version(version_id):
    return FormVersion.query.get(version_id)

def get_form_sections(form_version_id):
    return (
        FormSection.query.filter_by(form_version_id=form_version_id, is_deleted=False)
        .order_by(FormSection.display_order.asc(), FormSection.id.asc())
        .all()
    )

def get_form_version_fields(form_version_id):
    rows = (
        FieldVersion.query.with_entities(FieldVersion, Field)
        .join(Field, Field.id == FieldVersion.field_id)
        .filter(
            FieldVersion.form_version_id == form_version_id,
            FieldVersion.is_deleted.is_(False),
            Field.is_deleted.is_(False),
        )
        .order_by(Field.display_order.asc(), Field.id.asc())
        .all()
    )
    return rows


def _latest_form_version_id(form_id):
    latest = (
        FormVersion.query.filter_by(form_id=form_id)
        .order_by(FormVersion.version_number.desc())
        .first()
    )
    return latest.id if latest else None


def _preview_fields_for_version(form_version_id):
    fields = []
    for fv, field in get_form_version_fields(form_version_id):
        field_config = dict(fv.field_config or {})
        field_type = (fv.field_type or "").strip().lower()
        fields.append({
            "id": fv.field_id,
            "field_id": fv.field_id,
            "field_version_id": fv.id,
            "field_code": field.field_code,
            "display_order": field.display_order,
            "field_name": fv.field_name,
            "field_type": fv.field_type,
            "field_config": field_config,
            "section_id": fv.section_id,
            "section_code": fv.section.code if fv.section else "",
            "frequency": fv.frequency or "monthly",
            "calculated": field_type == "calculated",
        })
    return fields


def _preview_sections_for_version(form_version_id):
    return [{
        "id": section.id,
        "name": section.name,
        "code": section.code,
        "layout_type": section.layout_type,
        "display_order": section.display_order,
        "description": section.description or "",
    } for section in get_form_sections(form_version_id)]


def _preview_rows(fields):
    rows = []
    for month, month_name in MOCK_FY_MONTHS:
        year = MOCK_FY_START_YEAR if month >= 4 else MOCK_FY_START_YEAR + 1
        values = {}
        for field in fields:
            field_type = (field.get("field_type") or "").strip().lower()
            values[field["field_code"]] = {
                "submission_value_id": None,
                "raw_value": None,
                "calculated_value": None,
                "cell_state": "approved_locked" if field_type == "calculated" else "blank_editable",
                "is_locked": field_type == "calculated",
                "remark": None,
                "status": "preview_only" if field_type == "calculated" else None,
                "preview_value": None,
                "reportable_value": None,
                "warnings": [],
            }
        rows.append({
            "row_key": f"preview-{year}-{month:02d}",
            "year": year,
            "month": month,
            "label": f"{month_name} {year}",
            "period_label": f"{month_name} {year}",
            "period_id": None,
            "period_status": "OPEN",
            "submission_id": None,
            "submission_status": "Not Started",
            "is_locked": False,
            "editable": False,
            "editability": {"editable": False, "reason": "Preview only"},
            "values": values,
            "proofs": {},
            "issues": {},
            "is_active_period": False,
        })
    return rows


def _preview_workbook_values(fields, sections):
    section_by_id = {section["id"]: section for section in sections}
    workbook_values = {}
    for field in fields:
        section = section_by_id.get(field.get("section_id"))
        layout_type = (section.get("layout_type") if section else "monthly_table") or "monthly_table"
        is_non_monthly = (
            (field.get("frequency") or "monthly").strip().lower() in ("annual", "static")
            or layout_type.strip().lower() in ("annual_table", "reference_table")
        )
        if is_non_monthly:
            workbook_values[field["field_code"]] = {
                "workbook_value_id": None,
                "raw_value": None,
                "calculated_value": None,
                "cell_state": "approved_locked" if field.get("calculated") else "blank_editable",
                "is_locked": bool(field.get("calculated")),
                "remark": None,
            }
    return workbook_values


class _DraftPreviewCrossSheetResolver:
    def __init__(self, selected_form_id):
        self.selected_form_id = selected_form_id
        self._shape_cache = {}
        self._results_cache = {}
        self._resolving = set()
        self.resolution_order = []

        memberships = WorkbookForm.query.filter_by(form_id=selected_form_id).all()
        workbook_ids = [row.workbook_id for row in memberships]
        if len(set(workbook_ids)) != 1:
            self.form_by_id = {}
            self.label_by_form_id = {}
            return

        workbook_id = workbook_ids[0]
        rows = (
            WorkbookForm.query.filter_by(workbook_id=workbook_id)
            .order_by(WorkbookForm.display_order.asc(), WorkbookForm.id.asc())
            .all()
        )
        form_ids = [row.form_id for row in rows]
        forms = {form.id: form for form in Form.query.filter(Form.id.in_(form_ids)).all()}
        self.form_by_id = {
            row.form_id: forms[row.form_id]
            for row in rows
            if row.form_id in forms and _latest_form_version_id(row.form_id)
        }
        self.label_by_form_id = {
            row.form_id: (row.sheet_label or forms[row.form_id].name)
            for row in rows
            if row.form_id in forms
        }

    def _shape_for(self, form):
        if form.id not in self._shape_cache:
            from app.modules.SUBMIT.service import is_sheet_result_field, monthly_table_fields

            version_id = _latest_form_version_id(form.id)
            fields = _preview_fields_for_version(version_id)
            sections = _preview_sections_for_version(version_id)
            monthly_fields = monthly_table_fields(fields, sections)
            sheet_result_fields = [field for field in fields if is_sheet_result_field(field)]
            workbook_values = _preview_workbook_values(fields, sections)
            rows = _preview_rows(fields)
            self._shape_cache[form.id] = (fields, sections, monthly_fields, sheet_result_fields, workbook_values, rows)
        return self._shape_cache[form.id]

    def _fields_for(self, form):
        fields, _sections, _monthly_fields, _sheet_result_fields, _workbook_values, _rows = self._shape_for(form)
        return {field["field_code"]: field for field in fields}

    def _owner_forms_for_code(self, code, requesting_form_id):
        owners = []
        for form_id, form in self.form_by_id.items():
            if form_id == requesting_form_id:
                continue
            if code in self._fields_for(form):
                owners.append(form)
        return owners

    def resolve_external_for(self, form):
        self._resolving.add(form.id)
        return lambda code: self.resolve(code, form.id)

    def finish_external_for(self, form, sheet_results):
        self._resolving.discard(form.id)
        self._results_cache[form.id] = {result["field_code"]: result for result in sheet_results}

    def resolve(self, code, requesting_form_id):
        owners = self._owner_forms_for_code(code, requesting_form_id)
        if not owners:
            return None
        if len(owners) > 1:
            labels = [self.label_by_form_id.get(owner.id, owner.code) for owner in owners]
            return {
                "ok": False,
                "hard_error": True,
                "error_causes": [
                    f"Ambiguous cross-sheet formula token '{code}' exists on multiple sheets: {', '.join(labels)}."
                ],
            }

        owner = owners[0]
        owner_label = self.label_by_form_id.get(owner.id, owner.code)
        if owner.id in self._resolving:
            return {
                "ok": False,
                "hard_error": True,
                "error_causes": [f"Circular cross-sheet formula dependency involving sheet '{owner_label}'."],
            }

        result = self._results_for_form(owner).get(code) or {}
        owner_field = self._fields_for(owner).get(code) or {}
        field_label = owner_field.get("field_name") or code
        status = result.get("status")

        if status in ("calculated", "partial"):
            return {"ok": True, "value": result.get("value"), "partial": status == "partial"}
        if status == "error":
            return {
                "ok": False,
                "hard_error": True,
                "error_causes": result.get("error_causes") or [
                    f"'{field_label}' (from '{owner_label}') could not be calculated: {result.get('message') or 'error'}."
                ],
            }
        return {
            "ok": False,
            "hard_error": False,
            "blocking_causes": result.get("blocking_causes") or [(owner_label, field_label)],
        }

    def _results_for_form(self, form):
        if form.id in self._results_cache:
            return self._results_cache[form.id]

        from app.modules.SUBMIT.service import _compose_sheet_results

        fields, _sections, monthly_fields, sheet_result_fields, workbook_values, rows = self._shape_for(form)
        self.resolution_order.append(form.code)
        resolve_external = self.resolve_external_for(form)
        sheet_results = _compose_sheet_results(
            sheet_result_fields,
            monthly_fields,
            rows,
            resolve_external=resolve_external,
            own_sheet_label=self.label_by_form_id.get(form.id, form.code),
            annual_fields=fields,
            workbook_values=workbook_values,
        )
        self.finish_external_for(form, sheet_results)
        return self._results_cache[form.id]

def compose_preview_workbook_context(form_version_id):
    version = get_form_version(form_version_id)
    if not version:
        raise ValueError("Form version not found.")

    form = get_form(version.form_id)
    if not form:
        raise ValueError("Form not found.")

    fields = _preview_fields_for_version(form_version_id)
    sections = _preview_sections_for_version(form_version_id)
    rows = _preview_rows(fields)
    workbook_values = _preview_workbook_values(fields, sections)

    from app.modules.SUBMIT.service import is_sheet_result_field, _compose_sheet_results, monthly_table_fields

    sheet_result_fields = [field for field in fields if is_sheet_result_field(field)]
    table_fields = monthly_table_fields(fields, sections)
    cross_sheet_resolver = _DraftPreviewCrossSheetResolver(form.id)
    resolve_external = cross_sheet_resolver.resolve_external_for(form)
    sheet_results = _compose_sheet_results(
        sheet_result_fields,
        table_fields,
        rows,
        resolve_external=resolve_external,
        annual_fields=fields,
        workbook_values=workbook_values,
        own_sheet_label=form.name,
    )
    cross_sheet_resolver.finish_external_for(form, sheet_results)

    return {
        "financial_year": {
            "start_year": MOCK_FY_START_YEAR,
            "label": f"FY {MOCK_FY_START_YEAR}-{str(MOCK_FY_START_YEAR + 1)[-2:]}",
            "months": [
                {
                    "year": MOCK_FY_START_YEAR if month >= 4 else MOCK_FY_START_YEAR + 1,
                    "month": month,
                    "label": month_name,
                }
                for month, month_name in MOCK_FY_MONTHS
            ],
        },
        "site": {
            "id": None,
            "name": "Data Entry Preview",
            "code": "PREVIEW",
        },
        "selected_form": {
            "id": form.id,
            "name": form.name,
            "code": form.code,
            "workflow_id": None,
        },
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "status": version.status,
        },
        "fields": table_fields,
        "sections": sections,
        "workbook_values": workbook_values,
        "sheet_results": sheet_results,
        "preview_meta": {
            "sheet_result_field_count": len(sheet_result_fields),
            "dependency_resolution_order": cross_sheet_resolver.resolution_order,
        },
        "rows": rows,
    }

def save_form_sections(form_version_id, sections_list, user_id):
    if sections_list is None:
        return {}

    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")

    seen_codes = set()
    active_sections_by_code = {
        section.code: section
        for section in FormSection.query.filter_by(form_version_id=form_version_id, is_deleted=False).all()
    }
    saved_sections = {}

    for idx, section_data in enumerate(sections_list):
        section_id = section_data.get("id")
        name = (section_data.get("name") or "").strip()
        code = (section_data.get("code") or "").strip().lower().replace(" ", "_")
        layout_type = (section_data.get("layout_type") or "monthly_table").strip()
        description = (section_data.get("description") or "").strip() or None
        display_order = section_data.get("display_order") or idx + 1

        if not name:
            raise ValueError("Section name is required.")
        if not code:
            raise ValueError("Section code is required.")
        if code in seen_codes:
            raise ValueError(f"Duplicate section code '{code}' found in form sections.")
        if layout_type not in ALLOWED_SECTION_LAYOUT_TYPES:
            raise ValueError(f"Unsupported section layout type '{layout_type}'.")

        seen_codes.add(code)
        section = None
        if section_id:
            section = FormSection.query.filter_by(
                id=section_id,
                form_version_id=form_version_id,
                is_deleted=False,
            ).one_or_none()
        if not section:
            section = active_sections_by_code.get(code)
        if not section:
            section = FormSection(
                form_id=form_version.form_id,
                form_version_id=form_version_id,
                name=name,
                code=code,
                layout_type=layout_type,
                display_order=display_order,
                description=description,
                created_by=user_id,
                updated_by=user_id,
            )
            db.session.add(section)
            db.session.flush()
        else:
            section.name = name
            section.layout_type = layout_type
            section.display_order = display_order
            section.description = description
            section.updated_by = user_id

        saved_sections[code] = section

    saved_ids = {section.id for section in saved_sections.values()}
    for section in active_sections_by_code.values():
        if section.id not in saved_ids:
            section.is_deleted = True
            section.deleted_by = user_id
            section.deleted_at = datetime.now(timezone.utc)
            section.delete_reason = "Removed from form draft"

    db.session.flush()
    return saved_sections

def normalize_calculated_field_config(field_type, field_config, frequency):
    """
    "under_input_column" (a per-field FY total attached to one source field
    via a manual SUM_MONTHS formula) is legacy-only as of the automatic FY
    total feature -- every monthly numeric field now gets one synthesized
    for free (see SUBMIT.synthesize_automatic_fy_totals), so the Sheet
    Builder UI no longer offers it as a creatable Calculation Placement.
    A field that already has it (from before this change) keeps working
    exactly as before -- normalize_calculated_field_config still recognizes
    and preserves it, this function just never assigns it to a field that
    doesn't already have it. "below_monthly_table" (a genuine multi-field
    combined total needing a real custom formula) is unaffected and remains
    the only annual-result placement the UI can create going forward.
    """
    config = dict(field_config or {})
    normalized_type = (field_type or "").strip().lower()
    normalized_frequency = (frequency or "monthly").strip().lower()

    if normalized_type != "calculated":
        return config, normalized_frequency

    is_annual_result = (
        config.get("field_scope") == "annual_result"
        or config.get("result_role") in ("aggregate_result", "formula_result")
        or config.get("display_region") in ("below_monthly_table", "under_input_column")
    )

    if is_annual_result:
        normalized_frequency = "annual"
        config["field_scope"] = "annual_result"
        config["result_role"] = "aggregate_result"
        if config.get("display_region") != "under_input_column":
            config["display_region"] = "below_monthly_table"
        # blank_policy is intentionally left untouched here -- no UI has ever
        # offered a way to choose it deliberately, so a field with no
        # persisted blank_policy value just takes SUBMIT's DEFAULT_AGGREGATE_
        # BLANK_POLICY ("partial") at read time. This used to unconditionally
        # inject "strict" onto every annual-result field, which is exactly
        # the leftover scripts/fix_blank_policy_default.py cleans up -- don't
        # reintroduce it here.
        config["is_required"] = False
        config["remarks_required"] = False
        config["proof_required"] = False
    else:
        normalized_frequency = "monthly"
        config.setdefault("field_scope", "monthly")
        config.setdefault("result_role", "monthly_calculated")
        config.setdefault("display_region", "monthly_table")
        config.pop("blank_policy", None)

    return config, normalized_frequency

def save_form_draft_fields(form_version_id, fields_list, user_id, sections_list=None):
    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")
    if form_version.status != "Draft":
        raise ValueError("Only Draft versions can be modified.")

    section_map = save_form_sections(form_version_id, sections_list, user_id)
    if sections_list is None:
        section_map = {
            section.code: section
            for section in FormSection.query.filter_by(form_version_id=form_version_id, is_deleted=False).all()
        }
        
    # Check for duplicate field codes in the input list
    seen_codes = set()
    for f_data in fields_list:
        code = f_data.get("field_code")
        if code:
            code_strip = code.strip()
            if code_strip in seen_codes:
                raise ValueError(f"Duplicate field code '{code_strip}' found in form fields.")
            seen_codes.add(code_strip)

    # Fields omitted from this payload are about to be soft-deleted below --
    # block up front, before any mutation, if a published Formula still
    # references any of them. Checked as one pass over every omitted field so
    # a batch save is all-or-nothing: either the whole draft saves, or it
    # fails with every blocked field listed, never a silent partial save.
    present_codes = {f.get("field_code") for f in fields_list if f.get("field_code")}
    all_fields = Field.query.filter_by(form_id=form_version.form_id, is_deleted=False).all()
    fields_to_remove = [f for f in all_fields if f.field_code not in present_codes]
    blocked = []
    for f in fields_to_remove:
        referencing_formulas = _formulas_referencing_field(f)
        if referencing_formulas:
            blocked.append((f.field_code, referencing_formulas))
    if blocked:
        raise ValueError(_blocked_field_removal_message("Cannot save draft", blocked))

    # Soft-delete existing field_versions for this form_version_id instead of hard-deleting
    existing_fvs = FieldVersion.query.filter_by(form_version_id=form_version_id, is_deleted=False).all()
    for fv in existing_fvs:
        fv.is_deleted = True
        fv.deleted_by = user_id
        fv.deleted_at = datetime.now(timezone.utc)
        fv.delete_reason = "Overwritten by new draft save"

    # Soft-delete fields that are no longer present
    for f in fields_to_remove:
        f.is_deleted = True
        f.deleted_by = user_id
        f.deleted_at = datetime.now(timezone.utc)
        f.delete_reason = "Removed from form draft"

    db.session.flush()
    
    # Insert new field versions
    for idx, f_data in enumerate(fields_list):
        field_code = f_data.get("field_code")
        field_name = f_data.get("field_name")
        field_type = f_data.get("field_type")
        field_config = f_data.get("field_config", {})
        display_order = f_data.get("display_order", idx + 1)
        frequency = (f_data.get("frequency") or "monthly").strip()
        section_id = f_data.get("section_id")
        section_code = (f_data.get("section_code") or "").strip()
        
        if not field_code or not field_code.strip():
            raise ValueError("Field code is required.")
        if not field_name or not field_name.strip():
            raise ValueError("Field name is required.")
        if not field_type or not field_type.strip():
            raise ValueError("Field type is required.")
        field_config, frequency = normalize_calculated_field_config(field_type, field_config, frequency)
        if frequency not in ALLOWED_FIELD_FREQUENCIES:
            raise ValueError(f"Unsupported field frequency '{frequency}'.")

        section = None
        if section_code:
            section = section_map.get(section_code)
            if not section:
                raise ValueError(f"Field '{field_code}' references unknown section '{section_code}'.")
        elif section_id:
            section = FormSection.query.filter_by(
                id=section_id,
                form_version_id=form_version_id,
                is_deleted=False,
            ).one_or_none()
            if not section:
                raise ValueError(f"Field '{field_code}' references an invalid section.")
            
        # Find or create Field row
        field = Field.query.filter_by(form_id=form_version.form_id, field_code=field_code, is_deleted=False).first()
        if not field:
            field = Field(
                form_id=form_version.form_id,
                field_code=field_code.strip(),
                display_order=display_order,
                created_by=user_id,
                updated_by=user_id
            )
            db.session.add(field)
            db.session.flush()
        else:
            field.display_order = display_order
            field.updated_by = user_id
            
        # Get max version number for field
        max_ver = db.session.query(db.func.max(FieldVersion.version_number)).filter_by(
            field_id=field.id
        ).scalar() or 0
        
        fv = FieldVersion(
            field_id=field.id,
            version_number=max_ver + 1,
            field_name=field_name.strip(),
            field_type=field_type.strip(),
            field_config=field_config,
            form_version_id=form_version_id,
            section_id=section.id if section else None,
            frequency=frequency,
            created_by=user_id
        )
        db.session.add(fv)
        db.session.flush()
        
        # Link field
        field.current_version_id = fv.id
        
    db.session.flush()
    return True

def calculated_field_formula_swaps(old_form_version_id, new_form_version_id):
    """
    Compares calculated-field Formula identities between two form versions of
    the same form and returns every field that swapped to a genuinely
    different Formula (not just a new version of the same one, and not a
    field that's newly calculated or newly given its first formula -- both
    sides must already reference a formula). Read-only: never mutates
    anything, so it's safe to call before a version is actually published
    (see SUBMIT.preview_formula_swap_impact) as well as right after
    (publish_form_version's own trigger).

    Returns {field_code: {"field_name": str, "old_formula_id": int, "new_formula_id": int}}.
    """
    if not old_form_version_id or not new_form_version_id:
        return {}

    old_fields = get_form_version_fields(old_form_version_id)
    new_fields = get_form_version_fields(new_form_version_id)

    referenced_version_ids = {
        (fv.field_config or {}).get("formula_version_id")
        for fv, _f in (old_fields + new_fields)
        if fv.field_type == "calculated" and (fv.field_config or {}).get("formula_version_id")
    }
    formula_id_by_version_id = {
        v.id: v.formula_id
        for v in FormulaVersion.query.filter(FormulaVersion.id.in_(referenced_version_ids or [0])).all()
    }

    old_formula_id_by_code = {}
    for ofv, of in old_fields:
        if ofv.field_type != "calculated":
            continue
        old_fv_id = (ofv.field_config or {}).get("formula_version_id")
        if old_fv_id:
            old_formula_id_by_code[of.field_code] = formula_id_by_version_id.get(old_fv_id)

    swaps = {}
    for nfv, nf in new_fields:
        if nfv.field_type != "calculated":
            continue
        old_formula_id = old_formula_id_by_code.get(nf.field_code)
        if old_formula_id is None:
            continue
        new_fv_id = (nfv.field_config or {}).get("formula_version_id")
        new_formula_id = formula_id_by_version_id.get(new_fv_id) if new_fv_id else None
        if new_formula_id is not None and new_formula_id != old_formula_id:
            swaps[nf.field_code] = {
                "field_name": nfv.field_name,
                "old_formula_id": old_formula_id,
                "new_formula_id": new_formula_id,
            }
    return swaps


def publish_form_version(form_version_id, user_id):
    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")
    if form_version.status != "Draft":
        raise ValueError("Only Draft versions can be published.")
        
    fields = get_form_version_fields(form_version_id)
    if not fields:
        raise ValueError("Cannot publish an empty form. Add fields first.")
        
    # Validate fields config references
    for fv, f in fields:
        field_config = fv.field_config or {}
        
        # 1. Check dropdown has local field-level options
        if fv.field_type == "dropdown":
            if not local_dropdown_options(field_config):
                raise ValueError(f'Dropdown field "{fv.field_name}" must have at least one option.')
                
        # 2. Check calculated fields reference published formulas
        elif fv.field_type == "calculated":
            formula_ver_id = field_config.get("formula_version_id")
            if not formula_ver_id:
                raise ValueError(f"Calculated field '{f.field_code}' must reference a formula version.")
            formula_ver = FormulaVersion.query.get(formula_ver_id)
            if not formula_ver or formula_ver.published_at is None:
                raise ValueError(f"Calculated field '{f.field_code}' references a non-published formula version.")
                
    # Close previous published version
    prev_published = FormVersion.query.filter_by(
        form_id=form_version.form_id,
        status="Published"
    ).filter(FormVersion.id != form_version_id).first()

    # Diff against the version being replaced *before* archiving it, so a
    # genuine formula swap (a field re-pointed at a different Formula, not
    # just a new version of the same one) can be detected once this version
    # goes live.
    formula_swaps = (
        calculated_field_formula_swaps(prev_published.id, form_version_id)
        if prev_published else {}
    )

    if prev_published:
        prev_published.status = "Archived"

    # Mark Published
    form_version.status = "Published"
    form_version.published_at = datetime.now(timezone.utc)
    form_version.published_by = user_id

    form = get_form(form_version.form_id)
    form.current_version_id = form_version_id
    form.updated_by = user_id

    # A calculated field's formula is a live, in-place field_config edit (see
    # FRMULA.create_new_formula_draft -- formulas themselves are never edited
    # in place, but which Formula a field points at can change). If any
    # calculated field just swapped to a genuinely different Formula identity,
    # every open submission on this sheet needs to either be recalculated
    # against the new formula or, if already approved and locked, flagged for
    # review instead of silently recomputed.
    if formula_swaps:
        from app.modules.SUBMIT.service import recalc_or_flag_submissions_for_formula_swap
        recalc_or_flag_submissions_for_formula_swap(form.id, user_id)

    return form_version

def create_new_form_version_draft(form_id, user_id):
    form = get_form(form_id)
    if not form:
        raise ValueError("Form not found.")
        
    pending_draft = FormVersion.query.filter_by(
        form_id=form_id,
        status="Draft"
    ).first()
    if pending_draft:
        return pending_draft
        
    max_ver = db.session.query(db.func.max(FormVersion.version_number)).filter_by(
        form_id=form_id
    ).scalar() or 0
    
    new_version = FormVersion(
        form_id=form_id,
        version_number=max_ver + 1,
        status="Draft",
        created_by=user_id
    )
    db.session.add(new_version)
    db.session.flush()
    
    # Copy fields (and sections) from previous version
    latest_ver = FormVersion.query.filter_by(
        form_id=form_id
    ).filter(FormVersion.id != new_version.id).order_by(FormVersion.version_number.desc()).first()

    if latest_ver:
        # Clone sections into version-scoped rows first, so editing them on this
        # draft (rename, reorder, remove) never mutates the previous version's rows.
        prev_sections = FormSection.query.filter_by(
            form_version_id=latest_ver.id, is_deleted=False
        ).all()
        section_id_map = {}
        for prev_section in prev_sections:
            new_section = FormSection(
                form_id=form_id,
                form_version_id=new_version.id,
                name=prev_section.name,
                code=prev_section.code,
                layout_type=prev_section.layout_type,
                display_order=prev_section.display_order,
                description=prev_section.description,
                created_by=user_id,
                updated_by=user_id,
            )
            db.session.add(new_section)
            db.session.flush()
            section_id_map[prev_section.id] = new_section.id

        prev_fields = get_form_version_fields(latest_ver.id)
        for prev_fv, prev_f in prev_fields:
            # Create a new FieldVersion pointing to the new FormVersion
            # Get max version number for field
            max_fv_ver = db.session.query(db.func.max(FieldVersion.version_number)).filter_by(
                field_id=prev_f.id
            ).scalar() or 0

            new_fv = FieldVersion(
                field_id=prev_f.id,
                version_number=max_fv_ver + 1,
                field_name=prev_fv.field_name,
                field_type=prev_fv.field_type,
                field_config=prev_fv.field_config or {},
                form_version_id=new_version.id,
                section_id=section_id_map.get(prev_fv.section_id),
                frequency=prev_fv.frequency or "monthly",
                created_by=user_id
            )
            db.session.add(new_fv)
            db.session.flush()

            # Update field link
            prev_f.current_version_id = new_fv.id

    db.session.flush()
    return new_version


# ─────────────────────────────────────────────────────────────────────────
# Sheet/field replication: bulk field copy (Feature 1) and full sheet copy
# (Feature 2) share the same clone_fields_with_formulas() core -- every copy
# here is a fully independent, one-time snapshot (new Field/FieldVersion/
# Formula/FormulaVersion rows), never a linked/synced reference back to the
# original. Neither feature touches submitted data (SubmissionValue/
# WorkbookFieldValue) -- copying only ever creates new configuration rows.
# ─────────────────────────────────────────────────────────────────────────

def list_sheets_for_picker():
    """
    Lightweight sheet list for the cross-sheet/cross-workbook copy pickers --
    one row per (Form, Workbook) attachment, plus a row for any form with no
    workbook attachment at all (workbook_id/workbook_name null), so every
    possible copy destination is selectable. Excludes soft-deleted forms.
    Deliberately separate from FORMBLD's own "/api" list endpoint (which
    returns a much heavier payload per sheet and has no workbook join at
    all) rather than overloading that endpoint's existing contract.
    """
    import json as _json
    from app.modules.WKBK.model import Workbook, WorkbookForm

    forms = Form.query.filter_by(is_deleted=False).order_by(Form.name.asc()).all()

    attachments = {}
    rows = (
        WorkbookForm.query.with_entities(WorkbookForm, Workbook)
        .join(Workbook, Workbook.id == WorkbookForm.workbook_id)
        .filter(Workbook.is_active.is_(True))
        .all()
    )
    for wf, wb in rows:
        attachments.setdefault(wf.form_id, []).append({"id": wb.id, "name": wb.name})

    result = []
    for form in forms:
        display_name = form.name
        if form.description and form.description.startswith("{"):
            try:
                display_name = _json.loads(form.description).get("display_name") or form.name
            except Exception:
                pass

        workbooks = attachments.get(form.id, [])
        if not workbooks:
            result.append({
                "form_id": form.id,
                "name": display_name,
                "code": form.code,
                "workbook_id": None,
                "workbook_name": None,
            })
        else:
            for wb in workbooks:
                result.append({
                    "form_id": form.id,
                    "name": display_name,
                    "code": form.code,
                    "workbook_id": wb["id"],
                    "workbook_name": wb["name"],
                })
    return result


def _next_available_field_code(base_code, used_codes):
    """Generates a `<base>_copy`, `<base>_copy_2`, ... field_code not already
    in `used_codes` (mutated in place to reserve it, so a caller allocating
    several codes in one batch never hands out the same one twice)."""
    base = re.sub(r"[^a-z0-9_]+", "_", (base_code or "field").strip().lower()).strip("_") or "field"
    candidate = f"{base}_copy"
    suffix = 2
    while candidate in used_codes:
        candidate = f"{base}_copy_{suffix}"
        suffix += 1
    used_codes.add(candidate)
    return candidate


def _next_available_formula_code(base_code):
    """Formula.code is globally unique (uq_formula_code) -- never reuse the
    original code, generate a fresh `<base>_copy` variant instead."""
    from app.modules.FRMULA.model import Formula

    base = re.sub(r"[^a-z0-9_-]+", "_", (base_code or "formula").strip().lower()).strip("_") or "formula"
    candidate = f"{base}_copy"
    suffix = 2
    while Formula.query.filter_by(code=candidate).first() is not None:
        candidate = f"{base}_copy_{suffix}"
        suffix += 1
    return candidate


def _next_available_form_code(base_code):
    base = (base_code or "SHEET").strip() or "SHEET"
    candidate = f"{base}_COPY"
    suffix = 2
    while get_form_by_code(candidate) is not None:
        candidate = f"{base}_COPY{suffix}"
        suffix += 1
    return candidate


def _remap_formula_tokens(source_form_id, tokens, code_map):
    """
    Remaps every token key that is itself a field_code belonging to
    source_form_id, via code_map (old field_code -> new field_code). Tokens
    that aren't a field_code on the source sheet at all (value-set entry
    codes -- global constants, not sheet-scoped, see FRMULA.publish_formula_
    version's own tokens cross-check) pass through unchanged. A token that
    IS a field_code on the source sheet but has no entry in code_map means
    that field wasn't part of this copy batch -- that's an error, not
    something to silently drop, since the copied formula would otherwise
    reference a field_code that doesn't exist on the destination sheet.
    """
    if not tokens:
        return {}

    source_field_codes = {
        f.field_code for f in Field.query.filter_by(form_id=source_form_id, is_deleted=False).all()
    }
    remapped = {}
    for token_key, token_value in tokens.items():
        if token_key in source_field_codes:
            if token_key not in code_map:
                raise ValueError(
                    f"Cannot copy: formula references field '{token_key}', which "
                    "is not part of this copy. Include it in the selection or "
                    "copy the whole sheet instead."
                )
            remapped[code_map[token_key]] = token_value
        else:
            remapped[token_key] = token_value
    return remapped


def _remap_formula_expression(expression, code_map):
    """
    Textually substitutes every old field_code referenced in `expression`
    with its new counterpart, in a single regex pass over the original
    string (not a sequential per-code substitution loop) so a freshly
    generated new_code can never itself be re-matched by a different old_code
    later in the same operation. \\b word-boundary matching means a code is
    never partially matched inside a longer identifier that happens to share
    a prefix/suffix (e.g. "kwh" inside "kwh_total").
    """
    if not expression or not code_map:
        return expression
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(code) for code in sorted(code_map.keys(), key=len, reverse=True)) + r")\b"
    )
    return pattern.sub(lambda m: code_map[m.group(0)], expression)


def _clone_sections(source_form_version_id, destination_form, destination_form_version, user_id):
    """
    Clones every active FormSection from source_form_version_id onto
    destination_form_version, same field-by-field copy create_new_form_
    version_draft already uses to carry sections into a new version of the
    *same* form -- just re-parented onto a different destination form.
    Returns {old_section_id: new_section_id}.
    """
    source_sections = (
        FormSection.query.filter_by(form_version_id=source_form_version_id, is_deleted=False)
        .order_by(FormSection.display_order.asc(), FormSection.id.asc())
        .all()
    )
    section_id_map = {}
    for section in source_sections:
        new_section = FormSection(
            form_id=destination_form.id,
            form_version_id=destination_form_version.id,
            name=section.name,
            code=section.code,
            layout_type=section.layout_type,
            display_order=section.display_order,
            description=section.description,
            created_by=user_id,
            updated_by=user_id,
        )
        db.session.add(new_section)
        db.session.flush()
        section_id_map[section.id] = new_section.id
    return section_id_map


def clone_fields_with_formulas(source_form_id, field_rows, destination_form, destination_form_version, user_id):
    """
    Shared clone core for both bulk field copy and full sheet copy.

    field_rows: list of (FieldVersion, Field) tuples for the source fields to
    clone -- either a hand-picked subset (bulk field copy) or every active
    field on a version (full sheet copy).

    Clones each into a brand-new Field + FieldVersion on
    destination_form_version, with a freshly generated field_code unique
    within destination_form (existing uq_fields_code_per_form constraint),
    appended after any fields the destination sheet already has. If a cloned
    field is calculated and its field_config["formula_version_id"] belongs to
    a Formula owned by source_form_id, clones that Formula too (new unique
    code, form_id = destination_form.id) with expression/tokens remapped to
    the new field_codes via the mapping built in this same call, and
    publishes the new FormulaVersion immediately (never left as a draft).
    Two cloned fields that both reference the same source FormulaVersion
    share one cloned destination Formula, same as the source relationship.

    Formula.form_id is nullable -- formulas created before that column
    existed have no reliable owning-sheet attribution (see the model's own
    comment) and simply have form_id = None. Mirroring publish_formula_
    version's own "fall back to the old unscoped check" reasoning for these:
    a null-form_id formula is treated as a legacy same-sheet formula and its
    tokens are remapped the same as an explicitly-scoped one, raising the
    same "token doesn't resolve" error if it genuinely isn't. A formula whose
    form_id IS set but doesn't match source_form_id is a genuine cross-sheet
    reference -- which shouldn't be possible under the current formula-
    scoping rules -- and raises rather than silently copying a broken
    reference forward onto the destination sheet.

    Section resolution mirrors save_form_draft_fields's own lookup-by-code
    against the destination version's sections, except a source field whose
    section has no code match on the destination sheet is dropped to "no
    section" here instead of raising -- there's no interactive step in an
    automated copy to fix a missing section first. Full sheet copy avoids
    this path in practice by cloning every section (see _clone_sections)
    before calling this function, so a code match always exists there.

    Returns the list of newly created Field rows, in the same order as
    field_rows.
    """
    from app.modules.FRMULA.model import Formula, FormulaVersion

    used_codes = {
        f.field_code for f in Field.query.filter_by(form_id=destination_form.id, is_deleted=False).all()
    }

    code_map = {}
    plan = []
    for fv, f in field_rows:
        new_code = _next_available_field_code(f.field_code, used_codes)
        code_map[f.field_code] = new_code
        plan.append((f, fv, new_code))

    next_display_order = (
        db.session.query(db.func.max(Field.display_order))
        .filter(Field.form_id == destination_form.id, Field.is_deleted.is_(False))
        .scalar()
    ) or 0

    formula_clone_cache = {}
    new_fields = []

    for f, fv, new_code in plan:
        section_id = None
        if fv.section_id:
            source_section = FormSection.query.filter_by(id=fv.section_id, is_deleted=False).one_or_none()
            if source_section:
                dest_section = FormSection.query.filter_by(
                    form_version_id=destination_form_version.id,
                    code=source_section.code,
                    is_deleted=False,
                ).one_or_none()
                section_id = dest_section.id if dest_section else None

        field_config = dict(fv.field_config or {})

        if fv.field_type == "calculated" and field_config.get("formula_version_id"):
            old_version_id = field_config["formula_version_id"]
            if old_version_id in formula_clone_cache:
                new_version = formula_clone_cache[old_version_id]
                field_config["formula_version_id"] = new_version.id
                field_config["expression"] = new_version.expression
                field_config["tokens"] = new_version.tokens
            else:
                old_version = FormulaVersion.query.get(old_version_id)
                old_formula = (
                    Formula.query.filter_by(id=old_version.formula_id, is_deleted=False).one_or_none()
                    if old_version else None
                )
                if old_formula and old_formula.form_id is not None and old_formula.form_id != source_form_id:
                    raise ValueError(
                        f"Cannot copy: field '{f.field_code}' is calculated from "
                        f"formula '{old_formula.code}', which belongs to a "
                        "different sheet. Formulas are never shared across "
                        "sheets -- this points to a data integrity issue outside "
                        "the scope of this copy."
                    )
                if old_version and old_formula:
                    new_tokens = _remap_formula_tokens(source_form_id, old_version.tokens, code_map)
                    new_expression = _remap_formula_expression(old_version.expression, code_map)
                    new_formula_code = _next_available_formula_code(old_formula.code)

                    new_formula = Formula(
                        name=old_formula.name,
                        code=new_formula_code,
                        form_id=destination_form.id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                    db.session.add(new_formula)
                    db.session.flush()

                    new_version = FormulaVersion(
                        formula_id=new_formula.id,
                        version_number=1,
                        expression=new_expression,
                        tokens=new_tokens,
                        published_at=datetime.now(timezone.utc),
                        published_by=user_id,
                        created_by=user_id,
                    )
                    db.session.add(new_version)
                    db.session.flush()

                    new_formula.current_version_id = new_version.id
                    new_formula.updated_by = user_id

                    formula_clone_cache[old_version_id] = new_version
                    field_config["formula_version_id"] = new_version.id
                    field_config["expression"] = new_expression
                    field_config["tokens"] = new_tokens
                # else: formula_version_id points at a Formula/FormulaVersion
                # that no longer exists (or was soft-deleted) -- field_config's
                # formula_version_id/expression/tokens are left exactly as
                # copied from the source field below, same as before.

        next_display_order += 1
        new_field = Field(
            form_id=destination_form.id,
            field_code=new_code,
            display_order=next_display_order,
            created_by=user_id,
            updated_by=user_id,
        )
        db.session.add(new_field)
        db.session.flush()

        new_field_version = FieldVersion(
            field_id=new_field.id,
            version_number=1,
            field_name=fv.field_name,
            field_type=fv.field_type,
            field_config=field_config,
            form_version_id=destination_form_version.id,
            section_id=section_id,
            frequency=fv.frequency or "monthly",
            created_by=user_id,
        )
        db.session.add(new_field_version)
        db.session.flush()

        new_field.current_version_id = new_field_version.id
        new_fields.append(new_field)

    db.session.flush()
    return new_fields


def copy_fields_to_sheet(source_version_id, field_codes, destination_form_id, user_id):
    """
    Feature 1: bulk field copy. Clones the given field_codes from
    source_version_id onto destination_form_id's current draft version --
    creating one via create_new_form_version_draft (reused, not
    reimplemented) if the destination's current version isn't already a
    Draft. See clone_fields_with_formulas for the clone + formula-remap
    logic shared with copy_sheet_to_workbook (Feature 2).
    """
    source_version = FormVersion.query.get(source_version_id)
    if not source_version:
        raise ValueError("Source sheet version not found.")

    if not field_codes:
        raise ValueError("Select at least one field to copy.")

    destination_form = get_form(destination_form_id)
    if not destination_form:
        raise ValueError("Destination sheet not found.")

    all_source_fields = get_form_version_fields(source_version_id)
    by_code = {f.field_code: (fv, f) for fv, f in all_source_fields}
    missing = [code for code in field_codes if code not in by_code]
    if missing:
        raise ValueError(f"Field(s) not found on the source sheet: {', '.join(missing)}.")

    # Preserve the fields' own relative order in the destination sheet,
    # regardless of the order field_codes were passed in (e.g. Set-insertion
    # order from a multi-select UI).
    field_rows = sorted((by_code[code] for code in field_codes), key=lambda pair: pair[1].display_order or 0)

    destination_version = create_new_form_version_draft(destination_form.id, user_id)

    new_fields = clone_fields_with_formulas(
        source_version.form_id, field_rows, destination_form, destination_version, user_id,
    )
    return destination_form, destination_version, new_fields


def copy_sheet_to_workbook(source_form_id, destination_workbook_id, user_id):
    """
    Feature 2: full sheet copy. Creates an entirely independent new Form (new
    unique code) + FormVersion (status always Draft, regardless of the
    source's current status -- a deliberate product decision, not
    configurable or inherited), clones every Section (see _clone_sections)
    and every active Field/FieldVersion (with formulas remapped, see
    clone_fields_with_formulas) from the source form's most recent version,
    and attaches the new Form to destination_workbook_id via one new
    WorkbookForm row (add_sheet_to_workbook, reused). The source Form's own
    WorkbookForm rows are never touched.
    """
    import json as _json
    from app.modules.WKBK.service import add_sheet_to_workbook

    source_form = get_form(source_form_id)
    if not source_form:
        raise ValueError("Sheet not found.")

    source_version = (
        FormVersion.query.filter_by(form_id=source_form.id)
        .order_by(FormVersion.version_number.desc())
        .first()
    )
    if not source_version:
        raise ValueError("Sheet has no version to copy.")

    new_code = _next_available_form_code(source_form.code)
    new_name = f"{source_form.name} (Copy)"

    new_description = source_form.description
    if source_form.description and source_form.description.startswith("{"):
        try:
            parsed = _json.loads(source_form.description)
            parsed["display_name"] = f"{parsed.get('display_name') or source_form.name} (Copy)"
            new_description = _json.dumps(parsed)
        except Exception:
            pass

    new_form = Form(
        name=new_name,
        code=new_code,
        description=new_description,
        created_by=user_id,
        updated_by=user_id,
    )
    db.session.add(new_form)
    db.session.flush()

    new_version = FormVersion(
        form_id=new_form.id,
        version_number=1,
        status="Draft",
        created_by=user_id,
    )
    db.session.add(new_version)
    db.session.flush()

    _clone_sections(source_version.id, new_form, new_version, user_id)

    source_fields = get_form_version_fields(source_version.id)
    clone_fields_with_formulas(source_form.id, source_fields, new_form, new_version, user_id)

    workbook_form = add_sheet_to_workbook(
        workbook_id=destination_workbook_id, form_id=new_form.id, sheet_label=None,
    )

    return new_form, new_version, workbook_form
