from app.modules.FORMBLD.model import Field, FieldVersion


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

def get_form_version(version_id):
    return FormVersion.query.get(version_id)

def get_form_sections(form_id):
    return (
        FormSection.query.filter_by(form_id=form_id, is_deleted=False)
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

def compose_preview_workbook_context(form_version_id):
    version = get_form_version(form_version_id)
    if not version:
        raise ValueError("Form version not found.")

    form = get_form(version.form_id)
    if not form:
        raise ValueError("Form not found.")

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

    sections = [{
        "id": section.id,
        "name": section.name,
        "code": section.code,
        "layout_type": section.layout_type,
        "display_order": section.display_order,
        "description": section.description or "",
    } for section in get_form_sections(form.id)]

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
        "fields": fields,
        "sections": sections,
        "workbook_values": workbook_values,
        "rows": rows,
    }

def save_form_sections(form_id, sections_list, user_id):
    if sections_list is None:
        return {}

    seen_codes = set()
    active_sections_by_code = {
        section.code: section
        for section in FormSection.query.filter_by(form_id=form_id, is_deleted=False).all()
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
                form_id=form_id,
                is_deleted=False,
            ).one_or_none()
        if not section:
            section = active_sections_by_code.get(code)
        if not section:
            section = FormSection(
                form_id=form_id,
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

def save_form_draft_fields(form_version_id, fields_list, user_id, sections_list=None):
    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")
    if form_version.status != "Draft":
        raise ValueError("Only Draft versions can be modified.")

    section_map = save_form_sections(form_version.form_id, sections_list, user_id)
    if sections_list is None:
        section_map = {
            section.code: section
            for section in FormSection.query.filter_by(form_id=form_version.form_id, is_deleted=False).all()
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

    # Soft-delete existing field_versions for this form_version_id instead of hard-deleting
    existing_fvs = FieldVersion.query.filter_by(form_version_id=form_version_id, is_deleted=False).all()
    for fv in existing_fvs:
        fv.is_deleted = True
        fv.deleted_by = user_id
        fv.deleted_at = datetime.now(timezone.utc)
        fv.delete_reason = "Overwritten by new draft save"
        
    # Soft-delete fields that are no longer present
    present_codes = {f.get("field_code") for f in fields_list if f.get("field_code")}
    all_fields = Field.query.filter_by(form_id=form_version.form_id, is_deleted=False).all()
    for f in all_fields:
        if f.field_code not in present_codes:
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
                form_id=form_version.form_id,
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

def publish_form_version(form_version_id, user_id):
    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")
    if form_version.status != "Draft":
        raise ValueError("Only Draft versions can be published.")
        
    form = get_form(form_version.form_id)
    import json
    parsed_desc = {}
    if form and form.description and form.description.startswith("{"):
        try:
            parsed_desc = json.loads(form.description)
        except Exception:
            pass
            
    if not parsed_desc.get("sites"):
        raise ValueError("Site applicability must be assigned before publishing.")

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
    
    if prev_published:
        prev_published.status = "Archived"
        
    # Mark Published
    form_version.status = "Published"
    form_version.published_at = datetime.now(timezone.utc)
    form_version.published_by = user_id
    
    form = get_form(form_version.form_id)
    form.current_version_id = form_version_id
    form.updated_by = user_id
    
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
    
    # Copy fields from previous version
    latest_ver = FormVersion.query.filter_by(
        form_id=form_id
    ).filter(FormVersion.id != new_version.id).order_by(FormVersion.version_number.desc()).first()
    
    if latest_ver:
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
                section_id=prev_fv.section_id,
                frequency=prev_fv.frequency or "monthly",
                created_by=user_id
            )
            db.session.add(new_fv)
            db.session.flush()
            
            # Update field link
            prev_f.current_version_id = new_fv.id
            
    db.session.flush()
    return new_version
