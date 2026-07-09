"""Field, formula, and Excel mapping definitions for the Jaigarh FY25-26 workbook seed."""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_EXCEL_PATH = Path(
    "/Users/shubhamindulkar/Digital-GHG-inventory/../Downloads/GHG DI-1/"
    "FY25-26 GHG Final Sheets/Final Data_Jaigarh.xlsx"
).resolve()

SITE_CODE = "JAIGARH"
SITE_NAME = "Jaigarh Port"
WORKBOOK_CODE = "WKBK_JAIGARH_FY2526"
WORKBOOK_NAME = "Jaigarh FY25-26 GHG"
WORKFLOW_CODE = "WF_JAIGARH"
FY_START_YEAR = 2025

# Excel row 6 = April FY on 305-4; row 4 = April FY on Cargo Handled
EXCEL_MONTH_ROWS_3054 = list(range(6, 18))
EXCEL_MONTH_ROWS_CARGO = list(range(4, 16))
EXCEL_MONTH_ROWS = EXCEL_MONTH_ROWS_3054
FY_MONTHS = [
    (2025, 4), (2025, 5), (2025, 6), (2025, 7), (2025, 8), (2025, 9),
    (2025, 10), (2025, 11), (2025, 12),
    (2026, 1), (2026, 2), (2026, 3),
]

