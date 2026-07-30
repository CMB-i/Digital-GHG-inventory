"""
RPTBLD row-groups / metric-aliasing / computed-columns pivot (phase 2 of
report-level formulas, building on FRMULA's context="report" formulas from
phase 1). Covers config_json validation (row_groups, metric_aliases,
computed_columns) and pivot_report_data's full pipeline, including a
fidelity check against real cached workbook numbers and the PNP/MELT-style
per-site override case.
"""
import pytest

from app.modules.RPTBLD.service import (
    _evaluate_computed_columns,
    pivot_report_data,
    validate_computed_columns,
    validate_metric_aliases,
    validate_row_groups,
)


class TestRowGroupReferenceBaseValidation:
    def test_zero_reference_base_raises(self):
        row_groups = [
            {"id": "core", "label": "Core", "site_ids": [1, 2], "include_in_grand_total": True, "is_reference_base": False},
        ]
        with pytest.raises(ValueError, match="Exactly one row group"):
            validate_row_groups(row_groups)

    def test_two_reference_base_raises(self):
        row_groups = [
            {"id": "core", "label": "Core", "site_ids": [1], "include_in_grand_total": True, "is_reference_base": True},
            {"id": "extended", "label": "Extended", "site_ids": [2], "include_in_grand_total": True, "is_reference_base": True},
        ]
        with pytest.raises(ValueError, match="Exactly one row group"):
            validate_row_groups(row_groups)

    def test_exactly_one_reference_base_passes(self):
        row_groups = [
            {"id": "core", "label": "Core", "site_ids": [1], "include_in_grand_total": True, "is_reference_base": True},
            {"id": "extended", "label": "Extended", "site_ids": [2], "include_in_grand_total": True, "is_reference_base": False},
        ]
        validate_row_groups(row_groups)  # does not raise

    def test_empty_row_groups_skips_validation(self):
        validate_row_groups([])


class TestMetricAliasValidation:
    def test_orphaned_site_raises(self, make_site, make_form, make_field):
        site = make_site()
        other_site = make_site()
        form, form_version = make_form()
        field, _fv = make_field(form, form_version, "cargo_code")

        config = {
            "row_groups": [
                {"id": "core", "label": "Core", "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True},
            ],
            "metric_aliases": {
                "cargo": [{"site_id": other_site.id, "field_ids": [field.id], "op": "single", "verified": True}],
            },
        }
        with pytest.raises(ValueError, match="not present in any row group"):
            validate_metric_aliases(config)

    def test_sum_requires_at_least_two_field_ids(self, make_site, make_form, make_field):
        site = make_site()
        form, form_version = make_form()
        field, _fv = make_field(form, form_version, "cargo_code")

        config = {
            "row_groups": [
                {"id": "core", "label": "Core", "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True},
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [field.id], "op": "sum", "verified": True}],
            },
        }
        with pytest.raises(ValueError, match="op='sum' requires at least 2"):
            validate_metric_aliases(config)

    def test_single_requires_exactly_one_field_id(self, make_site, make_form, make_field):
        site = make_site()
        form, form_version = make_form()
        field_a, _fva = make_field(form, form_version, "cargo_code_a")
        field_b, _fvb = make_field(form, form_version, "cargo_code_b")

        config = {
            "row_groups": [
                {"id": "core", "label": "Core", "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True},
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [field_a.id, field_b.id], "op": "single", "verified": True}],
            },
        }
        with pytest.raises(ValueError, match="op='single' requires exactly 1"):
            validate_metric_aliases(config)

    def test_deleted_field_id_raises(self, make_site, make_form, make_field, db_session):
        from datetime import datetime, timezone

        site = make_site()
        form, form_version = make_form()
        field, _fv = make_field(form, form_version, "cargo_code")
        field.is_deleted = True
        field.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        config = {
            "row_groups": [
                {"id": "core", "label": "Core", "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True},
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [field.id], "op": "single", "verified": True}],
            },
        }
        with pytest.raises(ValueError, match="does not exist or is deleted"):
            validate_metric_aliases(config)

    def test_valid_config_passes(self, make_site, make_form, make_field):
        site = make_site()
        form, form_version = make_form()
        field, _fv = make_field(form, form_version, "cargo_code")

        config = {
            "row_groups": [
                {"id": "core", "label": "Core", "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True},
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [field.id], "op": "single", "verified": True}],
            },
        }
        validate_metric_aliases(config)  # does not raise


