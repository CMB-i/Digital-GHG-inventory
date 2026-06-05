from flask import Blueprint, render_template, jsonify, request
from app.common.decorators import require_permission
from app.common.auth import current_user
from app.common.responses import success_response, error_response
from app.database import db

from app.modules.WFLWBLD.service import (
    list_workflows,
    get_workflow,
    create_workflow,
    get_workflow_version,
    get_workflow_version_levels,
    save_workflow_draft_levels,
    publish_workflow_version,
    create_new_workflow_version_draft,
    delete_workflow
)
from app.modules.WFLWBLD.model import WorkflowVersion, WorkflowLevelApprover
from app.modules.USRMGMT.model import User

MODULE_CODE = "WFLWBLD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("workflow", "view")
def index():
    return render_template("modules/WFLWBLD/workflow_builder.html", module_code=MODULE_CODE)


@bp.route("/api", methods=["GET"])
@require_permission("workflow", "view")
def get_list():
    workflows = list_workflows()
    result = []
    for w in workflows:
        latest_version = WorkflowVersion.query.filter_by(workflow_id=w.id).order_by(WorkflowVersion.version_number.desc()).first()
        levels_count = 0
        if latest_version:
            from app.modules.WFLWBLD.model import WorkflowLevel
            levels_count = WorkflowLevel.query.filter_by(workflow_version_id=latest_version.id, is_deleted=False).count()
        result.append({
            "id": w.id,
            "name": w.name,
            "code": w.code,
            "levels_count": levels_count,
            "current_version_id": w.current_version_id,
            "latest_version_id": latest_version.id if latest_version else None,
            "latest_version_num": latest_version.version_number if latest_version else None,
            "latest_version_status": "Published" if (latest_version and latest_version.published_at is not None) else "Draft"
        })
    return jsonify(result)


@bp.route("/api", methods=["POST"])
@require_permission("workflow", "manage_forms")
def create():
    data = request.get_json() or {}
    name = data.get("name")
    code = data.get("code")
    
    user = current_user()
    try:
        wf = create_workflow(name, code, user.id)
        db.session.commit()
        return success_response(
            data={"id": wf.id, "name": wf.name, "code": wf.code},
            message="Workflow created successfully."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workflow_id>", methods=["PUT"])
@require_permission("workflow", "manage_forms")
def update_details(workflow_id):
    data = request.get_json() or {}
    name = data.get("name")
    
    wf = get_workflow(workflow_id)
    if not wf:
        return error_response("Workflow not found.", 404)
        
    try:
        if name:
            wf.name = name.strip()
        wf.updated_by = current_user().id
        db.session.commit()
        return success_response(message="Workflow details updated successfully.")
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>", methods=["GET"])
@require_permission("workflow", "view")
def get_version_details(version_id):
    version = get_workflow_version(version_id)
    if not version:
        return error_response("Workflow version not found.", 404)
        
    parent = get_workflow(version.workflow_id)
    levels = get_workflow_version_levels(version.id)
    
    # Check permissions
    user = current_user()
    from app.common.permissions import has_permission
    can_edit = has_permission(user.id, "workflow", "manage_forms")
    
    # Get all versions
    versions = WorkflowVersion.query.filter_by(workflow_id=version.workflow_id).order_by(WorkflowVersion.version_number.desc()).all()
    version_list = [{
        "id": v.id,
        "version_number": v.version_number,
        "status": "Published" if v.published_at is not None else "Draft"
    } for v in versions]
    
    # Get all active users
    active_users = User.query.filter_by(is_deleted=False, is_active=True).all()
    available_users = [{
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email
    } for u in active_users]
    
    # Construct levels data
    levels_data = []
    for lvl in levels:
        approvers = WorkflowLevelApprover.query.filter_by(workflow_level_id=lvl.id, is_deleted=False).order_by(WorkflowLevelApprover.sequence_number.asc(), WorkflowLevelApprover.id.asc()).all()
        approvers_list = []
        for app in approvers:
            app_user = User.query.get(app.user_id)
            approvers_list.append({
                "user_id": app.user_id,
                "sequence_number": app.sequence_number,
                "full_name": app_user.full_name if app_user else "Unknown User",
                "email": app_user.email if app_user else ""
            })
            
        levels_data.append({
            "id": lvl.id,
            "level_number": lvl.level_number,
            "level_name": lvl.level_name,
            "approval_mode": lvl.approval_mode,
            "approvers": approvers_list
        })
        
    data = {
        "workflow": {
            "id": parent.id,
            "name": parent.name,
            "code": parent.code
        },
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "status": "Published" if version.published_at is not None else "Draft",
            "published_at": version.published_at.isoformat() if version.published_at else None,
        },
        "levels": levels_data,
        "all_versions": version_list,
        "available_users": available_users,
        "permissions": {
            "can_edit": can_edit and version.published_at is None,
            "can_publish": can_edit and version.published_at is None,
            "can_create_version": can_edit and version.published_at is not None
        }
    }
    return jsonify(data)


@bp.route("/api/version/<int:version_id>/levels", methods=["POST"])
@require_permission("workflow", "manage_forms")
def save_levels(version_id):
    data = request.get_json() or {}
    levels_list = data.get("levels")
    if not isinstance(levels_list, list):
        return error_response("Levels must be a list.", 400)
        
    user = current_user()
    try:
        save_workflow_draft_levels(version_id, levels_list, user.id)
        db.session.commit()
        return success_response(message="Workflow levels saved successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/version/<int:version_id>/publish", methods=["POST"])
@require_permission("workflow", "manage_forms")
def publish(version_id):
    user = current_user()
    try:
        publish_workflow_version(version_id, user.id)
        db.session.commit()
        return success_response(message="Workflow published successfully.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workflow_id>/new-version", methods=["POST"])
@require_permission("workflow", "manage_forms")
def create_new_version(workflow_id):
    user = current_user()
    try:
        new_version = create_new_workflow_version_draft(workflow_id, user.id)
        db.session.commit()
        return success_response(
            data={"version_id": new_version.id, "version_number": new_version.version_number},
            message="New draft version created."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workflow_id>", methods=["DELETE"])
@require_permission("workflow", "manage_forms")
def delete(workflow_id):
    user = current_user()
    try:
        delete_workflow(workflow_id, user.id)
        db.session.commit()
        return success_response(message="Workflow deleted successfully.")
    except ValueError as e:
        return error_response(str(e), 400)
