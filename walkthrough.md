# Walkthrough — Jaigarh FY25-26 GHG & Energy Workbook Configurations

We have successfully seeded the new template workbook **Jaigarh FY25–26 GHG + Energy Workbook** (`wkbk_jaigarh_demo`), containing 9 distinct sheets and its associated **GHG Emission & Energy Constants** Value Set, while completely cleaning up all references to the previous Jaigarh workbook.

---

## 1. Value Set Configuration
A dedicated Value Set with code `GHG_CONSTANTS` was seeded with the following constants:

### Electricity Constants
* `grid_emission_factor`: `0.710` tCO2/MWh
* `other_source_emission_factor`: `0.710` tCO2/MWh
* `mwh_to_gj`: `3.6` GJ/MWh

### GWP Constants
* `r22_gwp`: `1960`
* `r32_gwp`: `771`
* `r410a_gwp`: `2256`
* `ch4_gwp`: `29.8`
* `n2o_gwp`: `273`

### Other Fuels & Fuel Constants
* `acetylene_ncv_gj_per_t`: `47.30` GJ/T
* `acetylene_emission_factor_tco2_per_t`: `3.38` tCO2/T
* `lpg_ncv_gj_per_t`: `47.30` GJ/T
* `lpg_emission_factor_tco2_per_t`: `2.985` tCO2/T
* `co2_fire_extinguisher_ef_tco2_per_t`: `1.0` tCO2/T
* `diesel_co2_ef`: `2.6898`, `diesel_ch4_ef`: `0.000108`, `diesel_n2o_ef`: `0.000022`, `diesel_energy_factor_gj_per_kl`: `36.12`
* `petrol_co2_ef`: `2.3372`, `petrol_ch4_ef`: `0.000099`, `petrol_n2o_ef`: `0.000020`, `petrol_energy_factor_gj_per_kl`: `32.88`
* `hfhsd_co2_ef`: `2.8311`, `hfhsd_ch4_ef`: `0.000109`, `hfhsd_n2o_ef`: `0.000022`, `hfhsd_energy_factor_gj_per_kl`: `36.40`
* `ifo_co2_ef`: `2.8311`, `ifo_ch4_ef`: `0.000109`, `ifo_n2o_ef`: `0.000022`, `ifo_energy_factor_gj_per_kl`: `36.40`

---

## 2. Configured Sheets & Fields

The workbook features 9 sheets, structured as follows:

### 1. Electricity Consumed (`form_jaigarh_electricity`)
* **Monthly Fields**:
  * `electricity_from_grid_mwh`: From Grid (MWh) [Input]
  * `electricity_other_source_mwh`: Other Source (MWh) [Input]
  * `electricity_total_mwh`: Total Electricity = `electricity_from_grid_mwh + electricity_other_source_mwh`
* **Aggregate Fields (Below Table)**:
  * `electricity_from_grid_total_mwh`: Total From Grid = `SUM_MONTHS(electricity_from_grid_mwh)`
  * `electricity_other_source_total_mwh`: Total Other Source = `SUM_MONTHS(electricity_other_source_mwh)`
  * `electricity_total_fy_mwh`: Total Electricity Consumed = `SUM_MONTHS(electricity_total_mwh)`
  * `electricity_from_grid_emission_tco2e`: GHG Emission From Grid = `electricity_from_grid_total_mwh * grid_emission_factor`
  * `electricity_other_source_emission_tco2e`: GHG Emission Other Source = `electricity_other_source_total_mwh * other_source_emission_factor`
  * `electricity_total_emission_tco2e`: Total Electricity GHG Emission = `electricity_from_grid_emission_tco2e + electricity_other_source_emission_tco2e`
  * `electricity_energy_consumption_gj`: Energy Consumption = `electricity_total_fy_mwh * mwh_to_gj`

### 2. Diesel Consumed (`form_jaigarh_diesel`)
* **Monthly Fields**:
  * `diesel_stationary_eqp_kl`: Stationary Eqp (KL) [Input]
  * `diesel_mobile_eqp_kl`: Mobile Eqp (KL) [Input]
  * `diesel_total_qty_kl`: Total Qty (KL) = `diesel_stationary_eqp_kl + diesel_mobile_eqp_kl`