class TestComputedColumnFormulaContextValidation:
    def test_field_context_formula_id_raises(self, make_user, created_objects):
        from app.modules.FRMULA.service import create_formula

        user = make_user()
        formula = create_formula("Field Ctx", f"test-cc-field-{user.id}", "1 + 1", {}, user.id)
        created_objects.append(formula)

        with pytest.raises(ValueError, match="not 'report'"):
            validate_computed_columns([{"id": "H", "label": "H", "formula_id": formula.id}])

    def test_report_context_formula_id_passes(self, make_user, created_objects):
        from app.modules.FRMULA.service import create_formula

        user = make_user()
        formula = create_formula(
            "Report Ctx", f"test-cc-report-{user.id}", "scope1 + scope2",
            {"scope1": {}, "scope2": {}}, user.id, context="report",
        )
        created_objects.append(formula)

        validate_computed_columns([{"id": "H", "label": "H", "formula_id": formula.id}])  # does not raise

    def test_nonexistent_formula_id_raises(self):
        with pytest.raises(ValueError, match="does not exist"):
            validate_computed_columns([{"id": "H", "label": "H", "formula_id": 999999999}])

    def test_cross_site_kind_does_not_require_formula_id(self):
        validate_computed_columns([
            {"id": "pct_contribution_total_ghg", "label": "% Contribution", "kind": "cross_site"},
            {"id": "variation_from_avg_intensity", "label": "Variation", "kind": "cross_site"},
        ])

    def test_cross_site_kind_is_not_evaluated_as_formula(self):
        result = _evaluate_computed_columns(
            [{"id": "pct_contribution_total_ghg", "label": "% Contribution", "kind": "cross_site"}],
            metric_aliases={},
            flat_index={},
            site_id=None,
            own_metrics={},
            group_subtotal_names={},
        )
        assert result == {}