FORMULA_DEFINITIONS = {
    "formula_jai_elec_total_mwh": {
        "name": "Jaigarh Electricity Total MWH",
        "expression": "jai_elec_grid_mwh + jai_elec_group_mwh",
    },
    "formula_jai_diesel_total_kl": {
        "name": "Jaigarh Diesel Total KL",
        "expression": "jai_diesel_stationary_kl + jai_diesel_mobile_kl",
    },
    "formula_jai_hfhsd_ifo_total_kl": {
        "name": "Jaigarh HFHSD+IFO Total KL",
        "expression": "jai_hfhsd_kl + jai_ifo_converted_kl",
    },
    "formula_jai_cargo_total_mt": {
        "name": "Jaigarh Cargo Total MT",
        "expression": "jai_cargo_non_coastal_mt + jai_cargo_coastal_mt",
    },
    "formula_jai_fy_elec_grid_mwh": {
        "name": "Jaigarh FY Grid MWH",
        "expression": "SUM_MONTHS(jai_elec_grid_mwh)",
    },
    "formula_jai_fy_elec_group_mwh": {
        "name": "Jaigarh FY Group MWH",
        "expression": "SUM_MONTHS(jai_elec_group_mwh)",
    },
    "formula_jai_fy_diesel_stationary_kl": {
        "name": "Jaigarh FY Diesel Stationary KL",
        "expression": "SUM_MONTHS(jai_diesel_stationary_kl)",
    },
    "formula_jai_fy_diesel_mobile_kl": {
        "name": "Jaigarh FY Diesel Mobile KL",
        "expression": "SUM_MONTHS(jai_diesel_mobile_kl)",
    },
    "formula_jai_fy_diesel_total_kl": {
        "name": "Jaigarh FY Diesel Total KL",
        "expression": "SUM_MONTHS(jai_diesel_total_kl)",
    },
    "formula_jai_fy_petrol_kl": {
        "name": "Jaigarh FY Petrol KL",
        "expression": "SUM_MONTHS(jai_petrol_kl)",
    },
    "formula_jai_fy_hfhsd_ifo_total_kl": {
        "name": "Jaigarh FY HFHSD+IFO KL",
        "expression": "SUM_MONTHS(jai_hfhsd_ifo_total_kl)",
    },
    "formula_jai_cargo_fy_total_mt": {
        "name": "Jaigarh FY Cargo Total MT",
        "expression": "SUM_MONTHS(jai_cargo_total_mt)",
    },
    "formula_jai_other_fuel_total_tco2": {
        "name": "Jaigarh Other Fuels tCO2",
        "expression": (
            "3.38 * jai_other_acetylene_qty + "
            "(jai_hfc_r32_qty * jai_hfc_r32_gwp + jai_hfc_410a_qty * jai_hfc_410a_gwp) / 1000"
        ),
    },
    "formula_jai_ghg_elec_grid_tco2e": {
        "name": "Jaigarh Grid Electricity tCO2e",
        "expression": "SUM_MONTHS(jai_elec_grid_mwh) * jai_grid_ef",
    },
    "formula_jai_ghg_elec_group_tco2e": {
        "name": "Jaigarh Group Electricity tCO2e",
        "expression": "SUM_MONTHS(jai_elec_group_mwh) * jai_group_ef",
    },
    "formula_jai_ghg_diesel_co2_tco2e": {
        "name": "Jaigarh Diesel CO2 tCO2e",
        "expression": "SUM_MONTHS(jai_diesel_total_kl) * 0.84 * 43 * 74.1 / 1000",
    },
    "formula_jai_ghg_diesel_ch4_tco2e": {
        "name": "Jaigarh Diesel CH4 tCO2e",
        "expression": "SUM_MONTHS(jai_diesel_total_kl) * 0.84 * 43 * 0.01 / 1000 * jai_gwp_ch4",
    },
    "formula_jai_ghg_diesel_n2o_tco2e": {
        "name": "Jaigarh Diesel N2O tCO2e",
        "expression": "SUM_MONTHS(jai_diesel_total_kl) * 0.84 * 43 * 0.0006 / 1000 * jai_gwp_n2o",
    },
    "formula_jai_ghg_petrol_co2_tco2e": {
        "name": "Jaigarh Petrol CO2 tCO2e",
        "expression": "SUM_MONTHS(jai_petrol_kl) * 0.74 * 44.3 * 69.3 / 1000",
    },
    "formula_jai_ghg_petrol_ch4_tco2e": {
        "name": "Jaigarh Petrol CH4 tCO2e",
        "expression": "SUM_MONTHS(jai_petrol_kl) * 0.74 * 43 * 0.033 / 1000 * jai_gwp_ch4",
    },
    "formula_jai_ghg_petrol_n2o_tco2e": {
        "name": "Jaigarh Petrol N2O tCO2e",
        "expression": "SUM_MONTHS(jai_petrol_kl) * 0.74 * 43 * 0.0032 / 1000 * jai_gwp_n2o",
    },
    "formula_jai_ghg_hfhsd_co2_tco2e": {
        "name": "Jaigarh HFHSD/IFO CO2 tCO2e",
        "expression": "SUM_MONTHS(jai_hfhsd_ifo_total_kl) * 0.9 * 40.4 * 77.4 / 1000",
    },
    "formula_jai_ghg_hfhsd_ch4_tco2e": {
        "name": "Jaigarh HFHSD/IFO CH4 tCO2e",
        "expression": "SUM_MONTHS(jai_hfhsd_ifo_total_kl) * 0.9 * 40.4 * 0.01 / 1000 * jai_gwp_ch4",
    },
    "formula_jai_ghg_hfhsd_n2o_tco2e": {
        "name": "Jaigarh HFHSD/IFO N2O tCO2e",
        "expression": "SUM_MONTHS(jai_hfhsd_ifo_total_kl) * 0.9 * 40.4 * 0.0006 / 1000 * jai_gwp_n2o",
    },
    "formula_jai_ghg_total_tco2": {
        "name": "Jaigarh Total GHG tCO2",
        "expression": (
            "jai_ghg_elec_grid_tco2e + jai_ghg_elec_group_tco2e + "
            "jai_ghg_diesel_co2_tco2e + jai_ghg_petrol_co2_tco2e + jai_ghg_hfhsd_co2_tco2e + "
            "jai_other_fuel_total_tco2 + jai_ghg_diesel_ch4_tco2e + jai_ghg_petrol_ch4_tco2e + "
            "jai_ghg_hfhsd_ch4_tco2e + jai_ghg_diesel_n2o_tco2e + jai_ghg_petrol_n2o_tco2e + "
            "jai_ghg_hfhsd_n2o_tco2e"
        ),
    },
    "formula_jai_ghg_intensity": {
        "name": "Jaigarh GHG Intensity",
        "expression": "jai_ghg_total_tco2 / 1000 / (jai_cargo_fy_total_mt / 1000000)",
    },
    "formula_jai_302_elec_gj": {
        "name": "Jaigarh 302-1 Electricity GJ",
        "expression": "SUM_MONTHS(jai_elec_total_mwh) * 3.6",
    },
    "formula_jai_302_diesel_gj": {
        "name": "Jaigarh 302-1 Diesel GJ",
        "expression": "SUM_MONTHS(jai_diesel_total_kl) * 0.84 * 43",
    },
    "formula_jai_302_petrol_gj": {
        "name": "Jaigarh 302-1 Petrol GJ",
        "expression": "SUM_MONTHS(jai_petrol_kl) * 0.74 * 44.3",
    },
    "formula_jai_302_hfhsd_gj": {
        "name": "Jaigarh 302-1 HFHSD/IFO GJ",
        "expression": "SUM_MONTHS(jai_hfhsd_ifo_total_kl) * 0.9 * 40.4",
    },
    "formula_jai_302_other_gj": {
        "name": "Jaigarh 302-1 Other Fuels GJ",
        "expression": "jai_other_acetylene_qty * 47.3",
    },
    "formula_jai_302_total_energy_gj": {
        "name": "Jaigarh 302-1 Total Energy GJ",
        "expression": (
            "jai_302_elec_gj + jai_302_diesel_gj + jai_302_petrol_gj + "
            "jai_302_hfhsd_gj + jai_302_other_gj"
        ),
    },
    "formula_jai_302_energy_intensity": {
        "name": "Jaigarh 302-1 Energy Intensity",
        "expression": "jai_302_total_energy_gj / 1000 / (jai_cargo_fy_total_mt / 1000000)",
    },
    "formula_jai_3051_scope1_total": {
        "name": "Jaigarh 305-1 Scope 1 Total",
        "expression": (
            "jai_ghg_diesel_co2_tco2e + jai_ghg_petrol_co2_tco2e + jai_ghg_hfhsd_co2_tco2e + "
            "jai_other_fuel_total_tco2 + jai_ghg_diesel_ch4_tco2e + jai_ghg_petrol_ch4_tco2e + "
            "jai_ghg_hfhsd_ch4_tco2e + jai_ghg_diesel_n2o_tco2e + jai_ghg_petrol_n2o_tco2e + "
            "jai_ghg_hfhsd_n2o_tco2e"
        ),
    },
    "formula_jai_3051_intensity": {
        "name": "Jaigarh 305-1 GHG Intensity",
        "expression": "jai_3051_scope1_total / 1000 / (jai_cargo_fy_total_mt / 1000000)",
    },
    "formula_jai_3052_scope2_total": {
        "name": "Jaigarh 305-2 Scope 2 Total",
        "expression": "jai_ghg_elec_grid_tco2e + jai_ghg_elec_group_tco2e",
    },
    "formula_jai_3052_intensity": {
        "name": "Jaigarh 305-2 GHG Intensity",
        "expression": "jai_3052_scope2_total / 1000 / (jai_cargo_fy_total_mt / 1000000)",
    },
    "formula_jai_gri_ref_cargo_fy_mt": {
        "name": "Jaigarh GRI Dashboard FY Cargo MT",
        "expression": "jai_cargo_fy_total_mt",
    },
    "formula_jai_gri_ref_elec_fy_mwh": {
        "name": "Jaigarh GRI Dashboard FY Electricity MWH",
        "expression": "SUM_MONTHS(jai_elec_total_mwh)",
    },
    "formula_jai_gri_ref_elec_grid_tco2": {
        "name": "Jaigarh GRI Dashboard Grid Scope 2",
        "expression": "jai_ghg_elec_grid_tco2e",
    },
    "formula_jai_gri_ref_elec_group_tco2": {
        "name": "Jaigarh GRI Dashboard Group Scope 2",
        "expression": "jai_ghg_elec_group_tco2e",
    },
}

