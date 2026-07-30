from datetime import datetime, timezone

from app.database import db
from app.modules.APPROV.model import ApprovalAction
from app.modules.APPROV.service import approve_submission, request_changes_submission
from app.modules.NOTIFY.model import Notification, NotificationConfig
from app.modules.SUBMIT.service import get_spoc_sheets_buckets, submit_submission
from app.modules.WFLWBLD.model import Workflow, WorkflowLevel, WorkflowLevelApprover, WorkflowVersion


def _two_level_workflow(approver, final_approver, system_user, created_objects):
    workflow = Workflow(
        name=f"Two Level Workflow {approver.id}",
        code=f"two-level-{approver.id}-{final_approver.id}",
        created_by=system_user,
        updated_by=system_user,
    )
    db.session.add(workflow)
    db.session.flush()
    created_objects.append(workflow)

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        published_at=datetime.now(timezone.utc),
        created_by=system_user,
    )
    db.session.add(version)
    db.session.flush()
    created_objects.append(version)
    workflow.current_version_id = version.id

    levels = []
    for number, user in ((1, approver), (2, final_approver)):
        level = WorkflowLevel(
            workflow_version_id=version.id,
            level_number=number,
            level_name=f"Level {number}",
            approval_mode="ANY_ONE",
            created_by=system_user,
            updated_by=system_user,
        )
        db.session.add(level)
        db.session.flush()
        created_objects.append(level)
        assignment = WorkflowLevelApprover(
            workflow_level_id=level.id,
            user_id=user.id,
            created_by=system_user,
            updated_by=system_user,
        )
        db.session.add(assignment)
        db.session.flush()
        created_objects.append(assignment)
        levels.append(level)

    db.session.flush()
    return version


def _notification_config(event_type, system_user, created_objects):
    config = NotificationConfig(
        name=f"Test {event_type}",
        event_type=event_type,
        message_template="{message}",
        recipient_type="dynamic",
        dynamic_role="spoc",
        channels="in_app",
        is_active=True,
        created_by=system_user,
        updated_by=system_user,
    )
    db.session.add(config)
    db.session.flush()
    created_objects.append(config)
    return config


def test_two_level_approval_emits_notifications_and_updates_spoc_bucket_status(
    make_user, make_site, make_form, make_field, make_reporting_period,
    make_access_grant, make_workbook, make_submission, make_submission_value,
    db_session, created_objects, system_user,
):
    submitter = make_user(full_name="SPOC Test User")
    level_one_approver = make_user(full_name="Approver Test User")
    final_approver = make_user(full_name="Final Approver Test User")
    site = make_site(name="Level Notification Site", code="SITE_LVL")
    form, form_version = make_form()
    field, field_version = make_field(form, form_version, "field_a")
    period = make_reporting_period(site, year=2026, month=6)
    workflow_version = _two_level_workflow(level_one_approver, final_approver, system_user, created_objects)
    make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])

    make_access_grant(
        submitter, "submission", scope_type="site", scope_site_id=site.id,
        can_create=True, can_submit=True, can_view=True, can_edit=True,
    )
    make_access_grant(
        level_one_approver, "submission", scope_type="site", scope_site_id=site.id,
        can_approve=True, can_reject=True, can_view=True,
    )
    make_access_grant(
        final_approver, "submission", scope_type="site", scope_site_id=site.id,
        can_approve=True, can_reject=True, can_view=True,
    )
    _notification_config("SUBMISSION_LEVEL_APPROVED", system_user, created_objects)
    _notification_config("SUBMISSION_APPROVED", system_user, created_objects)

    submission = make_submission(
        site, form, form_version, period, workflow_version,
        status="Draft", submitted_by=submitter, current_level=1,
    )
    make_submission_value(submission, field, field_version, raw_value="123")

    submit_submission(submission.id, submitter.id)
    db_session.commit()
    assert submission.status == "Submitted"
    assert submission.current_level == 1

    approve_submission(submission.id, level_one_approver.id, comment="Approved Level 1")
    db_session.commit()

    assert submission.status == "Under Review"
    assert submission.current_level == 2

    level_notification = Notification.query.filter_by(
        user_id=submitter.id,
        event_type="SUBMISSION_LEVEL_APPROVED",
        entity_type="submission",
        entity_id=submission.id,
    ).order_by(Notification.id.desc()).first()
    assert level_notification is not None
    assert level_notification.message == (
        f"Your submission for {form.name} ({site.name}) has been approved at Level 1."
    )
    created_objects.append(level_notification)

    buckets = get_spoc_sheets_buckets(submitter.id)
    bucket_item = next(
        item for item in buckets["submitted"]
        if item["submission_id"] == submission.id
    )
    assert bucket_item["status"] == "Under Review"
    assert bucket_item["status_text"] == "Under review"

    request_changes_submission(submission.id, final_approver.id, comment="Need correction in data entries")
    db_session.commit()
    submit_submission(submission.id, submitter.id)
    db_session.commit()

    assert submission.status == "Resubmitted"
    assert submission.current_level == 1
    first_level_action = ApprovalAction.query.filter_by(
        submission_id=submission.id,
        level_number=1,
        action="Approve",
    ).order_by(ApprovalAction.id.asc()).first()
    assert first_level_action.is_deleted is True

    approve_submission(submission.id, level_one_approver.id, comment="Approved Level 1 again")
    db_session.commit()
    approve_submission(submission.id, final_approver.id, comment="Approved Level 2")
    db_session.commit()

    assert submission.status == "Approved"
    assert submission.is_locked is True

    final_notification = Notification.query.filter_by(
        user_id=submitter.id,
        event_type="SUBMISSION_APPROVED",
        entity_type="submission",
        entity_id=submission.id,
    ).order_by(Notification.id.desc()).first()
    assert final_notification is not None
    assert final_notification.message == f"Your submission for {form.name} ({site.name}) has been approved."
    created_objects.append(final_notification)
