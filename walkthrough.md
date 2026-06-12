# Walkthrough — JSW Excel-Style Protected Theme & SPOC Sheets View Rebuild

This walkthrough summarizes the redesign and functionality rebuild of the SPOC Annual Workbook data-entry workspace (Phase 12B-3) and JSW "Excel opened in a browser, but protected" theme integration.

## Changes Made

### 1. Backend Service Updates

#### [service.py](file:///c:/Users/SHATAM%20RAI/Desktop/jsw/mywork/Digital-GHG-inventory/app/modules/SUBMIT/service.py)
* **Cross-Sheet Missing Warnings:** Added mapping of missing dependency codes to sheet names in `compose_calculation_results`. Missing dependencies now show specific warning messages: `"Cannot calculate yet — [Sheet Name] value is missing"`.
* **Form ID Serialization:** Included `form_id` in serialized calculated fields list to let the frontend group and render calculated results by their parent sheet tab.
* **Row Active Period Resolution:** Added `is_active_period` key to serialized rows in both `compose_annual_workbook_data` and `compose_calculation_results` to correctly highlight open month rows on the frontend.

### 2. Frontend Layout & Logic Updates

#### [annual_workbook.html](file:///c:/Users/SHATAM%20RAI/Desktop/jsw/mywork/Digital-GHG-inventory/templates/modules/SUBMIT/annual_workbook.html)
* **Rebuilt Layout:** Redesigned sheet container with horizontal scrolling support, inline Remarks column, and removed references to old buttons like "Submit selected month package".
* **Calculated Results Section:** Added calculated results table structure styled with a dark header (`CALCULATED RESULTS`) and a lock icon subtitle.
* **Fixed Footer Bar:** Added a sticky bottom action bar displaying autosave status on the left and primary buttons (Save draft, Submit [Sheet Name]) on the right.
* **Hidden File Uploader:** Added programmatic uploader trigger for sheet proof attachments.

#### [annual_workbook.js](file:///c:/Users/SHATAM%20RAI/Desktop/jsw/mywork/Digital-GHG-inventory/static/js/annual_workbook.js)
* **Status Dot Tabs:** Dynamically computes and displays colored status dots on sheet tabs based on the dashboard sheet status:
  - **Red:** Sent back
  - **Amber:** Draft
  - **Green:** Submitted
  - **Grey:** Not started
* **Debounced Autosave:** Edits are automatically autosaved 2 seconds after the user stops typing. The footer displays `Saving...` which updates to `Last saved X min ago` or `Last saved just now`.
* **Submit Validation:** The Submit button dynamically updates to match the current sheet's name. It validates required fields in real-time, showing a list of missing fields in a tooltip if any required fields are left blank.
* **Sent Back Scroll Nudge:** Added a pulse-animated red `Needs Correction` badge next to the title if any month is sent back. Clicking it scrolls to and highlights the target row.
* **Calculated Results Integration:** Automatically renders calculated cells in a dedicated section below the main table, displaying specific missing dependency warnings.

#### [workbook_sheet.js](file:///c:/Users/SHATAM%20RAI/Desktop/jsw/mywork/Digital-GHG-inventory/static/js/workbook_sheet.js)
* **Spreadsheet Grid:** Rebuilt table layout (April at top, March at bottom) with data point names as column headers and units in small grey text below.
* **Row Zebra Tints:** Highlights active period rows in light blue (`#dfeaf8`) and greys out approved/locked rows (`#eef3fa`), rendering them as flat plain text values rather than disabled input elements.
* **Remarks & Proof:** Renders `✓ Proof  Replace` if a document proof exists in the remarks column, or an upload button if it doesn't.
* **Real-time MoM Alerts:** Calculates month-over-month numeric increases in real-time. If a value exceeds the previous month's value by >20%, it expands an amber warning alert directly below that month row.

---

## Verification Results

### 1. Code Health & Syntax
* Syntax and compilation check run and passed: `python -m compileall app scripts`.
* JavaScript syntax check run and passed: `node --check static/js/workbook_sheet.js static/js/annual_workbook.js`.
* Alembic database schema check passed: `.venv/Scripts/alembic.exe heads`.
* Database seeded successfully via `seed.py`.

### 2. Manual Verification Checklist
1. Tab status dots rendered correctly based on workbook state.
2. The grid correctly listed months from April to March.
3. Active rows are clearly highlighted in light blue.
4. MoM validation logic dynamically displayed warning alerts for >20% increases.
5. Calculated results table correctly rendered below the monthly inputs.
6. Auto-saves and button tooltips operated seamlessly as expected.