ANNUAL_RESULT_CONFIG = {
    "field_scope": "annual_result",
    "result_role": "aggregate_result",
    "display_region": "under_input_column",
    "blank_policy": "strict",
    "is_required": False,
    "remarks_required": False,
    "proof_required": False,
    "round_off_decimals": 3,
}

READONLY_SUMMARY_CONFIG = {
    **ANNUAL_RESULT_CONFIG,
    "readonly": True,
}

VIZ_KPI_THIRD = {
    "visualization": {
        "widget": "kpi",
        "span": "third",
        "source_mode": "self",
        "show_unit": True,
        "show_formula_status": True,
    },
}

VIZ_KPI_HALF = {
    "visualization": {
        "widget": "kpi",
        "span": "half",
        "source_mode": "self",
        "show_unit": True,
        "show_formula_status": True,
    },
}

VIZ_KPI_FULL = {
    "visualization": {
        "widget": "kpi",
        "span": "full",
        "source_mode": "self",
        "show_unit": True,
        "show_formula_status": True,
    },
}

VIZ_LINE_ENERGY_TREND = {
    "visualization": {
        "widget": "line",
        "span": "full",
        "source_mode": "fields",
        "source_field_codes": [
            "jai_elec_grid_mwh",
            "jai_elec_group_mwh",
            "jai_diesel_total_kl",
            "jai_petrol_kl",
        ],
    },
}