* **Aggregate Fields (Below Table)**:
  * `diesel_stationary_total_kl`: Total Stationary Eqp = `SUM_MONTHS(diesel_stationary_eqp_kl)`
  * `diesel_mobile_total_kl`: Total Mobile Eqp = `SUM_MONTHS(diesel_mobile_eqp_kl)`
  * `diesel_total_fy_kl`: Total Diesel Qty = `SUM_MONTHS(diesel_total_qty_kl)`
  * `diesel_co2_emission_tco2e`: GHG Emission = `diesel_total_fy_kl * diesel_co2_ef`
  * `diesel_ch4_emission_tco2e`: Total Emissions CH4 = `diesel_total_fy_kl * diesel_ch4_ef * ch4_gwp`
  * `diesel_n2o_emission_tco2e`: Total Emissions N2O = `diesel_total_fy_kl * diesel_n2o_ef * n2o_gwp`
  * `diesel_total_emission_tco2e`: Total Diesel Emission = `diesel_co2_emission_tco2e + diesel_ch4_emission_tco2e + diesel_n2o_emission_tco2e`
  * `diesel_energy_consumption_gj`: Energy Consumption = `diesel_total_fy_kl * diesel_energy_factor_gj_per_kl`

### 3. Petrol Consumed (`form_jaigarh_petrol`)
* **Monthly Fields**:
  * `petrol_total_qty_kl`: Total Qty (KL) [Input]
* **Aggregate Fields (Below Table)**:
  * `petrol_total_fy_kl`: Total Petrol Qty = `SUM_MONTHS(petrol_total_qty_kl)`
  * `petrol_co2_emission_tco2e`: GHG Emission = `petrol_total_fy_kl * petrol_co2_ef`
  * `petrol_ch4_emission_tco2e`: Total Emissions CH4 = `petrol_total_fy_kl * petrol_ch4_ef * ch4_gwp`
  * `petrol_n2o_emission_tco2e`: Total Emissions N2O = `petrol_total_fy_kl * petrol_n2o_ef * n2o_gwp`
  * `petrol_total_emission_tco2e`: Total Petrol Emission = `petrol_co2_emission_tco2e + petrol_ch4_emission_tco2e + petrol_n2o_emission_tco2e`
  * `petrol_energy_consumption_gj`: Energy Consumption = `petrol_total_fy_kl * petrol_energy_factor_gj_per_kl`

### 4. HFHSD & IFO Consumed (`form_jaigarh_hfhsd_ifo`)
* **Monthly Fields**:
  * `hfhsd_qty_kl`: HFHSD Qty (KL) [Input]
  * `ifo_qty_kl`: IFO Qty (KL) [Input]
  * `hfhsd_ifo_total_qty_kl`: Total Qty = `hfhsd_qty_kl + ifo_qty_kl`
* **Aggregate Fields (Below Table)**:
  * `hfhsd_total_fy_kl`: Total HFHSD Qty = `SUM_MONTHS(hfhsd_qty_kl)`
  * `ifo_total_fy_kl`: Total IFO Qty = `SUM_MONTHS(ifo_qty_kl)`
  * `hfhsd_ifo_total_fy_kl`: Total HFHSD & IFO Qty = `SUM_MONTHS(hfhsd_ifo_total_qty_kl)`
  * `hfhsd_ifo_co2_emission_tco2e`: GHG Emission = `hfhsd_total_fy_kl * hfhsd_co2_ef + ifo_total_fy_kl * ifo_co2_ef`
  * `hfhsd_ifo_ch4_emission_tco2e`: Total Emissions CH4 = `(hfhsd_total_fy_kl * hfhsd_ch4_ef + ifo_total_fy_kl * ifo_ch4_ef) * ch4_gwp`
  * `hfhsd_ifo_n2o_emission_tco2e`: Total Emissions N2O = `(hfhsd_total_fy_kl * hfhsd_n2o_ef + ifo_total_fy_kl * ifo_n2o_ef) * n2o_gwp`
  * `hfhsd_ifo_total_emission_tco2e`: Total HFHSD & IFO Emission = `hfhsd_ifo_co2_emission_tco2e + hfhsd_ifo_ch4_emission_tco2e + hfhsd_ifo_n2o_emission_tco2e`
  * `hfhsd_energy_consumption_gj`: HFHSD Energy = `hfhsd_total_fy_kl * hfhsd_energy_factor_gj_per_kl`
  * `ifo_energy_consumption_gj`: IFO Energy = `ifo_total_fy_kl * ifo_energy_factor_gj_per_kl`
  * `hfhsd_ifo_energy_consumption_gj`: Total HFHSD & IFO Energy = `hfhsd_energy_consumption_gj + ifo_energy_consumption_gj`

