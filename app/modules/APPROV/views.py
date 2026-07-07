from flask import Blueprint, redirect, render_template, request
from app.database import db
from app.common.auth import current_user, require_login
from app.common.permissions import has_permission
from app.common.responses import success_response, error_response
from app.modules.ACCESS.model import AccessMatrix
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument, SubmissionPackage
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.APPROV.model import ApprovalAction, Issue
from app.modules.APPROV.service import (
    get_approver_queue,
    get_actioned_history,
    approve_submission,
    request_changes_submission,
    reject_submission,
    raise_issue,
    resolve_issue,
    clear_recalc_review,
    get_package_summary_for_reviewer,
    compose_package_review_data,
    list_package_value_issues,
    add_package_value_issue,
    approve_package,
    request_changes_package,
    reject_package,
)
from app.modules.SUBMIT.service import (
    compose_readonly_workbook_context,
    format_period_label,
    human_sheet_label,
    serialize_submission_value_issue,
    submission_value_issues_map,
)

MODULE_CODE = "APPROV"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


def _has_any_review_access(user):
    return AccessMatrix.query.filter(
        AccessMatrix.user_id == user.id,
        AccessMatrix.entity_type == "submission",
        AccessMatrix.is_deleted == False,
        (AccessMatrix.can_approve == True) | (AccessMatrix.can_reject == True),
    ).first() is not None


def _can_review_submission(user, submission, *actions):
    return any(
        has_permission(user.id, "submission", action, scope_site_id=submission.site_id)
        for action in actions
    )


def _page_no_access():
    return render_template("no_access.html"), 403


@bp.route("/")
@require_login
def index():
    user = current_user()
    if not _has_any_review_access(user):
        return _page_no_access()
    return render_template("modules/APPROV/approval_queue.html", module_code=MODULE_CODE)

@bp.route("/api/queue")
@require_login
def api_queue():
    user = current_user()
    if not _has_any_review_access(user):
        return error_response("Permission denied.", 403)
    try:
        pending = get_approver_queue(user.id)
        history = get_actioned_history(user.id)
        return success_response(data={
            "pending": pending,
            "history": history
        })
    except Exception as e:
        return error_response(str(e), 500)

@bp.route("/submissions/<int:submission_id>")
@require_login
def view_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    user = current_user()
    if submission.package_id and (
        _can_review_submission(user, submission, "approve", "reject") or
        has_permission(user.id, "submission", "view", scope_site_id=submission.site_id)
    ):
        return redirect(f"/module/APPROV/packages/{submission.package_id}")
    if not _can_review_submission(user, submission, "approve", "reject"):
        return _page_no_access()
    return render_template(
        "modules/APPROV/submission_review.html",
        module_code=MODULE_CODE,
        submission_id=submission.id
    )

@bp.route("/packages/<int:package_id>")
@require_login
def view_package(package_id):
    package = SubmissionPackage.query.get_or_404(package_id)
    user = current_user()
    if not compose_package_review_data(package.id, user.id):
        return _page_no_access()
    return render_template(
        "modules/APPROV/package_review.html",
        module_code=MODULE_CODE,
        package_id=package.id
    )

@bp.route("/api/packages/<int:package_id>/review")
@require_login
def get_package_review(package_id):
    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        return error_response("Package not found.", 404)

    user = current_user()
    review_data = compose_package_review_data(package.id, user.id)
    if not review_data:
        return error_response("Permission denied.", 403)

    return success_response(data=review_data)


