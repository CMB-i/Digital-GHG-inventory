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
