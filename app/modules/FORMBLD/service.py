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
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.VALSET.model import ValueSetVersion
from app.modules.FRMULA.model import FormulaVersion

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

def save_form_draft_fields(form_version_id, fields_list, user_id):
    form_version = FormVersion.query.get(form_version_id)
    if not form_version:
        raise ValueError("Form version not found.")
    if form_version.status != "Draft":
        raise ValueError("Only Draft versions can be modified.")
        
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
        
        if not field_code or not field_code.strip():
            raise ValueError("Field code is required.")
        if not field_name or not field_name.strip():
            raise ValueError("Field name is required.")
        if not field_type or not field_type.strip():
            raise ValueError("Field type is required.")
            
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
        
    if not parsed_desc.get("workflow_id"):
        raise ValueError("An approval workflow must be assigned before publishing.")

    fields = get_form_version_fields(form_version_id)
    if not fields:
        raise ValueError("Cannot publish an empty form. Add fields first.")
        
    # Validate fields config references
    for fv, f in fields:
        field_config = fv.field_config or {}
        
        # 1. Check dropdown references Approved value sets
        if fv.field_type == "dropdown":
            vs_ver_id = field_config.get("value_set_version_id")
            if not vs_ver_id:
                raise ValueError(f"Dropdown field '{f.field_code}' must reference a value set version.")
            vs_ver = ValueSetVersion.query.get(vs_ver_id)
            if not vs_ver or vs_ver.status != "Approved":
                raise ValueError(f"Dropdown field '{f.field_code}' references a non-approved value set version.")
                
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
        raise ValueError("A Draft version already exists. Work on that version first.")
        
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
                created_by=user_id
            )
            db.session.add(new_fv)
            db.session.flush()
            
            # Update field link
            prev_f.current_version_id = new_fv.id
            
    db.session.flush()
    return new_version
