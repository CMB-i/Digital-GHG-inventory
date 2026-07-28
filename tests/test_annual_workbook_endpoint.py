from decimal import Decimal

from app.modules.FORMBLD.model import FieldVersion
from app.modules.SUBMIT.model import WorkbookFieldValue
from app.modules.WKBK.model import WorkbookForm


def _attach_sheet(db_session, created_objects, workbook, form, display_order, label=None):
    row = WorkbookForm(
        workbook_id=workbook.id,
        form_id=form.id,
        display_order=display_order,
        sheet_label=label,
    )
    db_session.add(row)
    db_session.flush()
    created_objects.append(row)
    return row


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


def _annual_get(client, site, workbook, fy, form):
    response = client.get(
        "/module/SUBMIT/api/annual-workbook",
        query_string={
            "site_id": site.id,
            "workbook_id": workbook.id,
            "fy": fy,
            "form_id": form.id,
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _results_by_code(payload):
    return {row["field_code"]: row for row in payload["sheet_results"]}


class TestAnnualWorkbookEndpointFormulaResolution:
    def _build_workbook(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        electricity_form, electricity_version = make_form()
        electricity_raw, electricity_raw_version = make_field(
            electricity_form, electricity_version, "grid_kwh", field_type="number",
        )
        electricity_formula = make_formula_version("SUM_MONTHS(grid_kwh)", {"grid_kwh": {}})
        make_field(
            electricity_form, electricity_version, "fy_total_electricity_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": electricity_formula.id, "display_region": "below_monthly_table"},
        )

        ofr_form, ofr_version = make_form()
        ofr_raw, ofr_raw_version = make_field(
            ofr_form, ofr_version, "ofr_acetylene_qty_t", field_type="number", frequency="annual",
        )
        ofr_energy_formula = make_formula_version("ofr_acetylene_qty_t * 47.3", {"ofr_acetylene_qty_t": {}})
        ofr_emissions_formula = make_formula_version("ofr_acetylene_qty_t * 2", {"ofr_acetylene_qty_t": {}})
        make_field(
            ofr_form, ofr_version, "ofr_acetylene_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_energy_formula.id, "display_region": "below_monthly_table"},
        )
        make_field(
            ofr_form, ofr_version, "ofr_total_emissions_tco2",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_emissions_formula.id, "display_region": "below_monthly_table"},
        )

        fuel_form, fuel_version = make_form()
        fuel_raw, fuel_raw_version = make_field(fuel_form, fuel_version, "diesel_kl", field_type="number")
        diesel_formula = make_formula_version("SUM_MONTHS(diesel_kl) * 10", {"diesel_kl": {}})
        fuel_energy_formula = make_formula_version(
            "diesel_energy_gj + ofr_acetylene_gj",
            {"diesel_energy_gj": {}, "ofr_acetylene_gj": {}},
        )
        fuel_emissions_formula = make_formula_version(
            "ofr_total_emissions_tco2",
            {"ofr_total_emissions_tco2": {}},
        )
        make_field(
            fuel_form, fuel_version, "diesel_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": diesel_formula.id, "display_region": "below_monthly_table"},
        )
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_energy_formula.id, "display_region": "below_monthly_table"},
        )
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_emissions_formula.id, "display_region": "below_monthly_table"},
        )

        gri_form, gri_version = make_form()
        gri_energy_formula = make_formula_version(
            "fy_total_electricity_gj + fy_total_fuel_energy_gj",
            {"fy_total_electricity_gj": {}, "fy_total_fuel_energy_gj": {}},
        )
        gri_emissions_formula = make_formula_version(
            "fy_total_fuel_emissions_tco2e",
            {"fy_total_fuel_emissions_tco2e": {}},
        )
        make_field(
            gri_form, gri_version, "total_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": gri_energy_formula.id, "display_region": "below_monthly_table"},
        )
        make_field(
            gri_form, gri_version, "total_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": gri_emissions_formula.id, "display_region": "below_monthly_table"},
        )

        site = make_site()
        user = make_user()
        workflow_version = make_workflow([user])
        workbook = make_workbook(electricity_form, site, workflow_version=workflow_version, submitters=[user])
        _attach_sheet(db_session, created_objects, workbook, ofr_form, 20, "Other Fuels & Refrigerants")
        _attach_sheet(db_session, created_objects, workbook, fuel_form, 30, "Fuel Consumption")
        _attach_sheet(db_session, created_objects, workbook, gri_form, 40, "GRI Summary")
        make_access_grant(
            user, "submission", scope_type="global", can_view=True, can_create=True,
            can_edit=True, can_submit=True,
        )

        return {
            "site": site,
            "user": user,
            "workbook": workbook,
            "workflow_version": workflow_version,
            "electricity_form": electricity_form,
            "electricity_version": electricity_version,
            "electricity_raw": electricity_raw,
            "electricity_raw_version": electricity_raw_version,
            "ofr_form": ofr_form,
            "ofr_raw": ofr_raw,
            "ofr_raw_version": ofr_raw_version,
            "fuel_form": fuel_form,
            "fuel_version": fuel_version,
            "fuel_raw": fuel_raw,
            "fuel_raw_version": fuel_raw_version,
            "gri_form": gri_form,
        }

    def _populate_inputs(
        self, ctx, make_reporting_period, make_submission, make_submission_value,
        db_session, created_objects, system_user,
    ):
        months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
        for month in months:
            year = 2026 if month >= 4 else 2027
            period = make_reporting_period(ctx["site"], year=year, month=month)
            electricity_submission = make_submission(
                ctx["site"], ctx["electricity_form"], ctx["electricity_version"],
                period, ctx["workflow_version"],
            )
            fuel_submission = make_submission(
                ctx["site"], ctx["fuel_form"], ctx["fuel_version"],
                period, ctx["workflow_version"],
            )
            make_submission_value(
                electricity_submission, ctx["electricity_raw"],
                ctx["electricity_raw_version"], raw_value="10",
            )
            make_submission_value(
                fuel_submission, ctx["fuel_raw"], ctx["fuel_raw_version"], raw_value="2",
            )

        value = WorkbookFieldValue(
            site_id=ctx["site"].id,
            form_id=ctx["ofr_form"].id,
            field_id=ctx["ofr_raw"].id,
            field_version_id=ctx["ofr_raw_version"].id,
            fy_start_year=2026,
            value_text="0.026",
            numeric_value=Decimal("0.026"),
            cell_state="draft_filled",
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(value)
        db_session.flush()
        created_objects.append(value)

    def test_empty_workbook_endpoint_statuses_are_needs_input_not_unknown(
        self, client, make_form, make_field, make_formula_version, make_site,
        make_workflow, make_user, make_workbook, make_access_grant, db_session,
        created_objects,
    ):
        ctx = self._build_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )
        _login(client, ctx["user"])

        for form_key, expected_codes in (
            ("electricity_form", ["fy_total_electricity_gj"]),
            ("ofr_form", ["ofr_acetylene_gj", "ofr_total_emissions_tco2"]),
            ("gri_form", ["total_energy_gj", "total_emissions_tco2e"]),
        ):
            payload = _annual_get(client, ctx["site"], ctx["workbook"], 2026, ctx[form_key])
            body = str(payload)
            assert "Unknown formula variable" not in body
            results = _results_by_code(payload)
            for code in expected_codes:
                assert results[code]["status"] == "needs_input"

    def test_populated_workbook_endpoint_resolves_annual_and_cross_form_chain(
        self, client, make_form, make_field, make_formula_version, make_site,
        make_workflow, make_user, make_workbook, make_access_grant,
        make_reporting_period, make_submission, make_submission_value,
        db_session, created_objects, system_user,
    ):
        ctx = self._build_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )
        self._populate_inputs(
            ctx, make_reporting_period, make_submission, make_submission_value,
            db_session, created_objects, system_user,
        )
        _login(client, ctx["user"])

        ofr_results = _results_by_code(_annual_get(client, ctx["site"], ctx["workbook"], 2026, ctx["ofr_form"]))
        assert ofr_results["ofr_acetylene_gj"]["status"] == "calculated"
        assert ofr_results["ofr_acetylene_gj"]["value"] == round(0.026 * 47.3, 3)

        fuel_results = _results_by_code(_annual_get(client, ctx["site"], ctx["workbook"], 2026, ctx["fuel_form"]))
        assert fuel_results["fy_total_fuel_energy_gj"]["status"] == "calculated"
        assert fuel_results["fy_total_fuel_energy_gj"]["value"] == round(12 * 2 * 10 + 0.026 * 47.3, 3)
        assert fuel_results["fy_total_fuel_emissions_tco2e"]["status"] == "calculated"

        gri_payload = _annual_get(client, ctx["site"], ctx["workbook"], 2026, ctx["gri_form"])
        assert "Unknown formula variable" not in str(gri_payload)
        gri_results = _results_by_code(gri_payload)
        assert gri_results["total_energy_gj"]["status"] == "calculated"
        assert gri_results["total_energy_gj"]["value"] == round(12 * 10 + 12 * 2 * 10 + 0.026 * 47.3, 3)
        assert gri_results["total_emissions_tco2e"]["status"] == "calculated"


