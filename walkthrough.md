# Walkthrough — Jaigarh Energy & GHG Workbook Aggregate Configurations

We have successfully refined the configuration of the **Jaigarh Energy & GHG Workbook** (`wkbk_jaigarh`) to support the separation of monthly calculated table columns and below-table annual aggregate results (Sheet/FY results).

## Workbook Layout & Placements

Calculated fields have been split according to their logical context:
* **Monthly Calculated Columns** (Per-month table cells): Calculated row-by-row in the table grid.
* **Annual Aggregate Fields** (Sheet/FY result below table): Displayed as read-only aggregate summary cards below the table.

### Configured Sheets, Fields and Placements

1. **Electricity Consumed** (`form_jaigarh_electricity`)
   * **Monthly Columns**:
     * `elec_grid_mwh`: From Grid (MWH) [Input]
     * `elec_group_sourcing_mwh`: Group Co Sourcing (MWH) [Input]
     * `elec_total_mwh`: Total Electricity (MWH) = `elec_grid_mwh + elec_group_sourcing_mwh`
     * `elec_grid_emissions`: Grid Electricity Emissions (tCO2e) = `elec_grid_mwh * 0.71`
     * `elec_group_sourcing_emissions`: Group Co Sourcing Emissions (tCO2e) = `elec_group_sourcing_mwh * 0.71`
     * `elec_total_emissions`: Total Electricity Emissions (tCO2e) = `elec_grid_emissions + elec_group_sourcing_emissions`
     * `elec_energy_gj`: Electrical Energy Consumption (GJ) = `elec_total_mwh * 3.6`
   * **Aggregate Cards Below Table**:
     * `elec_grid_emissions_ann`: Total Grid Electricity Emissions (tCO2e) = `SUM_MONTHS(elec_grid_emissions)`
     * `elec_group_sourcing_emissions_ann`: Total Group Co Sourcing Emissions (tCO2e) = `SUM_MONTHS(elec_group_sourcing_emissions)`
     * `elec_total_emissions_ann`: Total Electricity Emissions (tCO2e) = `elec_grid_emissions_ann + elec_group_sourcing_emissions_ann`
     * `elec_energy_gj_ann`: Total Electrical Energy Consumption (GJ) = `SUM_MONTHS(elec_energy_gj)`

2. **Diesel Consumed** (`form_jaigarh_diesel`)
   * **Monthly Columns**:
     * `diesel_stationary_kl`: Stationary Eqp (KL) [Input]
     * `diesel_mobile_kl`: Mobile Eqp (KL) [Input]
     * `diesel_total_kl`: Total Diesel Qty (KL) = `diesel_stationary_kl + diesel_mobile_kl`
     * `diesel_stationary_emissions`: Stationary Diesel Emissions (tCO2e) = `diesel_stationary_kl * 2.6898`
     * `diesel_mobile_emissions`: Mobile Diesel Emissions (tCO2e) = `diesel_mobile_kl * 2.6932`
     * `diesel_total_emissions`: Total Diesel Emissions (tCO2e) = `diesel_stationary_emissions + diesel_mobile_emissions`
     * `diesel_energy_gj`: Diesel Energy (GJ) = `diesel_total_kl * 36.12`
   * **Aggregate Cards Below Table**:
     * `diesel_stationary_emissions_ann`: Total Stationary Diesel Emissions (tCO2e) = `SUM_MONTHS(diesel_stationary_emissions)`
     * `diesel_mobile_emissions_ann`: Total Mobile Diesel Emissions (tCO2e) = `SUM_MONTHS(diesel_mobile_emissions)`
     * `diesel_total_emissions_ann`: Total Diesel Emissions (tCO2e) = `diesel_stationary_emissions_ann + diesel_mobile_emissions_ann`
     * `diesel_energy_gj_ann`: Total Diesel Energy (GJ) = `SUM_MONTHS(diesel_energy_gj)`

