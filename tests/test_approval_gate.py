"""
Priority 1 (continued): needs_recalc_review at submit time, and the
final-approval gate that checks it (plus Issue / SubmissionValueIssue,
covered in test_regressions.py).
"""
import pytest

from app.modules.APPROV.service import approve_submission, clear_recalc_review, request_changes_submission
from app.modules.SUBMIT.service import submit_submission


def _grant(make_access_grant, user, site, action_flag):
    make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, **{action_flag: True})


@pytest.fixture()
def broken_calc_submission(
    make_form, make_field, make_formula_version, make_site, make_reporting_period,
    make_workflow, make_user, make_submission, make_access_grant,
):
    """
    A Draft submission with one raw field filled and one calculated field whose
    formula references a field code that doesn't exist -- guaranteed CALC_STATUS_ERROR,
    but the raw data is otherwise complete, so submit_submission should still succeed
    per the calc/raw-data decoupling (see README's SUBMIT section).
    """
    form, form_version = make_form()
    formula = make_formula_version("missing_field + 1", {"missing_field": {}})
    make_field(form, form_version, "field_a", field_type="number")
    field_c, _ = make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula.id})

    submitter = make_user()
    approver = make_user()
    site = make_site()
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])

    _grant(make_access_grant, submitter, site, "can_submit")
    _grant(make_access_grant, submitter, site, "can_edit")
    _grant(make_access_grant, approver, site, "can_approve")

    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")

    return {
        "form": form,
        "form_version": form_version,
        "field_c": field_c,
        "formula": formula,
        "submitter": submitter,
        "approver": approver,
        "site": site,
        "period": period,
        "workflow_version": workflow_version,
        "submission": submission,
    }


class TestNeedsRecalcReviewAtSubmit:
    def test_calc_error_sets_needs_recalc_review_true(
        self, make_submission_value, broken_calc_submission,
    ):
        ctx = broken_calc_submission
        from app.modules.FORMBLD.model import Field, FieldVersion

        field_a = Field.query.filter_by(form_id=ctx["form"].id, field_code="field_a").one()
        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(ctx["submission"], field_a, fv_a, raw_value="7")

        result = submit_submission(ctx["submission"].id, ctx["submitter"].id)
        submission = ctx["submission"]

        assert submission.status == "Submitted"
        assert submission.needs_recalc_review is True
        assert result["needs_recalc_review"] is True

    def test_clean_resolution_keeps_needs_recalc_review_false(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value, make_access_grant,
    ):
        form, form_version = make_form()
        formula = make_formula_version("field_a + 1", {"field_a": {}})
        make_field(form, form_version, "field_a", field_type="number")
        make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula.id})

        submitter = make_user()
        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        _grant(make_access_grant, submitter, site, "can_submit")
        _grant(make_access_grant, approver, site, "can_approve")

        submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")

        from app.modules.FORMBLD.model import Field, FieldVersion

        field_a = Field.query.filter_by(form_id=form.id, field_code="field_a").one()
        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(submission, field_a, fv_a, raw_value="7")

        submit_submission(submission.id, submitter.id)

        assert submission.status == "Submitted"
        assert submission.needs_recalc_review is False


class TestFinalApprovalGate:
    def test_blocked_while_needs_recalc_review_true(self, make_submission_value, broken_calc_submission, db_session):
        ctx = broken_calc_submission
        from app.modules.FORMBLD.model import Field, FieldVersion

        field_a = Field.query.filter_by(form_id=ctx["form"].id, field_code="field_a").one()
        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(ctx["submission"], field_a, fv_a, raw_value="7")
        submit_submission(ctx["submission"].id, ctx["submitter"].id)
        # Commit here to mirror two separate real requests (submit, then later
        # approve) each with their own commit/rollback lifecycle -- otherwise
        # the rollback below would undo the submission's creation along with
        # the failed approval, since neither was ever actually committed.
        db_session.commit()

        with pytest.raises(ValueError, match="needs recalculation review"):
            approve_submission(ctx["submission"].id, ctx["approver"].id)
        # approve_submission doesn't commit itself (callers do) -- it had already
        # flushed an "advance to Under Review" state change before hitting the
        # gate, same as the real view layer, which rolls back on this exact
        # ValueError. Mirror that here rather than asserting on an uncommitted,
        # never-rolled-back intermediate state no real caller would see.
        db_session.rollback()

        assert ctx["submission"].status == "Submitted"
        assert ctx["submission"].is_locked is False

    def test_clear_recalc_review_then_approve_succeeds(self, make_submission_value, broken_calc_submission):
        ctx = broken_calc_submission
        from app.modules.FORMBLD.model import Field, FieldVersion

        field_a = Field.query.filter_by(form_id=ctx["form"].id, field_code="field_a").one()
        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(ctx["submission"], field_a, fv_a, raw_value="7")
        submit_submission(ctx["submission"].id, ctx["submitter"].id)

        clear_recalc_review(ctx["submission"].id, ctx["approver"].id)
        assert ctx["submission"].needs_recalc_review is False

        approve_submission(ctx["submission"].id, ctx["approver"].id)
        assert ctx["submission"].status == "Approved"
        assert ctx["submission"].is_locked is True

    def test_resubmission_after_fix_clears_flag_automatically(self, make_submission_value, broken_calc_submission, created_objects, db_session):
        ctx = broken_calc_submission
        from app.modules.FORMBLD.model import Field, FieldVersion

        field_a = Field.query.filter_by(form_id=ctx["form"].id, field_code="field_a").one()
        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(ctx["submission"], field_a, fv_a, raw_value="7")
        submit_submission(ctx["submission"].id, ctx["submitter"].id)
        assert ctx["submission"].needs_recalc_review is True

        # Reviewer sends it back for changes.
        request_changes_submission(ctx["submission"].id, ctx["approver"].id, "Please fix the calculated field.")
        assert ctx["submission"].status == "Changes Requested"

        # The fix: point field_c's formula at a version that actually resolves,
        # simulating a corrected formula reference.
        fixed_formula = ctx["formula"]
        from app.modules.FRMULA.model import FormulaVersion

        fixed = FormulaVersion(
            formula_id=fixed_formula.formula_id,
            version_number=2,
            expression="field_a + 1",
            tokens={"field_a": {}},
            created_by=fixed_formula.created_by,
        )
        db_session.add(fixed)
        db_session.flush()
        created_objects.append(fixed)

        field_c_version = FieldVersion.query.get(ctx["field_c"].current_version_id)
        field_c_version.field_config = {"formula_version_id": fixed.id}
        db_session.flush()

        submit_submission(ctx["submission"].id, ctx["submitter"].id)

        assert ctx["submission"].status == "Resubmitted"
        assert ctx["submission"].needs_recalc_review is False
