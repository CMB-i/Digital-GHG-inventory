"use strict";
/**
 * Regression check for the annual-only-sheet blank render bug: a sheet with
 * zero monthly-frequency fields but one or more annual ("Sheet/FY result
 * below table") fields must not hit the "No fields configured" empty state.
 *
 * static/js/annual_workbook.js's renderTable() (the actual fix site) lives
 * entirely inside an unexported `document.addEventListener("DOMContentLoaded",
 * ...)` closure -- same constraint noted in tests/js/test_autosave_merge.js
 * ("this project has no JS test runner") -- so it can't be loaded and
 * invoked directly from a plain Node script the way an exported function
 * can. What IS exported and directly testable is the piece the fix actually
 * depends on to make annual-only results visible:
 * window.WorkbookSheet.renderSheetResultsOverflowHtml(sheetResults, { showAll }),
 * defined in static/js/workbook_sheet.js. This script exercises that
 * function, then documents a manual trace of renderTable() itself (see the
 * comment block below) covering the three scenarios from the bug report.
 *
 * Run with: node tests/js/test_annual_workbook_render.js
 *
 * ---------------------------------------------------------------------
 * Manual trace of static/js/annual_workbook.js renderTable() (as fixed):
 *
 * 1) 0 monthly fields + 2 annual fields (the bug case):
 *    fields = [], sheetResults = [r1, r2] (from state.workbook.sheet_results)
 *    -> hasMonthlyFields = false
 *    -> `!hasMonthlyFields && !sheetResults.length` is `true && false` = false,
 *       so the "No fields configured" empty state is skipped (emptyEl stays
 *       hidden, set on the line right after the guard).
 *    -> hasMonthlyFields is false, so window.WorkbookSheet.render(...) is
 *       NOT called and tableWrap is hidden (no monthly table to show).
 *    -> renderSheetResultsOverflow(sheetResults, { showAll: true }) is
 *       called, which (per the checks below) returns non-empty HTML built
 *       from every entry in sheetResults, and un-hides sheetResultsSection.
 *    Result: annual results section renders, no empty-state message.
 *
 * 2) 0 monthly fields + 0 annual fields (genuinely empty form):
 *    fields = [], sheetResults = []
 *    -> hasMonthlyFields = false
 *    -> `!hasMonthlyFields && !sheetResults.length` is `true && true` = true
 *       -> setEmpty(...) runs, "No fields configured" shows, function returns.
 *    Result: empty state still shows correctly (unchanged from before the fix).
 *
 * 3) N monthly fields only (today's common case), sheetResults = [] or not:
 *    fields = [f1, ...], hasMonthlyFields = true
 *    -> guard is false (hasMonthlyFields is true) regardless of sheetResults
 *       -> proceeds past the empty-state check exactly as before the fix.
 *    -> hasMonthlyFields is true, so tableWrap is shown and
 *       window.WorkbookSheet.render(...) runs exactly as before the fix
 *       (identical arguments, identical code path).
 *    -> renderSheetResultsOverflow(sheetResults, { showAll: false }) is
 *       called -- showAll defaults to falsy, so behavior is byte-for-byte
 *       identical to the pre-fix call `renderSheetResultsOverflow(sheetResults)`.
 *    Result: unaffected by the fix, monthly table renders as before.
 * ---------------------------------------------------------------------
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const uiHelpersSrc = fs.readFileSync(
  path.join(__dirname, "..", "..", "static", "js", "ui_helpers.js"),
  "utf8"
);
const workbookSheetSrc = fs.readFileSync(
  path.join(__dirname, "..", "..", "static", "js", "workbook_sheet.js"),
  "utf8"
);

// Same realm-sharing rationale as test_autosave_merge.js: no
// vm.createContext(), so window.WorkbookSheet ends up on this process's
// global `window`, in the same realm as the arrays/objects below.
global.window = global.window || {};
global.document = global.document || { getElementById: () => null };
vm.runInThisContext(uiHelpersSrc, { filename: "ui_helpers.js" });
vm.runInThisContext(workbookSheetSrc, { filename: "workbook_sheet.js" });
const { renderSheetResultsOverflowHtml, splitSheetResults } = global.window.WorkbookSheet;

let passed = 0;
function check(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`FAIL - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

// Two "Sheet/FY result below table" results, as SUBMIT/service.py's
// _compose_sheet_results() would build them for an annual-only sheet.
const annualSheetResults = [
  {
    field_id: 1,
    field_code: "total_scope1",
    label: "Total Scope 1",
    value: 123.456,
    unit: "tCO2e",
    status: "calculated",
    message: "",
    source_field_codes: ["diesel", "petrol"],
    display_region: "below_monthly_table",
  },
  {
    field_id: 2,
    field_code: "total_scope2",
    label: "Total Scope 2",
    value: 42,
    unit: "tCO2e",
    status: "partial",
    message: "7 of 12 months entered.",
    months_entered: 7,
    months_total: 12,
    source_field_codes: ["electricity"],
    display_region: "below_monthly_table",
  },
];

check("splitSheetResults keeps everything in footerResults (in-table footer is still the default path)", () => {
  const { footerResults, overflowResults } = splitSheetResults(annualSheetResults);
  assert.deepStrictEqual(footerResults, annualSheetResults);
  assert.deepStrictEqual(overflowResults, []);
});

check("showAll: true renders every annual result, even though none of them are ever in the overflow bucket", () => {
  const html = renderSheetResultsOverflowHtml(annualSheetResults, { showAll: true });
  assert.notStrictEqual(html, "", "must produce visible markup for an annual-only sheet");
  assert.ok(html.includes("Total Scope 1"), "first result label present");
  assert.ok(html.includes("Total Scope 2"), "second result label present");
  assert.ok(html.includes("123.456"), "calculated value rendered");
});

check("showAll: true with zero results still renders nothing (the true empty-state case)", () => {
  const html = renderSheetResultsOverflowHtml([], { showAll: true });
  assert.strictEqual(html, "");
});

check("without showAll (existing callers: form_builder.js, workbooks.js preview), behavior is unchanged and stays empty", () => {
  const html = renderSheetResultsOverflowHtml(annualSheetResults);
  assert.strictEqual(html, "", "monthly-table callers still rely on the in-table footer row, not this section");
});

console.log(`\n${passed} passed`);
if (process.exitCode) {
  console.error("FAILURES ABOVE");
} else {
  console.log("all checks passed");
}