class TestDraftWorkbookPreviewCrossSheetResolution:
    def _grant_preview_access(self, make_access_grant, user):
        make_access_grant(user, "form", scope_type="global", can_manage_forms=True)

    def _build_empty_preview_workbook(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        gri_form, gri_version = make_form()
        fuel_form, fuel_version = make_form()
        ofr_form, ofr_version = make_form()
        electricity_form, electricity_version = make_form()

        make_field(electricity_form, electricity_version, "grid_kwh", field_type="number")
        electricity_gj = make_formula_version("SUM_MONTHS(grid_kwh)", {"grid_kwh": {}})
        electricity_tco2e = make_formula_version("SUM_MONTHS(grid_kwh) * 2", {"grid_kwh": {}})
        make_field(
            electricity_form, electricity_version, "fy_total_electricity_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": electricity_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            electricity_form, electricity_version, "fy_total_electricity_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": electricity_tco2e.id, "display_region": "below_monthly_table"},
        )

        make_field(ofr_form, ofr_version, "ofr_acetylene_qty_t", field_type="number", frequency="annual")
        ofr_gj = make_formula_version("ofr_acetylene_qty_t * 47.3", {"ofr_acetylene_qty_t": {}})
        ofr_tco2 = make_formula_version("ofr_acetylene_qty_t * 2", {"ofr_acetylene_qty_t": {}})
        make_field(
            ofr_form, ofr_version, "ofr_other_fuels_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            ofr_form, ofr_version, "ofr_total_emissions_tco2",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_tco2.id, "display_region": "below_monthly_table"},
        )

        make_field(fuel_form, fuel_version, "diesel_kl", field_type="number")
        diesel_gj = make_formula_version("SUM_MONTHS(diesel_kl) * 10", {"diesel_kl": {}})
        fuel_gj = make_formula_version(
            "diesel_energy_gj + ofr_other_fuels_energy_gj",
            {"diesel_energy_gj": {}, "ofr_other_fuels_energy_gj": {}},
        )
        fuel_tco2e = make_formula_version(
            "ofr_total_emissions_tco2",
            {"ofr_total_emissions_tco2": {}},
        )
        make_field(
            fuel_form, fuel_version, "diesel_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": diesel_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_tco2e.id, "display_region": "below_monthly_table"},
        )

        total_energy = make_formula_version(
            "fy_total_fuel_energy_gj + fy_total_electricity_gj",
            {"fy_total_fuel_energy_gj": {}, "fy_total_electricity_gj": {}},
        )
        total_emissions = make_formula_version(
            "fy_total_fuel_emissions_tco2e + fy_total_electricity_tco2e",
            {"fy_total_fuel_emissions_tco2e": {}, "fy_total_electricity_tco2e": {}},
        )
        energy_intensity = make_formula_version("total_energy_gj / 2", {"total_energy_gj": {}})
        emissions_intensity = make_formula_version("total_emissions_tco2e / 2", {"total_emissions_tco2e": {}})
        make_field(
            gri_form, gri_version, "total_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": total_energy.id, "display_region": "below_monthly_table"},
        )
        make_field(
            gri_form, gri_version, "total_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": total_emissions.id, "display_region": "below_monthly_table"},
        )
        make_field(
            gri_form, gri_version, "ghg_energy_intensity",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": energy_intensity.id, "display_region": "below_monthly_table"},
        )
        make_field(
            gri_form, gri_version, "ghg_emissions_intensity",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": emissions_intensity.id, "display_region": "below_monthly_table"},
        )

        user = make_user()
        self._grant_preview_access(make_access_grant, user)
        site = make_site()
        workflow_version = make_workflow([user])
        workbook = make_workbook(gri_form, site, workflow_version=workflow_version)
        _attach_sheet(db_session, created_objects, workbook, fuel_form, 20, "Fuel")
        _attach_sheet(db_session, created_objects, workbook, ofr_form, 30, "OFR")
        _attach_sheet(db_session, created_objects, workbook, electricity_form, 40, "Electricity")
        return {
            "user": user,
            "gri_form": gri_form,
            "gri_version": gri_version,
            "fuel_form": fuel_form,
            "ofr_form": ofr_form,
            "electricity_form": electricity_form,
        }

    def _build_calculable_preview_workbook(
        self, make_form, make_field, make_formula_version, make_site, make_workflow,
        make_user, make_workbook, make_access_grant, db_session, created_objects,
    ):
        gri_form, gri_version = make_form()
        fuel_form, fuel_version = make_form()
        ofr_form, ofr_version = make_form()
        electricity_form, electricity_version = make_form()

        electricity_gj = make_formula_version("120", {})
        electricity_tco2e = make_formula_version("240", {})
        make_field(
            electricity_form, electricity_version, "fy_total_electricity_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": electricity_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            electricity_form, electricity_version, "fy_total_electricity_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": electricity_tco2e.id, "display_region": "below_monthly_table"},
        )

        ofr_gj = make_formula_version("10", {})
        ofr_tco2 = make_formula_version("5", {})
        make_field(
            ofr_form, ofr_version, "ofr_other_fuels_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            ofr_form, ofr_version, "ofr_total_emissions_tco2",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": ofr_tco2.id, "display_region": "below_monthly_table"},
        )

        fuel_gj = make_formula_version("ofr_other_fuels_energy_gj + 20", {"ofr_other_fuels_energy_gj": {}})
        fuel_tco2e = make_formula_version("ofr_total_emissions_tco2 + 2", {"ofr_total_emissions_tco2": {}})
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_gj.id, "display_region": "below_monthly_table"},
        )
        make_field(
            fuel_form, fuel_version, "fy_total_fuel_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": fuel_tco2e.id, "display_region": "below_monthly_table"},
        )

        total_energy = make_formula_version(
            "fy_total_fuel_energy_gj + fy_total_electricity_gj",
            {"fy_total_fuel_energy_gj": {}, "fy_total_electricity_gj": {}},
        )
        total_emissions = make_formula_version(
            "fy_total_fuel_emissions_tco2e + fy_total_electricity_tco2e",
            {"fy_total_fuel_emissions_tco2e": {}, "fy_total_electricity_tco2e": {}},
        )
        make_field(
            gri_form, gri_version, "total_energy_gj",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": total_energy.id, "display_region": "below_monthly_table"},
        )
        make_field(
            gri_form, gri_version, "total_emissions_tco2e",
            field_type="calculated", frequency="annual",
            field_config={"formula_version_id": total_emissions.id, "display_region": "below_monthly_table"},
        )

        user = make_user()
        self._grant_preview_access(make_access_grant, user)
        site = make_site()
        workflow_version = make_workflow([user])
        workbook = make_workbook(gri_form, site, workflow_version=workflow_version)
        _attach_sheet(db_session, created_objects, workbook, fuel_form, 20, "Fuel")
        _attach_sheet(db_session, created_objects, workbook, ofr_form, 30, "OFR")
        _attach_sheet(db_session, created_objects, workbook, electricity_form, 40, "Electricity")
        return user, gri_form, gri_version, fuel_form, ofr_form, electricity_form

    def _preview_get(self, client, user, form, version):
        _login(client, user)
        response = client.get(f"/module/FORMBLD/forms/{form.id}/preview-spoc?version_id={version.id}")
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()

    def test_empty_draft_gri_preview_propagates_sibling_needs_input_not_unknown(
        self, client, make_form, make_field, make_formula_version, make_site,
        make_workflow, make_user, make_workbook, make_access_grant,
        db_session, created_objects,
    ):
        ctx = self._build_empty_preview_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )

        payload = self._preview_get(client, ctx["user"], ctx["gri_form"], ctx["gri_version"])
        assert "Unknown formula variable" not in str(payload)
        results = _results_by_code(payload)

        for code in (
            "total_energy_gj",
            "total_emissions_tco2e",
            "ghg_energy_intensity",
            "ghg_emissions_intensity",
        ):
            assert results[code]["status"] == "needs_input"

    def test_draft_gri_preview_resolves_chain_by_dependency_not_tab_order(
        self, client, make_form, make_field, make_formula_version, make_site,
        make_workflow, make_user, make_workbook, make_access_grant,
        db_session, created_objects,
    ):
        user, gri_form, gri_version, fuel_form, ofr_form, electricity_form = self._build_calculable_preview_workbook(
            make_form, make_field, make_formula_version, make_site, make_workflow,
            make_user, make_workbook, make_access_grant, db_session, created_objects,
        )

        payload = self._preview_get(client, user, gri_form, gri_version)
        assert "Unknown formula variable" not in str(payload)
        results = _results_by_code(payload)
        assert results["total_energy_gj"]["status"] == "calculated"
        assert results["total_energy_gj"]["value"] == 150
        assert results["total_emissions_tco2e"]["status"] == "calculated"
        assert results["total_emissions_tco2e"]["value"] == 247
        assert payload["preview_meta"]["dependency_resolution_order"][:3] == [
            ofr_form.code,
            fuel_form.code,
            electricity_form.code,
        ]
