"""
Priority 1: the calc_status / needs_recalc_review system.

This is the highest-risk, least-tested code in the app per README's Known
Gaps -- the same 3-pass dependency resolution logic is independently
reimplemented five times across SUBMIT/APPROV, and recalculate_submission_formulas
is the one canonical implementation among them worth pinning down first.
"""
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.SUBMIT.service import (
    CALC_STATUS_ERROR,
    CALC_STATUS_OK,
    CALC_STATUS_PENDING,
    _build_fields_map,
    recalculate_submission_formulas,
)


def _fields_map(form_version):
    return _build_fields_map(get_form_version_fields(form_version.id))


class TestRecalculateSubmissionFormulas:
    def test_two_level_dependency_chain_resolves(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value,
    ):
        form, form_version = make_form()
        # field_c = field_a + field_b (level 1), field_d = field_c * 2 (level 2, depends on field_c)
        formula_c = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        formula_d = make_formula_version("field_c * 2", {"field_c": {}})

        field_a, _ = make_field(form, form_version, "field_a", field_type="number")
        field_b, _ = make_field(form, form_version, "field_b", field_type="number")
        field_c, _ = make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula_c.id})
        field_d, _ = make_field(form, form_version, "field_d", field_type="calculated", field_config={"formula_version_id": formula_d.id})

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        submission = make_submission(site, form, form_version, period, workflow_version)

        from app.modules.FORMBLD.model import FieldVersion

        fv_a = FieldVersion.query.get(field_a.current_version_id)
        fv_b = FieldVersion.query.get(field_b.current_version_id)
        make_submission_value(submission, field_a, fv_a, raw_value="10")
        make_submission_value(submission, field_b, fv_b, raw_value="4")

        fields_map = _fields_map(form_version)
        errors, values_by_field_id = recalculate_submission_formulas(submission, fields_map, approver.id)

        assert errors == {}
        assert values_by_field_id[field_c.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_c.id].calculated_value) == 14.0
        assert values_by_field_id[field_d.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_d.id].calculated_value) == 28.0

    def test_unknown_field_reference_returns_error(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission,
    ):
        form, form_version = make_form()
        # References a field code that doesn't exist on this form -- simulates a
        # deleted/renamed field a published formula still points at.
        formula = make_formula_version("deleted_field + 1", {"deleted_field": {}})
        field_c, _ = make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula.id})

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        submission = make_submission(site, form, form_version, period, workflow_version)

        fields_map = _fields_map(form_version)
        errors, values_by_field_id = recalculate_submission_formulas(submission, fields_map, approver.id)

        assert "field_c" in errors
        assert "Unknown formula variable" in errors["field_c"]
        assert values_by_field_id[field_c.id].calc_status == CALC_STATUS_ERROR

    def test_blank_upstream_input_returns_pending_not_error(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission,
    ):
        form, form_version = make_form()
        formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        make_field(form, form_version, "field_a", field_type="number")
        make_field(form, form_version, "field_b", field_type="number")
        field_c, _ = make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula.id})

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        # No SubmissionValue rows created for field_a/field_b at all -- genuinely blank.
        submission = make_submission(site, form, form_version, period, workflow_version)

        fields_map = _fields_map(form_version)
        errors, values_by_field_id = recalculate_submission_formulas(submission, fields_map, approver.id)

        assert "field_c" not in errors
        assert values_by_field_id[field_c.id].calc_status == CALC_STATUS_PENDING
        assert values_by_field_id[field_c.id].calculated_value is None
