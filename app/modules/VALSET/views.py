from flask import Blueprint, render_template, request, jsonify

from app.common.decorators import require_permission
from app.common.auth import current_user
from app.common.responses import success_response, error_response
from app.database import db
from app.modules.VALSET.service import (
    list_value_sets,
    get_value_set,
    create_value_set,
    get_value_set_version,
    get_value_set_entries,
    add_or_update_entries,
    submit_value_set_version,
    approve_value_set_version,
    reject_value_set_version,
    create_new_draft_version,
    delete_value_set
)
from app.modules.VALSET.model import ValueSetVersion
from app.modules.USRMGMT.model import User

MODULE_CODE = "VALSET"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("value_set", "view")
def index():
    return render_template("modules/VALSET/value_sets.html", module_code=MODULE_CODE)


@bp.route("/api", methods=["GET"])
@require_permission("value_set", "view")
def get_list():
    sets = list_value_sets()
    result = []
    for s in sets:
        # Determine latest and approved versions
        all_versions = ValueSetVersion.query.filter_by(value_set_id=s.id).order_by(ValueSetVersion.version_number.desc()).all()
        latest_version = all_versions[0] if all_versions else None
        
        approved_version = ValueSetVersion.query.filter_by(value_set_id=s.id, status="Approved").order_by(ValueSetVersion.version_number.desc()).first()
        
        result.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "description": s.description,
            "current_version_id": s.current_version_id,
            "latest_version_id": latest_version.id if latest_version else None,
            "latest_version_num": latest_version.version_number if latest_version else None,
            "latest_version_status": latest_version.status if latest_version else None,
            "approved_version_num": approved_version.version_number if approved_version else None,
        })
    return jsonify(result)


@bp.route("/api", methods=["POST"])
@require_permission("value_set", "manage_forms")
def create():
    data = request.get_json() or {}
    name = data.get("name")
    code = data.get("code")
    description = data.get("description")
    
    user = current_user()
    try:
        val_set = create_value_set(name, code, description, user.id)
        db.session.commit()
        return success_response(
            data={"id": val_set.id, "name": val_set.name, "code": val_set.code},
            message="Value set created successfully."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:value_set_id>", methods=["DELETE"])
@require_permission("value_set", "manage_forms")
def delete(value_set_id):
    data = request.get_json() or {}
    reason = data.get("reason")
    
    user = current_user()
    try:
        delete_value_set(value_set_id, user.id, reason)
        db.session.commit()
        return success_response(message="Value set deleted successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>", methods=["GET"])
@require_permission("value_set", "view")
def get_version_details(version_id):
    version = get_value_set_version(version_id)
    if not version:
        return error_response("Value set version not found.", 404)
        
    parent = get_value_set(version.value_set_id)
    entries = get_value_set_entries(version_id)
    user = current_user()
    
    # Load username helpers
    def get_user_name(uid):
        if not uid:
            return None
        u = User.query.get(uid)
        return u.full_name if u else None

    # Get all versions for parent
    versions = ValueSetVersion.query.filter_by(value_set_id=version.value_set_id).order_by(ValueSetVersion.version_number.desc()).all()
    version_list = [{
        "id": v.id,
        "version_number": v.version_number,
        "status": v.status,
    } for v in versions]

    # Load permissions context
    from app.common.permissions import has_permission
    can_approve = has_permission(user.id, "value_set", "approve")
    can_edit = has_permission(user.id, "value_set", "manage_forms")
    is_submitter = version.submitted_by == user.id

    data = {
        "value_set": {
            "id": parent.id,
            "name": parent.name,
            "code": parent.code,
            "description": parent.description,
        },
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "status": version.status,
            "effective_from": version.effective_from.isoformat() if version.effective_from else None,
            "effective_to": version.effective_to.isoformat() if version.effective_to else None,
            "rejection_reason": version.rejection_reason,
            "submitted_by": get_user_name(version.submitted_by),
            "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
            "approved_by": get_user_name(version.approved_by),
            "approved_at": version.approved_at.isoformat() if version.approved_at else None,
            "rejected_by": get_user_name(version.rejected_by),
            "rejected_at": version.rejected_at.isoformat() if version.rejected_at else None,
        },
        "entries": [{
            "id": e.id,
            "entry_code": e.entry_code,
            "entry_label": e.entry_label,
            "display_order": e.display_order,
            "is_active": e.is_active,
        } for e in entries],
        "all_versions": version_list,
        "permissions": {
            "can_edit": can_edit and version.status in ("Draft", "Rejected"),
            "can_submit": can_edit and version.status in ("Draft", "Rejected"),
            "can_approve": can_approve and version.status == "Submitted" and not is_submitter,
            "can_reject": can_approve and version.status == "Submitted" and not is_submitter,
            "can_create_version": can_edit and version.status == "Approved"
        }
    }
    return jsonify(data)


@bp.route("/api/version/<int:version_id>/entries", methods=["POST"])
@require_permission("value_set", "manage_forms")
def update_version_entries(version_id):
    data = request.get_json() or {}
    entries_list = data.get("entries")
    if not isinstance(entries_list, list):
        return error_response("Entries must be a list.", 400)
        
    user = current_user()
    try:
        add_or_update_entries(version_id, entries_list, user.id)
        db.session.commit()
        return success_response(message="Entries updated successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>/submit", methods=["POST"])
@require_permission("value_set", "manage_forms")
def submit_version(version_id):
    user = current_user()
    try:
        submit_value_set_version(version_id, user.id)
        db.session.commit()
        return success_response(message="Value set version submitted for approval.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>/approve", methods=["POST"])
@require_permission("value_set", "approve")
def approve_version(version_id):
    user = current_user()
    try:
        approve_value_set_version(version_id, user.id)
        db.session.commit()
        return success_response(message="Value set version approved successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>/reject", methods=["POST"])
@require_permission("value_set", "approve")
def reject_version(version_id):
    data = request.get_json() or {}
    reason = data.get("reason")
    
    user = current_user()
    try:
        reject_value_set_version(version_id, user.id, reason)
        db.session.commit()
        return success_response(message="Value set version rejected.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:value_set_id>/new-version", methods=["POST"])
@require_permission("value_set", "manage_forms")
def create_new_version(value_set_id):
    user = current_user()
    try:
        new_version = create_new_draft_version(value_set_id, user.id)
        db.session.commit()
        return success_response(
            data={"version_id": new_version.id, "version_number": new_version.version_number},
            message="New draft version created."
        )
    except ValueError as e:
        return error_response(str(e), 400)
