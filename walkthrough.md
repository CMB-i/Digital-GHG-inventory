# Walkthrough — Jaigarh Energy & GHG Workbook Conversion

We have successfully converted the **Jaigarh Energy & GHG** excel sheets into a fully configured, functional workbook in the application.

## Workbook Overview

A new workbook template **Jaigarh Energy & GHG Workbook** (`wkbk_jaigarh`) has been defined with **6 form sheets**, capturing all fuel usages, refrigerant emissions, energy conversions, and final GHG scopes/intensities.

### Configured Sheets and Fields

1. **Electricity Consumed** (`form_jaigarh_electricity`)
   * **From Grid (MWH)** (`elec_grid_mwh`): Input field
   * **Group Co Sourcing (MWH)** (`elec_group_sourcing_mwh`): Input field
   * **Total Electricity (MWH)** (`elec_total_mwh`): `elec_grid_mwh + elec_group_sourcing_mwh`
   * **Grid Electricity Emissions (tCO2e)** (`elec_grid_emissions`): `elec_grid_mwh * 0.71`
   * **Group Co Sourcing Emissions (tCO2e)** (`elec_group_sourcing_emissions`): `elec_group_sourcing_mwh * 0.71`
   * **Total Electricity Emissions (tCO2e)** (`elec_total_emissions`): `elec_grid_emissions + elec_group_sourcing_emissions`
   * **Electrical Energy Consumption (GJ)** (`elec_energy_gj`): `elec_total_mwh * 3.6`

2. **Diesel Consumed** (`form_jaigarh_diesel`)
   * **Stationary Eqp (KL)** (`diesel_stationary_kl`): Input field
   * **Mobile Eqp (KL)** (`diesel_mobile_kl`): Input field
   * **Total Diesel Qty (KL)** (`diesel_total_kl`): `diesel_stationary_kl + diesel_mobile_kl`
   * **Stationary Diesel Emissions (tCO2e)** (`diesel_stationary_emissions`): `diesel_stationary_kl * 2.6898`
   * **Mobile Diesel Emissions (tCO2e)** (`diesel_mobile_emissions`): `diesel_mobile_kl * 2.6932`
   * **Total Diesel Emissions (tCO2e)** (`diesel_total_emissions`): `diesel_stationary_emissions + diesel_mobile_emissions`
   * **Diesel Energy (GJ)** (`diesel_energy_gj`): `diesel_total_kl * 36.12`

3. **Petrol Consumed** (`form_jaigarh_petrol`)
   * **Total Qty (KL)** (`petrol_qty_kl`): Input field
   * **Total Petrol Emissions (tCO2e)** (`petrol_emissions`): `petrol_qty_kl * 2.3372`
   * **Petrol Energy (GJ)** (`petrol_energy_gj`): `petrol_qty_kl * 32.88`

4. **HFHSD & IFO Consumed** (`form_jaigarh_hfhsd_ifo`)
   * **HFHSD Qty (KL)** (`hfhsd_qty_kl`): Input field
   * **IFO Qty (KL)** (`ifo_qty_kl`): Input field
   * **Total Qty (KL)** (`hfhsd_ifo_total_kl`): `hfhsd_qty_kl + ifo_qty_kl`
   * **Total HFHSD & IFO Emissions (tCO2e)** (`hfhsd_ifo_emissions`): `hfhsd_ifo_total_kl * 2.8311`
   * **HFHSD & IFO Energy (GJ)** (`hfhsd_ifo_energy_gj`): `hfhsd_ifo_total_kl * 36.40`

5. **Other Fuels & Refrigerants** (`form_jaigarh_other_fuels`)
   * **Acetylene Qty (T)** (`acetylene_qty_t`): Input field
   * **LPG Qty (T)** (`lpg_qty_t`): Input field
   * **CO2 Fire Ext Qty (T)** (`co2_fire_ext_qty_t`): Input field
   * **R32 Qty (Kg)** (`r32_qty_kg`): Input field
   * **R410A Qty (Kg)** (`r410a_qty_kg`): Input field
   * **R22 Qty (Kg)** (`r22_qty_kg`): Input field
   * **Other Fuels & Refrigerants Emissions (tCO2e)** (`other_fuels_emissions`): `acetylene_qty_t * 4.2283 + lpg_qty_t * 2.985 + co2_fire_ext_qty_t * 1.0 + r32_qty_kg * 0.771 + r410a_qty_kg * 2.255`
   * **Other Fuels Energy (GJ)** (`other_fuels_energy_gj`): `acetylene_qty_t * 59.16 + lpg_qty_t * 47.3`

