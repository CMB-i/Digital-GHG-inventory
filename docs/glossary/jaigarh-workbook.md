# Jaigarh workbook glossary

Terms used in the Jaigarh FY25-26 GHG workbook configuration and seed scripts.

| Term | Definition |
|------|------------|
| Scenario sheet | A workbook tab aligned to how site staff collect data (cargo, electricity, fuel) rather than GRI disclosure codes |
| GRI summary sheet | Read-only tab (`form_jai_gri_summary`) showing calculated GRI 302-1, 305-1, and 305-2 outputs |
| Emission factor (EF) | tCO2 per MWH conversion factor for grid or group electricity (`jai_grid_ef`, `jai_group_ef`) |
| GWP reference | Global warming potential values for CH4 and N2O used in fuel GHG formulas (`jai_gwp_ch4`, `jai_gwp_n2o`) |
| Other fuels | Annual acetylene and HFC refrigerant quantities tracked outside monthly KL consumption |
| Cross-sheet formula | A calculated field whose expression references fields on another form in the same workbook; resolved by `_build_workbook_formula_context` in `app/modules/SUBMIT/service.py` |
| Annual result field | A calculated field with `frequency: annual` and `field_scope: annual_result` shown in summary cards or annual tables |
| FY subtotal | Former inline annual sum fields (`jai_fy_*`) removed from entry sheets; totals appear on GRI summary or inline GHG result sections |

## Workbook forms

| Form code | Sheet label | Role |
|-----------|-------------|------|
| `form_jai_cargo` | Cargo Handled | Monthly cargo entry |
| `form_jai_electricity` | Electricity | Monthly electricity + EF + scope 2 results |
| `form_jai_fuel` | Fuel Consumption | Monthly fuel + GWP/other fuels + scope 1 results |
| `form_jai_gri_summary` | GRI Summary | Read-only GRI 302-1 / 305-1 / 305-2 totals |
