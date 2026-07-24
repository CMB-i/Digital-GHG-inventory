from datetime import datetime, timezone

from flask import Blueprint, render_template, request, jsonify

from app.common.decorators import require_permission
from app.common.auth import current_user
from app.common.responses import success_response, error_response
from app.database import db
from app.modules.WKBK.service import (
    get_all_workbooks,
    create_workbook,
    get_workbook,
    get_workbook_with_sheets,
    add_sheet_to_workbook,
    remove_sheet_from_workbook,
    reorder_sheets,
    deactivate_workbook,
    get_addable_forms,
    get_workbook_sites,
    get_assignable_sites,
    add_site_to_workbook,
    remove_site_from_workbook,
    get_site_submitters,
    get_eligible_submitters,
    add_site_submitter,
    remove_site_submitter,
    check_workbook_readiness,
    rename_workbook,
    rename_workbook_sheet,
)
from app.modules.WFLWBLD.model import (
    Workflow, WorkflowVersion, WorkflowLevel, WorkflowLevelApprover,
)
from app.modules.USRMGMT.model import User

bp = Blueprint("wkbk", __name__, url_prefix="/workbooks")


# ── Pages ──────────────────────────────────────────────────────────────────────

@bp.route("/")
@require_permission("form", "manage_forms")
def index():
    return render_template("modules/WKBK/workbooks.html")