### 5. Other Fuels - Emissions (`form_jaigarh_other_fuels_emissions`)
* **Monthly Fields**:
  * `acetylene_quantity_t`: Acetylene Quantity (T) [Input]
  * `acetylene_emission_tco2`: Acetylene tCO2 = `acetylene_quantity_t * acetylene_emission_factor_tco2_per_t`
  * `lpg_quantity_t`: LPG Quantity (T) [Input]
  * `lpg_emission_tco2`: LPG tCO2 = `lpg_quantity_t * lpg_emission_factor_tco2_per_t`
  * `co2_fire_extinguisher_quantity_t`: CO2 Fire Extinguisher Quantity (T) [Input]
  * `co2_fire_extinguisher_emission_tco2`: CO2 Fire Extinguisher tCO2 = `co2_fire_extinguisher_quantity_t * co2_fire_extinguisher_ef_tco2_per_t`
  * `hfcs_emission_tco2`: HFCs Emission = `refrigerants_total_emission_mth` (Cross-sheet mirror)
  * `other_fuels_total_emissions_tco2_mth`: Total Other Fuels Emissions Mth = sum of above acetylene, lpg, fire extinguisher, and hfcs emissions
* **Aggregate Fields (Below Table)**:
  * `other_fuels_total_emissions_tco2`: Total Other Fuels Emissions = `SUM_MONTHS(other_fuels_total_emissions_tco2_mth)`

### 6. Refrigerants / GWP (`form_jaigarh_refrigerants_gwp`)
* **Monthly Fields**:
  * `r22_quantity_kg`, `r32_quantity_kg`, `r410a_quantity_kg`, `ch4_quantity_kg`, `n2o_quantity_kg` [Inputs]
  * `r22_emission_tco2e`: R22 Emission = `r22_quantity_kg * r22_gwp / 1000`
  * `r32_emission_tco2e`: R32 Emission = `r32_quantity_kg * r32_gwp / 1000`
  * `r410a_emission_tco2e`: 410A Emission = `r410a_quantity_kg * r410a_gwp / 1000`
  * `ch4_refrigerant_emission_tco2e`: CH4 Emission = `ch4_quantity_kg * ch4_gwp / 1000`
  * `n2o_refrigerant_emission_tco2e`: N2O Emission = `n2o_quantity_kg * n2o_gwp / 1000`
  * `refrigerants_total_emission_mth`: Total Refrigerants/HFCs Emission Mth = sum of above refrigerant emissions
* **Aggregate Fields (Below Table)**:
  * `refrigerants_total_emission_tco2e`: Total Refrigerants / HFCs Emission = `SUM_MONTHS(refrigerants_total_emission_mth)`

### 7. GHG Summary (`form_jaigarh_ghg_summary`)
* **Monthly Fields**:
  * `summary_electricity_emissions_mth`: Electricity Emissions Mth = `electricity_from_grid_mwh * grid_emission_factor + electricity_other_source_mwh * other_source_emission_factor`
  * `summary_diesel_emissions_mth`: Diesel Emissions Mth = sum of CO2, CH4, N2O diesel emissions
  * `summary_petrol_emissions_mth`: Petrol Emissions Mth = sum of CO2, CH4, N2O petrol emissions
  * `summary_hfhsd_ifo_emissions_mth`: HFHSD & IFO Emissions Mth = sum of CO2, CH4, N2O HFHSD/IFO emissions (using mirror inputs)
  * `summary_other_fuels_emissions_mth`: Other Fuels Emissions Mth = `other_fuels_total_emissions_tco2_mth`
  * `summary_refrigerants_emissions_mth`: Refrigerants Emissions Mth = `refrigerants_total_emission_mth`
  * `summary_total_emissions_mth`: Total Emissions Mth = sum of all monthly source emissions
  * `cargo_throughput_million_mt`: Cargo / Throughput (Million MT) [Input]
  * `hfhsd_total_fy_kl_mirror`: HFHSD Qty (KL) Mirror = `hfhsd_qty_kl`
  * `ifo_total_fy_kl_mirror`: IFO Qty (KL) Mirror = `ifo_qty_kl`