VIZ_LINE_CARGO_TREND = {
    "visualization": {
        "widget": "line",
        "span": "full",
        "source_mode": "fields",
        "source_field_codes": [
            "jai_cargo_non_coastal_mt",
            "jai_cargo_coastal_mt",
            "jai_cargo_total_mt",
        ],
    },
}

VIZ_DONUT_SCOPE_SPLIT = {
    "visualization": {
        "widget": "donut",
        "span": "half",
        "donut_segments": [
            {"field_code": "jai_3051_scope1_total", "label": "Scope 1"},
            {"field_code": "jai_3052_scope2_total", "label": "Scope 2"},
        ],
    },
}

ELECTRICITY_MONTHLY_FIELDS = {
    "jai_elec_grid_mwh",
    "jai_elec_group_mwh",
}

FUEL_MONTHLY_FIELDS = {
    "jai_diesel_stationary_kl",
    "jai_diesel_mobile_kl",
    "jai_petrol_kl",
    "jai_hfhsd_kl",
    "jai_ifo_converted_kl",
}

ANNUAL_EXCEL_VALUES_ELECTRICITY = {
    "jai_grid_ef",
    "jai_group_ef",
}

ANNUAL_EXCEL_VALUES_FUEL = {
    "jai_gwp_ch4",
    "jai_gwp_n2o",
    "jai_other_acetylene_qty",
    "jai_hfc_r32_qty",
    "jai_hfc_r32_gwp",
    "jai_hfc_410a_qty",
    "jai_hfc_410a_gwp",
}

