"use strict";
/**
 * Regression check for the autosave stale-response race (see README /
 * static/js/ui_helpers.js's reconcileAutosaveResponse): a debounced autosave
 * response must never clobber a field the user edited again while that
 * request was in flight.
 *
 * This project has no JS test runner (no package.json, no Jest) -- see
 * tests/test_smoke.py and README's "Running Tests" section, which are
 * pytest-only. This is a plain, dependency-free Node script instead: it loads
 * ui_helpers.js the same way a browser would (via Node's vm module, so the
 * IIFE's `window.UIHelpers` assignment runs unmodified) and asserts against
 * the real function, not a reimplementation of it.
 *
 * Run with: node tests/js/test_autosave_merge.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(
  path.join(__dirname, "..", "..", "static", "js", "ui_helpers.js"),
  "utf8"
);
// Deliberately NOT vm.createContext(): that creates a separate realm with its
// own Array/Object constructors, which makes assert.deepStrictEqual fail on
// the returned `skipped` array even when its contents are identical (a
// cross-realm-Array gotcha, not a real bug). Running in this context instead
// keeps everything in one realm; `window` just needs to exist as a plain
// object first since ui_helpers.js assigns window.UIHelpers at load time.
global.window = global.window || {};
global.document = global.document || { getElementById: () => null };
vm.runInThisContext(src, { filename: "ui_helpers.js" });
const { reconcileAutosaveResponse } = global.window.UIHelpers;

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

check("a field edited again mid-flight is preserved, not clobbered by the stale response", () => {
  // User typed "A" into field_x, autosave sent {field_x: "A"}. Before the
  // response returns, the user changes field_x to "B" locally. The response
  // now arrives echoing back the server's persisted "A".
  const current = { field_x: "B" };
  const sent = { field_x: "A" };
  const serverValues = { field_x: "A" };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_x, "B", "the newer local edit must survive");
  assert.deepStrictEqual(skipped, ["field_x"]);
});

check("an unrelated field with no local edit is updated from the response", () => {
  const current = { field_x: "B", field_y: "old" };
  const sent = { field_x: "A", field_y: "old" };
  const serverValues = { field_x: "A", field_y: "new-from-server" };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_x, "B", "still preserved");
  assert.strictEqual(current.field_y, "new-from-server", "untouched field takes the fresh server value");
  assert.deepStrictEqual(skipped, ["field_x"]);
});

check("a brand-new field key (e.g. a calculated field appearing for the first time) is applied", () => {
  const current = {};
  const sent = {};
  const serverValues = { field_c: 42 };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_c, 42);
  assert.deepStrictEqual(skipped, []);
});

check("the normal, no-interleaved-edit case applies every returned value", () => {
  const current = { field_a: "7" };
  const sent = { field_a: "7" };
  const serverValues = { field_a: "7", field_c: 14 };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_a, "7");
  assert.strictEqual(current.field_c, 14);
  assert.deepStrictEqual(skipped, []);
});

check("object-valued fields (e.g. file uploads) compare by reference, not deep equality", () => {
  const fileValue = { storage_key: "abc", original_name: "proof.pdf" };
  const current = { field_file: fileValue };
  const sent = { field_file: fileValue };
  // Server echoes back a structurally-identical but distinct object -- as it
  // would for a field the user did NOT re-upload during the round trip.
  const serverValues = { field_file: { storage_key: "abc", original_name: "proof.pdf" } };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_file, serverValues.field_file, "applied: same reference at send time as now");
  assert.deepStrictEqual(skipped, []);
});

check("a re-uploaded file mid-flight (new object reference) is correctly treated as changed", () => {
  const original = { storage_key: "abc", original_name: "proof.pdf" };
  const current = { field_file: original };
  const sent = { field_file: original };
  // User re-uploaded a different file locally before the response arrived.
  current.field_file = { storage_key: "xyz", original_name: "proof-v2.pdf" };
  const serverValues = { field_file: { storage_key: "abc", original_name: "proof.pdf" } };

  const skipped = reconcileAutosaveResponse(current, sent, serverValues);

  assert.strictEqual(current.field_file.storage_key, "xyz", "the newer upload must survive");
  assert.deepStrictEqual(skipped, ["field_file"]);
});

console.log(`\n${passed} passed`);
if (process.exitCode) {
  console.error("FAILURES ABOVE");
} else {
  console.log("all checks passed");
}