@bp.route("/<int:workbook_id>")
@require_permission("form", "manage_forms")
def detail(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return render_template("no_access.html"), 404
    return render_template("modules/WKBK/workbook_detail.html", workbook=wb)


# ── API ────────────────────────────────────────────────────────────────────────

@bp.route("/api", methods=["GET"])
@require_permission("form", "manage_forms")
def api_list():
    return jsonify(get_all_workbooks())


@bp.route("/api", methods=["POST"])
@require_permission("form", "manage_forms")
def api_create():
    data = request.get_json() or {}
    user = current_user()
    try:
        wb = create_workbook(
            name=data.get("name"),
            code=data.get("code"),
            description=data.get("description"),
            created_by=user.id,
        )
        db.session.commit()
        return success_response(
            data={"id": wb.id, "name": wb.name, "code": wb.code},
            message="Workbook created.",
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>", methods=["GET"])
@require_permission("form", "manage_forms")
def api_detail(workbook_id):
    wb, sheets = get_workbook_with_sheets(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    return jsonify({
        "id": wb.id,
        "name": wb.name,
        "code": wb.code,
        "status": wb.status,
        "description": wb.description,
        "sheets": sheets,
    })


@bp.route("/api/<int:workbook_id>/sheets/add", methods=["POST"])
@require_permission("form", "manage_forms")
def api_add_sheet(workbook_id):
    data = request.get_json() or {}
    try:
        add_sheet_to_workbook(
            workbook_id=workbook_id,
            form_id=data.get("form_id"),
            sheet_label=data.get("sheet_label"),
        )
        db.session.commit()
        _, sheets = get_workbook_with_sheets(workbook_id)
        return success_response(data={"sheets": sheets}, message="Sheet added.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sheets/remove", methods=["POST"])
@require_permission("form", "manage_forms")
def api_remove_sheet(workbook_id):
    data = request.get_json() or {}
    try:
        remove_sheet_from_workbook(workbook_id=workbook_id, form_id=data.get("form_id"))
        db.session.commit()
        return success_response(message="Sheet removed.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sheets/reorder", methods=["POST"])
@require_permission("form", "manage_forms")
def api_reorder_sheets(workbook_id):
    data = request.get_json() or {}
    ordered = data.get("ordered_form_ids", [])
    if not isinstance(ordered, list):
        return error_response("ordered_form_ids must be a list.", 400)
    try:
        reorder_sheets(workbook_id=workbook_id, ordered_form_ids=ordered)
        db.session.commit()
        return success_response(message="Order saved.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/deactivate", methods=["POST"])
@require_permission("form", "manage_forms")
def api_deactivate(workbook_id):
    try:
        deactivate_workbook(workbook_id)
        db.session.commit()
        return success_response(message="Workbook deactivated.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/rename", methods=["PUT"])
@require_permission("form", "manage_forms")
def api_rename_workbook(workbook_id):
    data = request.get_json() or {}
    name = data.get("name")
    try:
        wb = rename_workbook(workbook_id, name)
        db.session.commit()
        return success_response(
            data={"id": wb.id, "name": wb.name, "code": wb.code},
            message="Workbook renamed."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sheets/<int:form_id>/rename", methods=["PUT"])
@require_permission("form", "manage_forms")
def api_rename_sheet(workbook_id, form_id):
    data = request.get_json() or {}
    sheet_label = data.get("sheet_label")
    try:
        wf = rename_workbook_sheet(workbook_id, form_id, sheet_label)
        db.session.commit()
        _, sheets = get_workbook_with_sheets(workbook_id)
        return success_response(
            data={"sheets": sheets},
            message="Sheet renamed."
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/addable-forms", methods=["GET"])
@require_permission("form", "manage_forms")
def api_addable_forms(workbook_id):
    return jsonify(get_addable_forms(workbook_id))


@bp.route("/api/<int:workbook_id>/workflow", methods=["GET"])
@require_permission("form", "manage_forms")
def api_get_workflow_assignment(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    if not wb.workflow_id:
        return jsonify({"workflow_id": None})

    workflow = Workflow.query.filter_by(id=wb.workflow_id, is_deleted=False).first()
    if not workflow:
        return jsonify({"workflow_id": None})

    latest_version = (
        WorkflowVersion.query.filter_by(workflow_id=workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
        .first()
    )
    return jsonify({
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "workflow_code": workflow.code,
        "version_id": latest_version.id if latest_version else None,
        "version_status": (
            "Published"
            if latest_version and latest_version.published_at is not None
            else ("Draft" if latest_version else None)
        ),
    })


@bp.route("/api/<int:workbook_id>/workflow", methods=["POST"])
@require_permission("form", "manage_forms")
def api_set_workflow_assignment(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    data = request.get_json() or {}
    workflow_id = data.get("workflow_id")
    if workflow_id in ("", "null"):
        workflow_id = None

    if workflow_id is not None:
        try:
            workflow_id = int(workflow_id)
        except (TypeError, ValueError):
            return error_response("Invalid workflow_id.", 400)

        workflow = Workflow.query.filter_by(id=workflow_id, is_deleted=False).first()
        if not workflow:
            return error_response("Workflow not found.", 404)

    wb.workflow_id = workflow_id
    db.session.commit()
    return success_response(
        data={"workflow_id": wb.workflow_id},
        message="Workbook workflow assignment updated.",
    )


@bp.route("/api/<int:workbook_id>/sites", methods=["GET"])
@require_permission("form", "manage_forms")
def api_list_sites(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    return jsonify(get_workbook_sites(workbook_id))


@bp.route("/api/<int:workbook_id>/assignable-sites", methods=["GET"])
@require_permission("form", "manage_forms")
def api_assignable_sites(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    return jsonify(get_assignable_sites(workbook_id))


@bp.route("/api/<int:workbook_id>/sites", methods=["POST"])
@require_permission("form", "manage_forms")
def api_add_site(workbook_id):
    data = request.get_json() or {}
    user = current_user()
    try:
        add_site_to_workbook(workbook_id=workbook_id, site_id=data.get("site_id"), created_by=user.id)
        db.session.commit()
        return success_response(data={"sites": get_workbook_sites(workbook_id)}, message="Site added.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>", methods=["DELETE"])
@require_permission("form", "manage_forms")
def api_remove_site(workbook_id, site_id):
    try:
        remove_site_from_workbook(workbook_id=workbook_id, site_id=site_id)
        db.session.commit()
        return success_response(data={"sites": get_workbook_sites(workbook_id)}, message="Site removed.")
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>/submitters", methods=["GET"])
@require_permission("form", "manage_forms")
def api_list_submitters(workbook_id, site_id):
    return jsonify(get_site_submitters(workbook_id, site_id))


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>/eligible-submitters", methods=["GET"])
@require_permission("form", "manage_forms")
def api_eligible_submitters(workbook_id, site_id):
    return jsonify(get_eligible_submitters(workbook_id, site_id))


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>/submitters", methods=["POST"])
@require_permission("form", "manage_forms")
def api_add_submitter(workbook_id, site_id):
    data = request.get_json() or {}
    user = current_user()
    try:
        add_site_submitter(
            workbook_id=workbook_id,
            site_id=site_id,
            user_id=data.get("user_id"),
            created_by=user.id,
        )
        db.session.commit()
        return success_response(
            data={"submitters": get_site_submitters(workbook_id, site_id)},
            message="Submitter added.",
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>/submitters/<int:user_id>", methods=["DELETE"])
@require_permission("form", "manage_forms")
def api_remove_submitter(workbook_id, site_id, user_id):
    try:
        remove_site_submitter(workbook_id=workbook_id, site_id=site_id, user_id=user_id)
        db.session.commit()
        return success_response(
            data={"submitters": get_site_submitters(workbook_id, site_id)},
            message="Submitter removed.",
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/preview", methods=["GET"])
@require_permission("form", "manage_forms")
def api_preview(workbook_id):
    wb, sheets = get_workbook_with_sheets(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    return jsonify([
        {
            "form_id": s["form_id"],
            "sheet_label": s["sheet_label"],
            "latest_version_id": s["latest_version_id"],
        }
        for s in sheets
    ])


@bp.route("/api/<int:workbook_id>/readiness", methods=["GET"])
@require_permission("form", "manage_forms")
def api_readiness(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    checklist = check_workbook_readiness(workbook_id)
    return jsonify({"workbook_status": wb.status, "checklist": checklist})


@bp.route("/api/<int:workbook_id>/publish", methods=["POST"])
@require_permission("form", "manage_forms")
def api_publish_workbook(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    checklist = check_workbook_readiness(workbook_id)
    if not checklist["all_ok"]:
        return jsonify({"error": "Workbook is not ready to publish.", "checklist": checklist}), 400

    wb.status = "published"
    wb.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return success_response(data={"status": wb.status, "checklist": checklist})


# ── Chain builder helpers + routes ─────────────────────────────────────────────

def _build_chain_payload(wb):
    available_users = [
        {"id": u.id, "full_name": u.full_name, "email": u.email}
        for u in User.query.filter_by(is_deleted=False, is_active=True)
        .order_by(User.full_name.asc())
        .all()
    ]

    if not wb.workflow_id:
        return {
            "workflow_id": None,
            "version_id": None,
            "version_status": None,
            "levels": [],
            "approvers_by_site": {},
            "available_users": available_users,
        }

    workflow = Workflow.query.filter_by(id=wb.workflow_id, is_deleted=False).first()
    if not workflow:
        return {
            "workflow_id": None,
            "version_id": None,
            "version_status": None,
            "levels": [],
            "approvers_by_site": {},
            "available_users": available_users,
        }

    latest_version = (
        WorkflowVersion.query.filter_by(workflow_id=workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
        .first()
    )

    levels = []
    approvers_by_site = {}

    if latest_version:
        raw_levels = (
            WorkflowLevel.query.filter_by(
                workflow_version_id=latest_version.id, is_deleted=False
            )
            .order_by(WorkflowLevel.level_number.asc())
            .all()
        )

        level_ids = [l.id for l in raw_levels]

        for l in raw_levels:
            levels.append({
                "id": l.id,
                "level_number": l.level_number,
                "level_name": l.level_name,
                "level_type": "final" if l.level_name == "Final Approval" else "regular",
                "approval_mode": l.approval_mode,
                "skip_if_empty": l.skip_if_empty,
            })

        if level_ids:
            for approver in WorkflowLevelApprover.query.filter(
                WorkflowLevelApprover.workflow_level_id.in_(level_ids),
                WorkflowLevelApprover.is_deleted == False,
            ).all():
                site_key = str(approver.scope_site_id) if approver.scope_site_id else "null"
                if site_key not in approvers_by_site:
                    approvers_by_site[site_key] = []
                user = User.query.filter_by(
                    id=approver.user_id, is_deleted=False, is_active=True
                ).first()
                if user:
                    approvers_by_site[site_key].append({
                        "level_id": approver.workflow_level_id,
                        "user_id": approver.user_id,
                        "user_name": user.full_name,
                        "scope_site_id": approver.scope_site_id,
                    })

    version_status = None
    if latest_version:
        version_status = "Published" if latest_version.published_at is not None else "Draft"

    return {
        "workflow_id": workflow.id,
        "version_id": latest_version.id if latest_version else None,
        "version_status": version_status,
        "levels": levels,
        "approvers_by_site": approvers_by_site,
        "available_users": available_users,
    }


@bp.route("/api/<int:workbook_id>/chain", methods=["GET"])
@require_permission("form", "manage_forms")
def api_get_chain(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)
    return jsonify(_build_chain_payload(wb))


@bp.route("/api/<int:workbook_id>/chain/site/<int:site_id>", methods=["POST"])
@require_permission("form", "manage_forms")
def api_save_site_chain(workbook_id, site_id):
    from app.modules.WFLWBLD.service import (
        create_workflow as wf_create_workflow,
        create_new_workflow_version_draft as wf_create_draft,
        save_site_chain_levels,
    )

    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    data = request.get_json() or {}
    steps = data.get("steps", [])
    user = current_user()

    try:
        if not wb.workflow_id:
            name = wb.name + " Approval Path"
            code = wb.code.upper() + "_APPROVAL"
            workflow = wf_create_workflow(name=name, code=code, user_id=user.id)
            wb.workflow_id = workflow.id
            db.session.flush()

        workflow = Workflow.query.filter_by(id=wb.workflow_id, is_deleted=False).first()
        if not workflow:
            return error_response("Workflow not found.", 404)

        draft_version = WorkflowVersion.query.filter_by(
            workflow_id=workflow.id, published_at=None
        ).first()
        if not draft_version:
            draft_version = wf_create_draft(workflow_id=workflow.id, user_id=user.id)

        save_site_chain_levels(draft_version.id, site_id, steps, user.id)

        db.session.commit()
        return success_response(data=_build_chain_payload(wb))

    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/chain/publish", methods=["POST"])
@require_permission("form", "manage_forms")
def api_publish_chain(workbook_id):
    from app.modules.WFLWBLD.service import publish_workflow_version

    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    if not wb.workflow_id:
        return error_response("No approval path configured for this workbook.", 400)

    workflow = Workflow.query.filter_by(id=wb.workflow_id, is_deleted=False).first()
    if not workflow:
        return error_response("Approval path workflow not found.", 404)

    draft_version = WorkflowVersion.query.filter_by(
        workflow_id=workflow.id, published_at=None
    ).first()
    if not draft_version:
        return error_response("No draft version to publish — the approval path is already published.", 400)

    user = current_user()
    try:
        publish_workflow_version(draft_version.id, user.id)
        db.session.commit()
        return success_response(data=_build_chain_payload(wb))
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/chain", methods=["DELETE"])
@require_permission("form", "manage_forms")
def api_delete_chain(workbook_id):
    from app.modules.WFLWBLD.service import delete_workflow

    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    if not wb.workflow_id:
        return error_response("No approval path configured for this workbook.", 400)

    workflow_id = wb.workflow_id
    user = current_user()
    try:
        # Detach first: delete_workflow() refuses if any active Workbook still
        # points to it, which this workbook itself does until we clear it.
        wb.workflow_id = None
        db.session.flush()
        delete_workflow(workflow_id, user.id)
        db.session.commit()
        return success_response(data=_build_chain_payload(wb), message="Approval chain deleted.")
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/chain/init", methods=["POST"])
@require_permission("form", "manage_forms")
def api_init_chain(workbook_id):
    from app.modules.WFLWBLD.service import create_workflow as wf_create_workflow

    wb = get_workbook(workbook_id)
    if not wb:
        return error_response("Workbook not found.", 404)

    if wb.workflow_id:
        return success_response(
            data={"workflow_id": wb.workflow_id},
            message="Workflow already exists.",
        )

    user = current_user()
    try:
        name = wb.name + " Approval Path"
        code = wb.code.upper() + "_APPROVAL"
        workflow = wf_create_workflow(name=name, code=code, user_id=user.id)
        wb.workflow_id = workflow.id
        db.session.commit()
        return success_response(
            data={"workflow_id": workflow.id},
            message="Workflow created.",
        )
    except ValueError as e:
        return error_response(str(e), 400)