FORM_DEFINITIONS = [
    {
        "code": "form_jai_cargo",
        "name": "Cargo Handled",
        "sheet_label": "Cargo Handled",
        "display_order": 1,
        "sections": [
            {"code": "sec_cargo_monthly", "name": "Monthly Cargo", "layout_type": "monthly_table", "display_order": 1},
        ],
        "fields": [
            {"field_code": "jai_cargo_non_coastal_mt", "field_name": "Non Coastal Cargo (MT)", "field_type": "number", "section_code": "sec_cargo_monthly", "frequency": "monthly", "field_config": {"unit": "MT"}},
            {"field_code": "jai_cargo_coastal_mt", "field_name": "Coastal Cargo (MT)", "field_type": "number", "section_code": "sec_cargo_monthly", "frequency": "monthly", "field_config": {"unit": "MT"}},
            {"field_code": "jai_cargo_total_mt", "field_name": "Total Cargo (MT)", "field_type": "calculated", "section_code": "sec_cargo_monthly", "frequency": "monthly", "field_config": {"unit": "MT"}, "formula_code": "formula_jai_cargo_total_mt"},
            {"field_code": "jai_cargo_fy_total_mt", "field_name": "FY Total Cargo (MT)", "field_type": "calculated", "section_code": "sec_cargo_monthly", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "MT"}, "formula_code": "formula_jai_cargo_fy_total_mt"},
        ],
    },
    {
        "code": "form_jai_electricity",
        "name": "Electricity",
        "sheet_label": "Electricity",
        "display_order": 2,
        "sections": [
            {"code": "sec_elec_monthly", "name": "Monthly Consumption", "layout_type": "monthly_table", "display_order": 1},
            {"code": "sec_elec_ef", "name": "Emission Factors", "layout_type": "annual_table", "display_order": 2},
            {"code": "sec_elec_scope2", "name": "Scope 2 Results", "layout_type": "annual_table", "display_order": 3},
        ],
        "fields": [
            {"field_code": "jai_elec_grid_mwh", "field_name": "Grid Electricity (MWH)", "field_type": "number", "section_code": "sec_elec_monthly", "frequency": "monthly", "field_config": {"unit": "MWH"}},
            {"field_code": "jai_elec_group_mwh", "field_name": "Group Electricity (MWH)", "field_type": "number", "section_code": "sec_elec_monthly", "frequency": "monthly", "field_config": {"unit": "MWH"}},
            {"field_code": "jai_elec_total_mwh", "field_name": "Total Electricity (MWH)", "field_type": "calculated", "section_code": "sec_elec_monthly", "frequency": "monthly", "field_config": {"unit": "MWH"}, "formula_code": "formula_jai_elec_total_mwh"},
            {"field_code": "jai_grid_ef", "field_name": "Grid Emission Factor", "field_type": "number", "section_code": "sec_elec_ef", "frequency": "annual", "field_config": {"unit": "tCO2/MWH"}},
            {"field_code": "jai_group_ef", "field_name": "Group Emission Factor", "field_type": "number", "section_code": "sec_elec_ef", "frequency": "annual", "field_config": {"unit": "tCO2/MWH"}},
            {"field_code": "jai_ghg_elec_grid_tco2e", "field_name": "Grid GHG (tCO2e)", "field_type": "calculated", "section_code": "sec_elec_scope2", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_elec_grid_tco2e"},
            {"field_code": "jai_ghg_elec_group_tco2e", "field_name": "Group GHG (tCO2e)", "field_type": "calculated", "section_code": "sec_elec_scope2", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_elec_group_tco2e"},
        ],
    },
    {
        "code": "form_jai_fuel",
        "name": "Fuel Consumption",
        "sheet_label": "Fuel Consumption",
        "display_order": 3,
        "sections": [
            {"code": "sec_fuel_monthly", "name": "Monthly Consumption", "layout_type": "monthly_table", "display_order": 1},
            {"code": "sec_fuel_other", "name": "Other Fuels & GWP", "layout_type": "annual_table", "display_order": 2},
            {"code": "sec_fuel_scope1", "name": "Scope 1 Results", "layout_type": "annual_table", "display_order": 3},
        ],
        "fields": [
            {"field_code": "jai_diesel_stationary_kl", "field_name": "Diesel Stationary (KL)", "field_type": "number", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}},
            {"field_code": "jai_diesel_mobile_kl", "field_name": "Diesel Mobile (KL)", "field_type": "number", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}},
            {"field_code": "jai_diesel_total_kl", "field_name": "Diesel Total (KL)", "field_type": "calculated", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}, "formula_code": "formula_jai_diesel_total_kl"},
            {"field_code": "jai_petrol_kl", "field_name": "Petrol (KL)", "field_type": "number", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}},
            {"field_code": "jai_hfhsd_kl", "field_name": "HFHSD (KL)", "field_type": "number", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}},
            {"field_code": "jai_ifo_converted_kl", "field_name": "IFO Converted (KL)", "field_type": "number", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}},
            {"field_code": "jai_hfhsd_ifo_total_kl", "field_name": "HFHSD+IFO Total (KL)", "field_type": "calculated", "section_code": "sec_fuel_monthly", "frequency": "monthly", "field_config": {"unit": "KL"}, "formula_code": "formula_jai_hfhsd_ifo_total_kl"},
            {"field_code": "jai_gwp_ch4", "field_name": "CH4 GWP", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {}},
            {"field_code": "jai_gwp_n2o", "field_name": "N2O GWP", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {}},
            {"field_code": "jai_other_acetylene_qty", "field_name": "Acetylene Quantity (T)", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {"unit": "T"}},
            {"field_code": "jai_hfc_r32_qty", "field_name": "R32 Quantity (Kg)", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {"unit": "Kg"}},
            {"field_code": "jai_hfc_r32_gwp", "field_name": "R32 GWP", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {}},
            {"field_code": "jai_hfc_410a_qty", "field_name": "410A Quantity (Kg)", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {"unit": "Kg"}},
            {"field_code": "jai_hfc_410a_gwp", "field_name": "410A GWP", "field_type": "number", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {}},
            {"field_code": "jai_other_fuel_total_tco2", "field_name": "Other Fuels tCO2", "field_type": "calculated", "section_code": "sec_fuel_other", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2"}, "formula_code": "formula_jai_other_fuel_total_tco2"},
            {"field_code": "jai_ghg_diesel_co2_tco2e", "field_name": "Diesel CO2 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_diesel_co2_tco2e"},
            {"field_code": "jai_ghg_diesel_ch4_tco2e", "field_name": "Diesel CH4 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_diesel_ch4_tco2e"},
            {"field_code": "jai_ghg_diesel_n2o_tco2e", "field_name": "Diesel N2O (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_diesel_n2o_tco2e"},
            {"field_code": "jai_ghg_petrol_co2_tco2e", "field_name": "Petrol CO2 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_petrol_co2_tco2e"},
            {"field_code": "jai_ghg_petrol_ch4_tco2e", "field_name": "Petrol CH4 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_petrol_ch4_tco2e"},
            {"field_code": "jai_ghg_petrol_n2o_tco2e", "field_name": "Petrol N2O (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_petrol_n2o_tco2e"},
            {"field_code": "jai_ghg_hfhsd_co2_tco2e", "field_name": "HFHSD/IFO CO2 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_hfhsd_co2_tco2e"},
            {"field_code": "jai_ghg_hfhsd_ch4_tco2e", "field_name": "HFHSD/IFO CH4 (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_hfhsd_ch4_tco2e"},
            {"field_code": "jai_ghg_hfhsd_n2o_tco2e", "field_name": "HFHSD/IFO N2O (tCO2e)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2e"}, "formula_code": "formula_jai_ghg_hfhsd_n2o_tco2e"},
            {"field_code": "jai_ghg_total_tco2", "field_name": "Total GHG (tCO2)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2"}, "formula_code": "formula_jai_ghg_total_tco2"},
            {"field_code": "jai_ghg_intensity", "field_name": "GHG Intensity (000 tCO2/Million MT)", "field_type": "calculated", "section_code": "sec_fuel_scope1", "frequency": "annual", "field_config": {**ANNUAL_RESULT_CONFIG, "unit": "tCO2/MMT"}, "formula_code": "formula_jai_ghg_intensity"},
        ],
    },
    {
        "code": "form_jai_gri_summary",
        "name": "GRI Summary",
        "sheet_label": "GRI Summary",
        "display_order": 4,
        "sections": [
            {"code": "sec_gri_operations", "name": "Electricity & Cargo", "layout_type": "summary_dashboard", "display_order": 1},
            {"code": "sec_302_results", "name": "GRI 302-1 Energy", "layout_type": "summary_dashboard", "display_order": 2},
            {"code": "sec_3051_results", "name": "GRI 305-1 Direct Emissions", "layout_type": "summary_dashboard", "display_order": 3},
            {"code": "sec_3052_results", "name": "GRI 305-2 Indirect Emissions", "layout_type": "summary_dashboard", "display_order": 4},
            {"code": "sec_gri_overview", "name": "Emissions Overview", "layout_type": "summary_dashboard", "display_order": 5},
        ],
        "fields": [
            {"field_code": "jai_viz_elec_fy_mwh", "field_name": "FY Electricity (MWH)", "field_type": "calculated", "section_code": "sec_gri_operations", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "MWH"}, "formula_code": "formula_jai_gri_ref_elec_fy_mwh"},
            {"field_code": "jai_viz_cargo_fy_mt", "field_name": "FY Cargo Handled (MT)", "field_type": "calculated", "section_code": "sec_gri_operations", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "MT"}, "formula_code": "formula_jai_gri_ref_cargo_fy_mt"},
            {"field_code": "jai_viz_cargo_trend", "field_name": "Monthly Cargo Trend", "field_type": "calculated", "section_code": "sec_gri_operations", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_LINE_CARGO_TREND}, "formula_code": "formula_jai_gri_ref_cargo_fy_mt"},
            {"field_code": "jai_302_elec_gj", "field_name": "Electricity Energy (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "GJ"}, "formula_code": "formula_jai_302_elec_gj"},
            {"field_code": "jai_302_diesel_gj", "field_name": "Diesel Energy (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "GJ"}, "formula_code": "formula_jai_302_diesel_gj"},
            {"field_code": "jai_302_petrol_gj", "field_name": "Petrol Energy (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "GJ"}, "formula_code": "formula_jai_302_petrol_gj"},
            {"field_code": "jai_302_hfhsd_gj", "field_name": "HFHSD/IFO Energy (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "GJ"}, "formula_code": "formula_jai_302_hfhsd_gj"},
            {"field_code": "jai_302_other_gj", "field_name": "Other Fuels Energy (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "GJ"}, "formula_code": "formula_jai_302_other_gj"},
            {"field_code": "jai_302_total_energy_gj", "field_name": "Total Energy Consumption (GJ)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_FULL, "unit": "GJ"}, "formula_code": "formula_jai_302_total_energy_gj"},
            {"field_code": "jai_302_energy_intensity", "field_name": "Energy Intensity (000 GJ/Million MT)", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "GJ/MMT"}, "formula_code": "formula_jai_302_energy_intensity"},
            {"field_code": "jai_viz_energy_trend", "field_name": "Monthly Energy Inputs Trend", "field_type": "calculated", "section_code": "sec_302_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_LINE_ENERGY_TREND}, "formula_code": "formula_jai_302_elec_gj"},
            {"field_code": "jai_3051_scope1_total", "field_name": "Scope 1 Total (tCO2)", "field_type": "calculated", "section_code": "sec_3051_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "tCO2"}, "formula_code": "formula_jai_3051_scope1_total"},
            {"field_code": "jai_3051_intensity", "field_name": "Scope 1 GHG Intensity", "field_type": "calculated", "section_code": "sec_3051_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "tCO2/MMT"}, "formula_code": "formula_jai_3051_intensity"},
            {"field_code": "jai_viz_scope2_grid", "field_name": "Grid Electricity Scope 2 (tCO2)", "field_type": "calculated", "section_code": "sec_3052_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "tCO2e"}, "formula_code": "formula_jai_gri_ref_elec_grid_tco2"},
            {"field_code": "jai_viz_scope2_group", "field_name": "Group Electricity Scope 2 (tCO2)", "field_type": "calculated", "section_code": "sec_3052_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_THIRD, "unit": "tCO2e"}, "formula_code": "formula_jai_gri_ref_elec_group_tco2"},
            {"field_code": "jai_3052_scope2_total", "field_name": "Scope 2 Total (tCO2)", "field_type": "calculated", "section_code": "sec_3052_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "tCO2"}, "formula_code": "formula_jai_3052_scope2_total"},
            {"field_code": "jai_3052_intensity", "field_name": "Scope 2 GHG Intensity", "field_type": "calculated", "section_code": "sec_3052_results", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_KPI_HALF, "unit": "tCO2/MMT"}, "formula_code": "formula_jai_3052_intensity"},
            {"field_code": "jai_viz_scope_split", "field_name": "Scope 1 vs Scope 2 Emissions", "field_type": "calculated", "section_code": "sec_gri_overview", "frequency": "annual", "field_config": {**READONLY_SUMMARY_CONFIG, **VIZ_DONUT_SCOPE_SPLIT}, "formula_code": "formula_jai_3051_scope1_total"},
        ],
    },
]

# Excel cell mapping: field_code -> (sheet_name, column_letter, row_key)
# row_key is "3054" or "cargo" to select the correct month row list.
MONTHLY_EXCEL_MAP = {
    "jai_elec_grid_mwh": ("305-4", "C", "3054"),
    "jai_elec_group_mwh": ("305-4", "D", "3054"),
    "jai_diesel_stationary_kl": ("305-4", "H", "3054"),
    "jai_diesel_mobile_kl": ("305-4", "I", "3054"),
    "jai_petrol_kl": ("305-4", "M", "3054"),
    "jai_hfhsd_kl": ("305-4", "P", "3054"),
    "jai_ifo_converted_kl": ("305-4", "Q", "3054"),
    "jai_cargo_non_coastal_mt": ("Cargo Handled", "D", "cargo"),
    "jai_cargo_coastal_mt": ("Cargo Handled", "E", "cargo"),
}

MONTHLY_EXCEL_ROWS = {
    "3054": EXCEL_MONTH_ROWS_3054,
    "cargo": EXCEL_MONTH_ROWS_CARGO,
}

ANNUAL_EXCEL_VALUES = {
    **{code: ("305-4", cell) for code, cell in [
        ("jai_grid_ef", "C31"),
        ("jai_group_ef", "C32"),
    ]},
    **{code: ("305-4", cell) for code, cell in [
        ("jai_gwp_ch4", "V16"),
        ("jai_gwp_n2o", "V17"),
        ("jai_other_acetylene_qty", "U5"),
        ("jai_hfc_r32_qty", "U14"),
        ("jai_hfc_r32_gwp", "V14"),
        ("jai_hfc_410a_qty", "U15"),
        ("jai_hfc_410a_gwp", "V15"),
    ]},
}

ANNUAL_EXCEL_FORM_BY_FIELD = {
    **{code: "form_jai_electricity" for code in ANNUAL_EXCEL_VALUES_ELECTRICITY},
    **{code: "form_jai_fuel" for code in ANNUAL_EXCEL_VALUES_FUEL},
}

MONTHLY_FIELD_FORM_BY_CODE = {
    **{code: "form_jai_electricity" for code in ELECTRICITY_MONTHLY_FIELDS},
    **{code: "form_jai_fuel" for code in FUEL_MONTHLY_FIELDS},
    "jai_cargo_non_coastal_mt": "form_jai_cargo",
    "jai_cargo_coastal_mt": "form_jai_cargo",
}

VERIFICATION_CHECKS = [
    {"field_code": "jai_elec_grid_mwh", "aggregation": "sum_months", "excel_sheet": "305-4", "excel_cell": "C18", "tolerance": 0.1, "form_code": "form_jai_electricity"},
    {"field_code": "jai_elec_group_mwh", "aggregation": "sum_months", "excel_sheet": "305-4", "excel_cell": "D18", "tolerance": 0.1, "form_code": "form_jai_electricity"},
    {"field_code": "jai_ghg_total_tco2", "excel_sheet": "305-4", "excel_cell": "C21", "tolerance": 1.0, "form_code": "form_jai_fuel"},
    {"field_code": "jai_ghg_intensity", "excel_sheet": "305-4", "excel_cell": "C22", "tolerance": 0.01, "form_code": "form_jai_fuel"},
    {"field_code": "jai_cargo_fy_total_mt", "excel_sheet": "Cargo Handled", "excel_cell": "C16", "tolerance": 1.0, "form_code": "form_jai_cargo"},
    {"field_code": "jai_302_total_energy_gj", "excel_sheet": "302-1", "excel_cell": "C21", "tolerance": 1.0, "form_code": "form_jai_gri_summary"},
    {"field_code": "jai_3052_scope2_total", "excel_sheet": "305-2", "excel_cell": "C21", "tolerance": 1.0, "form_code": "form_jai_gri_summary"},
    {"field_code": "jai_3051_scope1_total", "excel_sheet": "305-1", "excel_cell": "C21", "tolerance": 1.0, "form_code": "form_jai_gri_summary"},
]

FORM_CODES = [form["code"] for form in FORM_DEFINITIONS]
FORMULA_CODES = list(FORMULA_DEFINITIONS.keys())


def formula_tokens(expression: str) -> dict:
    """Build token map from expression identifiers."""
    reserved = {"min", "max", "SUM_MONTHS"}
    names = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", expression or ""))
    names -= reserved
    return {name: "field" for name in sorted(names)}


def resolve_excel_path(path: str | None = None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(
        "/Users/shubhamindulkar/Downloads/GHG DI-1/FY25-26 GHG Final Sheets/Final Data_Jaigarh.xlsx"
    )