3. **Petrol Consumed** (`form_jaigarh_petrol`)
   * **Monthly Columns**:
     * `petrol_qty_kl`: Total Qty (KL) [Input]
     * `petrol_emissions`: Total Petrol Emissions (tCO2e) = `petrol_qty_kl * 2.3372`
     * `petrol_energy_gj`: Petrol Energy (GJ) = `petrol_qty_kl * 32.88`
   * **Aggregate Cards Below Table**:
     * `petrol_emissions_ann`: Total Petrol Emissions (tCO2e) = `SUM_MONTHS(petrol_emissions)`
     * `petrol_energy_gj_ann`: Total Petrol Energy (GJ) = `SUM_MONTHS(petrol_energy_gj)`

4. **HFHSD & IFO Consumed** (`form_jaigarh_hfhsd_ifo`)
   * **Monthly Columns**:
     * `hfhsd_qty_kl`: HFHSD Qty (KL) [Input]
     * `ifo_qty_kl`: IFO Qty (KL) [Input]
     * `hfhsd_ifo_total_kl`: Total Qty (KL) = `hfhsd_qty_kl + ifo_qty_kl`
     * `hfhsd_ifo_emissions`: Total HFHSD & IFO Emissions (tCO2e) = `hfhsd_ifo_total_kl * 2.8311`
     * `hfhsd_ifo_energy_gj`: HFHSD & IFO Energy (GJ) = `hfhsd_ifo_total_kl * 36.40`
   * **Aggregate Cards Below Table**:
     * `hfhsd_ifo_emissions_ann`: Total HFHSD & IFO Emissions (tCO2e) = `SUM_MONTHS(hfhsd_ifo_emissions)`
     * `hfhsd_ifo_energy_gj_ann`: Total HFHSD & IFO Energy (GJ) = `SUM_MONTHS(hfhsd_ifo_energy_gj)`

5. **Other Fuels & Refrigerants** (`form_jaigarh_other_fuels`)
   * **Monthly Columns**:
     * `acetylene_qty_t`, `lpg_qty_t`, `co2_fire_ext_qty_t` [Inputs]
     * `r32_qty_kg`, `r410a_qty_kg`, `r22_qty_kg` [Inputs]
     * `other_fuels_emissions`: Other Fuels & Refrigerants Emissions (tCO2e) = `acetylene_qty_t * 4.2283 + lpg_qty_t * 2.985 + co2_fire_ext_qty_t * 1.0 + r32_qty_kg * 0.771 + r410a_qty_kg * 2.255`
     * `other_fuels_energy_gj`: Other Fuels Energy (GJ) = `acetylene_qty_t * 59.16 + lpg_qty_t * 47.3`
   * **Aggregate Cards Below Table**:
     * `other_fuels_emissions_ann`: Total Other Fuels & Refrigerants Emissions (tCO2e) = `SUM_MONTHS(other_fuels_emissions)`
     * `other_fuels_energy_gj_ann`: Total Other Fuels Energy (GJ) = `SUM_MONTHS(other_fuels_energy_gj)`

