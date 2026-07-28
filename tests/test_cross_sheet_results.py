"""
Cross-sheet "Sheet/FY result below table" formulas: GRI Summary's fields sum
OTHER sheets' own FY totals (e.g. Cargo Handled's, Electricity's), which
compose_annual_workbook_data / _compose_sheet_results never supported --
every token was resolved only against the current sheet's own fields, so a
cross-sheet reference always failed with "Unknown formula variable" even
though FRMULA's formula builder now happily lets you build one.

See _CrossSheetResolver (app/modules/SUBMIT/service.py) for the resolution
design: sheet-level results have no persisted store anywhere (unlike a
monthly field's calculated_value), so sibling sheets are recomputed on
demand, memoized per request, scoped to sheets in the same workbook.

Unit-level coverage of _compose_sheet_results's resolve_external contract
(what happens for each of "ok" / pending / hard_error / unresolvable) lives
in tests/test_calc_status.py's TestComposeSheetResultsCrossSheetResolveExternal
-- this file exercises the real thing end-to-end: two actual sheets in one
workbook, real submissions, going through compose_annual_workbook_data.
"""
from decimal import Decimal

from app.modules.SUBMIT.model import WorkbookFieldValue
from app.modules.SUBMIT.service import compose_annual_workbook_data
from app.modules.WKBK.model import WorkbookForm


def _attach_sibling_sheet(db_session, created_objects, workbook, form, display_order):
    wf = WorkbookForm(workbook_id=workbook.id, form_id=form.id, display_order=display_order)
    db_session.add(wf)
    db_session.flush()
    created_objects.append(wf)