@bp.route("/api/packages/<int:package_id>/approve", methods=["POST"])
@require_login
def approve_package_endpoint(package_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        package, results = approve_package(package_id, user.id, comment)
        db.session.commit()
        return success_response(
            message="Package approved successfully.",
            data={"status": package.status, "results": results},
        )
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/packages/<int:package_id>/request-changes", methods=["POST"])
@require_login
def request_changes_package_endpoint(package_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        package, results = request_changes_package(package_id, user.id, comment)
        db.session.commit()
        return success_response(
            message="Package returned for changes successfully.",
            data={"status": package.status, "results": results},
        )
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/packages/<int:package_id>/reject", methods=["POST"])
@require_login
def reject_package_endpoint(package_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        package, results = reject_package(package_id, user.id, comment)
        db.session.commit()
        return success_response(
            message="Package rejected successfully.",
            data={"status": package.status, "results": results},
        )
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/packages/<int:package_id>/values/<int:value_id>/issues")
@require_login
def get_package_value_issues(package_id, value_id):
    user = current_user()
    try:
        issues = list_package_value_issues(package_id, value_id, user.id)
        return success_response(data={"issues": issues})
    except ValueError as e:
        return error_response(str(e), 403 if str(e) == "Permission denied." else 400)
    except Exception as e:
        return error_response(str(e), 500)

@bp.route("/api/packages/<int:package_id>/values/<int:value_id>/issues", methods=["POST"])
@require_login
def create_package_value_issue(package_id, value_id):
    user = current_user()
    data = request.get_json() or {}
    try:
        issue = add_package_value_issue(
            package_id,
            value_id,
            user.id,
            data.get("issue_text") or data.get("comment"),
        )
        db.session.commit()
        return success_response(
            message="Cell issue added successfully.",
            data={"issue": serialize_submission_value_issue(issue)},
        )
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 403 if str(e) == "Permission denied." else 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/packages/<int:package_id>")
@require_login
def get_package_summary(package_id):
    package = SubmissionPackage.query.get(package_id)
    if not package or package.is_deleted:
        return error_response("Package not found.", 404)

    user = current_user()
    queue_summary = get_package_summary_for_reviewer(package.id, user.id)
    if not queue_summary:
        return error_response("Permission denied.", 403)

    from app.modules.FORMBLD.model import Form
    from app.modules.SITEMST.model import Site
    from app.modules.PERIOD.model import ReportingPeriod
    from app.modules.USRMGMT.model import User

    site = Site.query.get(package.site_id)
    period = ReportingPeriod.query.get(package.period_id)
    submitter = User.query.get(package.submitted_by) if package.submitted_by else None
    submissions = Submission.query.filter_by(package_id=package.id, is_deleted=False).all()
    forms = {
        form.id: form
        for form in Form.query.filter(Form.id.in_([sub.form_id for sub in submissions] or [0])).all()
    }

    submissions_data = []
    for sub in submissions:
        submitter = User.query.get(sub.submitted_by) if sub.submitted_by else None
        submissions_data.append({
            "submission_id": sub.id,
            "form_id": sub.form_id,
            "form_name": human_sheet_label(forms[sub.form_id]) if sub.form_id in forms else "Untitled Sheet",
            "status": sub.status,
            "current_level": sub.current_level,
            "submitted_by": submitter.full_name if submitter else "System",
            "submitted_at": sub.submitted_at,
            "needs_recalc_review": sub.needs_recalc_review,
        })

    return success_response(data={
        "package": {
            "package_id": package.id,
            "package_type": package.package_type,
            "status": package.status,
            "site_id": package.site_id,
            "site_name": site.name if site else "Unknown Site",
            "period_id": package.period_id,
            "period_label": format_period_label(period.year, period.month) if period else "Unknown Period",
            "month": period.month if period else None,
            "year": period.year if period else None,
            "current_level": package.current_level,
            "submitted_by": submitter.full_name if submitter else "System",
            "submitted_at": package.submitted_at,
            "included_submission_count": len(submissions),
            "queue_summary": queue_summary,
        },
        "submissions": submissions_data,
    })

@bp.route("/api/submissions/<int:submission_id>")
@require_login
def get_submission_details(submission_id):
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return error_response("Submission not found.", 404)
    user = current_user()
    if not _can_review_submission(user, submission, "approve", "reject"):
        return error_response("Permission denied.", 403)

    try:
        # Load form fields
        fields = get_form_version_fields(submission.form_version_id)
        fields_data = []
        for fv, f in fields:
            fields_data.append({
                "field_id": f.id,
                "field_code": f.field_code,
                "field_name": fv.field_name,
                "field_type": fv.field_type,
                "field_config": fv.field_config or {},
                "display_order": f.display_order
            })

        # Load saved values
        db_values = SubmissionValue.query.filter_by(submission_id=submission_id).all()
        issue_map = submission_value_issues_map([val.id for val in db_values])
        values_data = {}
        for val in db_values:
            values_data[val.field_id] = {
                "submission_value_id": val.id,
                "raw_value": val.raw_value,
                "calculated_value": float(val.calculated_value) if val.calculated_value is not None else None,
                "cell_state": val.cell_state,
                "is_locked": val.is_locked,
                "remark": val.remark,
                "issues": issue_map.get(val.id, []),
                "calc_status": val.calc_status,
                "calc_error_message": val.calc_error_message,
            }

        # Load proofs
        proofs = ProofDocument.query.filter_by(submission_id=submission_id, is_deleted=False).all()
        proofs_data = {}
        for p in proofs:
            proofs_data[p.field_id] = {
                "id": p.id,
                "original_name": p.original_name,
                "storage_key": p.storage_key,
                "file_size_bytes": p.file_size_bytes
            }

        # Load issues
        issues = Issue.query.filter_by(submission_id=submission_id, is_deleted=False).all()
        issues_list = []
        for i in issues:
            issues_list.append({
                "id": i.id,
                "field_id": i.field_id,
                "title": i.title,
                "description": i.description,
                "status": i.status,
                "raised_by": i.raised_by,
                "resolved_at": i.resolved_at
            })

        # Load actions history
        actions = ApprovalAction.query.filter_by(submission_id=submission_id, is_deleted=False).order_by(ApprovalAction.acted_at.asc()).all()
        actions_list = []
        from app.modules.USRMGMT.model import User
        for a in actions:
            u = User.query.get(a.actor_id)
            actions_list.append({
                "actor_name": u.full_name if u else f"User {a.actor_id}",
                "level_number": a.level_number,
                "action": a.action,
                "comment": a.comment,
                "acted_at": a.acted_at
            })

        # Form basic metadata
        from app.modules.FORMBLD.model import Form
        from app.modules.SITEMST.model import Site
        from app.modules.PERIOD.model import ReportingPeriod

        form = Form.query.get(submission.form_id)
        site = Site.query.get(submission.site_id)
        period = ReportingPeriod.query.get(submission.reporting_period_id)
        fy_start_year = period.year if period and period.month >= 4 else (period.year - 1 if period else None)
        workbook_context = compose_readonly_workbook_context(
            submission.site_id,
            submission.form_id,
            fy_start_year,
            active_period_id=submission.reporting_period_id,
            form_version_id=submission.form_version_id,
        ) if fy_start_year else None

        from app.common.permissions import has_permission
        can_resubmit = (
            submission.status == "Changes Requested" and (
                has_permission(user.id, "submission", "create", scope_site_id=submission.site_id) or
                has_permission(user.id, "submission", "submit", scope_site_id=submission.site_id)
            )
        )

        metadata = {
            "submission_id": submission.id,
            "form_name": human_sheet_label(form),
            "site_name": site.name if site else "",
            "period_label": format_period_label(period.year, period.month) if period else "",
            "status": submission.status,
            "is_locked": submission.is_locked,
            "current_level": submission.current_level,
            "submitted_by": User.query.get(submission.submitted_by).full_name if submission.submitted_by else "",
            "submitted_at": submission.submitted_at,
            "can_resubmit": can_resubmit,
            "needs_recalc_review": submission.needs_recalc_review,
            "recalc_review_notes": submission.recalc_review_notes,
        }

        return success_response(data={
            "metadata": metadata,
            "fields": workbook_context["fields"] if workbook_context else fields_data,
            "sections": workbook_context.get("sections", []) if workbook_context else [],
            "workbook_values": workbook_context.get("workbook_values", {}) if workbook_context else {},
            "rows": workbook_context.get("rows", []) if workbook_context else [],
            "values": values_data,
            "proofs": proofs_data,
            "issues": issues_list,
            "actions": actions_list
        })
    except Exception as e:
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/approve", methods=["POST"])
@require_login
def approve(submission_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        sub = approve_submission(submission_id, user.id, comment)
        db.session.commit()
        return success_response(message="Submission approved successfully.", data={"status": sub.status})
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/request-changes", methods=["POST"])
@require_login
def request_changes(submission_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        sub = request_changes_submission(submission_id, user.id, comment)
        db.session.commit()
        return success_response(message="Changes requested successfully.", data={"status": sub.status})
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/reject", methods=["POST"])
@require_login
def reject(submission_id):
    user = current_user()
    comment = request.json.get("comment") if request.json else None
    try:
        sub = reject_submission(submission_id, user.id, comment)
        db.session.commit()
        return success_response(message="Submission rejected terminally.", data={"status": sub.status})
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/raise-issue", methods=["POST"])
@require_login
def raise_review_issue(submission_id):
    user = current_user()
    if not request.json:
        return error_response("Invalid request payload.", 400)
    field_id = request.json.get("field_id")
    title = request.json.get("title")
    description = request.json.get("description")
    try:
        issue = raise_issue(submission_id, field_id, title, description, user.id)
        db.session.commit()
        return success_response(message="Review issue raised successfully.", data={"issue_id": issue.id})
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/issues/<int:issue_id>/resolve", methods=["POST"])
@require_login
def resolve_review_issue(issue_id):
    user = current_user()
    try:
        resolve_issue(issue_id, user.id)
        db.session.commit()
        return success_response(message="Review issue resolved successfully.")
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/clear-recalc-review", methods=["POST"])
@require_login
def clear_submission_recalc_review(submission_id):
    user = current_user()
    comment = (request.json or {}).get("comment") if request.is_json else None
    try:
        clear_recalc_review(submission_id, user.id, comment)
        db.session.commit()
        return success_response(message="Recalculation review flag cleared.")
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@bp.route("/api/submissions/<int:submission_id>/audit-logs")
@require_login
def get_submission_audit_logs(submission_id):
    submission = Submission.query.get(submission_id)
    if not submission or submission.is_deleted:
        return error_response("Submission not found.", 404)

    user = current_user()
    has_view = has_permission(user.id, "submission", "view", scope_site_id=submission.site_id)
    has_submit = has_permission(user.id, "submission", "submit", scope_site_id=submission.site_id)
    has_approve = has_permission(user.id, "submission", "approve", scope_site_id=submission.site_id)
    has_reject = has_permission(user.id, "submission", "reject", scope_site_id=submission.site_id)
    if not (has_view or has_submit or has_approve or has_reject):
        return error_response("Permission denied.", 403)

    from app.modules.USRMGMT.model import User
    from app.modules.AUDITL.model import AuditLog

    actions = ApprovalAction.query.filter_by(submission_id=submission_id).all()
    logs = AuditLog.query.filter_by(
        entity_type="submission",
        entity_id=str(submission_id),
        action="SUBMIT"
    ).all()

    user_ids = {a.actor_id for a in actions} | {l.actor_user_id for l in logs if l.actor_user_id is not None}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u.full_name for u in users}

    events_raw = []
    for log in logs:
        new_vals = log.new_values or {}
        old_vals = log.old_values or {}
        new_status = new_vals.get("status")
        old_status = old_vals.get("status")

        if new_status == "Resubmitted" or old_status == "Changes Requested":
            action_label = "Resubmitted"
        else:
            action_label = "Submitted"

        dt = log.created_at
        events_raw.append((dt, {
            "timestamp": dt.isoformat(),
            "actor": user_map.get(log.actor_user_id, "System"),
            "action": action_label,
            "level": None,
            "comment": None,
            "is_approval_action": False
        }))

    for act in actions:
        dt = act.acted_at
        events_raw.append((dt, {
            "timestamp": dt.isoformat(),
            "actor": user_map.get(act.actor_id, "System"),
            "action": act.action,
            "level": act.level_number,
            "comment": act.comment,
            "is_approval_action": True
        }))

    events_raw.sort(key=lambda x: x[0])
    events = [item[1] for item in events_raw]

    return success_response(data=events)
