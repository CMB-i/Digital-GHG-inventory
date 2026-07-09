"""Summary dashboard visualization: layout types, payload composition, validation."""
from datetime import datetime, timezone

import pytest

from app.modules.FORMBLD.model import FormSection, FormVersion
from app.modules.FORMBLD.service import (
    compose_preview_workbook_context,
    save_form_draft_fields,
    save_form_sections,
)
from app.modules.SUBMIT.service import (
    _compose_visualization_payload,
    compose_annual_workbook_data,
)


class TestSummaryDashboardLayout:
    def test_save_form_sections_accepts_summary_dashboard(self, make_form, system_user, db_session):
        form, form_version = make_form()
        sections = save_form_sections(
            form_version.id,
            [
                {
                    "code": "sec_summary",
                    "name": "GRI Summary",
                    "layout_type": "summary_dashboard",
                    "display_order": 1,
                }
            ],
            system_user,
        )
        db_session.commit()

        section = sections["sec_summary"]
        assert section.layout_type == "summary_dashboard"
        persisted = FormSection.query.get(section.id)
        assert persisted.layout_type == "summary_dashboard"

    def test_save_form_draft_rejects_donut_with_one_segment(
        self, make_form, make_field, system_user, db_session
    ):
        form, published_version = make_form()
        draft_version = FormVersion(
            form_id=form.id,
            version_number=2,
            status="Draft",
            created_by=system_user,
        )
        db_session.add(draft_version)
        db_session.flush()

        save_form_sections(
            draft_version.id,
            [
                {
                    "code": "sec_dash",
                    "name": "Dashboard",
                    "layout_type": "summary_dashboard",
                    "display_order": 1,
                }
            ],
            system_user,
        )

        with pytest.raises(ValueError, match="at least 2 segments"):
            save_form_draft_fields(
                draft_version.id,
                [
                    {
                        "field_code": "viz_donut",
                        "field_name": "Scope Split",
                        "field_type": "calculated",
                        "section_code": "sec_dash",
                        "frequency": "annual",
                        "field_config": {
                            "field_scope": "annual_result",
                            "visualization": {
                                "widget": "donut",
                                "donut_segments": [
                                    {"field_code": "scope1", "label": "Scope 1"},
                                ],
                            },
                        },
                    }
                ],
                system_user,
                sections_list=None,
            )
        db_session.rollback()


class TestVisualizationPayload:
    def test_compose_visualization_payload_dashboard_widgets(self):
        sections = [
            {"id": 1, "name": "Energy", "layout_type": "summary_dashboard", "display_order": 1},
        ]
        fields = [
            {
                "field_code": "total_energy",
                "field_name": "Total Energy",
                "section_id": 1,
                "display_order": 1,
                "field_config": {
                    "unit": "GJ",
                    "visualization": {"widget": "kpi", "span": "full"},
                },
            },
            {
                "field_code": "energy_trend",
                "field_name": "Energy Trend",
                "section_id": 1,
                "display_order": 2,
                "field_config": {
                    "visualization": {
                        "widget": "line",
                        "span": "full",
                        "source_field_codes": ["elec_mwh", "diesel_kl"],
                    },
                },
            },
            {
                "field_code": "scope_split",
                "field_name": "Scope Split",
                "section_id": 1,
                "display_order": 3,
                "field_config": {
                    "visualization": {
                        "widget": "donut",
                        "span": "half",
                        "donut_segments": [
                            {"field_code": "scope1", "label": "Scope 1"},
                            {"field_code": "scope2", "label": "Scope 2"},
                        ],
                    },
                },
            },
        ]
        sheet_results = [
            {"field_code": "total_energy", "value": 1234.5, "unit": "GJ", "status": "calculated"},
            {"field_code": "scope1", "value": 100.0, "status": "calculated"},
            {"field_code": "scope2", "value": 200.0, "status": "calculated"},
        ]
        monthly_series = {
            "elec_mwh": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
            "diesel_kl": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        }
        months = [{"label": f"M{i}"} for i in range(1, 13)]

        payload = _compose_visualization_payload(
            sections,
            fields,
            sheet_results,
            site_id=None,
            workbook_id=None,
            fy_start_year=2025,
            months=months,
        )

        assert payload["mode"] == "dashboard"
        assert len(payload["panels"]) == 1
        assert len(payload["widgets"]) == 3

        kpi = next(w for w in payload["widgets"] if w["widget"] == "kpi")
        assert kpi["value"] == 1234.5
        assert kpi["status"] == "calculated"

        line = next(w for w in payload["widgets"] if w["widget"] == "line")
        assert len(line["series"]) == 2

        donut = next(w for w in payload["widgets"] if w["widget"] == "donut")
        assert len(donut["segments"]) == 2

    def test_preview_context_includes_mock_dashboard_series(self, make_form, make_field, system_user, db_session):
        form, form_version = make_form()
        sections = save_form_sections(
            form_version.id,
            [
                {
                    "code": "sec_dash",
                    "name": "Summary",
                    "layout_type": "summary_dashboard",
                    "display_order": 1,
                }
            ],
            system_user,
        )
        section = sections["sec_dash"]
        _, chart_fv = make_field(
            form,
            form_version,
            "chart_field",
            field_type="calculated",
            field_config={
                "field_scope": "annual_result",
                "visualization": {
                    "widget": "line",
                    "source_field_codes": ["monthly_a"],
                },
            },
            frequency="annual",
        )
        chart_fv.section_id = section.id
        db_session.flush()

        context = compose_preview_workbook_context(form_version.id)
        visualization = context.get("visualization") or {}
        assert visualization.get("mode") == "dashboard"
        assert "monthly_a" in (visualization.get("monthly_series") or {})


