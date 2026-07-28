"""
Priority 1: the calc_status / needs_recalc_review system.

This is the highest-risk, least-tested code in the app per README's Known
Gaps. recalculate_submission_formulas is the persisted/authoritative entry
point into the shared resolve_calculated_fields resolver (also used by the
preview and sheet-result paths), so it's the one worth pinning down first.
"""
from app.modules.FORMBLD.service import get_form_version_fields
from app.modules.SUBMIT.model import SubmissionValue
from app.modules.SUBMIT.service import (
    CALC_STATUS_ERROR,
    CALC_STATUS_OK,
    CALC_STATUS_PENDING,
    _build_fields_map,
    _compose_sheet_results,
    monthly_table_fields,
    _compute_preview_calculated_values,
    _field_payload,
    preview_formula_swap_impact,
    recalc_or_flag_submissions_for_formula_swap,
    recalculate_submission_formulas,
    synthesize_automatic_fy_totals,
)


def _make_draft_form_version(db_session, created_objects, system_user, form, version_number):
    from app.modules.FORMBLD.model import FormVersion

    version = FormVersion(form_id=form.id, version_number=version_number, status="Draft", created_by=system_user)
    db_session.add(version)
    db_session.flush()
    created_objects.append(version)
    return version


def _make_field_version(db_session, created_objects, system_user, field, form_version, version_number, field_type, field_config, field_name=None):
    from app.modules.FORMBLD.model import FieldVersion

    version = FieldVersion(
        field_id=field.id,
        version_number=version_number,
        field_name=field_name or field.field_code.replace("_", " ").title(),
        field_type=field_type,
        field_config=field_config or {},
        form_version_id=form_version.id,
        frequency="monthly",
        created_by=system_user,
        updated_by=system_user,
    )
    db_session.add(version)
    db_session.flush()
    created_objects.append(version)
    return version


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


class TestComposeSheetResultsPartialAggregates:
    """
    _compose_sheet_results / SUM_MONTHS: an FY aggregate now computes a
    partial result from whatever months are present instead of refusing to
    compute at all, unless the field's blank_policy is explicitly "strict".

    Scoped to cross-month aggregation only -- resolve_calculated_fields
    (row-level formulas like Total = A * B) is untouched by this change and
    still returns "pending" for a missing same-row operand, tested elsewhere
    in this file (see test_blank_upstream_input_returns_pending_not_error).
    """

    def _result_field(self, formula_version, blank_policy=None):
        config = {"formula_version_id": formula_version.id}
        if blank_policy is not None:
            config["blank_policy"] = blank_policy
        return {
            "field_id": 1,
            "field_code": "annual_total",
            "field_name": "Annual Total",
            "field_type": "calculated",
            "field_config": config,
        }

    def _monthly_field(self):
        return {"field_code": "diesel_kl", "field_type": "number", "frequency": "monthly"}

    def _rows(self, values):
        return [
            {"label": f"Month {i + 1}", "period_label": f"Month {i + 1}", "values": {"diesel_kl": v}}
            for i, v in enumerate(values)
        ]

    def test_full_months_present_is_calculated(self, make_formula_version):
        formula = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        rows = self._rows([10, 20, 30])

        results = _compose_sheet_results([self._result_field(formula)], [self._monthly_field()], rows)

        result = results[0]
        assert result["status"] == "calculated"
        assert result["value"] == 60
        assert result["months_entered"] is None
        assert result["months_total"] is None

    def test_some_months_present_is_partial_with_correct_sum(self, make_formula_version):
        formula = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        rows = self._rows([10, None, 30, "", 5])  # blanks in both None and "" form

        results = _compose_sheet_results([self._result_field(formula)], [self._monthly_field()], rows)

        result = results[0]
        assert result["status"] == "partial"
        assert result["value"] == 45  # 10 + 30 + 5 -- blanks skipped, not treated as zero
        assert result["months_entered"] == 3
        assert result["months_total"] == 5
        assert result["message"] == "3 of 5 months entered."

    def test_zero_months_present_is_needs_input(self, make_formula_version):
        formula = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        rows = self._rows([None, None, None])

        results = _compose_sheet_results([self._result_field(formula)], [self._monthly_field()], rows)

        result = results[0]
        assert result["status"] == "needs_input"
        assert result["value"] is None

    def test_explicit_strict_blank_policy_still_blocks(self, make_formula_version):
        formula = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        rows = self._rows([10, None, 30])

        results = _compose_sheet_results(
            [self._result_field(formula, blank_policy="strict")], [self._monthly_field()], rows,
        )

        result = results[0]
        assert result["status"] == "needs_input"
        assert result["value"] is None
        assert "missing for" in result["message"]


