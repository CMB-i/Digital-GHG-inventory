"""
Priority 3: regression tests for fixes made in this project's recent history
(per README's Known Gaps / Module Reference) -- pinning down behavior that
was silently wrong before and must not quietly regress.
"""
from datetime import date

import pytest

from app.common.permissions import has_permission


def _grant(make_access_grant, user, site, action_flag):
    make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, **{action_flag: True})


@pytest.fixture()
def approvable_submission(
    make_form, make_field, make_site, make_reporting_period, make_workflow, make_user,
    make_submission, make_access_grant, make_submission_value, db_session,
):
    """A Draft submission with one filled raw field and no calculated fields,
    ready to be moved to Submitted and then final-approved."""
    form, form_version = make_form()
    field_a, fva = make_field(form, form_version, "field_a", field_type="number")

    submitter = make_user()
    approver = make_user()
    site = make_site()
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])
    _grant(make_access_grant, submitter, site, "can_submit")
    _grant(make_access_grant, approver, site, "can_approve")

    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
    make_submission_value(submission, field_a, fva, raw_value="1")

    from app.modules.SUBMIT.service import submit_submission

    submit_submission(submission.id, submitter.id)
    db_session.commit()

    return {"submission": submission, "submitter": submitter, "approver": approver, "site": site}


class TestIssueBlocksApproval:
    def test_open_issue_blocks_final_approval(self, approvable_submission, db_session):
        from app.modules.APPROV.model import Issue
        from app.modules.APPROV.service import approve_submission

        ctx = approvable_submission
        issue = Issue(
            submission_id=ctx["submission"].id,
            field_id=None,
            raised_by=ctx["approver"].id,
            title="Looks off",
            description="Please double check this sheet.",
            status="Open",
            blocks_approval=True,
            created_by=ctx["approver"].id,
            updated_by=ctx["approver"].id,
        )
        db_session.add(issue)
        db_session.flush()

        with pytest.raises(ValueError, match="open issues blocking approval"):
            approve_submission(ctx["submission"].id, ctx["approver"].id)
        # Rolling back undoes both the failed approval's flushed state change
        # AND this issue's own (never-committed) creation in one step -- there
        # is nothing left in the DB to separately clean up afterward.
        db_session.rollback()
        assert ctx["submission"].status == "Submitted"

    def test_resolved_issue_does_not_block(self, approvable_submission, db_session):
        from app.modules.APPROV.model import Issue
        from app.modules.APPROV.service import approve_submission

        ctx = approvable_submission
        issue = Issue(
            submission_id=ctx["submission"].id,
            field_id=None,
            raised_by=ctx["approver"].id,
            title="Looks off",
            description="Please double check this sheet.",
            status="Resolved",
            blocks_approval=True,
            created_by=ctx["approver"].id,
            updated_by=ctx["approver"].id,
        )
        db_session.add(issue)
        db_session.flush()

        approve_submission(ctx["submission"].id, ctx["approver"].id)
        assert ctx["submission"].status == "Approved"

        db_session.delete(issue)


class TestSubmissionValueIssueBlocksApproval:
    def test_open_cell_issue_blocks_final_approval(self, approvable_submission, db_session):
        from app.modules.SUBMIT.model import SubmissionValue, SubmissionValueIssue
        from app.modules.APPROV.service import approve_submission

        ctx = approvable_submission
        value = SubmissionValue.query.filter_by(submission_id=ctx["submission"].id).first()
        issue = SubmissionValueIssue(
            submission_value_id=value.id,
            raised_by=ctx["approver"].id,
            issue_text="This cell looks wrong.",
            status="Open",
            blocks_approval=True,
            created_by=ctx["approver"].id,
            updated_by=ctx["approver"].id,
        )
        db_session.add(issue)
        db_session.flush()

        with pytest.raises(ValueError, match="open cell-level issues blocking approval"):
            approve_submission(ctx["submission"].id, ctx["approver"].id)
        # Same as above -- rollback undoes the failed approval and this
        # never-committed issue row together.
        db_session.rollback()
        assert ctx["submission"].status == "Submitted"

    def test_resolved_cell_issue_does_not_block(self, approvable_submission, db_session):
        from app.modules.SUBMIT.model import SubmissionValue, SubmissionValueIssue
        from app.modules.APPROV.service import approve_submission

        ctx = approvable_submission
        value = SubmissionValue.query.filter_by(submission_id=ctx["submission"].id).first()
        issue = SubmissionValueIssue(
            submission_value_id=value.id,
            raised_by=ctx["approver"].id,
            issue_text="This cell looks wrong.",
            status="Resolved",
            resolved_by=ctx["approver"].id,
            blocks_approval=True,
            created_by=ctx["approver"].id,
            updated_by=ctx["approver"].id,
        )
        db_session.add(issue)
        db_session.flush()

        approve_submission(ctx["submission"].id, ctx["approver"].id)
        assert ctx["submission"].status == "Approved"

        db_session.delete(issue)


