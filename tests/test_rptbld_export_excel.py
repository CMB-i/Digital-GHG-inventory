"""
export_report_to_excel: the existing flat-mode branch (Overview + "Report
Data" sheets) must stay byte-identical for templates that don't use
row_groups. Phase 3 only adds a new, additive "Report Data (Pivot)" sheet
when row_groups is configured, built from pivot_report_data() (phase 2).
Every assertion here reads the generated workbook back with openpyxl and
checks actual cell values/fills -- not just "no exception was raised."
"""
import io

import openpyxl
import pytest

from app.modules.RPTBLD.service import create_report_template, export_report_to_excel


class TestFlatModeExportUnaffected:
    def test_no_row_groups_produces_flat_only_workbook(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
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
        make_access_grant(user, "report", scope_type="global", can_export=True, can_view=True)

        template = create_report_template(
            "Flat Only Report", f"test-flat-xlsx-{user.id}", None, "global", None,
            {"form_ids": [form.id], "site_ids": [site.id]}, user.id,
        )
        created_objects.append(template)

        raw = export_report_to_excel(template.id, user.id)
        wb = openpyxl.load_workbook(io.BytesIO(raw))

        assert set(wb.sheetnames) == {"Overview", "Report Data"}

        ws = wb["Report Data"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, 9)]
        assert headers == ["Period", "Site Name", "Form Name", "Field Code", "Field Name", "Field Type", "Value", "Unit"]
        assert ws.cell(row=2, column=4).value == "cargo_code"
        assert ws.cell(row=2, column=7).value == 42.0


