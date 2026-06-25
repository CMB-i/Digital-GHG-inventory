import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.WKBK.model import Workbook, WorkbookSiteSubmitter
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, Field
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.SUBMIT.service import compose_calculation_results, compose_annual_workbook_data
from app.modules.USRMGMT.model import User
from app.modules.WFLWBLD.model import WorkflowVersion

def run_test():
    app = create_app()
    with app.app_context():
        print("Verifying Jaigarh FY25-26 GHG & Energy Workbook calculations...")
        
        # Start transaction rollback block
        db.session.rollback()
        
        # 1. Fetch user
        user = User.query.filter_by(is_active=True, is_deleted=False).first()
        assert user is not None, "No active user found in DB"
        print(f"Using user: {user.full_name} (ID: {user.id})")
        
        # 2. Fetch Workbook and Site
        wkbk = Workbook.query.filter_by(code="wkbk_jaigarh_demo").first()
        assert wkbk is not None, "Jaigarh demo workbook not found. Run seed script first."
        
        site = Site.query.filter_by(is_deleted=False).first()
        assert site is not None, "No site found in DB"
        print(f"Using site: {site.name} (ID: {site.id})")

        # Set user as submitter
        submitter = WorkbookSiteSubmitter.query.filter_by(
            workbook_id=wkbk.id,
            site_id=site.id,
            user_id=user.id
        ).first()
        if not submitter:
            submitter = WorkbookSiteSubmitter(
                workbook_id=wkbk.id,
                site_id=site.id,
                user_id=user.id,
                created_by=user.id
            )
            db.session.add(submitter)
            db.session.flush()
        
        # 3. Ensure all 12 reporting periods exist for FY25-26 (April 2025 - March 2026)
        periods = []
        for month_idx in range(12):
            m = (4 + month_idx - 1) % 12 + 1
            y = 2025 if m >= 4 else 2026
            p = ReportingPeriod.query.filter_by(site_id=site.id, year=y, month=m, is_deleted=False).first()
            if not p:
                p = ReportingPeriod(site_id=site.id, year=y, month=m, status="OPEN", created_by=user.id)
                db.session.add(p)
                db.session.flush()
            periods.append(p)
            
        wv = WorkflowVersion.query.first()
        assert wv is not None, "No workflow version found in database"

        # 4. Define Mock Values for April 2025
        mock_values = {
            # Electricity
            "electricity_from_grid_mwh": "100.0",
            "electricity_other_source_mwh": "200.0",
            # Diesel
            "diesel_stationary_eqp_kl": "10.0",
            "diesel_mobile_eqp_kl": "20.0",
            # Petrol
            "petrol_total_qty_kl": "5.0",
            # HFHSD & IFO
            "hfhsd_qty_kl": "50.0",
            "ifo_qty_kl": "50.0",
            # Other Fuels - Emissions
            "acetylene_quantity_t": "2.0",
            "lpg_quantity_t": "1.5",
            "co2_fire_extinguisher_quantity_t": "0.5",
            # Refrigerants
            "r22_quantity_kg": "5.0",
            "r32_quantity_kg": "10.0",
            "r410a_quantity_kg": "20.0",
            "ch4_quantity_kg": "1.0",
            "n2o_quantity_kg": "2.0",
            # Other Fuels - Energy
            "acetylene_energy_quantity_t": "2.0",
            "lpg_energy_quantity_t": "1.5",
            # GHG Summary & Energy Summary inputs
            "cargo_throughput_million_mt": "10.0",
            "energy_cargo_throughput_million_mt": "10.0"
        }

        # 5. Populate Submission Values in DB
        form_codes = [
            "form_jaigarh_electricity",
            "form_jaigarh_diesel",
            "form_jaigarh_petrol",
            "form_jaigarh_hfhsd_ifo",
            "form_jaigarh_other_fuels_emissions",
            "form_jaigarh_refrigerants_gwp",
            "form_jaigarh_ghg_summary",
            "form_jaigarh_energy_summary",
            "form_jaigarh_other_fuels_energy"
        ]
        forms = Form.query.filter(Form.code.in_(form_codes)).all()
        for form in forms:
            for p in periods:
                sub = Submission(
                    site_id=site.id,
                    form_id=form.id,
                    form_version_id=form.current_version_id,
                    reporting_period_id=p.id,
                    workflow_version_id=wv.id,
                    status="Approved",
                    submitted_by=user.id,
                    created_by=user.id
                )
                db.session.add(sub)
                db.session.flush()
                
                fields = Field.query.filter_by(form_id=form.id, is_deleted=False).all()
                for field in fields:
                    if field.field_code in mock_values:
                        # Value for April 2025, 0.0 for other months to test aggregates correctly
                        raw_val = mock_values[field.field_code] if p.month == 4 else "0.0"
                        val = SubmissionValue(
                            submission_id=sub.id,
                            field_id=field.id,
                            field_version_id=field.current_version_id,
                            raw_value=raw_val,
                            cell_state="approved_locked",
                            created_by=user.id
                        )
                        db.session.add(val)
        db.session.flush()
        print("Mock submissions generated for all 12 months.")

        # 6. Verify Calculations for April 2025
        print("\nVerifying monthly calculated columns for April 2025...")
        results = compose_calculation_results(
            site_id=site.id,
            workbook_id=wkbk.id,
            fy_start_year=2025,
            user_id=user.id
        )
        
        rows = results.get("rows", [])
        april_row = next((r for r in rows if r.get("month") == 4), None)
        assert april_row is not None, "April month row not found"
        
        april_vals = {code: info.get("calculated_value") for code, info in april_row.get("values", {}).items()}
        
        # Assertions for monthly calculated values
        print("April Values in DB:")
        for k, v in sorted(april_vals.items()):
            print(f"  {k}: {v}")
            
        assert float(april_vals["electricity_total_mwh"]) == 300.0
        assert float(april_vals["diesel_total_qty_kl"]) == 30.0
        assert float(april_vals["hfhsd_ifo_total_qty_kl"]) == 100.0
        assert float(april_vals["r22_emission_tco2e"]) == 9.8
        assert float(april_vals["r32_emission_tco2e"]) == 7.71
        assert float(april_vals["r410a_emission_tco2e"]) == 45.12
        assert float(april_vals["ch4_refrigerant_emission_tco2e"]) == 0.0298
        assert float(april_vals["n2o_refrigerant_emission_tco2e"]) == 0.546
        assert abs(float(april_vals["refrigerants_total_emission_mth"]) - 63.2058) < 1e-4
        assert abs(float(april_vals["acetylene_emission_tco2"]) - 6.76) < 1e-4
        assert abs(float(april_vals["lpg_emission_tco2"]) - 4.4775) < 1e-4
        assert abs(float(april_vals["co2_fire_extinguisher_emission_tco2"]) - 0.5) < 1e-4
        assert abs(float(april_vals["hfcs_emission_tco2"]) - 63.2058) < 1e-4
        assert abs(float(april_vals["other_fuels_total_emissions_tco2_mth"]) - 74.9433) < 1e-4
        
        # GHG summary mth
        assert abs(float(april_vals["summary_electricity_emissions_mth"]) - 213.0) < 1e-4
        assert abs(float(april_vals["summary_diesel_emissions_mth"]) - 80.970732) < 1e-4
        assert abs(float(april_vals["summary_petrol_emissions_mth"]) - 11.728051) < 1e-4
        assert abs(float(april_vals["summary_hfhsd_ifo_emissions_mth"]) - 284.03542) < 1e-4
        assert abs(float(april_vals["summary_other_fuels_emissions_mth"]) - 74.9433) < 1e-4
        assert abs(float(april_vals["summary_refrigerants_emissions_mth"]) - 63.2058) < 1e-4
        assert abs(float(april_vals["summary_total_emissions_mth"]) - 727.883303) < 1e-4
        print("-> Monthly calculated assertions PASSED!")

        # Populate calculated_value in DB from results to allow compose_annual_workbook_data to fetch them
        print("\nPopulating calculated_value in DB for testing sheet aggregates...")
        form_ids = [f.id for f in forms]
        all_fields = Field.query.filter(Field.form_id.in_(form_ids), Field.is_deleted == False).all()
        field_by_code = {f.field_code: f for f in all_fields}
        submissions_by_form_and_period = {
            (sub.form_id, sub.reporting_period_id): sub
            for sub in Submission.query.filter(
                Submission.site_id == site.id,
                Submission.form_id.in_(form_ids),
                Submission.is_deleted == False
            ).all()
        }
        
        for r in rows:
            r_year = r["year"]
            r_month = r["month"]
            p = next((period for period in periods if period.year == r_year and period.month == r_month), None)
            if not p:
                continue
            for f_code, info in r.get("values", {}).items():
                calc_val = info.get("calculated_value")
                if calc_val is not None:
                    field = field_by_code.get(f_code)
                    if not field:
                        continue
                    sub = submissions_by_form_and_period.get((field.form_id, p.id))
                    if not sub:
                        continue
                    # Find or create SubmissionValue
                    sv = SubmissionValue.query.filter_by(submission_id=sub.id, field_id=field.id).first()
                    if not sv:
                        sv = SubmissionValue(
                            submission_id=sub.id,
                            field_id=field.id,
                            field_version_id=field.current_version_id,
                            created_by=user.id
                        )
                        db.session.add(sv)
                    sv.calculated_value = calc_val
                    sv.cell_state = "approved_locked"
        db.session.flush()
        print("calculated_value populated in DB.")

        # 7. Verify aggregates and intensity calculations for each sheet
        print("\nVerifying below-table sheet aggregates...")
        for form in forms:
            print(f"Testing sheet results for: {form.name}...")
            sheet_data = compose_annual_workbook_data(
                user_id=user.id,
                site_id=site.id,
                workbook_id=wkbk.id,
                fy_start_year=2025,
                selected_form_id=form.id
            )
            sheet_results = {res["field_code"]: res["value"] for res in sheet_data.get("sheet_results", [])}
            
            if form.code == "form_jaigarh_electricity":
                assert float(sheet_results["electricity_from_grid_total_mwh"]) == 100.0
                assert float(sheet_results["electricity_other_source_total_mwh"]) == 200.0
                assert float(sheet_results["electricity_total_fy_mwh"]) == 300.0
                assert float(sheet_results["electricity_from_grid_emission_tco2e"]) == 71.0
                assert float(sheet_results["electricity_other_source_emission_tco2e"]) == 142.0
                assert float(sheet_results["electricity_total_emission_tco2e"]) == 213.0
                assert float(sheet_results["electricity_energy_consumption_gj"]) == 1080.0
                
            elif form.code == "form_jaigarh_diesel":
                assert float(sheet_results["diesel_stationary_total_kl"]) == 10.0
                assert float(sheet_results["diesel_mobile_total_kl"]) == 20.0
                assert float(sheet_results["diesel_total_fy_kl"]) == 30.0
                assert abs(float(sheet_results["diesel_co2_emission_tco2e"]) - 80.694) < 1e-4
                assert abs(float(sheet_results["diesel_ch4_emission_tco2e"]) - 0.096552) < 1e-4
                assert abs(float(sheet_results["diesel_n2o_emission_tco2e"]) - 0.18018) < 1e-4
                assert abs(float(sheet_results["diesel_total_emission_tco2e"]) - 80.970732) < 1e-4
                assert float(sheet_results["diesel_energy_consumption_gj"]) == 1083.6
                
            elif form.code == "form_jaigarh_petrol":
                assert float(sheet_results["petrol_total_fy_kl"]) == 5.0
                assert abs(float(sheet_results["petrol_co2_emission_tco2e"]) - 11.686) < 1e-4
                assert abs(float(sheet_results["petrol_ch4_emission_tco2e"]) - 0.014751) < 1e-4
                assert abs(float(sheet_results["petrol_n2o_emission_tco2e"]) - 0.0273) < 1e-4
                assert abs(float(sheet_results["petrol_total_emission_tco2e"]) - 11.728051) < 1e-4
                assert float(sheet_results["petrol_energy_consumption_gj"]) == 164.4
                
            elif form.code == "form_jaigarh_hfhsd_ifo":
                assert float(sheet_results["hfhsd_total_fy_kl"]) == 50.0
                assert float(sheet_results["ifo_total_fy_kl"]) == 50.0
                assert float(sheet_results["hfhsd_ifo_total_fy_kl"]) == 100.0
                assert abs(float(sheet_results["hfhsd_ifo_co2_emission_tco2e"]) - 283.11) < 1e-4
                assert abs(float(sheet_results["hfhsd_ifo_ch4_emission_tco2e"]) - 0.32482) < 1e-4
                assert abs(float(sheet_results["hfhsd_ifo_n2o_emission_tco2e"]) - 0.6006) < 1e-4
                assert abs(float(sheet_results["hfhsd_ifo_total_emission_tco2e"]) - 284.03542) < 1e-4
                assert float(sheet_results["hfhsd_energy_consumption_gj"]) == 1820.0
                assert float(sheet_results["ifo_energy_consumption_gj"]) == 1820.0
                assert float(sheet_results["hfhsd_ifo_energy_consumption_gj"]) == 3640.0
                
            elif form.code == "form_jaigarh_other_fuels_emissions":
                assert abs(float(sheet_results["other_fuels_total_emissions_tco2"]) - 74.9433) < 1e-4
                
            elif form.code == "form_jaigarh_refrigerants_gwp":
                assert abs(float(sheet_results["refrigerants_total_emission_tco2e"]) - 63.2058) < 1e-4
                
            elif form.code == "form_jaigarh_ghg_summary":
                assert abs(float(sheet_results["summary_electricity_emissions_tco2e"]) - 213.0) < 1e-4
                assert abs(float(sheet_results["summary_diesel_emissions_tco2e"]) - 80.970732) < 1e-4
                assert abs(float(sheet_results["summary_petrol_emissions_tco2e"]) - 11.728051) < 1e-4
                assert abs(float(sheet_results["summary_hfhsd_ifo_emissions_tco2e"]) - 284.03542) < 1e-4
                assert abs(float(sheet_results["summary_other_fuels_emissions_tco2e"]) - 74.9433) < 1e-4
                assert abs(float(sheet_results["summary_refrigerants_emissions_tco2e"]) - 63.2058) < 1e-4
                assert abs(float(sheet_results["total_emissions_tco2e"]) - 727.883303) < 1e-4
                assert abs(float(sheet_results["ghg_intensity_000_tco2e_per_million_mt"]) - 0.0727883303) < 1e-4
                
            elif form.code == "form_jaigarh_energy_summary":
                assert float(sheet_results["electrical_energy_consumption_gj"]) == 1080.0
                assert float(sheet_results["summary_diesel_energy_gj"]) == 1083.6
                assert float(sheet_results["summary_petrol_energy_gj"]) == 164.4
                assert float(sheet_results["summary_hfhsd_ifo_energy_gj"]) == 3640.0
                assert abs(float(sheet_results["summary_other_fuels_energy_gj"]) - 165.55) < 1e-4
                assert abs(float(sheet_results["fossil_fuel_energy_consumption_gj"]) - 5053.55) < 1e-4
                assert abs(float(sheet_results["total_energy_consumption_gj"]) - 6133.55) < 1e-4
                assert abs(float(sheet_results["electrical_energy_intensity_kj_per_mt"]) - 108.0) < 1e-4
                assert abs(float(sheet_results["fossil_fuel_energy_intensity_kj_per_mt"]) - 505.355) < 1e-4
                assert abs(float(sheet_results["energy_intensity_000_gj_per_million_mt"]) - 0.613355) < 1e-4

            elif form.code == "form_jaigarh_other_fuels_energy":
                assert abs(float(sheet_results["other_fuels_energy_consumption_gj"]) - 165.55) < 1e-4
                
            print(f"-> Form {form.code} aggregate assertions PASSED!")

        db.session.rollback()
        print("\nAll integration checks PASSED! Database rolled back successfully.")

if __name__ == "__main__":
    run_test()