* **Aggregate Fields (Below Table)**:
  * `summary_electricity_emissions_tco2e`: Electricity Emissions = `SUM_MONTHS(summary_electricity_emissions_mth)`
  * `summary_diesel_emissions_tco2e`: Diesel Emissions = `SUM_MONTHS(summary_diesel_emissions_mth)`
  * `summary_petrol_emissions_tco2e`: Petrol Emissions = `SUM_MONTHS(summary_petrol_emissions_mth)`
  * `summary_hfhsd_ifo_emissions_tco2e`: HFHSD & IFO Emissions = `SUM_MONTHS(summary_hfhsd_ifo_emissions_mth)`
  * `summary_other_fuels_emissions_tco2e`: Other Fuels Emissions = `SUM_MONTHS(summary_other_fuels_emissions_mth)`
  * `summary_refrigerants_emissions_tco2e`: Refrigerants / HFCs Emissions = `SUM_MONTHS(summary_refrigerants_emissions_mth)`
  * `total_emissions_tco2e`: Total Emissions = sum of all aggregate source emissions
  * `ghg_intensity_000_tco2e_per_million_mt`: GHG Intensity = `(total_emissions_tco2e / 1000) / SUM_MONTHS(cargo_throughput_million_mt)`

### 8. Energy Consumption Summary (`form_jaigarh_energy_summary`)
* **Monthly Fields**:
  * `summary_electricity_energy_gj_mth`: Electrical Energy Mth = `electricity_total_mwh * mwh_to_gj`
  * `summary_diesel_energy_gj_mth`: Diesel Energy Mth = `diesel_total_qty_kl * diesel_energy_factor_gj_per_kl`
  * `summary_petrol_energy_gj_mth`: Petrol Energy Mth = `petrol_total_qty_kl * petrol_energy_factor_gj_per_kl`
  * `summary_hfhsd_ifo_energy_gj_mth`: HFHSD & IFO Energy Mth = sum of HFHSD and IFO energy
  * `summary_other_fuels_energy_gj_mth`: Other Fuels Energy Mth = `other_fuels_energy_consumption_gj_mth`
  * `summary_fossil_fuel_energy_gj_mth`: Fossil Fuel Energy Mth = sum of diesel, petrol, HFHSD/IFO, and other fuels energy
  * `summary_total_energy_gj_mth`: Total Energy Mth = `summary_electricity_energy_gj_mth + summary_fossil_fuel_energy_gj_mth`
  * `energy_cargo_throughput_million_mt`: Cargo / Throughput (Million MT) [Input]
* **Aggregate Fields (Below Table)**:
  * `electrical_energy_consumption_gj`: Electrical Energy Consumption = `SUM_MONTHS(summary_electricity_energy_gj_mth)`
  * `summary_diesel_energy_gj`: Diesel Energy Consumption = `SUM_MONTHS(summary_diesel_energy_gj_mth)`
  * `summary_petrol_energy_gj`: Petrol Energy Consumption = `SUM_MONTHS(summary_petrol_energy_gj_mth)`
  * `summary_hfhsd_ifo_energy_gj`: HFHSD & IFO Energy Consumption = `SUM_MONTHS(summary_hfhsd_ifo_energy_gj_mth)`
  * `summary_other_fuels_energy_gj`: Other Fuels Energy Consumption = `SUM_MONTHS(summary_other_fuels_energy_gj_mth)`
  * `fossil_fuel_energy_consumption_gj`: Fossil Fuel Energy Consumption = sum of diesel, petrol, HFHSD/IFO, other fuels aggregate energy
  * `total_energy_consumption_gj`: Total Energy Consumption = `electrical_energy_consumption_gj + fossil_fuel_energy_consumption_gj`
  * `electrical_energy_intensity_kj_per_mt`: Electrical Energy Intensity = `electrical_energy_consumption_gj / SUM_MONTHS(energy_cargo_throughput_million_mt)`
  * `fossil_fuel_energy_intensity_kj_per_mt`: Fossil Fuel Energy Intensity = `fossil_fuel_energy_consumption_gj / SUM_MONTHS(energy_cargo_throughput_million_mt)`
  * `energy_intensity_000_gj_per_million_mt`: Total Energy Intensity = `(total_energy_consumption_gj / 1000) / SUM_MONTHS(energy_cargo_throughput_million_mt)`

### 9. Other Fuels - Energy (`form_jaigarh_other_fuels_energy`)
* **Monthly Fields**:
  * `acetylene_energy_quantity_t`: Acetylene Quantity (T) [Input]
  * `acetylene_energy_gj`: Acetylene Energy = `acetylene_energy_quantity_t * acetylene_ncv_gj_per_t`
  * `lpg_energy_quantity_t`: LPG Quantity (T) [Input]
  * `lpg_energy_gj`: LPG Energy = `lpg_energy_quantity_t * lpg_ncv_gj_per_t`
  * `other_fuels_energy_quantity_total_t`: Energy Consumption Quantity = `acetylene_energy_quantity_t + lpg_energy_quantity_t`
  * `other_fuels_energy_consumption_gj_mth`: Other Fuels Energy Consumption Mth = `acetylene_energy_gj + lpg_energy_gj`