class TestPivotModeExport:
    def _setup(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        from app.modules.FRMULA.model import FormulaVersion
        from app.modules.FRMULA.service import create_formula, publish_formula_version

        site = make_site()
        form, form_version = make_form()
        cargo_field, cargo_fv = make_field(form, form_version, "cargo_code")
        scope1_field, scope1_fv = make_field(form, form_version, "scope1_code")  # aliased, never submitted -> blank cell
        power_field, power_fv = make_field(form, form_version, "power_code")
        diesel_field, diesel_fv = make_field(form, form_version, "diesel_code")

        workflow_version = make_workflow([])
        period = make_reporting_period(site, year=2026, month=3)
        sub = make_submission(
            site, form, form_version, period, workflow_version,
            status="Approved", is_locked=True,
        )
        make_submission_value(sub, cargo_field, cargo_fv, raw_value="1000")
        make_submission_value(sub, power_field, power_fv, raw_value="250")
        make_submission_value(sub, diesel_field, diesel_fv, raw_value="180")
        # scope1_field deliberately has no SubmissionValue -- the aliased
        # column exists but this row's value is missing.

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_export=True, can_view=True)

        n_formula = create_formula(
            "Error Col", f"test-xlsx-n-{user.id}", "cargo + energy_fossil",
            {"cargo": {}, "energy_fossil": {}}, user.id, context="report",
        )
        created_objects.append(n_formula)
        n_version = FormulaVersion.query.filter_by(formula_id=n_formula.id, version_number=1).one()
        created_objects.append(n_version)
        publish_formula_version(n_version.id, user.id)

        config_json = {
            "form_ids": [form.id],
            "site_ids": [site.id],
            "row_groups": [
                {
                    "id": "core", "label": "Core", "subtotal_label": "Total",
                    "site_ids": [site.id],
                    "include_in_grand_total": True, "is_reference_base": True,
                },
            ],
            "metric_aliases": {
                "cargo": [{"site_id": site.id, "field_ids": [cargo_field.id], "op": "single", "verified": True}],
                "scope1": [{"site_id": site.id, "field_ids": [scope1_field.id], "op": "single", "verified": True}],
                "power_specific": [{"site_id": site.id, "field_ids": [power_field.id], "op": "single", "verified": False}],
                "diesel_specific": [{"site_id": site.id, "field_ids": [diesel_field.id], "op": "single", "verified": True}],
            },
            "computed_columns": [
                {"id": "N", "label": "Error Col", "formula_id": n_formula.id},
            ],
        }

        template = create_report_template(
            "Pivot Export Report", f"test-xlsx-pivot-{user.id}", None, "global", None, config_json, user.id,
        )
        created_objects.append(template)
        return template, user, site

    def test_pivot_export_produces_both_sheets(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        template, user, site = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        raw = export_report_to_excel(template.id, user.id)
        wb = openpyxl.load_workbook(io.BytesIO(raw))

        assert {"Overview", "Report Data", "Report Data (Pivot)"} <= set(wb.sheetnames)
        # The flat sheet's own headers are still exactly what they were before this phase.
        ws_flat = wb["Report Data"]
        headers = [ws_flat.cell(row=1, column=c).value for c in range(1, 9)]
        assert headers == ["Period", "Site Name", "Form Name", "Field Code", "Field Name", "Field Type", "Value", "Unit"]

    def test_pivot_sheet_layout_and_values(
        self, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        template, user, site = self._setup(
            make_site, make_form, make_field, make_workflow, make_reporting_period,
            make_submission, make_submission_value, make_user, make_access_grant, created_objects,
        )

        raw = export_report_to_excel(template.id, user.id)
        wb = openpyxl.load_workbook(io.BytesIO(raw))
        ws = wb["Report Data (Pivot)"]

        # Columns: 1=Row Group, 2=Site, 3=Cargo, 4=Scope1, 5=Power Specific,
        # 6=Diesel Specific, 7=Error Col (computed). energy_elec/energy_fossil/
        # scope2/total_ghg/petrol_specific/ifo_specific never aliased -> no columns.
        headers = [ws.cell(row=2, column=c).value for c in range(1, 8)]
        assert headers == ["Row Group", "Site", "Cargo", "Scope1", "Power Specific", "Diesel Specific", "Error Col"]

        # Banner merges over exactly the 2 specific-consumption columns
        # actually present (columns 5-6), not a hardcoded fixed range.
        assert ws.cell(row=1, column=5).value == "Specific Consumptions"
        merged_ranges = [str(r) for r in ws.merged_cells.ranges]
        assert "E1:F1" in merged_ranges
        assert ws.cell(row=1, column=3).value is None  # no banner over Cargo
        assert ws.cell(row=1, column=7).value is None  # no banner over the computed column

        # Row 3 is the (only) site row.
        assert ws.cell(row=3, column=1).value == "Core"
        assert ws.cell(row=3, column=3).value == 1000.0   # cargo, verified
        assert ws.cell(row=3, column=4).value is None     # scope1 aliased but never submitted -> blank, not 0/"None"
        assert ws.cell(row=3, column=5).value == 250.0    # power_specific, unverified
        assert ws.cell(row=3, column=6).value == 180.0    # diesel_specific, verified

        # Unverified sourced cell is amber-flagged; verified ones are not.
        amber = "FEF3C7"
        assert ws.cell(row=3, column=5).fill.start_color.rgb[-6:] == amber
        assert ws.cell(row=3, column=3).fill.start_color.rgb in (None, "00000000")
        assert ws.cell(row=3, column=6).fill.start_color.rgb in (None, "00000000")

        # Computed column error renders as text, not blank and not a Python exception repr.
        error_value = ws.cell(row=3, column=7).value
        assert error_value is not None
        assert isinstance(error_value, str)
        assert "energy_fossil" in error_value
        assert "Traceback" not in error_value
        assert "Error(" not in error_value

        # Row 4: subtotal, bold, labeled from the group's subtotal_label.
        assert ws.cell(row=4, column=2).value == "Total"
        assert ws.cell(row=4, column=2).font.bold is True
        assert ws.cell(row=4, column=3).value == 1000.0

        # Row 5: grand total, bold, default label since config_json carries none.
        assert ws.cell(row=5, column=2).value == "All Locations"
        assert ws.cell(row=5, column=2).font.bold is True
        assert ws.cell(row=5, column=3).value == 1000.0
