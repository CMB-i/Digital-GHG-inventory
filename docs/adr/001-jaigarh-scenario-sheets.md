# ADR 001: Jaigarh scenario-based workbook sheets

## Status

Accepted

## Context

The Jaigarh FY25-26 GHG workbook was initially seeded with five tabs that mirror the source Excel file: `Cargo Handled`, `302-1`, `305-1`, `305-2`, and `305-4`. Users enter data only on **Cargo Handled** and **305-4**; the GRI tabs (`302-1`, `305-1`, `305-2`) display read-only monthly mirrors and annual calculated totals. This structure optimizes for Excel export alignment, not for how site staff collect data.

Site staff think in operational scenarios: cargo throughput, electricity consumption, and fuel consumption. The redundant mirror fields and FY subtotals on entry sheets add noise without improving data quality.

## Decision

Restructure the Jaigarh workbook into **four tabs**:

1. **Cargo Handled** — monthly cargo inputs (unchanged)
2. **Electricity** — grid/group MWH, emission factors, scope 2 GHG results
3. **Fuel Consumption** — diesel, petrol, HFHSD/IFO monthly inputs; GWP and other-fuel references; scope 1 GHG results
4. **GRI Summary** — read-only calculated outputs for GRI 302-1, 305-1, and 305-2

Field codes and formula expressions are preserved. Only form placement and form codes change. Excel cell mappings continue to reference the original `305-4` sheet cells.

## Consequences

### Positive

- Simpler data-entry UX aligned with how site staff work
- Eliminates 24 redundant monthly mirror fields across three GRI tabs
- Removes seven FY inline subtotals from entry sheets
- GRI reporting totals remain available on a dedicated summary tab for auditors

### Negative

- Bookmarks to old tab names (`302-1`, `305-4`) break after re-seed
- Re-seed creates new workbook/site IDs (existing Jaigarh pilot behavior)
- Pattern is Jaigarh-specific until generalized for other ports

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| 3 tabs only (no GRI summary) | Auditors need GRI-labeled totals without hunting across entry sheets |
| Keep 5 Excel-mirror tabs | Perpetuates redundant mirrors and confusing entry flow |
| Separate reference tab for EF/GWP | Adds a fifth tab; factors belong on the sheets they apply to |