class TestValsetSelfApprovalBlocked:
    def _make_value_set(self, db_session, system_user, author):
        from app.modules.VALSET.model import ValueSet, ValueSetVersion

        vs = ValueSet(name="Test VS", code=f"test-vs-{author.id}", created_by=system_user, updated_by=system_user)
        db_session.add(vs)
        db_session.flush()

        draft = ValueSetVersion(value_set_id=vs.id, version_number=1, status="Draft", effective_from=date.today(), created_by=author.id)
        submitted = ValueSetVersion(value_set_id=vs.id, version_number=2, status="Submitted", effective_from=date.today(), created_by=author.id, submitted_by=author.id)
        db_session.add_all([draft, submitted])
        db_session.flush()
        return vs, draft, submitted

    def test_self_approval_blocked_on_draft_via_publish_path(self, make_user, db_session, system_user):
        from app.modules.VALSET.service import approve_value_set_version

        author = make_user()
        vs, draft, submitted = self._make_value_set(db_session, system_user, author)

        with pytest.raises(ValueError, match="cannot be the same user"):
            approve_value_set_version(draft.id, author.id)

        db_session.delete(submitted)
        db_session.delete(draft)
        vs.current_version_id = None
        db_session.flush()
        db_session.delete(vs)

    def test_self_approval_blocked_on_submitted_via_approve_path(self, make_user, db_session, system_user):
        from app.modules.VALSET.service import approve_value_set_version

        author = make_user()
        vs, draft, submitted = self._make_value_set(db_session, system_user, author)

        with pytest.raises(ValueError, match="cannot be the same user"):
            approve_value_set_version(submitted.id, author.id)

        db_session.delete(submitted)
        db_session.delete(draft)
        vs.current_version_id = None
        db_session.flush()
        db_session.delete(vs)

    def test_different_reviewer_can_approve(self, make_user, db_session, system_user):
        from app.modules.VALSET.service import approve_value_set_version

        author = make_user()
        reviewer = make_user()
        vs, draft, submitted = self._make_value_set(db_session, system_user, author)

        approve_value_set_version(submitted.id, reviewer.id)
        assert submitted.status == "Approved"
        assert submitted.approved_by == reviewer.id

        db_session.delete(draft)
        vs.current_version_id = None
        db_session.flush()
        db_session.delete(submitted)
        db_session.delete(vs)


class TestWildcardGrantIncludedInScoping:
    def test_rptbld_wildcard_grant_included_in_allowed_sites(self, make_user, make_access_grant, make_site):
        from app.modules.RPTBLD.service import _get_user_allowed_sites

        user = make_user()
        site = make_site()
        make_access_grant(user, "all", scope_type="site", scope_site_id=site.id, can_view=True)

        allowed_site_ids, is_global = _get_user_allowed_sites(user.id, "report")
        assert site.id in allowed_site_ids
        assert is_global is False

    def test_notify_role_recipient_includes_wildcard_grant_holder(self, make_user, make_access_grant, make_site):
        from app.modules.NOTIFY.service import resolve_recipients
        from app.modules.NOTIFY.model import NotificationConfig

        user = make_user()
        site = make_site()
        make_access_grant(user, "all", scope_type="site", scope_site_id=site.id, can_approve=True)

        config = NotificationConfig(
            recipient_type="role",
            target_entity_type="submission",
            target_permission="approve",
        )
        recipients = resolve_recipients(config, "submission", 1, {"site_id": site.id})

        assert any(r.id == user.id for r in recipients)


