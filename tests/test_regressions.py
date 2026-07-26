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
    """remove_site_from_workbook used to hard-delete the WorkbookSite row with
    no dependency check at all, even though deactivate_workbook (same
    dependency graph, whole-workbook scope) already blocks on in-progress
    submissions. This narrower removal must get the same guard, scoped to the
    specific site being removed.

    (remove_sheet_from_workbook, formerly tested alongside this, was removed
    when "Reuse existing sheet" and standalone sheet detachment were retired
    -- a sheet can no longer be detached from a workbook without deleting it
    outright; see delete_sheet in FORMBLD/service.py and its own tests.)"""

    def _setup(self, make_form, make_site, make_reporting_period, make_workflow, make_workbook):
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        workbook = make_workbook(form, site)
        return form, form_version, site, period, workflow_version, workbook

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


class TestSiteDeactivationBlockedByInProgressSubmissions:
    """deactivate_site used to have no dependency check at all -- just an
    existence check before flipping is_deleted. It must get the same
    in-progress-submission guard deactivate_workbook already has."""

    def _setup(self, make_form, make_site, make_reporting_period, make_workflow):
        form, form_version = make_form()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([])
        return form, form_version, site, period, workflow_version

    def test_deactivate_blocked_when_in_progress_submission_exists(
        self, make_form, make_site, make_reporting_period, make_workflow, make_submission, make_user,
    ):
        from app.modules.SITEMST.model import Site
        from app.modules.SITEMST.service import deactivate_site

        form, form_version, site, period, workflow_version = self._setup(
            make_form, make_site, make_reporting_period, make_workflow
        )
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Submitted")

        with pytest.raises(ValueError, match="Cannot deactivate site"):
            deactivate_site(site.id, actor.id)

        assert Site.query.filter_by(id=site.id, is_deleted=False).first() is not None

    def test_deactivate_succeeds_when_no_in_progress_submission(
        self, make_form, make_site, make_reporting_period, make_workflow, make_submission, make_user,
    ):
        from app.modules.SITEMST.model import Site
        from app.modules.SITEMST.service import deactivate_site

        form, form_version, site, period, workflow_version = self._setup(
            make_form, make_site, make_reporting_period, make_workflow
        )
        actor = make_user()
        make_submission(site, form, form_version, period, workflow_version, status="Approved")

        deactivated = deactivate_site(site.id, actor.id)

        assert deactivated is not None
        assert Site.query.filter_by(id=site.id, is_deleted=False).first() is None


class TestValueSetDeleteBlockedByActiveFieldReference:
    """delete_value_set used to require only a reason string and existence --
    no check for FieldVersion.field_config["value_set_version_id"] usage,
    since that's a JSON key, not a real FK."""

    def _make_value_set_version(self, db_session, system_user, author, code_suffix, status="Approved"):
        from app.modules.VALSET.model import ValueSet, ValueSetVersion

        vs = ValueSet(name="Test VS", code=f"test-vs-{code_suffix}", created_by=system_user, updated_by=system_user)
        db_session.add(vs)
        db_session.flush()

        version = ValueSetVersion(
            value_set_id=vs.id, version_number=1, status=status,
            effective_from=date.today(), created_by=author.id,
        )
        db_session.add(version)
        db_session.flush()
        return vs, version

    def test_delete_blocked_when_active_field_references_the_value_set(
        self, make_user, make_form, make_field, db_session, system_user,
    ):
        from app.modules.VALSET.service import delete_value_set

        author = make_user()
        vs, version = self._make_value_set_version(db_session, system_user, author, f"del-{author.id}")

        form, form_version = make_form()
        make_field(
            form, form_version, "dropdown_field", field_type="dropdown",
            field_config={"value_set_version_id": version.id},
        )

        with pytest.raises(ValueError, match="Cannot delete value set"):
            delete_value_set(vs.id, author.id, "no longer needed")

        db_session.delete(version)
        db_session.delete(vs)

    def test_delete_succeeds_when_no_field_references_the_value_set(
        self, make_user, db_session, system_user,
    ):
        from app.modules.VALSET.service import delete_value_set

        author = make_user()
        vs, version = self._make_value_set_version(db_session, system_user, author, f"del-ok-{author.id}")

        deleted = delete_value_set(vs.id, author.id, "no longer needed")

        assert deleted.is_deleted is True

        db_session.delete(version)
        db_session.delete(vs)


