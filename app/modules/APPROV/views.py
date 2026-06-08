from flask import Blueprint, render_template, request
from app.database import db
from app.common.auth import current_user, require_login
from app.common.permissions import has_permission
from app.common.responses import success_response, error_response
from app.modules.ACCESS.model import AccessMatrix
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.APPROV.model import ApprovalAction, Issue
from app.modules.APPROV.service import (
    get_approver_queue,
    get_actioned_history,
    approve_submission,
    request_changes_submission,
    reject_submission,
    raise_issue,
    resolve_issue
)
from app.modules.SUBMIT.service import format_period_label

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
    if not _can_review_submission(user, submission, "approve", "reject"):
        return _page_no_access()
    return render_template(
        "modules/APPROV/submission_review.html",
        module_code=MODULE_CODE,
        submission_id=submission.id
    )

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
        values_data = {}
        for val in db_values:
            values_data[val.field_id] = {
                "raw_value": val.raw_value,
                "calculated_value": float(val.calculated_value) if val.calculated_value is not None else None
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

        from app.common.permissions import has_permission
        can_resubmit = (
            submission.status == "Changes Requested" and (
                has_permission(user.id, "submission", "create", scope_site_id=submission.site_id) or
                has_permission(user.id, "submission", "submit", scope_site_id=submission.site_id)
            )
        )

        metadata = {
            "submission_id": submission.id,
            "form_name": form.name if form else "",
            "site_name": site.name if site else "",
            "period_label": format_period_label(period.year, period.month) if period else "",
            "status": submission.status,
            "current_level": submission.current_level,
            "submitted_by": User.query.get(submission.submitted_by).full_name if submission.submitted_by else "",
            "submitted_at": submission.submitted_at,
            "can_resubmit": can_resubmit
        }

        return success_response(data={
            "metadata": metadata,
            "fields": fields_data,
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