class TestWorkbookChildRemovalChecks:
    """remove_sheet_from_workbook/remove_site_from_workbook used to hard-delete
    the WorkbookForm/WorkbookSite row with no dependency check at all, even
    though deactivate_workbook (same dependency graph, whole-workbook scope)
    already blocks on in-progress submissions. These narrower removals must
    get the same guard, scoped to the specific sheet/site being removed."""

    def _setup(self, make_form, make_site, make_reporting_period, make_workflow, make_workbook):
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site)
        return form, form_version, site, period, workflow_version, workbook

    def test_remove_sheet_blocked_when_in_progress_submission_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
    ):
        from app.modules.WKBK.model import WorkbookForm
        from app.modules.WKBK.service import remove_sheet_from_workbook

        form, form_version, site, period, workflow_version, workbook = self._setup(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook
        )
        make_submission(site, form, form_version, period, workflow_version, status="Submitted")

        with pytest.raises(ValueError, match="Cannot remove sheet"):
            remove_sheet_from_workbook(workbook.id, form.id)

        assert WorkbookForm.query.filter_by(workbook_id=workbook.id, form_id=form.id).first() is not None

    def test_remove_sheet_succeeds_when_no_in_progress_submission(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
    ):
        from app.modules.WKBK.model import WorkbookForm
        from app.modules.WKBK.service import remove_sheet_from_workbook

        form, form_version, site, period, workflow_version, workbook = self._setup(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook
        )
        make_submission(site, form, form_version, period, workflow_version, status="Approved")

        remove_sheet_from_workbook(workbook.id, form.id)

        assert WorkbookForm.query.filter_by(workbook_id=workbook.id, form_id=form.id).first() is None

    def test_remove_site_blocked_when_in_progress_submission_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
    ):
        from app.modules.WKBK.model import WorkbookSite
        from app.modules.WKBK.service import remove_site_from_workbook

        form, form_version, site, period, workflow_version, workbook = self._setup(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook
        )
        make_submission(site, form, form_version, period, workflow_version, status="Under Review")

        with pytest.raises(ValueError, match="Cannot remove site"):
            remove_site_from_workbook(workbook.id, site.id)

        assert WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).first() is not None

    def test_remove_site_succeeds_when_no_in_progress_submission(
        self, make_form, make_site, make_reporting_period, make_workflow, make_workbook, make_submission,
    ):
        from app.modules.WKBK.model import WorkbookSite
        from app.modules.WKBK.service import remove_site_from_workbook

        form, form_version, site, period, workflow_version, workbook = self._setup(
            make_form, make_site, make_reporting_period, make_workflow, make_workbook
        )
        make_submission(site, form, form_version, period, workflow_version, status="Rejected")

        remove_site_from_workbook(workbook.id, site.id)

        assert WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).first() is None


