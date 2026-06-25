import os
from pathlib import Path
import sys
import re
from datetime import datetime, timezone, date

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion, FormSection
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter
from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry

def run():
    app = create_app()
    with app.app_context():
        print("Starting Jaigarh Demo Workbook seeding...")
        
        # Reset any aborted transaction
        db.session.rollback()
        
        # Get admin user
        admin_user = User.query.filter_by(email="admin@example.com").first()
        if not admin_user:
            admin_user = User.query.first()
            if not admin_user:
                print("FAILED: No users found in DB. Run seed script first.")
                sys.exit(1)

        # 1. Clean up old jaigarh workbook entries
        print("Cleaning up old Jaigarh workbook records...")
        old_wkbks = Workbook.query.filter(Workbook.code.in_(["wkbk_jaigarh", "wkbk_jaigarh_demo"])).all()
        for w in old_wkbks:
            WorkbookForm.query.filter_by(workbook_id=w.id).delete()
            WorkbookSite.query.filter_by(workbook_id=w.id).delete()
            WorkbookSiteSubmitter.query.filter_by(workbook_id=w.id).delete()
            db.session.delete(w)
        db.session.commit()

        # Clean up forms
        form_codes = [
            "form_jaigarh_electricity",
            "form_jaigarh_diesel",
            "form_jaigarh_petrol",
            "form_jaigarh_hfhsd_ifo",
            "form_jaigarh_other_fuels_emissions",
            "form_jaigarh_refrigerants_gwp",
            "form_jaigarh_ghg_summary",
            "form_jaigarh_energy_summary",
            "form_jaigarh_other_fuels_energy",
            # Old codes
            "form_jaigarh_other_fuels",
            "form_jaigarh_summary"
        ]
        
        old_forms = Form.query.filter(Form.code.in_(form_codes)).all()
        for f in old_forms:
            f.current_version_id = None
        db.session.commit()

        # Clean up formulas
        formula_codes = [
            # Electricity
            "electricity_total_mwh_formula", "electricity_from_grid_total_mwh_formula", "electricity_other_source_total_mwh_formula",
            "electricity_total_fy_mwh_formula", "electricity_from_grid_emission_tco2e_formula", "electricity_other_source_emission_tco2e_formula",
            "electricity_total_emission_tco2e_formula", "electricity_energy_consumption_gj_formula",
            # Diesel
            "diesel_total_qty_kl_formula", "diesel_stationary_total_kl_formula", "diesel_mobile_total_kl_formula",
            "diesel_total_fy_kl_formula", "diesel_co2_emission_tco2e_formula", "diesel_ch4_emission_tco2e_formula",
            "diesel_n2o_emission_tco2e_formula", "diesel_total_emission_tco2e_formula", "diesel_energy_consumption_gj_formula",
            # Petrol
            "petrol_total_fy_kl_formula", "petrol_co2_emission_tco2e_formula", "petrol_ch4_emission_tco2e_formula",
            "petrol_n2o_emission_tco2e_formula", "petrol_total_emission_tco2e_formula", "petrol_energy_consumption_gj_formula",
            # HFHSD & IFO
            "hfhsd_ifo_total_qty_kl_formula", "hfhsd_total_fy_kl_formula", "ifo_total_fy_kl_formula", "hfhsd_ifo_total_fy_kl_formula",
            "hfhsd_ifo_co2_emission_tco2e_formula", "hfhsd_ifo_ch4_emission_tco2e_formula", "hfhsd_ifo_n2o_emission_tco2e_formula",
            "hfhsd_ifo_total_emission_tco2e_formula", "hfhsd_energy_consumption_gj_formula", "ifo_energy_consumption_gj_formula",
            "hfhsd_ifo_energy_consumption_gj_formula",
            # Other Fuels - Emissions
            "acetylene_emission_tco2_formula", "lpg_emission_tco2_formula", "co2_fire_extinguisher_emission_tco2_formula",
            "hfcs_emission_tco2_formula", "other_fuels_total_emissions_tco2_mth_formula", "other_fuels_total_emissions_tco2_formula",
            # Refrigerants
            "r22_emission_tco2e_formula", "r32_emission_tco2e_formula", "r410a_emission_tco2e_formula",
            "ch4_refrigerant_emission_tco2e_formula", "n2o_refrigerant_emission_tco2e_formula",
            "refrigerants_total_emission_mth_formula", "refrigerants_total_emission_tco2e_formula",
            # GHG Summary
            "summary_electricity_emissions_mth_formula", "summary_diesel_emissions_mth_formula", "summary_petrol_emissions_mth_formula",
            "summary_hfhsd_ifo_emissions_mth_formula", "summary_other_fuels_emissions_mth_formula", "summary_refrigerants_emissions_mth_formula",
            "summary_total_emissions_mth_formula", "summary_electricity_emissions_tco2e_formula", "summary_diesel_emissions_tco2e_formula",
            "summary_petrol_emissions_tco2e_formula", "summary_hfhsd_ifo_emissions_tco2e_formula", "summary_other_fuels_emissions_tco2e_formula",
            "summary_refrigerants_emissions_tco2e_formula", "total_emissions_tco2e_formula", "ghg_intensity_000_tco2e_per_million_mt_formula",
            "hfhsd_total_fy_kl_mirror_formula", "ifo_total_fy_kl_mirror_formula",
            # Other Fuels - Energy
            "acetylene_energy_gj_formula", "lpg_energy_gj_formula", "other_fuels_energy_quantity_total_t_formula",
            "other_fuels_energy_consumption_gj_mth_formula", "other_fuels_energy_consumption_gj_formula",
            # Energy Summary
            "summary_electricity_energy_gj_mth_formula", "summary_diesel_energy_gj_mth_formula", "summary_petrol_energy_gj_mth_formula",
            "summary_hfhsd_ifo_energy_gj_mth_formula", "summary_other_fuels_energy_gj_mth_formula", "summary_fossil_fuel_energy_gj_mth_formula",
            "summary_total_energy_gj_mth_formula", "electrical_energy_consumption_gj_formula", "summary_diesel_energy_gj_formula",
            "summary_petrol_energy_gj_formula", "summary_hfhsd_ifo_energy_gj_formula", "summary_other_fuels_energy_gj_formula",
            "fossil_fuel_energy_consumption_gj_formula", "total_energy_consumption_gj_formula", "electrical_energy_intensity_kj_per_mt_formula",
            "fossil_fuel_energy_intensity_kj_per_mt_formula", "energy_intensity_000_gj_per_million_mt_formula"
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
        print("Idempotent cleanup finished.")

        # 2. Seed Value Set
        print("Seeding GHG Emission & Energy Constants Value Set...")
        for code in ["GHG_CONSTANTS", "ghg_emission_energy_constants"]:
            old_vs = ValueSet.query.filter_by(code=code).first()
            if old_vs:
                old_vs.current_version_id = None
                db.session.commit()
                versions = ValueSetVersion.query.filter_by(value_set_id=old_vs.id).all()
                for v in versions:
                    ValueSetEntry.query.filter_by(value_set_version_id=v.id).delete()
                ValueSetVersion.query.filter_by(value_set_id=old_vs.id).delete()
                db.session.delete(old_vs)
                db.session.commit()

        vs = ValueSet(
            name="GHG Emission & Energy Constants",
            code="GHG_CONSTANTS",
            description="Workbook constants (GWP, EF, NCV, conversions) for Jaigarh FY25-26 GHG & Energy workbook calculations.",
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(vs)
        db.session.flush()

        vsv = ValueSetVersion(
            value_set_id=vs.id,
            version_number=1,
            status="Approved",
            effective_from=date(2025, 4, 1),
            submitted_by=admin_user.id,
            submitted_at=datetime.now(timezone.utc),
            approved_by=admin_user.id,
            approved_at=datetime.now(timezone.utc),
            created_by=admin_user.id
        )
        db.session.add(vsv)
        db.session.flush()

        constants = {
            "grid_emission_factor": "0.710",
            "other_source_emission_factor": "0.710",
            "mwh_to_gj": "3.6",
            "r22_gwp": "1960",
            "r32_gwp": "771",
            "r410a_gwp": "2256",
            "ch4_gwp": "29.8",
            "n2o_gwp": "273",
            "acetylene_ncv_gj_per_t": "47.30",
            "acetylene_emission_factor_tco2_per_t": "3.38",
            "lpg_ncv_gj_per_t": "47.30",
            "lpg_emission_factor_tco2_per_t": "2.985",
            "co2_fire_extinguisher_ef_tco2_per_t": "1.0",
            "diesel_co2_ef": "2.6898",
            "diesel_ch4_ef": "0.000108",
            "diesel_n2o_ef": "0.000022",
            "diesel_energy_factor_gj_per_kl": "36.12",
            "petrol_co2_ef": "2.3372",
            "petrol_ch4_ef": "0.000099",
            "petrol_n2o_ef": "0.000020",
            "petrol_energy_factor_gj_per_kl": "32.88",
            "hfhsd_co2_ef": "2.8311",
            "hfhsd_ch4_ef": "0.000109",
            "hfhsd_n2o_ef": "0.000022",
            "hfhsd_energy_factor_gj_per_kl": "36.40",
            "ifo_co2_ef": "2.8311",
            "ifo_ch4_ef": "0.000109",
            "ifo_n2o_ef": "0.000022",
            "ifo_energy_factor_gj_per_kl": "36.40"
        }

        for idx, (k, v) in enumerate(constants.items(), start=1):
            db.session.add(ValueSetEntry(
                value_set_version_id=vsv.id,
                entry_code=k,
                entry_label=v,
                display_order=idx,
                is_active=True,
                created_by=admin_user.id,
                updated_by=admin_user.id
            ))

        vs.current_version_id = vsv.id
        db.session.flush()
        print("Value set GHG_CONSTANTS seeded.")

        # 3. Create Workbook
        wkbk = Workbook(
            name="Jaigarh FY25–26 GHG + Energy Workbook",
            code="wkbk_jaigarh_demo",
            description="Workbook template capturing monthly electricity, fossil fuels, refrigerants, and GHG summary for Jaigarh site for FY25–26.",
            status="published",
            created_by=admin_user.id
        )
        db.session.add(wkbk)
        db.session.flush()

        # 4. Form definitions
        forms_def = [
            {
                "name": "Electricity Consumed",
                "code": "form_jaigarh_electricity",
                "display_order": 1,
                "fields": [
                    {"code": "electricity_from_grid_mwh", "name": "From Grid (MWH)", "type": "number", "unit": "MWh", "display_order": 1},
                    {"code": "electricity_other_source_mwh", "name": "Other Source (MWH)", "type": "number", "unit": "MWh", "display_order": 2},
                    {"code": "electricity_total_mwh", "name": "Total Electricity (MWH)", "type": "calculated", "formula_expression": "electricity_from_grid_mwh + electricity_other_source_mwh", "unit": "MWh", "display_order": 3},
                    
                    # Sheet results (Aggregates below table)
                    {"code": "electricity_from_grid_total_mwh", "name": "Total From Grid", "type": "calculated", "formula_expression": "SUM_MONTHS(electricity_from_grid_mwh)", "is_aggregate": True, "unit": "MWh", "display_order": 4},
                    {"code": "electricity_other_source_total_mwh", "name": "Total Other Source", "type": "calculated", "formula_expression": "SUM_MONTHS(electricity_other_source_mwh)", "is_aggregate": True, "unit": "MWh", "display_order": 5},
                    {"code": "electricity_total_fy_mwh", "name": "Total Electricity Consumed", "type": "calculated", "formula_expression": "SUM_MONTHS(electricity_total_mwh)", "is_aggregate": True, "unit": "MWh", "display_order": 6},
                    {"code": "electricity_from_grid_emission_tco2e", "name": "GHG Emission From Grid", "type": "calculated", "formula_expression": "electricity_from_grid_total_mwh * grid_emission_factor", "is_aggregate": True, "unit": "tCO2e", "display_order": 7},
                    {"code": "electricity_other_source_emission_tco2e", "name": "GHG Emission Other Source", "type": "calculated", "formula_expression": "electricity_other_source_total_mwh * other_source_emission_factor", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "electricity_total_emission_tco2e", "name": "Total Electricity GHG Emission", "type": "calculated", "formula_expression": "electricity_from_grid_emission_tco2e + electricity_other_source_emission_tco2e", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "electricity_energy_consumption_gj", "name": "Energy Consumption", "type": "calculated", "formula_expression": "electricity_total_fy_mwh * mwh_to_gj", "is_aggregate": True, "unit": "GJ", "display_order": 10},
                ]
            },
            {
                "name": "Diesel Consumed",
                "code": "form_jaigarh_diesel",
                "display_order": 2,
                "fields": [
                    {"code": "diesel_stationary_eqp_kl", "name": "Stationary Eqp (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    {"code": "diesel_mobile_eqp_kl", "name": "Mobile Eqp (KL)", "type": "number", "unit": "KL", "display_order": 2},
                    {"code": "diesel_total_qty_kl", "name": "Total Qty (KL)", "type": "calculated", "formula_expression": "diesel_stationary_eqp_kl + diesel_mobile_eqp_kl", "unit": "KL", "display_order": 3},
                    
                    # Sheet results (Aggregates below table)
                    {"code": "diesel_stationary_total_kl", "name": "Total Stationary Eqp", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_stationary_eqp_kl)", "is_aggregate": True, "unit": "KL", "display_order": 4},
                    {"code": "diesel_mobile_total_kl", "name": "Total Mobile Eqp", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_mobile_eqp_kl)", "is_aggregate": True, "unit": "KL", "display_order": 5},
                    {"code": "diesel_total_fy_kl", "name": "Total Diesel Qty", "type": "calculated", "formula_expression": "SUM_MONTHS(diesel_total_qty_kl)", "is_aggregate": True, "unit": "KL", "display_order": 6},
                    {"code": "diesel_co2_emission_tco2e", "name": "GHG Emission", "type": "calculated", "formula_expression": "diesel_total_fy_kl * diesel_co2_ef", "is_aggregate": True, "unit": "tCO2e", "display_order": 7},
                    {"code": "diesel_ch4_emission_tco2e", "name": "Total Emissions CH4", "type": "calculated", "formula_expression": "diesel_total_fy_kl * diesel_ch4_ef * ch4_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "diesel_n2o_emission_tco2e", "name": "Total Emissions N2O", "type": "calculated", "formula_expression": "diesel_total_fy_kl * diesel_n2o_ef * n2o_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "diesel_total_emission_tco2e", "name": "Total Diesel Emission", "type": "calculated", "formula_expression": "diesel_co2_emission_tco2e + diesel_ch4_emission_tco2e + diesel_n2o_emission_tco2e", "is_aggregate": True, "unit": "tCO2e", "display_order": 10},
                    {"code": "diesel_energy_consumption_gj", "name": "Energy Consumption", "type": "calculated", "formula_expression": "diesel_total_fy_kl * diesel_energy_factor_gj_per_kl", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                ]
            },
            {
                "name": "Petrol Consumed",
                "code": "form_jaigarh_petrol",
                "display_order": 3,
                "fields": [
                    {"code": "petrol_total_qty_kl", "name": "Total Qty (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    
                    # Sheet results (Aggregates below table)
                    {"code": "petrol_total_fy_kl", "name": "Total Petrol Qty", "type": "calculated", "formula_expression": "SUM_MONTHS(petrol_total_qty_kl)", "is_aggregate": True, "unit": "KL", "display_order": 2},
                    {"code": "petrol_co2_emission_tco2e", "name": "GHG Emission", "type": "calculated", "formula_expression": "petrol_total_fy_kl * petrol_co2_ef", "is_aggregate": True, "unit": "tCO2e", "display_order": 3},
                    {"code": "petrol_ch4_emission_tco2e", "name": "Total Emissions CH4", "type": "calculated", "formula_expression": "petrol_total_fy_kl * petrol_ch4_ef * ch4_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 4},
                    {"code": "petrol_n2o_emission_tco2e", "name": "Total Emissions N2O", "type": "calculated", "formula_expression": "petrol_total_fy_kl * petrol_n2o_ef * n2o_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 5},
                    {"code": "petrol_total_emission_tco2e", "name": "Total Petrol Emission", "type": "calculated", "formula_expression": "petrol_co2_emission_tco2e + petrol_ch4_emission_tco2e + petrol_n2o_emission_tco2e", "is_aggregate": True, "unit": "tCO2e", "display_order": 6},
                    {"code": "petrol_energy_consumption_gj", "name": "Energy Consumption", "type": "calculated", "formula_expression": "petrol_total_fy_kl * petrol_energy_factor_gj_per_kl", "is_aggregate": True, "unit": "GJ", "display_order": 7},
                ]
            },
            {
                "name": "HFHSD & IFO Consumed",
                "code": "form_jaigarh_hfhsd_ifo",
                "display_order": 4,
                "fields": [
                    {"code": "hfhsd_qty_kl", "name": "HFHSD Qty (KL)", "type": "number", "unit": "KL", "display_order": 1},
                    {"code": "ifo_qty_kl", "name": "IFO Qty (KL)", "type": "number", "unit": "KL", "display_order": 2},
                    {"code": "hfhsd_ifo_total_qty_kl", "name": "Total Qty (KL)", "type": "calculated", "formula_expression": "hfhsd_qty_kl + ifo_qty_kl", "unit": "KL", "display_order": 3},
                    
                    # Sheet results (Aggregates below table)
                    {"code": "hfhsd_total_fy_kl", "name": "Total HFHSD Qty", "type": "calculated", "formula_expression": "SUM_MONTHS(hfhsd_qty_kl)", "is_aggregate": True, "unit": "KL", "display_order": 4},
                    {"code": "ifo_total_fy_kl", "name": "Total IFO Qty", "type": "calculated", "formula_expression": "SUM_MONTHS(ifo_qty_kl)", "is_aggregate": True, "unit": "KL", "display_order": 5},
                    {"code": "hfhsd_ifo_total_fy_kl", "name": "Total HFHSD & IFO Qty", "type": "calculated", "formula_expression": "SUM_MONTHS(hfhsd_ifo_total_qty_kl)", "is_aggregate": True, "unit": "KL", "display_order": 6},
                    {"code": "hfhsd_ifo_co2_emission_tco2e", "name": "GHG Emission", "type": "calculated", "formula_expression": "hfhsd_total_fy_kl * hfhsd_co2_ef + ifo_total_fy_kl * ifo_co2_ef", "is_aggregate": True, "unit": "tCO2e", "display_order": 7},
                    {"code": "hfhsd_ifo_ch4_emission_tco2e", "name": "Total Emissions CH4", "type": "calculated", "formula_expression": "(hfhsd_total_fy_kl * hfhsd_ch4_ef + ifo_total_fy_kl * ifo_ch4_ef) * ch4_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 8},
                    {"code": "hfhsd_ifo_n2o_emission_tco2e", "name": "Total Emissions N2O", "type": "calculated", "formula_expression": "(hfhsd_total_fy_kl * hfhsd_n2o_ef + ifo_total_fy_kl * ifo_n2o_ef) * n2o_gwp", "is_aggregate": True, "unit": "tCO2e", "display_order": 9},
                    {"code": "hfhsd_ifo_total_emission_tco2e", "name": "Total HFHSD & IFO Emission", "type": "calculated", "formula_expression": "hfhsd_ifo_co2_emission_tco2e + hfhsd_ifo_ch4_emission_tco2e + hfhsd_ifo_n2o_emission_tco2e", "is_aggregate": True, "unit": "tCO2e", "display_order": 10},
                    {"code": "hfhsd_energy_consumption_gj", "name": "HFHSD Energy Consumption", "type": "calculated", "formula_expression": "hfhsd_total_fy_kl * hfhsd_energy_factor_gj_per_kl", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                    {"code": "ifo_energy_consumption_gj", "name": "IFO Energy Consumption", "type": "calculated", "formula_expression": "ifo_total_fy_kl * ifo_energy_factor_gj_per_kl", "is_aggregate": True, "unit": "GJ", "display_order": 12},
                    {"code": "hfhsd_ifo_energy_consumption_gj", "name": "Total HFHSD & IFO Energy", "type": "calculated", "formula_expression": "hfhsd_energy_consumption_gj + ifo_energy_consumption_gj", "is_aggregate": True, "unit": "GJ", "display_order": 13},
                ]
            },
            {
                "name": "Other Fuels - Emissions",
                "code": "form_jaigarh_other_fuels_emissions",
                "display_order": 5,
                "fields": [
                    {"code": "acetylene_quantity_t", "name": "Acetylene Quantity", "type": "number", "unit": "T", "display_order": 1},
                    {"code": "acetylene_emission_tco2", "name": "Acetylene tCO2", "type": "calculated", "formula_expression": "acetylene_quantity_t * acetylene_emission_factor_tco2_per_t", "unit": "tCO2", "display_order": 2},
                    {"code": "lpg_quantity_t", "name": "LPG Quantity", "type": "number", "unit": "T", "display_order": 3},
                    {"code": "lpg_emission_tco2", "name": "LPG tCO2", "type": "calculated", "formula_expression": "lpg_quantity_t * lpg_emission_factor_tco2_per_t", "unit": "tCO2", "display_order": 4},
                    {"code": "co2_fire_extinguisher_quantity_t", "name": "CO2 Fire Extinguisher Quantity", "type": "number", "unit": "T", "display_order": 5},
                    {"code": "co2_fire_extinguisher_emission_tco2", "name": "CO2 Fire Extinguisher tCO2", "type": "calculated", "formula_expression": "co2_fire_extinguisher_quantity_t * co2_fire_extinguisher_ef_tco2_per_t", "unit": "tCO2", "display_order": 6},
                    {"code": "hfcs_emission_tco2", "name": "HFCs Emission", "type": "calculated", "formula_expression": "refrigerants_total_emission_mth", "unit": "tCO2", "display_order": 7},
                    {"code": "other_fuels_total_emissions_tco2_mth", "name": "Total Other Fuels Emissions Mth", "type": "calculated", "formula_expression": "acetylene_emission_tco2 + lpg_emission_tco2 + co2_fire_extinguisher_emission_tco2 + hfcs_emission_tco2", "unit": "tCO2", "display_order": 8},
                    
                    # Sheet results
                    {"code": "other_fuels_total_emissions_tco2", "name": "Total Other Fuels Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(other_fuels_total_emissions_tco2_mth)", "is_aggregate": True, "unit": "tCO2", "display_order": 9},
                ]
            },
            {
                "name": "Refrigerants / GWP",
                "code": "form_jaigarh_refrigerants_gwp",
                "display_order": 6,
                "fields": [
                    {"code": "r22_quantity_kg", "name": "R22 Quantity", "type": "number", "unit": "kg", "display_order": 1},
                    {"code": "r22_emission_tco2e", "name": "R22 Emission", "type": "calculated", "formula_expression": "r22_quantity_kg * r22_gwp / 1000", "unit": "tCO2e", "display_order": 2},
                    {"code": "r32_quantity_kg", "name": "R32 Quantity", "type": "number", "unit": "kg", "display_order": 3},
                    {"code": "r32_emission_tco2e", "name": "R32 Emission", "type": "calculated", "formula_expression": "r32_quantity_kg * r32_gwp / 1000", "unit": "tCO2e", "display_order": 4},
                    {"code": "r410a_quantity_kg", "name": "410A Quantity", "type": "number", "unit": "kg", "display_order": 5},
                    {"code": "r410a_emission_tco2e", "name": "410A Emission", "type": "calculated", "formula_expression": "r410a_quantity_kg * r410a_gwp / 1000", "unit": "tCO2e", "display_order": 6},
                    {"code": "ch4_quantity_kg", "name": "CH4 Quantity", "type": "number", "unit": "kg", "display_order": 7},
                    {"code": "ch4_refrigerant_emission_tco2e", "name": "CH4 Emission", "type": "calculated", "formula_expression": "ch4_quantity_kg * ch4_gwp / 1000", "unit": "tCO2e", "display_order": 8},
                    {"code": "n2o_quantity_kg", "name": "N2O Quantity", "type": "number", "unit": "kg", "display_order": 9},
                    {"code": "n2o_refrigerant_emission_tco2e", "name": "N2O Emission", "type": "calculated", "formula_expression": "n2o_quantity_kg * n2o_gwp / 1000", "unit": "tCO2e", "display_order": 10},
                    {"code": "refrigerants_total_emission_mth", "name": "Total Refrigerants/HFCs Emission Mth", "type": "calculated", "formula_expression": "r22_emission_tco2e + r32_emission_tco2e + r410a_emission_tco2e + ch4_refrigerant_emission_tco2e + n2o_refrigerant_emission_tco2e", "unit": "tCO2e", "display_order": 11},
                    
                    # Sheet results
                    {"code": "refrigerants_total_emission_tco2e", "name": "Total Refrigerants / HFCs Emission", "type": "calculated", "formula_expression": "SUM_MONTHS(refrigerants_total_emission_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 12},
                ]
            },
            {
                "name": "GHG Summary",
                "code": "form_jaigarh_ghg_summary",
                "display_order": 7,
                "fields": [
                    {"code": "summary_electricity_emissions_mth", "name": "Electricity Emissions Mth", "type": "calculated", "formula_expression": "electricity_from_grid_mwh * grid_emission_factor + electricity_other_source_mwh * other_source_emission_factor", "unit": "tCO2e", "display_order": 1},
                    {"code": "summary_diesel_emissions_mth", "name": "Diesel Emissions Mth", "type": "calculated", "formula_expression": "diesel_total_qty_kl * diesel_co2_ef + diesel_total_qty_kl * diesel_ch4_ef * ch4_gwp + diesel_total_qty_kl * diesel_n2o_ef * n2o_gwp", "unit": "tCO2e", "display_order": 2},
                    {"code": "summary_petrol_emissions_mth", "name": "Petrol Emissions Mth", "type": "calculated", "formula_expression": "petrol_total_qty_kl * petrol_co2_ef + petrol_total_qty_kl * petrol_ch4_ef * ch4_gwp + petrol_total_qty_kl * petrol_n2o_ef * n2o_gwp", "unit": "tCO2e", "display_order": 3},
                    {"code": "summary_hfhsd_ifo_emissions_mth", "name": "HFHSD & IFO Emissions Mth", "type": "calculated", "formula_expression": "hfhsd_total_fy_kl_mirror * hfhsd_co2_ef + ifo_total_fy_kl_mirror * ifo_co2_ef + (hfhsd_total_fy_kl_mirror * hfhsd_ch4_ef + ifo_total_fy_kl_mirror * ifo_ch4_ef) * ch4_gwp + (hfhsd_total_fy_kl_mirror * hfhsd_n2o_ef + ifo_total_fy_kl_mirror * ifo_n2o_ef) * n2o_gwp", "unit": "tCO2e", "display_order": 4},
                    {"code": "summary_other_fuels_emissions_mth", "name": "Other Fuels Emissions Mth", "type": "calculated", "formula_expression": "other_fuels_total_emissions_tco2_mth", "unit": "tCO2e", "display_order": 5},
                    {"code": "summary_refrigerants_emissions_mth", "name": "Refrigerants Emissions Mth", "type": "calculated", "formula_expression": "refrigerants_total_emission_mth", "unit": "tCO2e", "display_order": 6},
                    {"code": "summary_total_emissions_mth", "name": "Total Emissions Mth", "type": "calculated", "formula_expression": "summary_electricity_emissions_mth + summary_diesel_emissions_mth + summary_petrol_emissions_mth + summary_hfhsd_ifo_emissions_mth + summary_other_fuels_emissions_mth + summary_refrigerants_emissions_mth", "unit": "tCO2e", "display_order": 7},
                    
                    {"code": "cargo_throughput_million_mt", "name": "Cargo / Throughput", "type": "number", "unit": "Million MT", "display_order": 8},
                    
                    # Mirror helpers
                    {"code": "hfhsd_total_fy_kl_mirror", "name": "HFHSD Qty (KL) Mirror", "type": "calculated", "formula_expression": "hfhsd_qty_kl", "unit": "KL", "display_order": 9},
                    {"code": "ifo_total_fy_kl_mirror", "name": "IFO Qty (KL) Mirror", "type": "calculated", "formula_expression": "ifo_qty_kl", "unit": "KL", "display_order": 10},
                    
                    # Sheet results (aggregates)
                    {"code": "summary_electricity_emissions_tco2e", "name": "Electricity Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_electricity_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 11},
                    {"code": "summary_diesel_emissions_tco2e", "name": "Diesel Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_diesel_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 12},
                    {"code": "summary_petrol_emissions_tco2e", "name": "Petrol Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_petrol_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 13},
                    {"code": "summary_hfhsd_ifo_emissions_tco2e", "name": "HFHSD & IFO Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_hfhsd_ifo_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 14},
                    {"code": "summary_other_fuels_emissions_tco2e", "name": "Other Fuels Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_other_fuels_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 15},
                    {"code": "summary_refrigerants_emissions_tco2e", "name": "Refrigerants / HFCs Emissions", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_refrigerants_emissions_mth)", "is_aggregate": True, "unit": "tCO2e", "display_order": 16},
                    {"code": "total_emissions_tco2e", "name": "Total Emissions", "type": "calculated", "formula_expression": "summary_electricity_emissions_tco2e + summary_diesel_emissions_tco2e + summary_petrol_emissions_tco2e + summary_hfhsd_ifo_emissions_tco2e + summary_other_fuels_emissions_tco2e + summary_refrigerants_emissions_tco2e", "is_aggregate": True, "unit": "tCO2e", "display_order": 17},
                    {"code": "ghg_intensity_000_tco2e_per_million_mt", "name": "GHG Intensity", "type": "calculated", "formula_expression": "(total_emissions_tco2e / 1000) / SUM_MONTHS(cargo_throughput_million_mt)", "is_aggregate": True, "unit": "000' tCO2e/Million MT", "display_order": 18},
                ]
            },
            {
                "name": "Energy Consumption Summary",
                "code": "form_jaigarh_energy_summary",
                "display_order": 8,
                "fields": [
                    {"code": "summary_electricity_energy_gj_mth", "name": "Electrical Energy Mth", "type": "calculated", "formula_expression": "electricity_total_mwh * mwh_to_gj", "unit": "GJ", "display_order": 1},
                    {"code": "summary_diesel_energy_gj_mth", "name": "Diesel Energy Mth", "type": "calculated", "formula_expression": "diesel_total_qty_kl * diesel_energy_factor_gj_per_kl", "unit": "GJ", "display_order": 2},
                    {"code": "summary_petrol_energy_gj_mth", "name": "Petrol Energy Mth", "type": "calculated", "formula_expression": "petrol_total_qty_kl * petrol_energy_factor_gj_per_kl", "unit": "GJ", "display_order": 3},
                    {"code": "summary_hfhsd_ifo_energy_gj_mth", "name": "HFHSD & IFO Energy Mth", "type": "calculated", "formula_expression": "hfhsd_qty_kl * hfhsd_energy_factor_gj_per_kl + ifo_qty_kl * ifo_energy_factor_gj_per_kl", "unit": "GJ", "display_order": 4},
                    {"code": "summary_other_fuels_energy_gj_mth", "name": "Other Fuels Energy Mth", "type": "calculated", "formula_expression": "other_fuels_energy_consumption_gj_mth", "unit": "GJ", "display_order": 5},
                    {"code": "summary_fossil_fuel_energy_gj_mth", "name": "Fossil Fuel Energy Mth", "type": "calculated", "formula_expression": "summary_diesel_energy_gj_mth + summary_petrol_energy_gj_mth + summary_hfhsd_ifo_energy_gj_mth + summary_other_fuels_energy_gj_mth", "unit": "GJ", "display_order": 6},
                    {"code": "summary_total_energy_gj_mth", "name": "Total Energy Mth", "type": "calculated", "formula_expression": "summary_electricity_energy_gj_mth + summary_fossil_fuel_energy_gj_mth", "unit": "GJ", "display_order": 7},
                    
                    {"code": "energy_cargo_throughput_million_mt", "name": "Cargo / Throughput", "type": "number", "unit": "Million MT", "display_order": 8},
                    
                    # Sheet results (aggregates)
                    {"code": "electrical_energy_consumption_gj", "name": "Electrical Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_electricity_energy_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 9},
                    {"code": "summary_diesel_energy_gj", "name": "Diesel Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_diesel_energy_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 10},
                    {"code": "summary_petrol_energy_gj", "name": "Petrol Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_petrol_energy_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 11},
                    {"code": "summary_hfhsd_ifo_energy_gj", "name": "HFHSD & IFO Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_hfhsd_ifo_energy_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 12},
                    {"code": "summary_other_fuels_energy_gj", "name": "Other Fuels Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(summary_other_fuels_energy_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 13},
                    {"code": "fossil_fuel_energy_consumption_gj", "name": "Fossil Fuel Energy Consumption", "type": "calculated", "formula_expression": "summary_diesel_energy_gj + summary_petrol_energy_gj + summary_hfhsd_ifo_energy_gj + summary_other_fuels_energy_gj", "is_aggregate": True, "unit": "GJ", "display_order": 14},
                    {"code": "total_energy_consumption_gj", "name": "Total Energy Consumption", "type": "calculated", "formula_expression": "electrical_energy_consumption_gj + fossil_fuel_energy_consumption_gj", "is_aggregate": True, "unit": "GJ", "display_order": 15},
                    {"code": "electrical_energy_intensity_kj_per_mt", "name": "Electrical Energy Intensity", "type": "calculated", "formula_expression": "electrical_energy_consumption_gj / SUM_MONTHS(energy_cargo_throughput_million_mt)", "is_aggregate": True, "unit": "KJ/MT", "display_order": 16},
                    {"code": "fossil_fuel_energy_intensity_kj_per_mt", "name": "Fossil Fuel Energy Intensity", "type": "calculated", "formula_expression": "fossil_fuel_energy_consumption_gj / SUM_MONTHS(energy_cargo_throughput_million_mt)", "is_aggregate": True, "unit": "KJ/MT", "display_order": 17},
                    {"code": "energy_intensity_000_gj_per_million_mt", "name": "Total Energy Intensity", "type": "calculated", "formula_expression": "(total_energy_consumption_gj / 1000) / SUM_MONTHS(energy_cargo_throughput_million_mt)", "is_aggregate": True, "unit": "000' GJ/Million MT", "display_order": 18},
                ]
            },
            {
                "name": "Other Fuels - Energy",
                "code": "form_jaigarh_other_fuels_energy",
                "display_order": 9,
                "fields": [
                    {"code": "acetylene_energy_quantity_t", "name": "Acetylene Quantity", "type": "number", "unit": "T", "display_order": 1},
                    {"code": "acetylene_energy_gj", "name": "Acetylene Energy", "type": "calculated", "formula_expression": "acetylene_energy_quantity_t * acetylene_ncv_gj_per_t", "unit": "GJ", "display_order": 2},
                    {"code": "lpg_energy_quantity_t", "name": "LPG Quantity", "type": "number", "unit": "T", "display_order": 3},
                    {"code": "lpg_energy_gj", "name": "LPG Energy", "type": "calculated", "formula_expression": "lpg_energy_quantity_t * lpg_ncv_gj_per_t", "unit": "GJ", "display_order": 4},
                    {"code": "other_fuels_energy_quantity_total_t", "name": "Energy Consumption Quantity", "type": "calculated", "formula_expression": "acetylene_energy_quantity_t + lpg_energy_quantity_t", "unit": "T", "display_order": 5},
                    {"code": "other_fuels_energy_consumption_gj_mth", "name": "Other Fuels Energy Consumption Mth", "type": "calculated", "formula_expression": "acetylene_energy_gj + lpg_energy_gj", "unit": "GJ", "display_order": 6},
                    
                    # Sheet result
                    {"code": "other_fuels_energy_consumption_gj", "name": "Other Fuels Energy Consumption", "type": "calculated", "formula_expression": "SUM_MONTHS(other_fuels_energy_consumption_gj_mth)", "is_aggregate": True, "unit": "GJ", "display_order": 7},
                ]
            }
        ]

        # 5. Build Forms in DB
        for form_def in forms_def:
            print(f"Creating form '{form_def['name']}' ({form_def['code']})...")
            
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
            layout_type = "monthly_table"
            section = FormSection(
                form_id=form.id,
                name=form_def["name"] + " Section",
                code=form_def["code"] + "_section",
                layout_type=layout_type,
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

        # 6. Link site and submitters
        print("Linking workbook to active sites...")
        site = Site.query.filter_by(is_deleted=False).first()
        if site:
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
            print(f"Workbook linked to site: {site.name} for user: {admin_user.full_name}")

        db.session.commit()
        print("Jaigarh Demo Workbook and 9 Sheets seeded successfully!")

if __name__ == "__main__":
    run()
