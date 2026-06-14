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
)
from app.modules.WFLWBLD.model import Workflow, WorkflowVersion

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
        add_site_to_workbook(
            workbook_id=workbook_id,
            site_id=data.get("site_id"),
            created_by=user.id,
        )
        db.session.commit()
        return success_response(
            data={"sites": get_workbook_sites(workbook_id)},
            message="Site added.",
        )
    except ValueError as e:
        return error_response(str(e), 400)


@bp.route("/api/<int:workbook_id>/sites/<int:site_id>", methods=["DELETE"])
@require_permission("form", "manage_forms")
def api_remove_site(workbook_id, site_id):
    try:
        remove_site_from_workbook(workbook_id=workbook_id, site_id=site_id)
        db.session.commit()
        return success_response(
            data={"sites": get_workbook_sites(workbook_id)},
            message="Site removed.",
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