class TestComposeAnnualWorkbookDashboard:
    def test_compose_annual_workbook_data_returns_dashboard_mode(
        self,
        make_form,
        make_field,
        make_formula_version,
        make_site,
        make_reporting_period,
        make_workflow,
        make_user,
        make_workbook,
        make_access_grant,
        make_submission,
        make_submission_value,
        system_user,
        db_session,
    ):
        from app.modules.FORMBLD.model import FieldVersion

        monthly_form, monthly_fv = make_form()
        monthly_section = FormSection(
            form_id=monthly_form.id,
            form_version_id=monthly_fv.id,
            name="Monthly",
            code="sec_monthly",
            layout_type="monthly_table",
            display_order=1,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(monthly_section)
        db_session.flush()

        monthly_field, monthly_fv_field = make_field(
            monthly_form,
            monthly_fv,
            "elec_mwh",
            field_type="number",
            field_config={"unit": "MWh"},
        )
        fv_monthly = FieldVersion.query.get(monthly_field.current_version_id)
        fv_monthly.section_id = monthly_section.id
        db_session.flush()

        dash_form, dash_fv = make_form()
        dash_section = FormSection(
            form_id=dash_form.id,
            form_version_id=dash_fv.id,
            name="Summary",
            code="sec_summary",
            layout_type="summary_dashboard",
            display_order=1,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(dash_section)
        db_session.flush()

        formula = make_formula_version("elec_mwh", {"elec_mwh": {}})
        kpi_field, _ = make_field(
            dash_form,
            dash_fv,
            "total_elec",
            field_type="calculated",
            field_config={
                "field_scope": "annual_result",
                "formula_version_id": formula.id,
                "unit": "MWh",
                "visualization": {"widget": "kpi", "span": "full"},
            },
            frequency="annual",
        )
        trend_field, _ = make_field(
            dash_form,
            dash_fv,
            "elec_trend",
            field_type="calculated",
            field_config={
                "field_scope": "annual_result",
                "formula_version_id": formula.id,
                "visualization": {
                    "widget": "line",
                    "span": "full",
                    "source_field_codes": ["elec_mwh"],
                },
            },
            frequency="annual",
        )
        for field in (kpi_field, trend_field):
            fv = FieldVersion.query.get(field.current_version_id)
            fv.section_id = dash_section.id
        db_session.flush()

        submitter = make_user()
        site = make_site()
        workflow_version = make_workflow([submitter])
        make_access_grant(
            submitter,
            "submission",
            scope_type="site",
            scope_site_id=site.id,
            can_view=True,
            can_edit=True,
            can_submit=True,
        )

        workbook = make_workbook(monthly_form, site, workflow_version=workflow_version, submitters=[submitter])
        from app.modules.WKBK.model import WorkbookForm

        wf_dash = WorkbookForm(workbook_id=workbook.id, form_id=dash_form.id, display_order=20)
        db_session.add(wf_dash)
        db_session.flush()

        period = make_reporting_period(site, year=2025, month=4)
        submission = make_submission(site, monthly_form, monthly_fv, period, workflow_version)
        make_submission_value(submission, monthly_field, fv_monthly, raw_value="100")
        db_session.commit()

        payload = compose_annual_workbook_data(
            submitter.id,
            site.id,
            workbook.id,
            2025,
            selected_form_id=dash_form.id,
        )

        visualization = payload.get("visualization") or {}
        assert visualization.get("mode") == "dashboard"
        kpi_widgets = [w for w in visualization.get("widgets", []) if w.get("widget") == "kpi"]
        assert kpi_widgets
        assert kpi_widgets[0].get("field_code") == "total_elec"

        monthly_series = visualization.get("monthly_series") or {}
        assert "elec_mwh" in monthly_series
