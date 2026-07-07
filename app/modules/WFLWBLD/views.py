# Standalone Workflow Builder UI disabled — current complexity needs are met by
# WKBK's simplified chain editor, which depends on this module's service layer
# (save_workflow_draft_levels, publish_workflow_version, etc.) internally. Every
# route below is blocked by the before_request hook further down; the service
# and model layers are untouched and still fully used by SUBMIT, APPROV, NOTIFY,
# FORMBLD, and WKBK. Re-enable by removing that hook (and restoring the nav/
# dashboard links in app/__init__.py) if multi-level/SEQUENTIAL chains are
# needed again through this dedicated UI.

import json

from flask import Blueprint, render_template, jsonify, request
from app.common.decorators import require_permission
from app.common.auth import current_user, is_api_request
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
    delete_workflow,
    get_eligible_level_approvers,
    validate_workflow_path_for_site,
)
from app.modules.WFLWBLD.model import WorkflowVersion, WorkflowLevelApprover
from app.modules.FORMBLD.model import Form
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site

MODULE_CODE = "WFLWBLD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.before_request
def _feature_disabled():
    if is_api_request():
        return error_response("This feature is not currently available.", 404)
    return render_template("feature_unavailable.html"), 404


def _parse_form_metadata(form):
    metadata = {
        "display_name": form.name,
        "gri_code": "",
        "sites": [],
        "frequency": "Monthly",
        "workflow_id": None,
        "description_text": form.description or "",
    }
    if form.description and form.description.startswith("{"):
        try:
            metadata.update(json.loads(form.description))
        except Exception:
            pass
    return metadata


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

    sites = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    available_sites = [{
        "id": site.id,
        "name": site.name,
        "code": site.code,
    } for site in sites]

    linked_forms = []
    available_forms = []
    forms = Form.query.filter_by(is_deleted=False).order_by(Form.name.asc()).all()
    for form in forms:
        metadata = _parse_form_metadata(form)
        site_ids = []
        for site_id in metadata.get("sites") or []:
            try:
                site_ids.append(int(site_id))
            except (TypeError, ValueError):
                continue

        available_forms.append({
            "id": form.id,
            "name": metadata.get("display_name") or form.name,
            "code": form.code,
            "site_ids": site_ids,
            "workflow_id": metadata.get("workflow_id"),
        })

        try:
            linked_workflow_id = int(metadata.get("workflow_id"))
        except (TypeError, ValueError):
            linked_workflow_id = None
        if linked_workflow_id != parent.id:
            continue

        linked_forms.append({
            "id": form.id,
            "name": metadata.get("display_name") or form.name,
            "code": form.code,
            "site_ids": site_ids,
        })
    
    # Construct levels data
    levels_data = []
    for lvl in levels:
        approvers = WorkflowLevelApprover.query.filter_by(workflow_level_id=lvl.id, is_deleted=False).order_by(WorkflowLevelApprover.sequence_number.asc(), WorkflowLevelApprover.id.asc()).all()
        approvers_list = []
        for app in approvers:
            app_user = User.query.get(app.user_id)
            approvers_list.append({
                "user_id": app.user_id,
                "scope_site_id": app.scope_site_id,
                "sequence_number": app.sequence_number,
                "full_name": app_user.full_name if app_user else "Unknown User",
                "email": app_user.email if app_user else "",
                "site_name": next((site.name for site in sites if site.id == app.scope_site_id), None)
            })
            
        levels_data.append({
            "id": lvl.id,
            "level_number": lvl.level_number,
            "level_name": lvl.level_name,
            "approval_mode": lvl.approval_mode,
            "skip_if_empty": lvl.skip_if_empty,
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
        "available_sites": available_sites,
        "available_forms": available_forms,
        "linked_forms": linked_forms,
        "permissions": {
            "can_edit": can_edit and version.published_at is None,
            "can_publish": can_edit and version.published_at is None,
            "can_create_version": can_edit and version.published_at is not None
        }
    }
    return jsonify(data)


@bp.route("/api/version/<int:version_id>/preview")
@require_permission("workflow", "view")
def preview_site_path(version_id):
    site_id = request.args.get("site_id", type=int)
    if not site_id:
        return error_response("Site is required for workflow preview.", 400)

    version = get_workflow_version(version_id)
    if not version:
        return error_response("Workflow version not found.", 404)

    levels = get_workflow_version_levels(version.id)
    preview_rows = []
    has_warning = False

    for level in levels:
        approvers = get_eligible_level_approvers(level, site_id)
        if approvers:
            users = []
            for assignment in approvers:
                user = User.query.get(assignment.user_id)
                users.append({
                    "user_id": assignment.user_id,
                    "name": user.full_name if user else f"User {assignment.user_id}",
                    "scope": "All Sites" if assignment.scope_site_id is None else "This Site",
                })
            preview_rows.append({
                "level_number": level.level_number,
                "level_name": level.level_name,
                "status": "active",
                "approvers": users,
            })
        elif level.skip_if_empty:
            preview_rows.append({
                "level_number": level.level_number,
                "level_name": level.level_name,
                "status": "skipped",
                "approvers": [],
            })
        else:
            has_warning = True
            preview_rows.append({
                "level_number": level.level_number,
                "level_name": level.level_name,
                "status": "blocked",
                "approvers": [],
            })
            break

    try:
        validate_workflow_path_for_site(version, site_id)
        message = None
    except ValueError as error:
        has_warning = True
        message = str(error)

    return success_response(data={
        "rows": preview_rows,
        "has_warning": has_warning,
        "message": message,
    })


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