class TestCrossSheetValueResolution:
    """
    Two sheets, one workbook: "Cargo Handled"-style upstream sheet with a
    plain monthly field (its FY total is synthesized automatically, exactly
    like every real sheet's per-field FY totals), and a "GRI Summary"-style
    downstream sheet whose one field's formula references that FY total's
    field code directly (bare, not SUM_MONTHS-wrapped -- matching how the
    real GRI Summary formulas were built).
    """

    def _build_workbook(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        upstream_form, upstream_version = make_form()
        upstream_field, upstream_field_version = make_field(
            upstream_form, upstream_version, "upstream_monthly", field_type="number",
        )
        upstream_total_code = "upstream_monthly__auto_fy_total"

        downstream_form, downstream_version = make_form()
        formula = make_formula_version(f"{upstream_total_code} * 2", {upstream_total_code: {}})
        make_field(
            downstream_form, downstream_version, "downstream_total", field_type="calculated",
            field_config={"formula_version_id": formula.id, "display_region": "below_monthly_table"},
        )

        site = make_site()
        user = make_user()
        workflow_version = make_workflow([user])
        workbook = make_workbook(upstream_form, site, workflow_version=workflow_version, submitters=[user])
        _attach_sibling_sheet(db_session, created_objects, workbook, downstream_form, display_order=20)
        make_access_grant(user, "submission", scope_type="global", can_view=True, can_submit=True)

        return upstream_form, upstream_version, upstream_field, upstream_field_version, downstream_form, site, user, workbook

    def test_downstream_value_resolves_once_upstream_data_is_entered(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_workbook, make_access_grant, make_submission,
        make_submission_value, db_session, created_objects,
    ):
        (
            upstream_form, upstream_version, upstream_field, upstream_field_version,
            downstream_form, site, user, workbook,
        ) = self._build_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )

        # make_reporting_period defaults to year=2026, month=4 -- the first
        # month of FY 2026, matching fy_start_year=2026 below.
        period = make_reporting_period(site)
        workflow_version = make_workflow([user])
        submission = make_submission(site, upstream_form, upstream_version, period, workflow_version)
        make_submission_value(submission, upstream_field, upstream_field_version, raw_value="100")

        data = compose_annual_workbook_data(
            user.id, site_id=site.id, workbook_id=workbook.id, fy_start_year=2026,
            selected_form_id=downstream_form.id,
        )

        results = {r["field_code"]: r for r in data["sheet_results"]}
        result = results["downstream_total"]
        # Only April has a real submission -- the other 11 months of the FY
        # have no ReportingPeriod at all, so upstream's own automatic FY
        # total is itself "partial", and that partiality correctly
        # propagates downstream (see TestComposeSheetResultsCrossSheetResolveExternal's
        # partial-upstream test for that mechanism in isolation).
        assert result["status"] == "partial"
        assert result["value"] == 200.0
        assert "is itself a partial result" in result["message"]

    def test_no_upstream_data_surfaces_as_pending_not_unknown_variable(
        self, make_form, make_field, make_formula_version, make_site, make_reporting_period,
        make_workflow, make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        (
            upstream_form, upstream_version, upstream_field, upstream_field_version,
            downstream_form, site, user, workbook,
        ) = self._build_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )
        # No ReportingPeriod, no Submission, no SubmissionValue at all for the
        # upstream sheet -- this is the "Jaigarh workbook, July 2025, GRI
        # Summary, currently-empty Cargo Handled/Electricity/Fuel Consumption"
        # repro case.

        data = compose_annual_workbook_data(
            user.id, site_id=site.id, workbook_id=workbook.id, fy_start_year=2026,
            selected_form_id=downstream_form.id,
        )

        results = {r["field_code"]: r for r in data["sheet_results"]}
        result = results["downstream_total"]
        assert result["status"] == "needs_input"
        assert "Unknown formula variable" not in result["message"]
        assert "Waiting on" in result["message"]
        assert upstream_form.name in result["message"]

    def test_sibling_annual_result_uses_saved_workbook_values(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
        system_user,
    ):
        upstream_form, upstream_version = make_form()
        raw_field, raw_version = make_field(
            upstream_form,
            upstream_version,
            "ofr_acetylene_qty_t",
            field_type="number",
            frequency="annual",
        )
        formula = make_formula_version("ofr_acetylene_qty_t * 47.3", {"ofr_acetylene_qty_t": {}})
        make_field(
            upstream_form,
            upstream_version,
            "ofr_acetylene_gj",
            field_type="calculated",
            frequency="annual",
            field_config={"formula_version_id": formula.id, "display_region": "below_monthly_table"},
        )

        downstream_form, downstream_version = make_form()
        downstream_formula = make_formula_version("ofr_acetylene_gj + 10", {"ofr_acetylene_gj": {}})
        make_field(
            downstream_form,
            downstream_version,
            "fuel_total",
            field_type="calculated",
            frequency="annual",
            field_config={"formula_version_id": downstream_formula.id, "display_region": "below_monthly_table"},
        )

        site = make_site()
        user = make_user()
        workflow_version = make_workflow([user])
        workbook = make_workbook(downstream_form, site, workflow_version=workflow_version, submitters=[user])
        _attach_sibling_sheet(db_session, created_objects, workbook, upstream_form, display_order=20)
        make_access_grant(user, "submission", scope_type="global", can_view=True, can_submit=True)

        saved_value = WorkbookFieldValue(
            site_id=site.id,
            form_id=upstream_form.id,
            field_id=raw_field.id,
            field_version_id=raw_version.id,
            fy_start_year=2026,
            value_text="0.026",
            numeric_value=Decimal("0.026"),
            cell_state="draft_filled",
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(saved_value)
        db_session.flush()
        created_objects.append(saved_value)

        data = compose_annual_workbook_data(
            user.id, site_id=site.id, workbook_id=workbook.id, fy_start_year=2026,
            selected_form_id=downstream_form.id,
        )

        results = {r["field_code"]: r for r in data["sheet_results"]}
        assert results["fuel_total"]["status"] == "calculated"
        assert results["fuel_total"]["value"] == round(0.026 * 47.3 + 10, 3)


class TestCrossSheetCircularDependency:
    """
    Sheet A's result field formula references Sheet B's, and Sheet B's
    references Sheet A's right back -- a cross-sheet cycle, only possible at
    all because FRMULA's cross-sheet formula builder is unscoped enough to
    let two sibling sheets point at each other. Point 3 of the cross-sheet
    design brief: this must surface as a clear blocking error, never an
    infinite recursion or a crash.
    """

    def test_mutual_cross_sheet_reference_surfaces_as_error_not_infinite_loop(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        form_a, version_a = make_form()
        form_b, version_b = make_form()

        formula_a = make_formula_version("b_total + 1", {"b_total": {}})
        formula_b = make_formula_version("a_total + 1", {"a_total": {}})
        make_field(
            form_a, version_a, "a_total", field_type="calculated",
            field_config={"formula_version_id": formula_a.id, "field_scope": "annual_result"},
        )
        make_field(
            form_b, version_b, "b_total", field_type="calculated",
            field_config={"formula_version_id": formula_b.id, "field_scope": "annual_result"},
        )

        site = make_site()
        user = make_user()
        workflow_version = make_workflow([user])
        workbook = make_workbook(form_a, site, workflow_version=workflow_version, submitters=[user])
        _attach_sibling_sheet(db_session, created_objects, workbook, form_b, display_order=20)
        make_access_grant(user, "submission", scope_type="global", can_view=True, can_submit=True)

        # The real assertion is simply that this call returns at all (no
        # RecursionError / infinite loop) within the test's normal timeout.
        data = compose_annual_workbook_data(
            user.id, site_id=site.id, workbook_id=workbook.id, fy_start_year=2026,
            selected_form_id=form_a.id,
        )

        results = {r["field_code"]: r for r in data["sheet_results"]}
        assert results["a_total"]["status"] == "error"
        assert "circular cross-sheet" in results["a_total"]["message"].lower()