class TestComposeSheetResultsDependencyPropagation:
    """
    A result field's formula can reference another result field directly (a
    bare, non-SUM_MONTHS token) -- same-sheet, or, via resolve_external, a
    sibling sheet's (see _CrossSheetResolver and TestCrossSheetResults in
    tests/test_cross_sheet_results.py for the full cross-sheet path). Before
    this, a dependency that was itself legitimately still pending/errored
    made evaluate_formula raise NameNotDefined, surfacing as a generic
    "Unknown formula variable" -- confusing, since the token DOES exist, it
    just hasn't resolved yet. Every case here was previously unreachable in
    practice (no sheet had a result field referencing another result field
    directly, only SUM_MONTHS of its own monthly fields), which is why it
    went unnoticed until GRI Summary's cross-sheet formulas hit the same
    pattern.

    A dependency chain's message is flattened to its ROOT cause(s), not
    nested per hop -- see TestBlockingCauseFlattening below for that
    specifically. These tests just cover the single-hop same-sheet case.
    """

    def test_same_sheet_pending_dependency_surfaces_as_needs_input_not_unknown_variable(self, make_formula_version):
        formula_a = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        formula_b = make_formula_version("field_a * 2", {"field_a": {}})
        field_a = {
            "field_id": 1, "field_code": "field_a", "field_name": "Field A",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_a.id},
        }
        field_b = {
            "field_id": 2, "field_code": "field_b", "field_name": "Field B",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_b.id},
        }
        monthly_fields = [{"field_code": "diesel_kl", "field_type": "number", "frequency": "monthly"}]
        rows = [{"label": "Apr", "values": {"diesel_kl": None}}]  # nothing entered

        results = {
            r["field_code"]: r for r in _compose_sheet_results(
                [field_a, field_b], monthly_fields, rows, own_sheet_label="This Sheet",
            )
        }

        assert results["field_a"]["status"] == "needs_input"
        assert results["field_b"]["status"] == "needs_input"
        assert "Unknown formula variable" not in results["field_b"]["message"]
        assert results["field_b"]["message"] == "Waiting on: This Sheet (Field A)."
        assert results["field_b"]["blocking_causes"] == [("This Sheet", "Field A")]

    def test_same_sheet_errored_dependency_propagates_root_cause_not_a_wrapper(self, make_formula_version):
        # field_a's own formula references a token that doesn't exist
        # anywhere (a genuinely broken/stale reference) -- ITS error message
        # IS the root cause. field_b, which merely references field_a, must
        # surface that same root cause directly, not a second-hand
        # "'Field A' could not be calculated" wrapper around it.
        formula_a = make_formula_version("missing_field + 1", {"missing_field": {}})
        formula_b = make_formula_version("field_a * 2", {"field_a": {}})
        field_a = {
            "field_id": 1, "field_code": "field_a", "field_name": "Field A",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_a.id},
        }
        field_b = {
            "field_id": 2, "field_code": "field_b", "field_name": "Field B",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_b.id},
        }

        results = {r["field_code"]: r for r in _compose_sheet_results([field_a, field_b], [], [])}

        assert results["field_a"]["status"] == "error"
        assert results["field_b"]["status"] == "error"
        # Same root cause text on both -- field_b didn't wrap it in another layer.
        assert results["field_a"]["error_causes"] == results["field_b"]["error_causes"]
        assert "Unknown formula variable" in results["field_b"]["message"]
        assert "Field A" not in results["field_b"]["message"]