6. **Energy & GHG Summary** (`form_jaigarh_summary`)
   * **Production (Million MT)** (`production_million_mt`): Input field
   * **Total Scope 1 (Direct) Emissions (tCO2e)** (`total_scope1_emissions`): `diesel_total_emissions + petrol_emissions + hfhsd_ifo_emissions + other_fuels_emissions`
   * **Total Scope 2 (Indirect) Emissions (tCO2e)** (`total_scope2_emissions`): `elec_total_emissions`
   * **Total GHG Emissions (tCO2e)** (`total_ghg_emissions`): `total_scope1_emissions + total_scope2_emissions`
   * **Total Energy Consumption (GJ)** (`total_energy_gj`): `elec_energy_gj + diesel_energy_gj + petrol_energy_gj + hfhsd_ifo_energy_gj + other_fuels_energy_gj`
   * **Energy Intensity (GJ/Million MT)** (`energy_intensity`): `total_energy_gj / production_million_mt`
   * **GHG Intensity (tCO2e/Million MT)** (`ghg_intensity`): `total_ghg_emissions / production_million_mt`

---

## Verification & Validation Results

We executed the test verification script `scratch/test_jaigarh_calculations.py` to assert the correctness of all formula configurations.

### Test Inputs (April 2025)
* Grid Electricity = `100.0` MWH
* Group Sourcing Electricity = `200.0` MWH
* Diesel (Stationary) = `10.0` KL
* Diesel (Mobile) = `20.0` KL
* Petrol = `5.0` KL
* HFHSD = `50.0` KL, IFO = `50.0` KL
* Acetylene = `2.0` T, LPG = `0.0` T, CO2 Fire Ext = `0.0` T
* R32 = `10.0` kg, R410A = `20.0` kg, R22 = `0.0` kg
* Production = `10.0` Million MT

### Evaluated Outputs
The script yielded the following results, matching the spreadsheet calculations exactly:

```text
Total Diesel Qty (KL)                         | diesel_total_kl                = 30.0
Stationary Diesel Emissions (tCO2e)           | diesel_stationary_emissions    = 26.898
Mobile Diesel Emissions (tCO2e)               | diesel_mobile_emissions        = 53.864
Total Diesel Emissions (tCO2e)                | diesel_total_emissions         = 80.762
Diesel Energy (GJ)                            | diesel_energy_gj               = 1083.6
Total Electricity (MWH)                       | elec_total_mwh                 = 300.0
Grid Electricity Emissions (tCO2e)            | elec_grid_emissions            = 71.0
Group Co Sourcing Emissions (tCO2e)           | elec_group_sourcing_emissions  = 142.0
Total Electricity Emissions (tCO2e)           | elec_total_emissions           = 213.0
Electrical Energy Consumption (GJ)            | elec_energy_gj                 = 1080.0
Total Scope 1 (Direct) Emissions (tCO2e)      | total_scope1_emissions         = 436.8246
Total Scope 2 (Indirect) Emissions (tCO2e)    | total_scope2_emissions         = 213.0
Total GHG Emissions (tCO2e)                   | total_ghg_emissions            = 649.8246
Total Energy Consumption (GJ)                 | total_energy_gj                = 6086.32
Energy Intensity (GJ/Million MT)              | energy_intensity               = 608.632
GHG Intensity (tCO2e/Million MT)              | ghg_intensity                  = 64.98246
Total Qty (KL)                                | hfhsd_ifo_total_kl             = 100.0
Total HFHSD & IFO Emissions (tCO2e)           | hfhsd_ifo_emissions            = 283.11
HFHSD & IFO Energy (GJ)                       | hfhsd_ifo_energy_gj            = 3640.0
Other Fuels & Refrigerants Emissions (tCO2e)  | other_fuels_emissions          = 61.2666
Other Fuels Energy (GJ)                       | other_fuels_energy_gj          = 118.32
Total Petrol Emissions (tCO2e)                | petrol_emissions               = 11.686
Petrol Energy (GJ)                            | petrol_energy_gj               = 164.4
```

All 23 cross-sheet formulas evaluate successfully using the multi-pass calculation engine.
