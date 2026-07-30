"""
compose_cross_site_intensity_report -- the SPT / Non-SPT cross-site GHG
intensity summary replicating Combined_JSW_Infra_YTD_2025-26.xlsx Sheet1.

Builds real per-site workbooks (shared field set, separate Workbook/
Submission rows per site) through the same submit_svc machinery
_site_flat_index_for_fy uses, so these are genuine integration tests of the
SUM_MONTHS-correct path, not a re-implementation of the composer's own math.

Covers: the flat_index last-write-wins bug is actually bypassed (not just
believed to be); include_unapproved gating both ways; the Mangalore-
Container-style op="sum" 2-field alias case; the U/V fix (populated for
Non-SPT rows, unlike the source); and the N/P cross-row scoping against the
SPT group's own total specifically (the easiest part of this feature to get
subtly wrong).
"""
import pytest

from app.modules.RPTBLD.service import compose_cross_site_intensity_report

FY_MONTHS_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def _build_metric_form(make_form, make_field, make_formula_version):
    """One shared Form (cargo/elec/scope1/scope2/power_a/power_b/diesel, each
    a monthly raw field plus an explicit SUM_MONTHS annual field) reused
    across every site's own Workbook in these tests -- mirrors production's
    real fy_total_* field convention exactly."""
    form, form_version = make_form()
    fields = {}

    def _add(raw_code, annual_code):
        raw_field, raw_version = make_field(form, form_version, raw_code, field_type="number", frequency="monthly")
        formula_version = make_formula_version(f"SUM_MONTHS({raw_code})", {raw_code: {}})
        annual_field, annual_version = make_field(
            form, form_version, annual_code, field_type="calculated", frequency="annual",
            field_config={"formula_version_id": formula_version.id, "display_region": "below_monthly_table"},
        )
        fields[raw_code] = (raw_field, raw_version)
        fields[annual_code] = (annual_field, annual_version)

    _add("cargo_qty", "fy_total_cargo")
    _add("elec_qty", "fy_total_energy_elec")
    _add("scope1_qty", "fy_total_scope1")
    _add("scope2_qty", "fy_total_scope2")
    _add("power_a_qty", "fy_total_power_a")
    _add("power_b_qty", "fy_total_power_b")
    _add("diesel_qty", "fy_total_diesel")
    return form, form_version, fields


def _populate_site_months(
    site, form, form_version, fields, monthly_values,
    make_workflow, make_user, make_workbook, make_access_grant,
    make_reporting_period, make_submission, make_submission_value,
    draft_month_indices=None,
):
    """monthly_values: {raw_code: [12 values, Apr..Mar, None to skip]}.
    draft_month_indices: month indices (0-based, Apr..Mar order) whose
    submission is Draft+unlocked instead of Approved+locked."""
    draft_month_indices = draft_month_indices or set()
    user = make_user()
    workflow_version = make_workflow([user])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[user])
    make_access_grant(
        user, "submission", scope_type="global",
        can_view=True, can_create=True, can_edit=True, can_submit=True,
    )

    for i, month in enumerate(FY_MONTHS_ORDER):
        year = 2026 if month >= 4 else 2027
        period = make_reporting_period(site, year=year, month=month)
        if i in draft_month_indices:
            status, locked = "Draft", False
        else:
            status, locked = "Approved", True
        submission = make_submission(
            site, form, form_version, period, workflow_version,
            status=status, is_locked=locked,
        )
        for raw_code, values in monthly_values.items():
            value = values[i]
            if value is None:
                continue
            raw_field, raw_version = fields[raw_code]
            make_submission_value(submission, raw_field, raw_version, raw_value=str(value))

    return workbook


def _base_config(row_groups, metric_aliases, computed_columns=None, include_unapproved=True):
    return {
        "row_groups": row_groups,
        "metric_aliases": metric_aliases,
        "computed_columns": computed_columns or [],
        "include_unapproved": include_unapproved,
    }


def _single_alias(site_id, field_id):
    return [{"site_id": site_id, "field_ids": [field_id], "op": "single", "verified": True}]