class TestPivotReportDataFidelity:
    """
    site_a reproduces real, previously-verified workbook numbers (cargo
    24,572,656 / scope1 1,947.54 / scope2 9,399.65) so this is a genuine
    fidelity check, not a tautology. site_b is synthetic fixture data used
    to exercise cross-site subtotal/grand-total summation.
    """

    def _setup(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version
        from app.modules.RPTBLD.service import create_report_template

        site_a = make_site()  # Dharamtar-equivalent
        site_b = make_site()

        form, form_version = make_form()
        cargo_field, cargo_fv = make_field(form, form_version, "cargo_code")
        scope1_field, scope1_fv = make_field(form, form_version, "scope1_code")
        scope2_field, scope2_fv = make_field(form, form_version, "scope2_code")
        override_field, override_fv = make_field(form, form_version, "h_override_code")

        workflow_version = make_workflow([])

        period_a = make_reporting_period(site_a, year=2026, month=3)
        period_b = make_reporting_period(site_b, year=2026, month=3)

        sub_a = make_submission(
            site_a, form, form_version, period_a, workflow_version,
            status="Approved", is_locked=True,
        )
        sub_b = make_submission(
            site_b, form, form_version, period_b, workflow_version,
            status="Approved", is_locked=True,
        )

        make_submission_value(sub_a, cargo_field, cargo_fv, raw_value="24572656")
        make_submission_value(sub_a, scope1_field, scope1_fv, raw_value="1947.54")
        make_submission_value(sub_a, scope2_field, scope2_fv, raw_value="9399.65")

        make_submission_value(sub_b, cargo_field, cargo_fv, raw_value="1000000")
        make_submission_value(sub_b, scope1_field, scope1_fv, raw_value="100")
        make_submission_value(sub_b, scope2_field, scope2_fv, raw_value="200")

        # PNP/MELT-style override: only site_b sources "H" directly instead
        # of computing it.
        make_submission_value(sub_b, override_field, override_fv, raw_value="5000")

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)

        h_formula = create_formula(
            "GHG Sum", f"test-pivot-h-{user.id}", "scope1 + scope2",
            {"scope1": {}, "scope2": {}}, user.id, context="report",
        )
        created_objects.append(h_formula)
        h_version = FormulaVersion.query.filter_by(formula_id=h_formula.id, version_number=1).one()
        created_objects.append(h_version)
        publish_formula_version(h_version.id, user.id)

        n_formula = create_formula(
            "Bad Ratio", f"test-pivot-n-{user.id}", "cargo / power_specific",
            {"cargo": {}, "power_specific": {}}, user.id, context="report",
        )
        created_objects.append(n_formula)
        n_version = FormulaVersion.query.filter_by(formula_id=n_formula.id, version_number=1).one()
        created_objects.append(n_version)
        publish_formula_version(n_version.id, user.id)

        config_json = {
            "form_ids": [form.id],
            "site_ids": [site_a.id, site_b.id],
            "row_groups": [
                {
                    "id": "core", "label": "Core Sites", "subtotal_label": "Total",
                    "site_ids": [site_a.id, site_b.id],
                    "include_in_grand_total": True, "is_reference_base": True,
                },
            ],
            "metric_aliases": {
                "cargo": [
                    {"site_id": site_a.id, "field_ids": [cargo_field.id], "op": "single", "verified": True},
                    {"site_id": site_b.id, "field_ids": [cargo_field.id], "op": "single", "verified": True},
                ],
                "scope1": [
                    {"site_id": site_a.id, "field_ids": [scope1_field.id], "op": "single", "verified": True},
                    {"site_id": site_b.id, "field_ids": [scope1_field.id], "op": "single", "verified": True},
                ],
                "scope2": [
                    {"site_id": site_a.id, "field_ids": [scope2_field.id], "op": "single", "verified": True},
                    {"site_id": site_b.id, "field_ids": [scope2_field.id], "op": "single", "verified": True},
                ],
                "H": [
                    {"site_id": site_b.id, "field_ids": [override_field.id], "op": "single", "verified": False},
                ],
            },
            "computed_columns": [
                {"id": "H", "label": "GHG Sum", "formula_id": h_formula.id},
                {"id": "N", "label": "Bad Ratio", "formula_id": n_formula.id},
            ],
        }

        template = create_report_template(
            "Pivot Fidelity Report", f"test-pivot-{user.id}", None, "global", None, config_json, user.id,
        )
        created_objects.append(template)

        return template, user, site_a, site_b

    def test_pivot_reproduces_real_site_numbers_and_grand_total(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        template, user, site_a, site_b = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        result = pivot_report_data(template.id, user.id)

        assert result["template_id"] == template.id
        assert len(result["row_groups"]) == 1

        core = result["row_groups"][0]
        assert core["id"] == "core"

        rows_by_site = {r["site_id"]: r for r in core["site_rows"]}

        row_a = rows_by_site[site_a.id]
        assert row_a["metrics"]["cargo"] == {"value": 24572656.0, "verified": True}
        assert row_a["metrics"]["scope1"] == {"value": 1947.54, "verified": True}
        assert row_a["metrics"]["scope2"] == {"value": 9399.65, "verified": True}

        row_b = rows_by_site[site_b.id]
        assert row_b["metrics"]["cargo"] == {"value": 1000000.0, "verified": True}
        assert row_b["metrics"]["scope1"] == {"value": 100.0, "verified": True}
        assert row_b["metrics"]["scope2"] == {"value": 200.0, "verified": True}

        # Subtotal: real number + synthetic number summed.
        assert core["subtotal"]["metrics"]["cargo"] == pytest.approx(25572656.0)
        assert core["subtotal"]["metrics"]["scope1"] == pytest.approx(2047.54)
        assert core["subtotal"]["metrics"]["scope2"] == pytest.approx(9599.65)

        # Only one group, included in grand total -- grand total mirrors the subtotal.
        assert result["grand_total"]["metrics"]["cargo"] == pytest.approx(25572656.0)
        assert result["grand_total"]["metrics"]["scope1"] == pytest.approx(2047.54)
        assert result["grand_total"]["metrics"]["scope2"] == pytest.approx(9599.65)

        # A metric nobody ever aliased is None, not 0.
        assert row_a["metrics"]["power_specific"] == {"value": None, "verified": False}

    def test_computed_column_evaluates_from_formula_for_non_overridden_site(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        template, user, site_a, site_b = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        result = pivot_report_data(template.id, user.id)
        core = result["row_groups"][0]
        rows_by_site = {r["site_id"]: r for r in core["site_rows"]}

        row_a = rows_by_site[site_a.id]
        assert row_a["computed"]["H"]["source"] == "computed"
        assert row_a["computed"]["H"]["value"] == pytest.approx(1947.54 + 9399.65)
        assert row_a["computed"]["H"]["error"] is None

    def test_pnp_melt_style_override_round_trips(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        template, user, site_a, site_b = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        result = pivot_report_data(template.id, user.id)
        core = result["row_groups"][0]
        rows_by_site = {r["site_id"]: r for r in core["site_rows"]}

        row_b = rows_by_site[site_b.id]
        assert row_b["computed"]["H"]["source"] == "override"
        assert row_b["computed"]["H"]["value"] == 5000.0
        assert row_b["computed"]["H"]["verified"] is False
        assert row_b["computed"]["H"]["error"] is None

        # Subtotal/grand total never override -- always the formula, never a
        # single site's sourced cell.
        assert core["subtotal"]["computed"]["H"]["source"] == "computed"
        assert result["grand_total"]["computed"]["H"]["source"] == "computed"

    def test_computed_column_referencing_unaliased_metric_renders_blank_not_error(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        """
        power_specific is never aliased for either site here -- a genuinely-
        absent metric (the same shape as a real site with no petrol/IFO
        consumption). This must degrade to a blank cell (value=None,
        error=None), same as kind="cross_site" columns already do for a
        missing dependency -- not raise "Unknown formula variable", which
        would be indistinguishable from an actual formula bug.
        """
        template, user, site_a, site_b = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        result = pivot_report_data(template.id, user.id)
        core = result["row_groups"][0]
        rows_by_site = {r["site_id"]: r for r in core["site_rows"]}

        for row in (rows_by_site[site_a.id], rows_by_site[site_b.id], core["subtotal"]):
            n_cell = row["computed"]["N"]
            assert n_cell["value"] is None
            assert n_cell["source"] == "computed"
            assert n_cell["error"] is None

        # A blank cell elsewhere doesn't take down the rest of the report.
        row_a = rows_by_site[site_a.id]
        assert row_a["computed"]["H"]["error"] is None
        assert row_a["metrics"]["cargo"]["value"] == 24572656.0

    def test_genuine_formula_evaluation_error_still_produces_explicit_error(
        self, make_site, make_form, make_field, make_user, make_access_grant, created_objects,
    ):
        """
        Distinguishes "missing token -> blank" (tested above) from "every
        token present but evaluation itself fails" -- e.g. a division by
        zero -- which must still surface as an explicit per-cell error, not
        silently blank. Both metrics are aliased and non-None here, so this
        exercises the try/except FormulaValidationError path in
        _evaluate_computed_columns, not the missing-token guard.
        """
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version
        from app.modules.RPTBLD.service import create_report_template

        site = make_site()
        form, form_version = make_form()
        cargo_field, cargo_fv = make_field(form, form_version, "cargo_code")
        zero_field, zero_fv = make_field(form, form_version, "zero_code")

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)

        formula = create_formula(
            "Div By Zero", f"test-divzero-{user.id}", "cargo / scope2",
            {"cargo": {}, "scope2": {}}, user.id, context="report",
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
        created_objects.append(version)
        publish_formula_version(version.id, user.id)

        config_json = {
            "form_ids": [form.id],
            "site_ids": [site.id],
            "row_groups": [
                {
                    "id": "core", "label": "Core", "subtotal_label": "Total",
                    "site_ids": [site.id], "include_in_grand_total": True, "is_reference_base": True,
                },
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [cargo_field.id], "op": "single", "verified": True}],
                "scope2": [{"site_id": site.id, "field_ids": [zero_field.id], "op": "single", "verified": True}],
            },
            "computed_columns": [{"id": "DIV0", "label": "Div By Zero", "formula_id": formula.id}],
        }
        # zero_field needs a real submitted value of 0 (not left blank) so
        # this exercises an actual evaluation-time error, not the missing-
        # token guard tested above.
        from datetime import datetime, timezone
        from app.modules.WFLWBLD.model import Workflow, WorkflowVersion
        wf = Workflow(name="wf", code=f"wf-{user.id}", created_by=user.id, updated_by=user.id)
        from app.database import db as _db
        _db.session.add(wf)
        _db.session.flush()
        created_objects.append(wf)
        wfv = WorkflowVersion(workflow_id=wf.id, version_number=1, published_at=datetime.now(timezone.utc), created_by=user.id)
        _db.session.add(wfv)
        _db.session.flush()
        created_objects.append(wfv)
        wf.current_version_id = wfv.id
        _db.session.flush()

        from app.modules.PERIOD.model import ReportingPeriod
        from app.modules.SUBMIT.model import Submission, SubmissionValue

        period = ReportingPeriod(site_id=site.id, year=2026, month=3, status="OPEN", created_by=user.id, updated_by=user.id)
        _db.session.add(period)
        _db.session.flush()
        created_objects.append(period)

        submission = Submission(
            site_id=site.id, form_id=form.id, form_version_id=form_version.id,
            reporting_period_id=period.id, workflow_version_id=wfv.id,
            status="Approved", is_locked=True, current_level=1,
            created_by=user.id, updated_by=user.id,
        )
        _db.session.add(submission)
        _db.session.flush()
        created_objects.append(submission)

        cargo_value = SubmissionValue(submission_id=submission.id, field_id=cargo_field.id, field_version_id=cargo_fv.id, raw_value="1000", created_by=user.id, updated_by=user.id)
        zero_value = SubmissionValue(submission_id=submission.id, field_id=zero_field.id, field_version_id=zero_fv.id, raw_value="0", created_by=user.id, updated_by=user.id)
        _db.session.add_all([cargo_value, zero_value])
        _db.session.flush()
        created_objects.extend([cargo_value, zero_value])

        template = create_report_template(
            "Div Zero Report", f"test-divzero-tpl-{user.id}", None, "global", None, config_json, user.id,
        )
        created_objects.append(template)

        result = pivot_report_data(template.id, user.id)
        row = result["row_groups"][0]["site_rows"][0]
        cell = row["computed"]["DIV0"]
        assert cell["value"] is None
        assert cell["error"] is not None
        assert "zero" in cell["error"].lower() or "division" in cell["error"].lower()


class TestPivotGrandTotalExclusion:
    """pivot_report_data's grand total filters by include_in_grand_total, but
    every fidelity-test fixture uses a single group where that flag is always
    True -- so the exclusion path was never actually exercised by a real
    test. Two groups here, one excluded, with a deliberately absurd value in
    the excluded group so a leak into the grand total would be impossible to
    miss."""

    def test_excluded_group_does_not_leak_into_grand_total(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        from app.modules.RPTBLD.service import create_report_template

        included_site = make_site()
        excluded_site = make_site()

        form, form_version = make_form()
        cargo_field, cargo_fv = make_field(form, form_version, "cargo_code")

        workflow_version = make_workflow([])

        included_period = make_reporting_period(included_site, year=2026, month=3)
        excluded_period = make_reporting_period(excluded_site, year=2026, month=3)

        included_sub = make_submission(
            included_site, form, form_version, included_period, workflow_version,
            status="Approved", is_locked=True,
        )
        excluded_sub = make_submission(
            excluded_site, form, form_version, excluded_period, workflow_version,
            status="Approved", is_locked=True,
        )

        make_submission_value(included_sub, cargo_field, cargo_fv, raw_value="1000")
        # Deliberately absurd -- if this leaks into the grand total, it's unmissable.
        make_submission_value(excluded_sub, cargo_field, cargo_fv, raw_value="999999999999")

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)

        config_json = {
            "form_ids": [form.id],
            "site_ids": [included_site.id, excluded_site.id],
            "row_groups": [
                {
                    "id": "included_group", "label": "Included", "subtotal_label": "Total",
                    "site_ids": [included_site.id],
                    "include_in_grand_total": True, "is_reference_base": True,
                },
                {
                    "id": "excluded_group", "label": "Excluded", "subtotal_label": "Total (Excluded)",
                    "site_ids": [excluded_site.id],
                    "include_in_grand_total": False, "is_reference_base": False,
                },
            ],
            "metric_aliases": {
                "cargo": [
                    {"site_id": included_site.id, "field_ids": [cargo_field.id], "op": "single", "verified": True},
                    {"site_id": excluded_site.id, "field_ids": [cargo_field.id], "op": "single", "verified": True},
                ],
            },
        }

        template = create_report_template(
            "Grand Total Exclusion Report", f"test-gtexcl-{user.id}", None, "global", None, config_json, user.id,
        )
        created_objects.append(template)

        result = pivot_report_data(template.id, user.id)

        included_group = next(g for g in result["row_groups"] if g["id"] == "included_group")
        excluded_group = next(g for g in result["row_groups"] if g["id"] == "excluded_group")

        # Both groups compute their own subtotal correctly...
        assert included_group["subtotal"]["metrics"]["cargo"] == pytest.approx(1000.0)
        assert excluded_group["subtotal"]["metrics"]["cargo"] == pytest.approx(999999999999.0)

        # ...but the grand total matches ONLY the included group's subtotal.
        assert result["grand_total"]["metrics"]["cargo"] == pytest.approx(1000.0)
        assert result["grand_total"]["metrics"]["scope1"] is None


class TestGenerateReportDataUnchanged:
    """generate_report_data's flat-row contract must not change -- pivot_report_data
    only reuses it. This locks in the existing keys (site_id/field_id are new,
    additive keys; nothing existing was removed or renamed)."""

    def test_flat_row_shape_and_values(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        from app.modules.RPTBLD.service import create_report_template, generate_report_data

        site = make_site()
        form, form_version = make_form()
        field, fv = make_field(form, form_version, "cargo_code")
        workflow_version = make_workflow([])
        period = make_reporting_period(site, year=2026, month=3)
        sub = make_submission(
            site, form, form_version, period, workflow_version,
            status="Approved", is_locked=True,
        )
        make_submission_value(sub, field, fv, raw_value="42")

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)

        template = create_report_template(
            "Flat Row Report", f"test-flat-{user.id}", None, "global", None,
            {"form_ids": [form.id], "site_ids": [site.id]}, user.id,
        )
        created_objects.append(template)

        rows = generate_report_data(template.id, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row["site_id"] == site.id
        assert row["field_id"] == field.id
        assert row["value"] == 42.0
        assert set(row.keys()) == {
            "period_label", "site_id", "site_name", "form_name", "field_id",
            "field_code", "field_name", "field_type", "value", "unit",
        }


class TestEmissionFactorVersion:
    def test_defaults_when_no_row_present(self):
        from app.modules.RPTBLD.service import get_emission_factor_version

        assert get_emission_factor_version() == "V21"

    def test_returns_configured_value(self, db_session, created_objects, make_user):
        from app.modules.RPTBLD.model import AppConfig
        from app.modules.RPTBLD.service import get_emission_factor_version

        user = make_user()
        row = AppConfig(
            config_key="cea_emission_factor_version",
            config_value="V22",
            config_type="string",
            updated_by=user.id,
        )
        db_session.add(row)
        db_session.flush()
        created_objects.append(row)

        assert get_emission_factor_version() == "V22"
