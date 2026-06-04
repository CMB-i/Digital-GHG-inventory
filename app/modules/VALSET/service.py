from datetime import datetime, date, timezone
from app.database import db
from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry

def list_value_sets():
    return ValueSet.query.filter_by(is_deleted=False).all()

def get_value_set(value_set_id):
    return ValueSet.query.filter_by(id=value_set_id, is_deleted=False).one_or_none()

def get_value_set_by_code(code):
    return ValueSet.query.filter_by(code=code, is_deleted=False).one_or_none()

def create_value_set(name, code, description, user_id):
    if not name or not name.strip():
        raise ValueError("Value set name is required.")
    if not code or not code.strip():
        raise ValueError("Value set code is required.")
    
    # Check duplicate code
    existing = get_value_set_by_code(code)
    if existing:
        raise ValueError(f"Value set with code '{code}' already exists.")
        
    value_set = ValueSet(
        name=name.strip(),
        code=code.strip(),
        description=description,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(value_set)
    db.session.flush()
    
    # Create initial version
    version = ValueSetVersion(
        value_set_id=value_set.id,
        version_number=1,
        status="Draft",
        effective_from=date.today(),
        created_by=user_id
    )
    db.session.add(version)
    db.session.flush()
    
    return value_set

def get_value_set_version(version_id):
    return ValueSetVersion.query.get(version_id)

def get_value_set_entries(version_id):
    return ValueSetEntry.query.filter_by(
        value_set_version_id=version_id,
        is_deleted=False
    ).order_by(ValueSetEntry.display_order.asc(), ValueSetEntry.id.asc()).all()

def add_or_update_entries(version_id, entries_list, user_id):
    version = get_value_set_version(version_id)
    if not version:
        raise ValueError("Value set version not found.")
    if version.status not in ("Draft", "Rejected"):
        raise ValueError("Cannot edit entries for a version that is not in Draft or Rejected status.")
        
    # Mark existing entries as deleted first
    existing_entries = ValueSetEntry.query.filter_by(
        value_set_version_id=version_id,
        is_deleted=False
    ).all()
    for entry in existing_entries:
        entry.is_deleted = True
        entry.deleted_by = user_id
        entry.deleted_at = datetime.now(timezone.utc)
        entry.delete_reason = "Overwritten during batch entry update"
    
    db.session.flush()
    
    # Insert new entries
    for idx, entry_data in enumerate(entries_list):
        entry_code = entry_data.get("entry_code")
        entry_label = entry_data.get("entry_label")
        display_order = entry_data.get("display_order", idx + 1)
        is_active = entry_data.get("is_active", True)
        
        if not entry_code or not entry_code.strip():
            raise ValueError("Entry code is required.")
        if not entry_label or not entry_label.strip():
            raise ValueError("Entry label is required.")
            
        entry = ValueSetEntry(
            value_set_version_id=version_id,
            entry_code=entry_code.strip(),
            entry_label=entry_label.strip(),
            display_order=display_order,
            is_active=is_active,
            created_by=user_id,
            updated_by=user_id
        )
        db.session.add(entry)
    
    db.session.flush()
    return get_value_set_entries(version_id)

def submit_value_set_version(version_id, user_id):
    version = get_value_set_version(version_id)
    if not version:
        raise ValueError("Value set version not found.")
    if version.status not in ("Draft", "Rejected"):
        raise ValueError("Only Draft or Rejected versions can be submitted.")
        
    # Check if there is at least one active entry
    entries = get_value_set_entries(version_id)
    active_entries = [e for e in entries if e.is_active]
    if not active_entries:
        raise ValueError("Cannot submit a value set version with no active entries.")
        
    version.status = "Submitted"
    version.submitted_by = user_id
    version.submitted_at = datetime.now(timezone.utc)
    return version

def approve_value_set_version(version_id, user_id):
    version = get_value_set_version(version_id)
    if not version:
        raise ValueError("Value set version not found.")
    if version.status != "Submitted":
        raise ValueError("Only Submitted versions can be approved.")
        
    # Self-approval check
    if version.submitted_by == user_id:
        raise ValueError("Approver cannot be the same user who submitted the value set version.")
        
    # Set status
    version.status = "Approved"
    version.approved_by = user_id
    version.approved_at = datetime.now(timezone.utc)
    
    # Update parent ValueSet current version
    value_set = get_value_set(version.value_set_id)
    if not value_set:
        raise ValueError("Parent value set not found.")
        
    # Close previously active version
    prev_approved_version = ValueSetVersion.query.filter_by(
        value_set_id=version.value_set_id,
        status="Approved"
    ).filter(ValueSetVersion.id != version_id).filter(ValueSetVersion.effective_to.is_(None)).one_or_none()
    
    if prev_approved_version:
        prev_approved_version.effective_to = date.today()
        
    value_set.current_version_id = version_id
    value_set.updated_by = user_id
    
    return version

def reject_value_set_version(version_id, user_id, reason):
    if not reason or not reason.strip():
        raise ValueError("Rejection reason is mandatory.")
        
    version = get_value_set_version(version_id)
    if not version:
        raise ValueError("Value set version not found.")
    if version.status != "Submitted":
        raise ValueError("Only Submitted versions can be rejected.")
        
    # Self-rejection check
    if version.submitted_by == user_id:
        raise ValueError("Approver cannot be the same user who submitted the value set version.")
        
    version.status = "Rejected"
    version.rejected_by = user_id
    version.rejected_at = datetime.now(timezone.utc)
    version.rejection_reason = reason.strip()
    return version

def create_new_draft_version(value_set_id, user_id):
    value_set = get_value_set(value_set_id)
    if not value_set:
        raise ValueError("Value set not found.")
        
    # Check if there is already a Draft or Submitted version
    pending_version = ValueSetVersion.query.filter(
        ValueSetVersion.value_set_id == value_set_id,
        ValueSetVersion.status.in_(["Draft", "Submitted"])
    ).first()
    if pending_version:
        raise ValueError(f"A version in {pending_version.status} state already exists. Work on that version first.")
        
    # Get latest version number
    max_ver = db.session.query(db.func.max(ValueSetVersion.version_number)).filter_by(
        value_set_id=value_set_id
    ).scalar() or 0
    
    new_version_num = max_ver + 1
    
    new_version = ValueSetVersion(
        value_set_id=value_set_id,
        version_number=new_version_num,
        status="Draft",
        effective_from=date.today(),
        created_by=user_id
    )
    db.session.add(new_version)
    db.session.flush()
    
    # Copy entries from previous approved/active version
    latest_approved = ValueSetVersion.query.filter_by(
        value_set_id=value_set_id,
        status="Approved"
    ).order_by(ValueSetVersion.version_number.desc()).first()
    
    # If no approved, copy from last version regardless of status
    source_version = latest_approved
    if not source_version:
        source_version = ValueSetVersion.query.filter_by(
            value_set_id=value_set_id
        ).filter(ValueSetVersion.id != new_version.id).order_by(ValueSetVersion.version_number.desc()).first()
        
    if source_version:
        entries = get_value_set_entries(source_version.id)
        for entry in entries:
            new_entry = ValueSetEntry(
                value_set_version_id=new_version.id,
                entry_code=entry.entry_code,
                entry_label=entry.entry_label,
                display_order=entry.display_order,
                is_active=entry.is_active,
                created_by=user_id,
                updated_by=user_id
            )
            db.session.add(new_entry)
            
    db.session.flush()
    return new_version

def delete_value_set(value_set_id, user_id, reason):
    if not reason or not reason.strip():
        raise ValueError("Delete reason is mandatory.")
        
    value_set = get_value_set(value_set_id)
    if not value_set:
        raise ValueError("Value set not found.")
        
    value_set.is_deleted = True
    value_set.deleted_by = user_id
    value_set.deleted_at = datetime.now(timezone.utc)
    value_set.delete_reason = reason.strip()
    return value_set