class TestFyTotalBypassesFlatIndexBug:
    """generate_report_data/pivot_report_data's flat_index is last-write-wins
    across months (silently keeps only the last-processed month's value).
    compose_cross_site_intensity_report must never reproduce that -- it goes
    through _site_flat_index_for_fy's SUM_MONTHS-correct path instead. A
    huge, obviously-distinct last month makes a last-write-wins regression
    unmissable."""

    def test_multi_month_cargo_sums_correctly_not_last_write_wins(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        site = make_site()
        form, form_version, fields = _build_metric_form(make_form, make_field, make_formula_version)

        cargo_values = [100] * 11 + [100000]  # last month is deliberately huge
        _populate_site_months(
            site, form, form_version, fields, {"cargo_qty": cargo_values},
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
        )

        config = _base_config(
            row_groups=[{
                "id": "grp", "label": "Group", "subtotal_label": "Total",
                "site_ids": [site.id], "is_reference_base": True, "include_in_grand_total": True,
            }],
            metric_aliases={"cargo": _single_alias(site.id, fields["fy_total_cargo"][0].id)},
        )

        result = compose_cross_site_intensity_report([site.id], 2026, config)
        row = result["row_groups"][0]["site_rows"][0]

        # Correct SUM_MONTHS total: 11*100 + 100000 = 101100.
        # A last-write-wins regression would show 100000 alone.
        assert row["metrics"]["cargo"]["value"] == pytest.approx(101100)


class TestIncludeUnapprovedGating:
    def test_draft_month_included_when_include_unapproved_true_excluded_when_false(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        site = make_site()
        form, form_version, fields = _build_metric_form(make_form, make_field, make_formula_version)

        # 11 Approved months of 1000, plus one Draft month (index 5) of a
        # deliberately absurd value -- unmissable if wrongly included/excluded.
        cargo_values = [1000] * 12
        cargo_values[5] = 999999
        _populate_site_months(
            site, form, form_version, fields, {"cargo_qty": cargo_values},
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
            draft_month_indices={5},
        )

        row_groups = [{
            "id": "grp", "label": "Group", "subtotal_label": "Total",
            "site_ids": [site.id], "is_reference_base": True, "include_in_grand_total": True,
        }]
        metric_aliases = {"cargo": _single_alias(site.id, fields["fy_total_cargo"][0].id)}

        config_included = _base_config(row_groups, metric_aliases, include_unapproved=True)
        config_excluded = _base_config(row_groups, metric_aliases, include_unapproved=False)

        result_included = compose_cross_site_intensity_report([site.id], 2026, config_included)
        result_excluded = compose_cross_site_intensity_report([site.id], 2026, config_excluded)

        row_included = result_included["row_groups"][0]["site_rows"][0]
        row_excluded = result_excluded["row_groups"][0]["site_rows"][0]

        assert row_included["metrics"]["cargo"]["value"] == pytest.approx(11 * 1000 + 999999)
        assert row_excluded["metrics"]["cargo"]["value"] == pytest.approx(11 * 1000)
        assert result_included["include_unapproved"] is True
        assert result_excluded["include_unapproved"] is False


class TestSumOfTwoFieldsAlias:
    """Mangalore Container / Jaigarh-style case: a site with no single
    combined power field sums two raw components via op="sum" -- confirms
    _resolve_alias_entry_value's sum path is exercised against real,
    SUM_MONTHS-derived FY totals, not just unit-level dicts."""

    def test_op_sum_resolves_to_combined_total(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        site = make_site()
        form, form_version, fields = _build_metric_form(make_form, make_field, make_formula_version)

        _populate_site_months(
            site, form, form_version, fields,
            {"power_a_qty": [40] * 12, "power_b_qty": [60] * 12},
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
        )

        config = _base_config(
            row_groups=[{
                "id": "grp", "label": "Group", "subtotal_label": "Total",
                "site_ids": [site.id], "is_reference_base": True, "include_in_grand_total": True,
            }],
            metric_aliases={
                "power_specific": [{
                    "site_id": site.id,
                    "field_ids": [fields["fy_total_power_a"][0].id, fields["fy_total_power_b"][0].id],
                    "op": "sum", "verified": True,
                }],
            },
        )

        result = compose_cross_site_intensity_report([site.id], 2026, config)
        row = result["row_groups"][0]["site_rows"][0]

        # 12 months of 40 + 12 months of 60 = 480 + 720 = 1200.
        assert row["metrics"]["power_specific"]["value"] == pytest.approx(1200)


class TestNPCrossRowScopingAndUVFix:
    """The primary fixture: 3 SPT sites + 2 Non-SPT sites with known
    cargo/scope1/scope2 FY totals, verifying:
      - N (% Contribution) divides EVERY row's Total GHG Emission by the
        SPT group's own Total -- including the Non-SPT rows, which is the
        source's actual (non-obvious) behavior, not a bug.
      - P (Variation) is populated ONLY for SPT rows; None everywhere else
        (Non-SPT rows, every subtotal row, the grand total).
      - power_consumption_mwh / diesel_consumption_kl (U/V) are populated
        for Non-SPT rows too -- the source leaves these blank there, which
        this composer deliberately does not replicate.
      - The Non-SPT group's own internal subtotal is NOT the grand total;
        the grand total is SPT-subtotal + Non-SPT-rows-sum, matching the
        source's "Total All Locations" row.
    """

    def _build(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        make_user_for_formulas, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        form, form_version, fields = _build_metric_form(make_form, make_field, make_formula_version)

        spt_sites = [make_site() for _ in range(3)]
        non_spt_sites = [make_site() for _ in range(2)]

        # (cargo, scope1, scope2) FY totals per site -- exact multiples of 12
        # so constant integer monthly values reproduce these totals exactly.
        exact_totals = {
            spt_sites[0]: {"cargo_qty": 12000, "scope1_qty": 96, "scope2_qty": 192},
            spt_sites[1]: {"cargo_qty": 19200, "scope1_qty": 144, "scope2_qty": 348},
            spt_sites[2]: {"cargo_qty": 4800, "scope1_qty": 48, "scope2_qty": 48},
            non_spt_sites[0]: {"cargo_qty": 7920, "scope1_qty": 84, "scope2_qty": 24},
            non_spt_sites[1]: {"cargo_qty": 1920, "scope1_qty": 36, "scope2_qty": 60},
        }

        power_diesel_totals = {}
        for site in spt_sites + non_spt_sites:
            power_diesel_totals[site] = {"power_a_qty": 60, "diesel_qty": 12}

        for site, totals in exact_totals.items():
            monthly_values = {code: [total // 12] * 12 for code, total in totals.items()}
            pd = power_diesel_totals[site]
            monthly_values["power_a_qty"] = [pd["power_a_qty"] // 12] * 12
            monthly_values["diesel_qty"] = [pd["diesel_qty"] // 12] * 12
            _populate_site_months(
                site, form, form_version, fields, monthly_values,
                make_workflow, make_user, make_workbook, make_access_grant,
                make_reporting_period, make_submission, make_submission_value,
            )

        formula_user = make_user_for_formulas()
        m_formula = create_formula(
            "Total GHG", f"test-cross-m-{formula_user.id}", "scope1 + scope2",
            {"scope1": {}, "scope2": {}}, formula_user.id, context="report",
        )
        created_objects.append(m_formula)
        m_version = FormulaVersion.query.filter_by(formula_id=m_formula.id, version_number=1).one()
        created_objects.append(m_version)
        publish_formula_version(m_version.id, formula_user.id)

        o_formula = create_formula(
            "GHG Intensity", f"test-cross-o-{formula_user.id}", "(scope1 + scope2) * 1000 / cargo",
            {"scope1": {}, "scope2": {}, "cargo": {}}, formula_user.id, context="report",
        )
        created_objects.append(o_formula)
        o_version = FormulaVersion.query.filter_by(formula_id=o_formula.id, version_number=1).one()
        created_objects.append(o_version)
        publish_formula_version(o_version.id, formula_user.id)

        def alias_for(metric_key, field_key):
            return [
                {"site_id": site.id, "field_ids": [fields[field_key][0].id], "op": "single", "verified": True}
                for site in spt_sites + non_spt_sites
            ]

        metric_aliases = {
            "cargo": alias_for("cargo", "fy_total_cargo"),
            "scope1": alias_for("scope1", "fy_total_scope1"),
            "scope2": alias_for("scope2", "fy_total_scope2"),
            "power_specific": alias_for("power_specific", "fy_total_power_a"),
            "diesel_specific": alias_for("diesel_specific", "fy_total_diesel"),
            "power_consumption_mwh": alias_for("power_consumption_mwh", "fy_total_power_a"),
            "diesel_consumption_kl": alias_for("diesel_consumption_kl", "fy_total_diesel"),
        }

        config = _base_config(
            row_groups=[
                {
                    "id": "spt", "label": "SPT", "subtotal_label": "Total",
                    "site_ids": [s.id for s in spt_sites],
                    "is_reference_base": True, "include_in_grand_total": True,
                },
                {
                    "id": "non_spt", "label": "Non-SPT",
                    "subtotal_label": "Total All Locations (incl. Non SPT)",
                    "site_ids": [s.id for s in non_spt_sites],
                    "is_reference_base": False, "include_in_grand_total": True,
                    "suppress_own_subtotal": True,
                },
            ],
            metric_aliases=metric_aliases,
            computed_columns=[
                {"id": "total_ghg_emission", "label": "Total GHG Emission", "formula_id": m_formula.id},
                {"id": "ghg_intensity", "label": "GHG Intensity", "formula_id": o_formula.id},
                {"id": "pct_contribution_total_ghg", "label": "% Contribution", "kind": "cross_site"},
                {"id": "variation_from_avg_intensity", "label": "Variation", "kind": "cross_site"},
            ],
        )

        all_site_ids = [s.id for s in spt_sites + non_spt_sites]
        return spt_sites, non_spt_sites, all_site_ids, config

    def test_n_divides_every_row_by_spt_total_including_non_spt(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        spt_sites, non_spt_sites, all_site_ids, config = self._build(
            make_site, make_form, make_field, make_formula_version,
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
            make_user, created_objects,
        )

        result = compose_cross_site_intensity_report(all_site_ids, 2026, config)

        # SPT total M = (96+192) + (144+348) + (48+48) = 288 + 492 + 96 = 876
        spt_total_m = 876

        rows_by_site = {}
        for group in result["row_groups"]:
            for row in group["site_rows"]:
                rows_by_site[row["site_id"]] = (row, group["is_reference_base"])

        expected_m = {
            spt_sites[0].id: 96 + 192,
            spt_sites[1].id: 144 + 348,
            spt_sites[2].id: 48 + 48,
            non_spt_sites[0].id: 84 + 24,
            non_spt_sites[1].id: 36 + 60,
        }

        for site_id, m in expected_m.items():
            row, _is_spt = rows_by_site[site_id]
            assert row["computed"]["total_ghg_emission"]["value"] == pytest.approx(m)
            expected_pct = m / spt_total_m * 100
            assert row["computed"]["pct_contribution_total_ghg"]["value"] == pytest.approx(expected_pct)

        # Non-SPT rows' % contribution is explicitly against the SPT total,
        # never the Non-SPT group's own (much smaller) subtotal.
        non_spt_row, _ = rows_by_site[non_spt_sites[0].id]
        non_spt_only_total = (84 + 24) + (36 + 60)
        wrong_pct_if_scoped_to_own_group = non_spt_row["computed"]["total_ghg_emission"]["value"] / non_spt_only_total * 100
        assert non_spt_row["computed"]["pct_contribution_total_ghg"]["value"] != pytest.approx(wrong_pct_if_scoped_to_own_group)

    def test_p_populated_only_for_spt_rows(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        spt_sites, non_spt_sites, all_site_ids, config = self._build(
            make_site, make_form, make_field, make_formula_version,
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
            make_user, created_objects,
        )

        result = compose_cross_site_intensity_report(all_site_ids, 2026, config)

        # SPT group's own O: total M=876, total cargo=12000+19200+4800=36000
        spt_total_o = 876 * 1000 / 36000

        spt_group = next(g for g in result["row_groups"] if g["is_reference_base"])
        non_spt_group = next(g for g in result["row_groups"] if not g["is_reference_base"])

        expected_o = {
            spt_sites[0].id: (96 + 192) * 1000 / 12000,
            spt_sites[1].id: (144 + 348) * 1000 / 19200,
            spt_sites[2].id: (48 + 48) * 1000 / 4800,
        }
        for row in spt_group["site_rows"]:
            expected_variation = spt_total_o - expected_o[row["site_id"]]
            assert row["computed"]["variation_from_avg_intensity"]["value"] == pytest.approx(expected_variation)

        for row in non_spt_group["site_rows"]:
            assert row["computed"]["variation_from_avg_intensity"]["value"] is None

        assert spt_group["subtotal"]["computed"]["variation_from_avg_intensity"]["value"] is None
        assert non_spt_group["subtotal"]["computed"]["variation_from_avg_intensity"]["value"] is None
        assert result["grand_total"]["computed"]["variation_from_avg_intensity"]["value"] is None

        # % Contribution is likewise blank on every subtotal / grand total row --
        # not meaningful for an aggregate row.
        assert spt_group["subtotal"]["computed"]["pct_contribution_total_ghg"]["value"] is None
        assert non_spt_group["subtotal"]["computed"]["pct_contribution_total_ghg"]["value"] is None
        assert result["grand_total"]["computed"]["pct_contribution_total_ghg"]["value"] is None

    def test_uv_populated_for_non_spt_rows_fixing_source_gap(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        spt_sites, non_spt_sites, all_site_ids, config = self._build(
            make_site, make_form, make_field, make_formula_version,
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
            make_user, created_objects,
        )

        result = compose_cross_site_intensity_report(all_site_ids, 2026, config)

        non_spt_group = next(g for g in result["row_groups"] if not g["is_reference_base"])
        for row in non_spt_group["site_rows"]:
            assert row["metrics"]["power_consumption_mwh"]["value"] == pytest.approx(60)
            assert row["metrics"]["diesel_consumption_kl"]["value"] == pytest.approx(12)

    def test_non_spt_groups_own_subtotal_is_not_the_grand_total(
        self, make_site, make_form, make_field, make_formula_version,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        created_objects,
    ):
        spt_sites, non_spt_sites, all_site_ids, config = self._build(
            make_site, make_form, make_field, make_formula_version,
            make_workflow, make_user, make_workbook, make_access_grant,
            make_reporting_period, make_submission, make_submission_value,
            make_user, created_objects,
        )

        result = compose_cross_site_intensity_report(all_site_ids, 2026, config)

        spt_group = next(g for g in result["row_groups"] if g["is_reference_base"])
        non_spt_group = next(g for g in result["row_groups"] if not g["is_reference_base"])

        spt_total_cargo = 12000 + 19200 + 4800
        non_spt_only_cargo = 7920 + 1920
        grand_total_cargo = spt_total_cargo + non_spt_only_cargo

        assert spt_group["subtotal"]["metrics"]["cargo"] == pytest.approx(spt_total_cargo)
        # The Non-SPT group's own internal subtotal is only its 2 rows' sum --
        # NOT the grand total -- even though the source labels the row that
        # appears in this position "Total All Locations (incl. Non SPT)".
        assert non_spt_group["subtotal"]["metrics"]["cargo"] == pytest.approx(non_spt_only_cargo)
        assert non_spt_group["subtotal"]["metrics"]["cargo"] != pytest.approx(grand_total_cargo)

        assert result["grand_total"]["metrics"]["cargo"] == pytest.approx(grand_total_cargo)