class TestValueSetEntryEditRequiresDraftVersion:
    """add_or_update_entries used to replace all entries for a version
    regardless of status, including an already-Approved version in active
    use. Entry edits must be restricted to Draft versions, mirroring
    FORMBLD.save_form_draft_fields' Draft-only convention."""

    def _make_value_set_version(self, db_session, system_user, author, code_suffix, status):
        from app.modules.VALSET.model import ValueSet, ValueSetVersion

        vs = ValueSet(name="Test VS", code=f"test-vs-{code_suffix}", created_by=system_user, updated_by=system_user)
        db_session.add(vs)
        db_session.flush()

        version = ValueSetVersion(
            value_set_id=vs.id, version_number=1, status=status,
            effective_from=date.today(), created_by=author.id,
        )
        db_session.add(version)
        db_session.flush()
        return vs, version

    def test_entries_blocked_on_approved_version(self, make_user, db_session, system_user):
        from app.modules.VALSET.service import add_or_update_entries

        author = make_user()
        vs, version = self._make_value_set_version(db_session, system_user, author, f"entries-{author.id}", "Approved")

        with pytest.raises(ValueError, match="Draft version"):
            add_or_update_entries(version.id, [{"entry_code": "a", "entry_label": "A"}], author.id)

        db_session.delete(version)
        db_session.delete(vs)

    def test_entries_succeed_on_draft_version(self, make_user, db_session, system_user):
        from app.modules.VALSET.service import add_or_update_entries

        author = make_user()
        vs, version = self._make_value_set_version(db_session, system_user, author, f"entries-ok-{author.id}", "Draft")

        entries = add_or_update_entries(version.id, [{"entry_code": "a", "entry_label": "A"}], author.id)

        assert len(entries) == 1
        assert entries[0].entry_code == "a"

        for e in entries:
            db_session.delete(e)
        vs.current_version_id = None
        db_session.flush()
        db_session.delete(version)
        db_session.delete(vs)