class TestComposeSheetResultsAnnualInputs:
    def _annual_raw_field(self, code="annual_qty", name="Annual Qty"):
        return {
            "field_id": 10,
            "field_code": code,
            "field_name": name,
            "field_type": "number",
            "frequency": "annual",
            "field_config": {},
        }

    def _result_field(self, formula_version, code="annual_result", name="Annual Result", field_id=20):
        return {
            "field_id": field_id,
            "field_code": code,
            "field_name": name,
            "field_type": "calculated",
            "frequency": "annual",
            "field_config": {
                "formula_version_id": formula_version.id,
                "display_region": "below_monthly_table",
            },
        }

    def test_populated_annual_raw_field_calculates(self, make_formula_version):
        formula = make_formula_version("annual_qty * 47.3", {"annual_qty": {}})
        raw_field = self._annual_raw_field()
        result_field = self._result_field(formula)

        results = _compose_sheet_results(
            [result_field],
            [],
            [],
            annual_fields=[raw_field, result_field],
            workbook_values={"annual_qty": {"raw_value": "0.026", "calculated_value": 0.026}},
            own_sheet_label="Other Fuels",
        )

        assert results[0]["status"] == "calculated"
        assert results[0]["value"] == round(0.026 * 47.3, 3)

    def test_blank_annual_raw_field_needs_input_not_unknown_variable(self, make_formula_version):
        formula = make_formula_version("annual_qty * 47.3", {"annual_qty": {}})
        raw_field = self._annual_raw_field()
        result_field = self._result_field(formula)

        results = _compose_sheet_results(
            [result_field],
            [],
            [],
            annual_fields=[raw_field, result_field],
            workbook_values={"annual_qty": {"raw_value": None, "calculated_value": None}},
            own_sheet_label="Other Fuels",
        )

        assert results[0]["status"] == "needs_input"
        assert "Unknown formula variable" not in results[0]["message"]
        assert results[0]["message"] == "Waiting on: Other Fuels (Annual Qty)."

    def test_chained_annual_results_resolve_in_dependency_order(self, make_formula_version):
        formula_a = make_formula_version("annual_qty * 2", {"annual_qty": {}})
        formula_b = make_formula_version("annual_a + 5", {"annual_a": {}})
        raw_field = self._annual_raw_field()
        field_a = self._result_field(formula_a, code="annual_a", name="Annual A", field_id=21)
        field_b = self._result_field(formula_b, code="annual_b", name="Annual B", field_id=22)

        results = {
            r["field_code"]: r for r in _compose_sheet_results(
                [field_b, field_a],
                [],
                [],
                annual_fields=[raw_field, field_a, field_b],
                workbook_values={"annual_qty": {"raw_value": "3", "calculated_value": 3}},
                own_sheet_label="Other Fuels",
            )
        }

        assert results["annual_a"]["status"] == "calculated"
        assert results["annual_a"]["value"] == 6
        assert results["annual_b"]["status"] == "calculated"
        assert results["annual_b"]["value"] == 11

    def test_upstream_annual_needs_input_propagates_through_chain(self, make_formula_version):
        formula_a = make_formula_version("annual_qty * 2", {"annual_qty": {}})
        formula_b = make_formula_version("annual_a + 5", {"annual_a": {}})
        raw_field = self._annual_raw_field()
        field_a = self._result_field(formula_a, code="annual_a", name="Annual A", field_id=21)
        field_b = self._result_field(formula_b, code="annual_b", name="Annual B", field_id=22)

        results = {
            r["field_code"]: r for r in _compose_sheet_results(
                [field_b, field_a],
                [],
                [],
                annual_fields=[raw_field, field_a, field_b],
                workbook_values={"annual_qty": {"raw_value": "", "calculated_value": None}},
                own_sheet_label="Other Fuels",
            )
        }

        assert results["annual_a"]["status"] == "needs_input"
        assert results["annual_b"]["status"] == "needs_input"
        assert results["annual_b"]["message"] == "Waiting on: Other Fuels (Annual Qty)."


