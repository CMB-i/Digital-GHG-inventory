"""
Route-level tests for RPTBLD/views.py's phase-4 additions: GET
/api/canonical-metrics (read-only vocabulary for the frontend's metric
aliasing/computed-column panels) and GET /api/templates/<id>/pivot-preview
(a thin wrapper around pivot_report_data, mirroring the existing /preview
route's error handling). Existing routes in this file have no prior test
coverage, so this is the first file for it.
"""
from app.modules.RPTBLD.service import METRIC_KEY_DISPLAY_ORDER, CROSS_SITE_SHEET1_COLUMNS, pivot_report_data


class TestCanonicalMetricsRoute:
    def test_requires_permission(self, client, make_user):
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.get("/module/RPTBLD/api/canonical-metrics")
        assert resp.status_code == 403

    def test_returns_the_canonical_metric_vocabulary_in_order(
        self, client, make_user, make_access_grant,
    ):
        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get("/module/RPTBLD/api/canonical-metrics")
        assert resp.status_code == 200
        assert resp.get_json() == {
            "metrics": list(METRIC_KEY_DISPLAY_ORDER),
            "sheet1_columns": list(CROSS_SITE_SHEET1_COLUMNS),
        }

    def test_sheet1_columns_is_the_same_source_the_excel_export_uses(
        self, client, make_user, make_access_grant,
    ):
        """The whole point of serving this from the backend: reports.js
        fetches this instead of hardcoding its own copy, so the web preview
        and the Excel export (_write_pivot_sheet, which imports
        CROSS_SITE_SHEET1_COLUMNS directly) can never drift apart again."""
        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get("/module/RPTBLD/api/canonical-metrics")
        sheet1_columns = resp.get_json()["sheet1_columns"]
        assert [c["label"] for c in sheet1_columns] == [
            "Cargo Handled (MT)", "Energy (GJ) - Electrical", "Energy Intensity Electrical (KJ/MT)",
            "Energy (GJ) - Fossil Fuels", "Energy Intensity Fossil Fuels (KJ/MT)", "Energy (GJ)",
            "Energy Intensity (000' GJ/Mn MT)", "GHG Emission Scope-1 (tCO2e)", "Scope-1 GHG Intensity (KgCO2e/MT)",
            "GHG Emission Scope-2 (tCO2e)", "Scope-2 GHG Intensity (KgCO2e/MT)", "Total GHG Emission (tCO2e)",
            "% Contribution of Total Emissions", "GHG Intensity (KgCO2e/MT)", "Variation from Average Intensity",
            "Electrical Power (MWH/MnT)", "Diesel (KL/MnT)", "Petrol (KL/MnT)", "IFO/HFHSD (KL/MnT)",
            "Power Consumption MWH", "Diesel Consumption KL",
        ]


class TestPivotPreviewRoute:
    def test_requires_permission(self, client, make_user):
        stranger = make_user()
        with client.session_transaction() as sess:
            sess["user_id"] = stranger.id

        resp = client.get("/module/RPTBLD/api/templates/999999/pivot-preview")
        assert resp.status_code == 403

    def test_nonexistent_template_returns_400(self, client, make_user, make_access_grant):
        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get("/module/RPTBLD/api/templates/999999/pivot-preview")
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"

    def test_returns_pivot_report_data_shape_unmodified(
        self, client, make_site, make_form, make_field, make_workflow, make_reporting_period,
        make_submission, make_submission_value, make_user, make_access_grant, created_objects,
    ):
        from app.modules.RPTBLD.service import create_report_template

        site = make_site()
        form, form_version = make_form()
        cargo_field, cargo_fv = make_field(form, form_version, "cargo_code")
        workflow_version = make_workflow([])
        period = make_reporting_period(site, year=2026, month=3)
        sub = make_submission(
            site, form, form_version, period, workflow_version,
            status="Approved", is_locked=True,
        )
        make_submission_value(sub, cargo_field, cargo_fv, raw_value="500")

        user = make_user()
        make_access_grant(user, "report", scope_type="global", can_view=True)

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
            },
        }
        template = create_report_template(
            "Pivot Preview Route Report", f"test-pivot-route-{user.id}", None, "global", None, config_json, user.id,
        )
        created_objects.append(template)

        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get(f"/module/RPTBLD/api/templates/{template.id}/pivot-preview")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"

        expected = pivot_report_data(template.id, user.id)
        assert body["data"] == expected
