"""
Priority 1: the calc_status / needs_recalc_review system.

This is the highest-risk, least-tested code in the app per README's Known
Gaps. recalculate_submission_formulas is the persisted/authoritative entry
point into the shared resolve_calculated_fields resolver (also used by the
preview and sheet-result paths), so it's the one worth pinning down first.
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

    def test_circular_dependency_returns_error_not_pending(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission,
    ):
        form, form_version = make_form()
        # field_x depends on field_y and vice versa -- neither can ever resolve,
        # so both must surface as ERROR rather than being stuck at PENDING forever.
        formula_x = make_formula_version("field_y + 1", {"field_y": {}})
        formula_y = make_formula_version("field_x + 1", {"field_x": {}})
        field_x, _ = make_field(form, form_version, "field_x", field_type="calculated", field_config={"formula_version_id": formula_x.id}, display_order=10)
        field_y, _ = make_field(form, form_version, "field_y", field_type="calculated", field_config={"formula_version_id": formula_y.id}, display_order=20)

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        submission = make_submission(site, form, form_version, period, workflow_version)

        fields_map = _fields_map(form_version)
        errors, values_by_field_id = recalculate_submission_formulas(submission, fields_map, approver.id)

        assert "field_x" in errors
        assert "circular formula dependency" in errors["field_x"].lower()
        assert "field_y" in errors["field_x"]
        assert values_by_field_id[field_x.id].calc_status == CALC_STATUS_ERROR
        assert values_by_field_id[field_x.id].calculated_value is None

        assert "field_y" in errors
        assert "circular formula dependency" in errors["field_y"].lower()
        assert "field_x" in errors["field_y"]
        assert values_by_field_id[field_y.id].calc_status == CALC_STATUS_ERROR
        assert values_by_field_id[field_y.id].calculated_value is None

    def test_four_level_chain_resolves_in_one_pass_in_adversarial_order(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value,
    ):
        """
        field_e depends on field_d depends on field_c depends on field_b depends
        on field_a (a 4-level calculated-field chain) -- but display_order (and
        therefore fields_map iteration order) is set to the WORST case: the
        deepest-dependent field first, the base input last. The old hardcoded
        3-pass loop only propagates one dependency level per pass in this
        order, so field_e would still be stuck PENDING after 3 passes. The
        topological-order resolver must get this right in a single pass
        regardless of iteration order.
        """
        form, form_version = make_form()
        formula_b = make_formula_version("field_a * 2", {"field_a": {}})
        formula_c = make_formula_version("field_b * 2", {"field_b": {}})
        formula_d = make_formula_version("field_c * 2", {"field_c": {}})
        formula_e = make_formula_version("field_d * 2", {"field_d": {}})

        # display_order deliberately reversed relative to the dependency chain.
        field_e, _ = make_field(form, form_version, "field_e", field_type="calculated", field_config={"formula_version_id": formula_e.id}, display_order=10)
        field_d, _ = make_field(form, form_version, "field_d", field_type="calculated", field_config={"formula_version_id": formula_d.id}, display_order=20)
        field_c, _ = make_field(form, form_version, "field_c", field_type="calculated", field_config={"formula_version_id": formula_c.id}, display_order=30)
        field_b, _ = make_field(form, form_version, "field_b", field_type="calculated", field_config={"formula_version_id": formula_b.id}, display_order=40)
        field_a, _ = make_field(form, form_version, "field_a", field_type="number", display_order=50)

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        submission = make_submission(site, form, form_version, period, workflow_version)

        from app.modules.FORMBLD.model import FieldVersion

        fv_a = FieldVersion.query.get(field_a.current_version_id)
        make_submission_value(submission, field_a, fv_a, raw_value="3")

        fields_map = _fields_map(form_version)
        errors, values_by_field_id = recalculate_submission_formulas(submission, fields_map, approver.id)

        assert errors == {}
        assert values_by_field_id[field_b.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_b.id].calculated_value) == 6.0
        assert values_by_field_id[field_c.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_c.id].calculated_value) == 12.0
        assert values_by_field_id[field_d.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_d.id].calculated_value) == 24.0
        assert values_by_field_id[field_e.id].calc_status == CALC_STATUS_OK
        assert float(values_by_field_id[field_e.id].calculated_value) == 48.0