class TestBlockingCauseFlattening:
    """
    The actual bug this was written for: GRI Summary's intensity fields
    depend on another GRI field (same-sheet) which itself depends on
    cross-sheet fields, and before this fix each hop's full "Cannot
    calculate: ..." text got embedded inside the next hop's message, 3-4
    levels deep. A dependency chain must collapse to one flat, deduplicated,
    per-sheet-grouped list of ROOT causes instead.
    """

    def test_two_hop_chain_flattens_to_the_cross_sheet_root_not_the_intermediate_field(self, make_formula_version):
        # field_b (same sheet) depends on cross-sheet field_a via
        # resolve_external; field_c depends on field_b. field_c's message
        # must name the cross-sheet root directly, not "field_b is waiting on...".
        formula_b = make_formula_version("upstream_total + 1", {"upstream_total": {}})
        formula_c = make_formula_version("field_b * 2", {"field_b": {}})
        field_b = {
            "field_id": 1, "field_code": "field_b", "field_name": "Field B",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_b.id},
        }
        field_c = {
            "field_id": 2, "field_code": "field_c", "field_name": "Field C",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_c.id},
        }
        resolve_external = lambda code: (
            {"ok": False, "hard_error": False, "blocking_causes": [("Cargo Handled", "FY Total Cargo")]}
            if code == "upstream_total" else None
        )

        results = {
            r["field_code"]: r for r in _compose_sheet_results(
                [field_b, field_c], [], [], resolve_external=resolve_external, own_sheet_label="GRI Summary",
            )
        }

        assert results["field_b"]["message"] == "Waiting on: Cargo Handled (FY Total Cargo)."
        # field_c's message names the ORIGINAL cross-sheet root directly --
        # it does not say "Field B" or repeat "Cannot calculate" twice.
        assert results["field_c"]["message"] == "Waiting on: Cargo Handled (FY Total Cargo)."
        assert results["field_c"]["message"].count("Cannot calculate") == 0
        assert "Field B" not in results["field_c"]["message"]

    def test_multiple_cross_sheet_roots_are_grouped_by_sheet_and_deduplicated(self, make_formula_version):
        # A field referencing two upstream fields, one of which resolves via
        # two different (deduplicated) sheets, and one shared field code
        # reached through more than one path (deduplicated within a sheet too).
        formula = make_formula_version(
            "electricity_gj + fuel_gj + electricity_tco2e", {"electricity_gj": {}, "fuel_gj": {}, "electricity_tco2e": {}},
        )
        field = {
            "field_id": 1, "field_code": "total", "field_name": "Total",
            "field_type": "calculated", "field_config": {"formula_version_id": formula.id},
        }

        def resolve_external(code):
            if code == "electricity_gj":
                return {"ok": False, "hard_error": False, "blocking_causes": [("Electricity", "FY Total Electricity (GJ)")]}
            if code == "electricity_tco2e":
                # Same sheet as electricity_gj's cause, different field --
                # must be grouped under the SAME "Electricity" bucket.
                return {"ok": False, "hard_error": False, "blocking_causes": [("Electricity", "FY Total Electricity (tCO2e)")]}
            if code == "fuel_gj":
                return {"ok": False, "hard_error": False, "blocking_causes": [("Fuel Consumption", "FY Total Fuel Energy (GJ)")]}
            return None

        results = _compose_sheet_results([field], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "needs_input"
        assert results[0]["message"] == (
            "Waiting on: Electricity (FY Total Electricity (GJ), FY Total Electricity (tCO2e)), "
            "Fuel Consumption (FY Total Fuel Energy (GJ))."
        )

    def test_genuine_error_in_the_chain_surfaces_distinctly_not_lumped_with_pending(self, make_formula_version):
        # If the ROOT cause is a genuine error (not just "no data yet"), the
        # dependent field must become "error" too, not "needs_input" -- a
        # structural problem must never read as ordinary missing data.
        formula = make_formula_version("broken_upstream + 1", {"broken_upstream": {}})
        field = {
            "field_id": 1, "field_code": "total", "field_name": "Total",
            "field_type": "calculated", "field_config": {"formula_version_id": formula.id},
        }
        resolve_external = lambda code: {
            "ok": False, "hard_error": True,
            "error_causes": ["Circular cross-sheet formula dependency involving sheet 'Cargo Handled'."],
        }

        results = _compose_sheet_results([field], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "error"
        assert "Circular cross-sheet" in results[0]["message"]
        assert "Waiting on:" not in results[0]["message"]


class TestComposeSheetResultsCrossSheetResolveExternal:
    """
    _compose_sheet_results's resolve_external contract in isolation, via a
    hand-written stub -- the real caller (_CrossSheetResolver.resolve(), see
    tests/test_cross_sheet_results.py) is exercised end-to-end elsewhere;
    this pins down exactly what _compose_sheet_results does with each shape
    resolve_external can return, without needing a real workbook/DB for it.
    """

    def _field(self, formula_version):
        return {
            "field_id": 1, "field_code": "gri_total", "field_name": "GRI Total",
            "field_type": "calculated", "field_config": {"formula_version_id": formula_version.id},
        }

    def test_ok_value_is_used_in_formula(self, make_formula_version):
        formula = make_formula_version("cargo_fy_total * 2", {"cargo_fy_total": {}})
        resolve_external = lambda code: {"ok": True, "value": 21} if code == "cargo_fy_total" else None

        results = _compose_sheet_results([self._field(formula)], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "calculated"
        assert results[0]["value"] == 42

    def test_pending_upstream_surfaces_as_needs_input_with_clear_message(self, make_formula_version):
        formula = make_formula_version("cargo_fy_total * 2", {"cargo_fy_total": {}})
        resolve_external = lambda code: {
            "ok": False, "hard_error": False, "blocking_causes": [("Cargo Handled", "FY Total Cargo")],
        }

        results = _compose_sheet_results([self._field(formula)], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "needs_input"
        assert results[0]["message"] == "Waiting on: Cargo Handled (FY Total Cargo)."

    def test_hard_error_upstream_surfaces_as_error(self, make_formula_version):
        formula = make_formula_version("cargo_fy_total * 2", {"cargo_fy_total": {}})
        message = "Circular cross-sheet formula dependency involving sheet 'Cargo Handled'."
        resolve_external = lambda code: {"ok": False, "hard_error": True, "error_causes": [message]}

        results = _compose_sheet_results([self._field(formula)], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "error"
        assert "Circular cross-sheet" in results[0]["message"]

    def test_partial_upstream_downgrades_result_to_partial_with_note(self, make_formula_version):
        formula = make_formula_version("cargo_fy_total * 2", {"cargo_fy_total": {}})
        note = "'FY Total Cargo' from 'Cargo Handled' is itself a partial result (1 of 12 months entered.)."
        resolve_external = lambda code: {"ok": True, "value": 21, "partial": True, "note": note}

        results = _compose_sheet_results([self._field(formula)], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "partial"
        assert results[0]["value"] == 42
        assert note in results[0]["message"]
        # No monthly aggregate operands were involved at all, so there's no
        # "X of Y months" fraction to report -- must stay None, not "0 of 0".
        assert results[0]["months_total"] is None

    def test_unresolvable_token_falls_through_to_existing_unknown_variable_error(self, make_formula_version):
        # resolve_external returning None means "not a field anywhere in the
        # workbook" -- a genuinely broken/stale token reference, same as
        # today's behavior with no resolve_external at all.
        formula = make_formula_version("ghost_field + 1", {"ghost_field": {}})
        resolve_external = lambda code: None

        results = _compose_sheet_results([self._field(formula)], [], [], resolve_external=resolve_external)

        assert results[0]["status"] == "error"
        assert "Unknown formula variable" in results[0]["message"]


class TestAutomaticFyTotals:
    """
    Every monthly numeric field (raw input or a per-row calculated field)
    gets a zero-setup FY total synthesized for it -- no more manually
    building a second Field with a SUM_MONTHS formula. Annual/static fields
    never reach synthesize_automatic_fy_totals at all (monthly_table_fields
    excludes them upstream), and a field that already has an explicit
    per-field override must not also get a duplicate automatic one.
    """

    def test_monthly_numeric_field_gets_automatic_fy_total(self):
        monthly_fields = [{"field_code": "diesel_kl", "field_type": "number", "frequency": "monthly", "field_config": {}}]

        synthetic = synthesize_automatic_fy_totals(monthly_fields, [])
        assert len(synthetic) == 1
        assert synthetic[0]["field_config"]["auto_aggregate_source_field_code"] == "diesel_kl"

        rows = [
            {"label": "Apr", "values": {"diesel_kl": 10}},
            {"label": "May", "values": {"diesel_kl": 20}},
        ]
        results = _compose_sheet_results(synthetic, monthly_fields, rows)

        assert len(results) == 1
        assert results[0]["status"] == "calculated"
        assert results[0]["value"] == 30
        assert results[0]["source_field_codes"] == ["diesel_kl"]

    def test_annual_static_field_gets_no_automatic_entry(self):
        fields = [
            {"field_code": "diesel_kl", "field_type": "number", "frequency": "monthly", "field_config": {}, "section_id": None},
            {"field_code": "site_area", "field_type": "number", "frequency": "annual", "field_config": {}, "section_id": None},
        ]
        monthly_fields = monthly_table_fields(fields, [])
        monthly_codes = {f["field_code"] for f in monthly_fields}
        # The annual field is excluded upstream, before synthesis even runs --
        # its "aggregate" would be a trivial identity (its own single value),
        # not a real SUM_MONTHS computation, so it never gets a synthetic entry.
        assert monthly_codes == {"diesel_kl"}

        synthetic = synthesize_automatic_fy_totals(monthly_fields, [])
        synthetic_sources = {s["field_config"]["auto_aggregate_source_field_code"] for s in synthetic}
        assert synthetic_sources == {"diesel_kl"}

    def test_field_with_explicit_manual_override_does_not_get_duplicate(self, make_formula_version):
        formula = make_formula_version("SUM_MONTHS(diesel_kl)", {"diesel_kl": {}})
        monthly_fields = [{"field_code": "diesel_kl", "field_type": "number", "frequency": "monthly", "field_config": {}}]
        explicit_result_fields = [{
            "field_id": 99,
            "field_code": "diesel_kl_fy_total",
            "field_name": "Diesel FY Total",
            "field_type": "calculated",
            "field_config": {"formula_version_id": formula.id, "display_region": "under_input_column"},
        }]

        synthetic = synthesize_automatic_fy_totals(monthly_fields, explicit_result_fields)
        assert synthetic == []

        rows = [
            {"label": "Apr", "values": {"diesel_kl": 10}},
            {"label": "May", "values": {"diesel_kl": 20}},
        ]
        results = _compose_sheet_results(explicit_result_fields + synthetic, monthly_fields, rows)

        assert len(results) == 1
        assert results[0]["field_code"] == "diesel_kl_fy_total"
        assert results[0]["status"] == "calculated"
        assert results[0]["value"] == 30

    def test_monthly_calculated_field_gets_automatic_fy_total_of_its_computed_values(self):
        monthly_fields = [{
            "field_code": "row_total",
            "field_type": "calculated",
            "frequency": "monthly",
            "field_config": {"formula_version_id": 1},  # a per-row formula, unrelated to this aggregate
        }]

        synthetic = synthesize_automatic_fy_totals(monthly_fields, [])
        assert len(synthetic) == 1
        assert synthetic[0]["field_config"]["auto_aggregate_source_field_code"] == "row_total"

        rows = [
            {"label": "Apr", "values": {"row_total": 5}},
            {"label": "May", "values": {"row_total": 15}},
        ]
        results = _compose_sheet_results(synthetic, monthly_fields, rows)

        assert results[0]["status"] == "calculated"
        assert results[0]["value"] == 20
class TestRecalcOrFlagSubmissionsForFormulaSwap:
    """
    A calculated field's formula_version_id is a live, in-place field_config
    edit (unlike the Formula itself, which is never edited in place once
    published -- see test_formula_lifecycle.py). recalc_or_flag_submissions_for_
    formula_swap is what runs immediately after that live edit: open
    submissions get recalculated against whatever formula is now live for the
    field, while anything already Approved and locked is frozen and flagged
    for reviewer follow-up instead of silently recomputed.
    """

    def _setup(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value, new_formula_expression,
    ):
        form, form_version = make_form()
        old_formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        new_formula = make_formula_version(new_formula_expression, {"field_a": {}, "field_b": {}})

        field_a, fv_a = make_field(form, form_version, "field_a", field_type="number")
        field_b, fv_b = make_field(form, form_version, "field_b", field_type="number")
        # field_c's live field_config already points at the new formula --
        # simulating the moment right after the swap was saved.
        field_c, fv_c = make_field(
            form, form_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": new_formula.id},
        )

        approver = make_user()
        site = make_site()
        workflow_version = make_workflow([approver])
        months = iter([4, 5, 6, 7, 8, 9])

        def _make_submission_with_values(status, **kwargs):
            # uq_active_submission is unique on (site_id, form_id, reporting_period_id),
            # so each submission in this test needs its own period.
            period = make_reporting_period(site, month=next(months))
            submission = make_submission(site, form, form_version, period, workflow_version, status=status, **kwargs)
            make_submission_value(submission, field_a, fv_a, raw_value="3")
            make_submission_value(submission, field_b, fv_b, raw_value="4")
            # Seed field_c with a stale calculated value computed under the OLD formula.
            make_submission_value(
                submission, field_c, fv_c,
                calculated_value=7, formula_version_id=old_formula.id, calc_status=CALC_STATUS_OK,
            )
            return submission

        return form, field_c, approver, _make_submission_with_values

    def test_recalculates_open_submissions_and_flags_approved_locked(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value,
    ):
        form, field_c, approver, _make_submission_with_values = self._setup(
            make_form, make_field, make_formula_version, make_site, make_reporting_period,
            make_workflow, make_user, make_submission, make_submission_value,
            new_formula_expression="field_a * field_b",
        )

        draft_sub = _make_submission_with_values("Draft")
        submitted_sub = _make_submission_with_values("Submitted")
        approved_sub = _make_submission_with_values("Approved", is_locked=True)

        result = recalc_or_flag_submissions_for_formula_swap(form.id, approver.id)

        assert set(result["recalculated"]) == {draft_sub.id, submitted_sub.id}
        assert result["flagged"] == [approved_sub.id]

        draft_c = SubmissionValue.query.filter_by(submission_id=draft_sub.id, field_id=field_c.id).one()
        assert draft_c.calc_status == CALC_STATUS_OK
        assert float(draft_c.calculated_value) == 12.0  # 3 * 4 under the new formula

        submitted_c = SubmissionValue.query.filter_by(submission_id=submitted_sub.id, field_id=field_c.id).one()
        assert float(submitted_c.calculated_value) == 12.0

        # Approved + locked: value untouched, flagged for reviewer follow-up instead.
        approved_c = SubmissionValue.query.filter_by(submission_id=approved_sub.id, field_id=field_c.id).one()
        assert float(approved_c.calculated_value) == 7.0
        assert approved_sub.needs_recalc_review is True

    def test_recalculates_under_review_resubmitted_and_changes_requested(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value,
    ):
        form, field_c, approver, _make_submission_with_values = self._setup(
            make_form, make_field, make_formula_version, make_site, make_reporting_period,
            make_workflow, make_user, make_submission, make_submission_value,
            new_formula_expression="field_a * field_b",
        )

        under_review_sub = _make_submission_with_values("Under Review")
        resubmitted_sub = _make_submission_with_values("Resubmitted")
        changes_requested_sub = _make_submission_with_values("Changes Requested")

        result = recalc_or_flag_submissions_for_formula_swap(form.id, approver.id)

        assert set(result["recalculated"]) == {under_review_sub.id, resubmitted_sub.id, changes_requested_sub.id}
        assert result["flagged"] == []

        for submission in (under_review_sub, resubmitted_sub, changes_requested_sub):
            value = SubmissionValue.query.filter_by(submission_id=submission.id, field_id=field_c.id).one()
            assert value.calc_status == CALC_STATUS_OK
            assert float(value.calculated_value) == 12.0


class TestPreviewFormulaSwapImpact:
    """
    preview_formula_swap_impact runs the same diff as publish_form_version's
    trigger, but read-only and before publish, so the Sheet Builder can warn
    the user first. It must stay silent (zero impact) whenever there's
    nothing to warn about: the formula didn't actually change, or the sheet
    has no submissions yet.
    """

    def test_zero_impact_when_formula_unchanged(
        self, make_form, make_field, make_formula_version, db_session, created_objects, system_user,
    ):
        form, published_version = make_form()
        formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        make_field(form, published_version, "field_a", field_type="number")
        make_field(form, published_version, "field_b", field_type="number")
        field_c, _fv_c = make_field(
            form, published_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": formula.id},
        )

        draft_version = _make_draft_form_version(db_session, created_objects, system_user, form, 2)
        _make_field_version(
            db_session, created_objects, system_user, field_c, draft_version, 2,
            "calculated", {"formula_version_id": formula.id},
        )

        assert preview_formula_swap_impact(draft_version.id) == {"total_affected": 0, "fields": []}

    def test_zero_impact_when_no_submissions_exist(
        self, make_form, make_field, make_formula_version, db_session, created_objects, system_user,
    ):
        form, published_version = make_form()
        old_formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        new_formula = make_formula_version("field_a * field_b", {"field_a": {}, "field_b": {}})
        make_field(form, published_version, "field_a", field_type="number")
        make_field(form, published_version, "field_b", field_type="number")
        field_c, _fv_c = make_field(
            form, published_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": old_formula.id},
        )

        draft_version = _make_draft_form_version(db_session, created_objects, system_user, form, 2)
        _make_field_version(
            db_session, created_objects, system_user, field_c, draft_version, 2,
            "calculated", {"formula_version_id": new_formula.id},
        )

        # A real formula swap, but no submissions exist on this sheet at all.
        assert preview_formula_swap_impact(draft_version.id) == {"total_affected": 0, "fields": []}

    def test_counts_mixed_submission_statuses(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, db_session, created_objects, system_user,
    ):
        form, published_version = make_form()
        old_formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        new_formula = make_formula_version("field_a * field_b", {"field_a": {}, "field_b": {}})
        make_field(form, published_version, "field_a", field_type="number")
        make_field(form, published_version, "field_b", field_type="number")
        field_c, _fv_c = make_field(
            form, published_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": old_formula.id},
        )

        draft_version = _make_draft_form_version(db_session, created_objects, system_user, form, 2)
        _make_field_version(
            db_session, created_objects, system_user, field_c, draft_version, 2,
            "calculated", {"formula_version_id": new_formula.id}, field_name="Field C",
        )

        approver = make_user()
        site = make_site()
        workflow_version = make_workflow([approver])
        months = iter([4, 5, 6, 7])

        def _sub(status, **kwargs):
            period = make_reporting_period(site, month=next(months))
            return make_submission(site, form, published_version, period, workflow_version, status=status, **kwargs)

        _sub("Draft")
        _sub("Submitted")
        _sub("Approved", is_locked=True)
        _sub("Rejected")  # terminal -- excluded from both buckets

        result = preview_formula_swap_impact(draft_version.id)

        assert result["total_affected"] == 3
        assert len(result["fields"]) == 1
        field_entry = result["fields"][0]
        assert field_entry["field_code"] == "field_c"
        assert field_entry["field_name"] == "Field C"
        assert field_entry["recalculated_count"] == 2
        assert field_entry["flagged_count"] == 1
        assert field_entry["status_breakdown"] == {"Draft": 1, "Submitted": 1, "Approved": 1}


class TestPreviewCalculatedValuesSkipsLockedSubmissions:
    """
    _compute_preview_calculated_values fills a blank calculated cell with a
    live, non-persisted computation purely for read-only display (e.g. a
    field added to the sheet after some submissions were already approved
    and locked never got a persisted row). That's correct for an open,
    editable submission -- it's a live preview. On an Approved + is_locked
    submission it isn't: the displayed number would silently drift every
    time the live formula changes, with no flag and no persisted record,
    which is exactly what locking is supposed to prevent. Locked submissions
    must be skipped entirely, not just filtered out after computing.
    """

    def test_locked_submission_with_no_persisted_value_is_not_computed(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value,
    ):
        form, form_version = make_form()
        formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        field_a, fv_a = make_field(form, form_version, "field_a", field_type="number")
        field_b, fv_b = make_field(form, form_version, "field_b", field_type="number")
        make_field(
            form, form_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": formula.id},
        )

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        locked_submission = make_submission(
            site, form, form_version, period, workflow_version, status="Approved", is_locked=True,
        )
        # Raw inputs exist, but field_c was never calculated/persisted for this
        # submission -- e.g. added to the sheet after it was already locked.
        make_submission_value(locked_submission, field_a, fv_a, raw_value="3")
        make_submission_value(locked_submission, field_b, fv_b, raw_value="4")

        fields = _field_payload(form_version.id)
        preview = _compute_preview_calculated_values([locked_submission], fields)

        assert preview == {}

    def test_open_submission_still_gets_a_live_preview_even_after_a_formula_swap(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_submission, make_submission_value, db_session,
    ):
        form, form_version = make_form()
        old_formula = make_formula_version("field_a + field_b", {"field_a": {}, "field_b": {}})
        new_formula = make_formula_version("field_a * field_b", {"field_a": {}, "field_b": {}})
        field_a, fv_a = make_field(form, form_version, "field_a", field_type="number")
        field_b, fv_b = make_field(form, form_version, "field_b", field_type="number")
        field_c, fv_c = make_field(
            form, form_version, "field_c", field_type="calculated",
            field_config={"formula_version_id": old_formula.id},
        )

        approver = make_user()
        site = make_site()
        period = make_reporting_period(site)
        workflow_version = make_workflow([approver])
        locked_submission = make_submission(
            site, form, form_version, period, workflow_version, status="Approved", is_locked=True,
        )
        make_submission_value(locked_submission, field_a, fv_a, raw_value="3")
        make_submission_value(locked_submission, field_b, fv_b, raw_value="4")

        # Simulate the live, in-place field_config edit a formula swap makes.
        fv_c.field_config = {"formula_version_id": new_formula.id}
        db_session.flush()

        fields = _field_payload(form_version.id)

        # Still skipped for the locked submission, even against the new formula.
        assert _compute_preview_calculated_values([locked_submission], fields) == {}

        # An open submission in the identical post-swap state is unaffected by
        # this guard -- it still gets its live preview, now under the new formula.
        open_submission = make_submission(
            site, form, form_version,
            make_reporting_period(site, month=5), workflow_version, status="Draft",
        )
        make_submission_value(open_submission, field_a, fv_a, raw_value="3")
        make_submission_value(open_submission, field_b, fv_b, raw_value="4")

        preview = _compute_preview_calculated_values([open_submission], fields)
        assert preview[open_submission.id]["field_c"]["status"] == CALC_STATUS_OK
        assert preview[open_submission.id]["field_c"]["value"] == 12.0  # 3 * 4 under the new formula