class TestFormulaPublishFieldScopedToOwnForm:
    """publish_formula_version used to validate tokens against every active
    Field in the system, despite field_code only being unique per-form -- so
    a formula could publish while referencing a field code that actually
    belongs to a different sheet. Validation must be scoped to the formula's
    own form_id."""

    def test_publish_fails_when_token_belongs_to_a_different_form(
        self, make_form, make_field, make_user, db_session, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        own_form, _own_form_version = make_form()
        other_form, other_form_version = make_form()
        make_field(other_form, other_form_version, "shared_code")

        user = make_user()
        formula = create_formula(
            "Test Formula", f"test-scope-{user.id}", "shared_code + 1",
            {"shared_code": {}}, user.id, form_id=own_form.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        with pytest.raises(ValueError, match="does not exist as an active field"):
            publish_formula_version(version.id, user.id)

    def test_publish_succeeds_when_token_belongs_to_the_formulas_own_form(
        self, make_form, make_field, make_user, db_session, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        own_form, own_form_version = make_form()
        make_field(own_form, own_form_version, "own_code")

        user = make_user()
        formula = create_formula(
            "Test Formula", f"test-scope-ok-{user.id}", "own_code + 1",
            {"own_code": {}}, user.id, form_id=own_form.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        publish_formula_version(version.id, user.id)

        assert version.published_at is not None
        assert formula.current_version_id == version.id


class TestFormulaReportContext:
    """Formula.context lets the same Formula/FormulaVersion tables and the
    same publish_formula_version/evaluate_formula functions serve RPTBLD's
    report-level formulas, not just FORMBLD's field-level ones. A
    context="report" formula's tokens validate against a fixed canonical
    metric vocabulary (plus "{group_id}__{metric_key}" group-subtotal
    references, checked by shape only -- confirming the group_id exists in a
    given ReportTemplate's config_json is RPTBLD's job in a later phase, not
    FRMULA's here) instead of Field.field_code/ValueSetEntry.entry_code."""

    def test_create_formula_defaults_to_field_context(self, make_user, created_objects):
        from app.modules.FRMULA.service import create_formula

        user = make_user()
        formula = create_formula(
            "Default Context Formula", f"test-default-ctx-{user.id}", "1 + 1", {}, user.id,
        )
        created_objects.append(formula)

        assert formula.context == "field"

    def test_report_context_formula_publishes_with_canonical_metric_tokens(
        self, make_user, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        user = make_user()
        formula = create_formula(
            "Total GHG Ratio", f"test-report-ctx-ok-{user.id}", "scope1 + scope2",
            {"scope1": {}, "scope2": {}}, user.id, context="report",
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        publish_formula_version(version.id, user.id)

        assert version.published_at is not None
        assert formula.current_version_id == version.id

    def test_report_context_formula_publishes_with_group_subtotal_token(
        self, make_user, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        user = make_user()
        formula = create_formula(
            "Core Group GHG", f"test-report-ctx-group-{user.id}", "core__total_ghg + 1",
            {"core__total_ghg": {}}, user.id, context="report",
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        publish_formula_version(version.id, user.id)

        assert version.published_at is not None

    def test_report_context_formula_publish_fails_on_unrecognized_token(
        self, make_user, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        user = make_user()
        formula = create_formula(
            "Bogus Metric", f"test-report-ctx-bad-{user.id}", "not_a_real_metric + 1",
            {"not_a_real_metric": {}}, user.id, context="report",
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        with pytest.raises(ValueError, match="not a recognized report metric"):
            publish_formula_version(version.id, user.id)

    def test_field_context_publish_behavior_is_unchanged_by_report_context_addition(
        self, make_form, make_field, make_user, created_objects,
    ):
        """Regression guard: a default (context="field") formula's create/
        publish/evaluate roundtrip -- including the still-active field/value-set
        token cross-check -- behaves identically to before the context column
        existed."""
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version, evaluate_formula

        own_form, own_form_version = make_form()
        make_field(own_form, own_form_version, "field_ctx_code")

        user = make_user()
        formula = create_formula(
            "Field Context Formula", f"test-field-ctx-{user.id}", "field_ctx_code + 1",
            {"field_ctx_code": {}}, user.id, form_id=own_form.id,
        )
        created_objects.append(formula)
        assert formula.context == "field"

        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)

        publish_formula_version(version.id, user.id)
        assert version.published_at is not None
        assert formula.current_version_id == version.id

        result = evaluate_formula(version.expression, {"field_ctx_code": 5})
        assert result == 6

        # A token that isn't a live field/value-set code still fails exactly
        # like before, even though report-context tokens now exist.
        bad_formula = create_formula(
            "Field Context Bad Token", f"test-field-ctx-bad-{user.id}", "scope1 + 1",
            {"scope1": {}}, user.id, form_id=own_form.id,
        )
        created_objects.append(bad_formula)
        bad_version = FormulaVersion.query.filter_by(formula_id=bad_formula.id, version_number=1).one()
        created_objects.append(bad_version)

        with pytest.raises(ValueError, match="does not exist as an active field"):
            publish_formula_version(bad_version.id, user.id)


class TestFieldRemovalBlockedByFormulaReference:
    """save_form_draft_fields soft-deletes any field omitted from a draft-save
    payload with no check for whether a published Formula's tokens still
    reference it -- FormulaVersion.tokens has no FK to Field (raw JSON), so
    this can't be caught by the database. Must block outright, same as every
    other entity in this delete work (Site, Period, Sheet, Value Set), not
    just warn and let the removal through anyway."""

    def _draft_version_id(self, form, user, created_objects):
        # make_form() returns a Published version -- save_form_draft_fields
        # only accepts a Draft one, so give each test a real draft version to
        # save against (create_new_form_version_draft is the same helper
        # "Edit as Draft" in the Sheet Builder uses).
        from app.modules.FORMBLD.service import create_new_form_version_draft

        draft_version = create_new_form_version_draft(form.id, user.id)
        created_objects.append(draft_version)
        return draft_version.id

    def _publish_formula(self, make_user, created_objects, form, expression, tokens, name, code_suffix):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        user = make_user()
        formula = create_formula(
            name, f"test-field-delete-{code_suffix}", expression,
            tokens, user.id, form_id=form.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)
        publish_formula_version(version.id, user.id)
        return formula, version

    def test_field_removal_blocked_when_an_active_formula_references_it(
        self, make_form, make_field, make_user, created_objects,
    ):
        from app.modules.FORMBLD.model import Field
        from app.modules.FORMBLD.service import save_form_draft_fields

        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        formula, _version = self._publish_formula(
            make_user, created_objects, form, "field_a + 1", {"field_a": {}},
            "Diesel Emissions", "a",
        )
        actor = make_user()
        draft_version_id = self._draft_version_id(form, actor, created_objects)

        with pytest.raises(ValueError, match=formula.name):
            save_form_draft_fields(draft_version_id, [], actor.id)

        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is not None

    def test_field_removal_succeeds_when_no_formula_references_it(
        self, make_form, make_field, make_user, created_objects,
    ):
        from app.modules.FORMBLD.model import Field
        from app.modules.FORMBLD.service import save_form_draft_fields

        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        actor = make_user()
        draft_version_id = self._draft_version_id(form, actor, created_objects)

        save_form_draft_fields(draft_version_id, [], actor.id)

        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is None

    def test_batch_draft_save_blocks_and_reports_every_referenced_field(
        self, make_form, make_field, make_user, created_objects,
    ):
        """Two fields, each referenced by a different published formula, both
        omitted in the same save -- the error must name both formulas, and
        neither field (nor an unrelated third, harmlessly-omitted field) may
        end up partially deleted -- the whole batch fails together."""
        from app.modules.FORMBLD.model import Field
        from app.modules.FORMBLD.service import save_form_draft_fields

        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "field_a")
        field_b, _fvb = make_field(form, form_version, "field_b")
        field_c, _fvc = make_field(form, form_version, "field_c")
        formula_1, _v1 = self._publish_formula(
            make_user, created_objects, form, "field_a + 1", {"field_a": {}},
            "Diesel Emissions", "b1",
        )
        formula_2, _v2 = self._publish_formula(
            make_user, created_objects, form, "field_b + 1", {"field_b": {}},
            "Grid Emissions", "b2",
        )
        actor = make_user()
        draft_version_id = self._draft_version_id(form, actor, created_objects)

        with pytest.raises(ValueError) as exc_info:
            save_form_draft_fields(draft_version_id, [], actor.id)

        message = str(exc_info.value)
        assert formula_1.name in message
        assert formula_2.name in message
        assert "field_a" in message
        assert "field_b" in message

        assert Field.query.filter_by(id=field_a.id, is_deleted=False).first() is not None
        assert Field.query.filter_by(id=field_b.id, is_deleted=False).first() is not None
        assert Field.query.filter_by(id=field_c.id, is_deleted=False).first() is not None


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