6. **Energy & GHG Summary** (`form_jaigarh_summary`)
   * **Monthly Columns**:
     * `production_million_mt`: Production (Million MT) [Input]
     * `summary_scope1_emissions`: Scope 1 Emissions (tCO2e) = `diesel_total_emissions + petrol_emissions + hfhsd_ifo_emissions + other_fuels_emissions` (resolves cross-sheet dependencies on monthly values)
     * `summary_scope2_emissions`: Scope 2 Emissions (tCO2e) = `elec_total_emissions`
     * `summary_ghg_emissions`: Total GHG Emissions (tCO2e) = `summary_scope1_emissions + summary_scope2_emissions`
     * `summary_energy_gj`: Total Energy Consumption (GJ) = `elec_energy_gj + diesel_energy_gj + petrol_energy_gj + hfhsd_ifo_energy_gj + other_fuels_energy_gj`
     * `summary_energy_intensity`: Energy Intensity (GJ/Million MT) = `summary_energy_gj / production_million_mt`
     * `summary_ghg_intensity`: GHG Intensity (tCO2e/Million MT) = `summary_ghg_emissions / production_million_mt`
   * **Aggregate Cards Below Table**:
     * `total_scope1_emissions`: Total Scope 1 (Direct) Emissions (tCO2e) = `SUM_MONTHS(summary_scope1_emissions)`
     * `total_scope2_emissions`: Total Scope 2 (Indirect) Emissions (tCO2e) = `SUM_MONTHS(summary_scope2_emissions)`
     * `total_ghg_emissions`: Total GHG Emissions (tCO2e) = `total_scope1_emissions + total_scope2_emissions`
     * `total_energy_gj`: Total Energy Consumption (GJ) = `SUM_MONTHS(summary_energy_gj)`
     * `energy_intensity`: Energy Intensity (GJ/Million MT) = `total_energy_gj / SUM_MONTHS(production_million_mt)`
     * `ghg_intensity`: GHG Intensity (tCO2e/Million MT) = `total_ghg_emissions / SUM_MONTHS(production_million_mt)`

---

## Verification & Validation Results

We verified that the monthly columns calculate correctly across sheets, and the annual summary aggregates evaluate perfectly at the sheet level.

### Test Inputs (April 2025)
* Grid Electricity = `100.0` MWH, Sourcing = `200.0` MWH
* Diesel (Stationary) = `10.0` KL, Diesel (Mobile) = `20.0` KL
* Petrol = `5.0` KL
* HFHSD = `50.0` KL, IFO = `50.0` KL
* Acetylene = `2.0` T, LPG = `0.0` T, CO2 = `0.0` T
* R32 = `10.0` kg, R410A = `20.0` kg, R22 = `0.0` kg
* Production = `10.0` Million MT

### Monthly Calculation Results (April 2025)
* `diesel_total_kl` = `30.0`
* `elec_total_mwh` = `300.0`
* `hfhsd_ifo_total_kl` = `100.0`
* `summary_scope1_emissions` = `436.8246`
* `summary_scope2_emissions` = `213.0`
* `summary_ghg_emissions` = `649.8246`
* `summary_energy_gj` = `6086.32`
* `summary_energy_intensity` = `608.632`
* `summary_ghg_intensity` = `64.98246`

### Sheet-Level Aggregate Results (Below-Table Summary Cards)
* **Electricity Consumed**:
  * Total Grid Emissions: `71.0` tCO2e
  * Total Sourcing Emissions: `142.0` tCO2e
  * Total Electricity Emissions: `213.0` tCO2e
  * Total Electrical Energy: `1080.0` GJ
* **Diesel Consumed**:
  * Total Stationary Emissions: `26.898` tCO2e
  * Total Mobile Emissions: `53.864` tCO2e
  * Total Diesel Emissions: `80.762` tCO2e
  * Total Diesel Energy: `1083.6` GJ
* **Petrol Consumed**:
  * Total Petrol Emissions: `11.686` tCO2e
  * Total Petrol Energy: `164.4` GJ
* **HFHSD & IFO Consumed**:
  * Total HFHSD & IFO Emissions: `283.11` tCO2e
  * Total HFHSD & IFO Energy: `3640.0` GJ
* **Other Fuels & Refrigerants**:
  * Total Other Fuels & Refrigerants Emissions: `61.2666` tCO2e
  * Total Other Fuels Energy: `118.32` GJ
* **Energy & GHG Summary**:
  * Total Scope 1 (Direct) Emissions: `436.8246` tCO2e
  * Total Scope 2 (Indirect) Emissions: `213.0` tCO2e
  * Total GHG Emissions: `649.8246` tCO2e
  * Total Energy Consumption: `6086.32` GJ
  * Energy Intensity: `608.632` GJ/Million MT
  * GHG Intensity: `64.98246` tCO2e/Million MT