* **Aggregate Fields (Below Table)**:
  * `other_fuels_energy_consumption_gj`: Other Fuels Energy Consumption = `SUM_MONTHS(other_fuels_energy_consumption_gj_mth)`

---

## 3. Mathematical Validation Results

The mathematical validation script [test_demo_calculations.py](file:///c:/Users/SHATAM%20RAI/Desktop/jsw/mywork/Digital-GHG-inventory/scratch/test_demo_calculations.py) was executed to test the calculations under mock inputs for April 2025. 

### A. Mock Inputs (April 2025)
* Grid Electricity = `100.0` MWh, Other Source = `200.0` MWh
* Diesel: Stationary = `10.0` KL, Mobile = `20.0` KL
* Petrol = `5.0` KL
* HFHSD = `50.0` KL, IFO = `50.0` KL
* Acetylene = `2.0` T, LPG = `1.5` T, CO2 Fire Ext. = `0.5` T
* R22 = `5.0` kg, R32 = `10.0` kg, 410A = `20.0` kg, CH4 = `1.0` kg, N2O = `2.0` kg
* Cargo Throughput = `10.0` Million MT

### B. Verified Outputs (April 2025 Monthly)
* Total Electricity = `300.0` MWh
* Total Diesel = `30.0` KL
* Total HFHSD & IFO = `100.0` KL
* Acetylene Emissions = `6.76` tCO2
* LPG Emissions = `4.4775` tCO2
* CO2 Fire Ext. Emissions = `0.5` tCO2
* Total Refrigerants/HFCs Emissions = `63.2058` tCO2e
* Total Other Fuels Emissions = `74.9433` tCO2e
* GHG Summary Monthly:
  * Electricity Emissions: `213.0` tCO2e
  * Diesel Emissions: `80.970732` tCO2e
  * Petrol Emissions: `11.728051` tCO2e
  * HFHSD & IFO Emissions: `284.03542` tCO2e
  * Other Fuels Emissions: `74.9433` tCO2e
  * Refrigerants Emissions: `63.2058` tCO2e
  * **Total Monthly Emissions**: `727.883303` tCO2e
* Energy Consumption Summary Monthly:
  * Electrical Energy: `1080.0` GJ
  * Diesel Energy: `1083.6` GJ
  * Petrol Energy: `164.4` GJ
  * HFHSD & IFO Energy: `3640.0` GJ
  * Other Fuels Energy: `165.55` GJ
  * Fossil Fuel Energy: `5053.55` GJ
  * **Total Monthly Energy**: `6133.55` GJ

### C. Verified Sheet-Level Aggregates (Sheet Results)
* **Electricity Consumed**:
  * Total Electricity Consumed: `300.0` MWh
  * GHG Emission From Grid: `71.0` tCO2e
  * GHG Emission Other Source: `142.0` tCO2e
  * Total Electricity GHG Emission: `213.0` tCO2e
  * Energy Consumption: `1080.0` GJ
* **Diesel Consumed**:
  * GHG Emission: `80.694` tCO2e
  * Total Emissions CH4: `0.096552` tCO2e
  * Total Emissions N2O: `0.18018` tCO2e
  * Total Diesel Emission: `80.970732` tCO2e
  * Energy Consumption: `1083.6` GJ
* **Petrol Consumed**:
  * Total Petrol Emission: `11.728051` tCO2e
  * Energy Consumption: `164.4` GJ
* **HFHSD & IFO Consumed**:
  * Total HFHSD & IFO Emission: `284.03542` tCO2e
  * Total HFHSD & IFO Energy: `3640.0` GJ
* **Other Fuels - Emissions**:
  * Total Other Fuels Emissions: `74.9433` tCO2
* **Refrigerants / GWP**:
  * Total Refrigerants / HFCs Emission: `63.2058` tCO2e
* **GHG Summary**:
  * Total Emissions: `727.883303` tCO2e
  * GHG Intensity: `0.0727883303` 000' tCO2e/Million MT
* **Energy Consumption Summary**:
  * Electrical Energy Consumption: `1080.0` GJ
  * Fossil Fuel Energy Consumption: `5053.55` GJ
  * Total Energy Consumption: `6133.55` GJ
  * Electrical Energy Intensity: `108.0` KJ/MT
  * Fossil Fuel Energy Intensity: `505.355` KJ/MT
  * Total Energy Intensity: `0.613355` 000' GJ/Million MT
* **Other Fuels - Energy**:
  * Other Fuels Energy Consumption: `165.55` GJ
