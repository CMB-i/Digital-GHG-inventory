import os
from pathlib import Path
import sys
import re
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion, FormSection
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter

def run():
    app = create_app()
    with app.app_context():
        print("Starting Jaigarh Workbook and Sheets seeding...")
        
        # Reset any aborted transaction
        db.session.rollback()
        
        # Get admin user
        admin_user = User.query.filter_by(email="admin@example.com").first()
        if not admin_user:
            # Try to get any user
            admin_user = User.query.first()
            if not admin_user:
                print("FAILED: No users found in DB. Run seed script first.")
                sys.exit(1)

        # 1. Clean up potential old records to be idempotent
        print("Cleaning up old Jaigarh workbook and sheet records...")
        old_wkbk = Workbook.query.filter_by(code="wkbk_jaigarh").first()
        if old_wkbk:
            WorkbookForm.query.filter_by(workbook_id=old_wkbk.id).delete()
            WorkbookSite.query.filter_by(workbook_id=old_wkbk.id).delete()
            WorkbookSiteSubmitter.query.filter_by(workbook_id=old_wkbk.id).delete()
            Workbook.query.filter_by(id=old_wkbk.id).delete()

        form_codes = [
            "form_jaigarh_electricity",
            "form_jaigarh_diesel",
            "form_jaigarh_petrol",
            "form_jaigarh_hfhsd_ifo",
            "form_jaigarh_other_fuels",
            "form_jaigarh_summary"
        ]
        
        old_forms = Form.query.filter(Form.code.in_(form_codes)).all()
        for f in old_forms:
            f.current_version_id = None
            
        formula_codes = [
            "elec_total_mwh_formula", "elec_grid_emissions_formula", "elec_group_sourcing_emissions_formula", "elec_total_emissions_formula", "elec_energy_gj_formula",
            "diesel_total_kl_formula", "diesel_stationary_emissions_formula", "diesel_mobile_emissions_formula", "diesel_total_emissions_formula", "diesel_energy_gj_formula",
            "petrol_emissions_formula", "petrol_energy_gj_formula",
            "hfhsd_ifo_total_kl_formula", "hfhsd_ifo_emissions_formula", "hfhsd_ifo_energy_gj_formula",
            "other_fuels_emissions_formula", "other_fuels_energy_gj_formula",
            "total_scope1_emissions_formula", "total_scope2_emissions_formula", "total_energy_gj_formula", "total_ghg_emissions_formula", "energy_intensity_formula", "ghg_intensity_formula"
        ]
        old_formulas = Formula.query.filter(Formula.code.in_(formula_codes)).all()
        for formula in old_formulas:
            formula.current_version_id = None
        db.session.commit()

        for f in old_forms:
            old_fields = Field.query.filter_by(form_id=f.id).all()
            for fd in old_fields:
                fd.current_version_id = None
        db.session.commit()

        for f in old_forms:
            old_fields = Field.query.filter_by(form_id=f.id).all()
            field_ids = [fd.id for fd in old_fields]
            if field_ids:
                FieldVersion.query.filter(FieldVersion.field_id.in_(field_ids)).delete()
                Field.query.filter(Field.id.in_(field_ids)).delete()
            FormVersion.query.filter_by(form_id=f.id).delete()
            FormSection.query.filter_by(form_id=f.id).delete()
            Form.query.filter_by(id=f.id).delete()

        for formula in old_formulas:
            FormulaVersion.query.filter_by(formula_id=formula.id).delete()
            Formula.query.filter_by(id=formula.id).delete()
            
        db.session.commit()
        print("Cleanup done.")

        # 2. Create the Workbook
        wkbk = Workbook(
            name="Jaigarh Energy & GHG Workbook",
            code="wkbk_jaigarh",
            description="Workbook template capturing monthly electricity, fossil fuels, refrigerants, and GHG summary for Jaigarh site.",
            status="published",
            created_by=admin_user.id
        )
        db.session.add(wkbk)
        db.session.flush()

        # 3. Define Form Sheets and Fields
        forms_def = [
            {
                "name": "Electricity Consumed",
                "code": "form_jaigarh_electricity",
                "display_order": 1,
                "fields": [
                    {"code": "elec_grid_mwh", "name": "From Grid (MWH)", "type": "number", "unit": "MWH", "display_order": 1},
                    {"code": "elec_group_sourcing_mwh", "name": "Group Co Sourcing (MWH)", "type": "number", "unit": "MWH", "display_order": 2},
                    {"code": "elec_total_mwh", "name": "Total Electricity (MWH)", "type": "calculated", "formula_expression": "elec_grid_mwh + elec_group_sourcing_mwh", "unit": "MWH", "display_order": 3},
                    
                    # Monthly calculations (columns)
                    {"code": "elec_grid_emissions", "name": "Grid Electricity Emissions (tCO2e)", "type": "calculated", "formula_expression": "elec_grid_mwh * 0.71", "unit": "tCO2e", "display_order": 4},
                    {"code": "elec_group_sourcing_emissions", "name": "Group Co Sourcing Emissions (tCO2e)", "type": "calculated", "formula_expression": "elec_group_sourcing_mwh * 0.71", "unit": "tCO2e", "display_order": 5},
                    {"code": "elec_total_emissions", "name": "Total Electricity Emissions (tCO2e)", "type": "calculated", "formula_expression": "elec_grid_emissions + elec_group_sourcing_emissions", "unit": "tCO2e", "display_order": 6},
                    {"code": "elec_energy_gj", "name": "Electrical Energy Consumption (GJ)", "type": "calculated", "formula_expression": "elec_total_mwh * 3.6", "unit": "GJ", "display_order": 7},
                    
                    # Below-table aggregates
                    {"code": "elec_grid_emissions_ann", "name": "Total Grid Electricity Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(elec_grid_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "elec_group_sourcing_emissions_ann", "name": "Total Group Co Sourcing Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(elec_group_sourcing_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "elec_total_emissions_ann", "name": "Total Electricity Emissions (tCO2e)", "type": "calculated", "formula_expression": "elec_grid_emissions_ann + elec_group_sourcing_emissions_ann", "is_aggregate": True, "unit": "tCO2e", "display_order": 10},
                    {"code": "elec_energy_gj_ann", "name": "Total Electrical Energy Consumption (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(elec_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                ]
            },
            {
                "name": "Diesel Consumed",
                "code": "form_jaigarh_diesel",
                "display_order": 2,
                "fields": [
                    {"code": "diesel_stationary_kl", "name": "Stationary Eqp (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    {"code": "diesel_mobile_kl", "name": "Mobile Eqp (KL)", "type": "number", "unit": "KL", "display_order": 2},
                    {"code": "diesel_total_kl", "name": "Total Diesel Qty (KL)", "type": "calculated", "formula_expression": "diesel_stationary_kl + diesel_mobile_kl", "unit": "KL", "display_order": 3},
                    
                    # Monthly calculations (columns)
                    {"code": "diesel_stationary_emissions", "name": "Stationary Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "diesel_stationary_kl * 2.6898", "unit": "tCO2e", "display_order": 4},
                    {"code": "diesel_mobile_emissions", "name": "Mobile Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "diesel_mobile_kl * 2.6932", "unit": "tCO2e", "display_order": 5},
                    {"code": "diesel_total_emissions", "name": "Total Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "diesel_stationary_emissions + diesel_mobile_emissions", "unit": "tCO2e", "display_order": 6},
                    {"code": "diesel_energy_gj", "name": "Diesel Energy (GJ)", "type": "calculated", "formula_expression": "diesel_total_kl * 36.12", "unit": "GJ", "display_order": 7},
                    
                    # Below-table aggregates
                    {"code": "diesel_stationary_emissions_ann", "name": "Total Stationary Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_stationary_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "diesel_mobile_emissions_ann", "name": "Total Mobile Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_mobile_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "diesel_total_emissions_ann", "name": "Total Diesel Emissions (tCO2e)", "type": "calculated", "formula_expression": "diesel_stationary_emissions_ann + diesel_mobile_emissions_ann", "is_aggregate": True, "unit": "tCO2e", "display_order": 10},
                    {"code": "diesel_energy_gj_ann", "name": "Total Diesel Energy (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                ]
            },
            {
                "name": "Petrol Consumed",
                "code": "form_jaigarh_petrol",
                "display_order": 3,
                "fields": [
                    {"code": "petrol_qty_kl", "name": "Total Qty (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    
                    # Monthly calculations (columns)
                    {"code": "petrol_emissions", "name": "Total Petrol Emissions (tCO2e)", "type": "calculated", "formula_expression": "petrol_qty_kl * 2.3372", "unit": "tCO2e", "display_order": 2},
                    {"code": "petrol_energy_gj", "name": "Petrol Energy (GJ)", "type": "calculated", "formula_expression": "petrol_qty_kl * 32.88", "unit": "GJ", "display_order": 3},
                    
                    # Below-table aggregates
                    {"code": "petrol_emissions_ann", "name": "Total Petrol Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(petrol_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 4},
                    {"code": "petrol_energy_gj_ann", "name": "Total Petrol Energy (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(petrol_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 5},
                ]
            },
            {
                "name": "HFHSD & IFO Consumed",
                "code": "form_jaigarh_hfhsd_ifo",
                "display_order": 4,
                "fields": [
                    {"code": "hfhsd_qty_kl", "name": "HFHSD Qty (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    {"code": "ifo_qty_kl", "name": "IFO Qty (KL)", "type": "number", "unit": "KL", "display_order": 2},
                    {"code": "hfhsd_ifo_total_kl", "name": "Total Qty (KL)", "type": "calculated", "formula_expression": "hfhsd_qty_kl + ifo_qty_kl", "unit": "KL", "display_order": 3},
                    
                    # Monthly calculations (columns)
                    {"code": "hfhsd_ifo_emissions", "name": "Total HFHSD & IFO Emissions (tCO2e)", "type": "calculated", "formula_expression": "hfhsd_ifo_total_kl * 2.8311", "unit": "tCO2e", "display_order": 4},
                    {"code": "hfhsd_ifo_energy_gj", "name": "HFHSD & IFO Energy (GJ)", "type": "calculated", "formula_expression": "hfhsd_ifo_total_kl * 36.40", "unit": "GJ", "display_order": 5},
                    
                    # Below-table aggregates
                    {"code": "hfhsd_ifo_emissions_ann", "name": "Total HFHSD & IFO Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(hfhsd_ifo_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 6},
                    {"code": "hfhsd_ifo_energy_gj_ann", "name": "Total HFHSD & IFO Energy (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(hfhsd_ifo_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 7},
                ]
            },
            {
                "name": "Other Fuels & Refrigerants",
                "code": "form_jaigarh_other_fuels",
                "display_order": 5,
                "fields": [
                    {"code": "acetylene_qty_t", "name": "Acetylene Qty (T)", "type": "number", "unit": "T", "display_order": 1},
                    {"code": "lpg_qty_t", "name": "LPG Qty (T)", "type": "number", "unit": "T", "display_order": 2},
                    {"code": "co2_fire_ext_qty_t", "name": "CO2 Fire Ext Qty (T)", "type": "number", "unit": "T", "display_order": 3},
                    {"code": "r32_qty_kg", "name": "R32 Qty (Kg)", "type": "number", "unit": "Kg", "display_order": 4},
                    {"code": "r410a_qty_kg", "name": "R410A Qty (Kg)", "type": "number", "unit": "Kg", "display_order": 5},
                    {"code": "r22_qty_kg", "name": "R22 Qty (Kg)", "type": "number", "unit": "Kg", "display_order": 6},
                    
                    # Monthly calculations (columns)
                    {"code": "other_fuels_emissions", "name": "Other Fuels & Refrigerants Emissions (tCO2e)", "type": "calculated", "formula_expression": "acetylene_qty_t * 4.2283 + lpg_qty_t * 2.985 + co2_fire_ext_qty_t * 1.0 + r32_qty_kg * 0.771 + r410a_qty_kg * 2.255", "unit": "tCO2e", "display_order": 7},
                    {"code": "other_fuels_energy_gj", "name": "Other Fuels Energy (GJ)", "type": "calculated", "formula_expression": "acetylene_qty_t * 59.16 + lpg_qty_t * 47.3", "unit": "GJ", "display_order": 8},
                    
                    # Below-table aggregates
                    {"code": "other_fuels_emissions_ann", "name": "Total Other Fuels & Refrigerants Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(other_fuels_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "other_fuels_energy_gj_ann", "name": "Total Other Fuels Energy (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(other_fuels_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 10},
                ]
            },
            {
                "name": "Energy & GHG Summary",
                "code": "form_jaigarh_summary",
                "display_order": 6,
                "fields": [
                    {"code": "production_million_mt", "name": "Production (Million MT)", "type": "number", "unit": "Million MT", "display_order": 1},
                    
                    # Monthly calculations (columns)
                    {"code": "summary_scope1_emissions", "name": "Scope 1 Emissions (tCO2e)", "type": "calculated", "formula_expression": "diesel_total_emissions + petrol_emissions + hfhsd_ifo_emissions + other_fuels_emissions", "unit": "tCO2e", "display_order": 2},
                    {"code": "summary_scope2_emissions", "name": "Scope 2 Emissions (tCO2e)", "type": "calculated", "formula_expression": "elec_total_emissions", "unit": "tCO2e", "display_order": 3},
                    {"code": "summary_ghg_emissions", "name": "Total GHG Emissions (tCO2e)", "type": "calculated", "formula_expression": "summary_scope1_emissions + summary_scope2_emissions", "unit": "tCO2e", "display_order": 4},
                    {"code": "summary_energy_gj", "name": "Total Energy Consumption (GJ)", "type": "calculated", "formula_expression": "elec_energy_gj + diesel_energy_gj + petrol_energy_gj + hfhsd_ifo_energy_gj + other_fuels_energy_gj", "unit": "GJ", "display_order": 5},
                    {"code": "summary_energy_intensity", "name": "Energy Intensity (GJ/Million MT)", "type": "calculated", "formula_expression": "summary_energy_gj / production_million_mt", "unit": "GJ/Million MT", "display_order": 6},
                    {"code": "summary_ghg_intensity", "name": "GHG Intensity (tCO2e/Million MT)", "type": "calculated", "formula_expression": "summary_ghg_emissions / production_million_mt", "unit": "tCO2e/Million MT", "display_order": 7},
                    
                    # Below-table aggregates
                    {"code": "total_scope1_emissions", "name": "Total Scope 1 (Direct) Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_scope1_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "total_scope2_emissions", "name": "Total Scope 2 (Indirect) Emissions (tCO2e)", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_scope2_emissions)", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "total_ghg_emissions", "name": "Total GHG Emissions (tCO2e)", "type": "calculated", "formula_expression": "total_scope1_emissions + total_scope2_emissions", "is_aggregate": True, "unit": "tCO2e", "display_order": 10},
                    {"code": "total_energy_gj", "name": "Total Energy Consumption (GJ)", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_energy_gj)", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                    {"code": "energy_intensity", "name": "Energy Intensity (GJ/Million MT)", "type": "calculated", "formula_expression": "total_energy_gj / SUM_MONTHS(production_million_mt)", "is_aggregate": True, "unit": "GJ/Million MT", "display_order": 12},
                    {"code": "ghg_intensity", "name": "GHG Intensity (tCO2e/Million MT)", "type": "calculated", "formula_expression": "total_ghg_emissions / SUM_MONTHS(production_million_mt)", "is_aggregate": True, "unit": "tCO2e/Million MT", "display_order": 13},
                ]
            }
        ]

        # 4. Build Forms in DB
        for form_def in forms_def:
            print(f"Creating form '{form_def['name']}'...")
            
            # Create Form
            form = Form(
                name=form_def["name"],
                code=form_def["code"],
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(form)
            db.session.flush()

            # Create Section (default layout monthly_table)
            section = FormSection(
                form_id=form.id,
                name=form_def["name"] + " Section",
                code=form_def["code"] + "_section",
                layout_type="monthly_table",
                display_order=1,
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(section)
            db.session.flush()

            # Create FormVersion
            fv = FormVersion(
                form_id=form.id,
                version_number=1,
                status="Approved",
                published_at=datetime.now(timezone.utc),
                published_by=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(fv)
            db.session.flush()

            # Link form current_version
            form.current_version_id = fv.id

            # Create Fields
            for field_def in form_def["fields"]:
                f = Field(
                    form_id=form.id,
                    field_code=field_def["code"],
                    display_order=field_def["display_order"],
                    is_deleted=False,
                    created_by=admin_user.id
                )
                db.session.add(f)
                db.session.flush()

                field_config = {}
                if field_def.get("unit"):
                    field_config["unit"] = field_def["unit"]

                is_agg = field_def.get("is_aggregate", False)
                if is_agg:
                    field_config["display_region"] = "below_monthly_table"
                    field_config["field_scope"] = "annual_result"
                    field_config["result_role"] = "aggregate_result"
                    field_config["blank_policy"] = "strict"

                if field_def["type"] == "calculated":
                    # Create Formula
                    formula = Formula(
                         name=field_def["name"] + " Formula",
                         code=field_def["code"] + "_formula",
                         created_by=admin_user.id,
                         updated_by=admin_user.id
                    )
                    db.session.add(formula)
                    db.session.flush()

                    # Extract tokens
                    tokens_list = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', field_def["formula_expression"])
                    exclude_tokens = {"min", "max", "SUM_MONTHS"}
                    tokens = {t: "field" for t in tokens_list if t not in exclude_tokens and not t.replace('.', '', 1).isdigit() and not t.isdigit()}
                    
                    formula_ver = FormulaVersion(
                        formula_id=formula.id,
                        version_number=1,
                        expression=field_def["formula_expression"],
                        tokens=tokens,
                        published_at=datetime.now(timezone.utc),
                        published_by=admin_user.id,
                        created_by=admin_user.id
                    )
                    db.session.add(formula_ver)
                    db.session.flush()

                    formula.current_version_id = formula_ver.id
                    field_config["formula_version_id"] = formula_ver.id

                # Create FieldVersion
                fv_field = FieldVersion(
                    form_version_id=fv.id,
                    field_id=f.id,
                    version_number=1,
                    field_name=field_def["name"],
                    field_type=field_def["type"],
                    field_config=field_config,
                    frequency="annual" if is_agg else "monthly",
                    section_id=section.id,
                    created_by=admin_user.id
                )
                db.session.add(fv_field)
                db.session.flush()
                f.current_version_id = fv_field.id
                db.session.flush()

            # Map the form to the workbook
            wkbk_form = WorkbookForm(
                workbook_id=wkbk.id,
                form_id=form.id,
                display_order=form_def["display_order"],
                sheet_label=form_def["name"]
            )
            db.session.add(wkbk_form)

        # 5. Link sites and submitters
        print("Linking workbook to active sites...")
        sites = Site.query.filter_by(is_deleted=False).all()
        for site in sites:
            wkbk_site = WorkbookSite(
                workbook_id=wkbk.id,
                site_id=site.id,
                created_by=admin_user.id
            )
            db.session.add(wkbk_site)
            
            wkbk_submitter = WorkbookSiteSubmitter(
                workbook_id=wkbk.id,
                site_id=site.id,
                user_id=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(wkbk_submitter)

        db.session.commit()
        print("Jaigarh Workbook and Sheets seeded successfully!")

if __name__ == "__main__":
    run()