class TestNotificationDeliveryFailureRecorded:
    """
    Priority 3 continued: send_mock_email/send_mock_whatsapp used to only
    print() on failure -- no Notification row was ever created for those
    channels, so a failed email/WhatsApp send was invisible everywhere except
    a console nobody watches. Now every channel attempt (success or failure)
    persists a real, queryable Notification row via delivery_status/delivery_error.
    """

    def test_failed_email_send_persists_a_queryable_failure_record(
        self, make_user, db_session, created_objects, monkeypatch, system_user,
    ):
        from app.modules.NOTIFY.model import Notification, NotificationConfig, UserNotificationPreference
        from app.modules.NOTIFY import service as notify_service

        user = make_user()

        pref = UserNotificationPreference(
            user_id=user.id, pref_in_app=True, pref_desktop=False,
            pref_email=True, pref_whatsapp=False,
        )
        db_session.add(pref)
        db_session.flush()
        created_objects.append(pref)

        config = NotificationConfig(
            name="Test Email Config",
            event_type="TEST_EMAIL_EVENT",
            message_template="Hello {name}",
            recipient_type="users",
            recipient_user_ids=str(user.id),
            channels="email",
            is_active=True,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(config)
        db_session.flush()
        created_objects.append(config)

        monkeypatch.setattr(
            notify_service, "send_mock_email",
            lambda to_email, subject, body: (False, "SMTP connection refused"),
        )

        dispatched = notify_service.dispatch_notification_event(
            event_type="TEST_EMAIL_EVENT",
            entity_type="submission",
            entity_id=1,
            context={"name": "Test"},
        )

        assert len(dispatched) == 1
        assert dispatched[0].channel == "email"
        assert dispatched[0].delivery_status == "failed"
        assert dispatched[0].delivery_error == "SMTP connection refused"
        created_objects.append(dispatched[0])

        # Genuinely queryable, not just the in-memory return value.
        failed = Notification.query.filter_by(
            user_id=user.id, channel="email", delivery_status="failed",
        ).all()
        assert len(failed) == 1
        assert failed[0].delivery_error == "SMTP connection refused"

    def test_successful_email_send_still_records_sent_status(
        self, make_user, db_session, created_objects, monkeypatch, system_user,
    ):
        from app.modules.NOTIFY.model import NotificationConfig, UserNotificationPreference
        from app.modules.NOTIFY import service as notify_service

        user = make_user()

        pref = UserNotificationPreference(
            user_id=user.id, pref_in_app=True, pref_desktop=False,
            pref_email=True, pref_whatsapp=False,
        )
        db_session.add(pref)
        db_session.flush()
        created_objects.append(pref)

        config = NotificationConfig(
            name="Test Email Config Success",
            event_type="TEST_EMAIL_EVENT_OK",
            message_template="Hello {name}",
            recipient_type="users",
            recipient_user_ids=str(user.id),
            channels="email",
            is_active=True,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(config)
        db_session.flush()
        created_objects.append(config)

        monkeypatch.setattr(
            notify_service, "send_mock_email",
            lambda to_email, subject, body: (True, None),
        )

        dispatched = notify_service.dispatch_notification_event(
            event_type="TEST_EMAIL_EVENT_OK",
            entity_type="submission",
            entity_id=1,
            context={"name": "Test"},
        )

        assert len(dispatched) == 1
        assert dispatched[0].delivery_status == "sent"
        assert dispatched[0].delivery_error is None
        created_objects.append(dispatched[0])

    def test_notify_spoc_fallback_only_skips_when_something_actually_sent(
        self, make_form, make_field, make_site, make_reporting_period, make_workflow,
        make_user, make_submission, db_session, created_objects, monkeypatch, system_user,
    ):
        """
        notify_spoc's in-app fallback must fire based on whether anything was
        actually delivered, not merely attempted -- otherwise a channel that
        now persists a "failed" record (instead of silently vanishing) would
        wrongly look like "some result exists, skip the safety net."
        """
        from app.modules.NOTIFY.model import Notification, NotificationConfig, UserNotificationPreference
        from app.modules.NOTIFY import service as notify_service

        form, form_version = make_form()
        make_field(form, form_version, "field_a", field_type="number")
        submitter = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([make_user()])
        submission = make_submission(site, form, form_version, period, workflow_version, status="Submitted", submitted_by=submitter)

        pref = UserNotificationPreference(
            user_id=submitter.id, pref_in_app=True, pref_desktop=False,
            pref_email=True, pref_whatsapp=False,
        )
        db_session.add(pref)
        db_session.flush()
        created_objects.append(pref)

        config = NotificationConfig(
            name="Test SPOC Approved Email-only Config",
            event_type="SUBMISSION_APPROVED",
            message_template="{message}",
            recipient_type="dynamic",
            dynamic_role="spoc",
            channels="email",
            is_active=True,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(config)
        db_session.flush()
        created_objects.append(config)

        monkeypatch.setattr(
            notify_service, "send_mock_email",
            lambda to_email, subject, body: (False, "SMTP connection refused"),
        )

        result = notify_service.notify_spoc(submission.id, "APPROVED", "Your submission was approved.")

        # The only configured channel (email) failed -- the in-app fallback
        # must still fire so the submitter gets *something*.
        assert result is not None
        assert result.channel == "in_app"
        created_objects.append(result)

        in_app = Notification.query.filter_by(user_id=submitter.id, channel="in_app").all()
        assert len(in_app) == 1
