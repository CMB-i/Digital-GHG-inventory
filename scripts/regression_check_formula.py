"""
regression_check_formula.py — Functional regression check for a form's
calculated fields: computes actual output NUMBERS (not formula text) using
the real SUBMIT runtime compute path, so scripts/rename_copied_sheet.py can
be checked for correctness beyond "the plan printed the right renames."

Two distinct evaluation paths exist in SUBMIT/service.py for a calculated
field, and this script reuses both rather than reimplementing either:

  - resolve_calculated_fields(persist=False) -- the no-persist preview path
    (see its own docstring: "persist=False ... computes the same statuses
    read-only") for ordinary per-row/monthly calculated fields.
  - _compose_sheet_results(...) -- for "sheet result" calculated fields
    (annual aggregates, e.g. a SUM_MONTHS FY total): per its own docstring,
    this "has always been computed fresh and read-only, every request, with
    nothing equivalent to write to."

Neither path touches the database for writes -- no Submission or
SubmissionValue row is ever created. A synthetic 12-row monthly `rows`
structure is built in memory (mirroring the shape
_monthly_series_for_results expects) with deterministic sample values
assigned by field_id (stable across a rename, unlike field_code), so a
--diff-against comparison matches fields by identity rather than by the
string that's being renamed.

Usage:
    python scripts/regression_check_formula.py --form-code CARGO_MCT
    python scripts/regression_check_formula.py --form-id 21 --out /tmp/before.json
    python scripts/regression_check_formula.py --form-code CARGO_MCT --diff-against /tmp/before.json
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.modules.FORMBLD.model import Form, FormVersion
from app.modules.SUBMIT.service import (
    _field_payload,
    _sections_payload,
    monthly_table_fields,
    is_sheet_result_field,
    resolve_calculated_fields,
    _compose_sheet_results,
    get_approved_valsets_snapshot,
)
from app.modules.WKBK.model import WorkbookForm


def resolve_form(form_id, form_code):
    if form_id is not None:
        return Form.query.filter_by(id=form_id).one_or_none()
    return Form.query.filter_by(code=form_code).one_or_none()


def resolve_form_version_id(form):
    if form.current_version_id:
        return form.current_version_id
    latest = (
        FormVersion.query.filter_by(form_id=form.id)
        .order_by(FormVersion.version_number.desc())
        .first()
    )
    return latest.id if latest else None


def sample_raw_values_by_field_id(raw_fields):
    """
    Deterministic sample value per raw field, assigned by field_id (stable
    across a rename) rather than by field_code (which is exactly what's
    being renamed) -- so a before/after run assigns the identical sample
    input to "the same field" regardless of what its code is called.
    """
    ordered = sorted(raw_fields, key=lambda f: f["field_id"])
    return {f["field_id"]: 100.0 * (idx + 1) for idx, f in enumerate(ordered)}


def workbook_form_rows_for(form):
    memberships = WorkbookForm.query.filter_by(form_id=form.id).all()
    workbook_ids = {row.workbook_id for row in memberships}
    if len(workbook_ids) != 1:
        return []
    workbook_id = next(iter(workbook_ids))
    return (
        WorkbookForm.query.filter_by(workbook_id=workbook_id)
        .order_by(WorkbookForm.display_order, WorkbookForm.id)
        .all()
    )


def _form_shape(form):
    form_version_id = resolve_form_version_id(form)
    if not form_version_id:
        raise ValueError(f"Form id={form.id} code={form.code!r} has no version to evaluate.")

    fields = _field_payload(form_version_id)
    sections = _sections_payload(form_version_id)
    monthly_fields = monthly_table_fields(fields, sections)
    explicit_result_fields = [f for f in fields if is_sheet_result_field(f)]
    return form_version_id, fields, monthly_fields, explicit_result_fields


def _synthetic_rows_and_preview(fields, monthly_fields):
    fields_map = {f["field_code"]: f for f in fields}

    raw_fields = [f for f in fields if f["field_type"] != "calculated"]
    sample_by_field_id = sample_raw_values_by_field_id(raw_fields)
    raw_values_by_code = {f["field_code"]: sample_by_field_id[f["field_id"]] for f in raw_fields}

    value_set_snapshot = get_approved_valsets_snapshot()

    # Sample inputs are constant every month, so every month's
    # resolve_calculated_fields() call produces the same result -- month 1's
    # result already represents every month for the non-aggregate fields.
    monthly_calc_result = None
    rows = []
    for month in range(1, 13):
        field_values = dict(raw_values_by_code)
        calc_result = resolve_calculated_fields(
            fields_map, field_values, value_set_snapshot, apply_rounding=True,
        )
        if monthly_calc_result is None:
            monthly_calc_result = calc_result

        row_values = dict(raw_values_by_code)
        for code, res in calc_result.items():
            if res["status"] == "ok" and res["value"] is not None:
                row_values[code] = res["value"]
        rows.append({"year": 2026, "month": month, "label": f"Sample Month {month}", "values": row_values})

    workbook_values = {
        f["field_code"]: {
            "raw_value": raw_values_by_code[f["field_code"]],
            "calculated_value": raw_values_by_code[f["field_code"]],
        }
        for f in raw_fields
    }
    return fields_map, raw_fields, sample_by_field_id, monthly_calc_result, rows, workbook_values


def compute_regression_snapshot(form):
    form_version_id, fields, monthly_fields, explicit_result_fields = _form_shape(form)
    fields_map, raw_fields, sample_by_field_id, monthly_calc_result, rows, workbook_values = (
        _synthetic_rows_and_preview(fields, monthly_fields)
    )

    workbook_rows = workbook_form_rows_for(form)
    sibling_forms = {}
    form_by_id = {}
    if workbook_rows:
        form_ids = [row.form_id for row in workbook_rows]
        form_by_id = {f.id: f for f in Form.query.filter(Form.id.in_(form_ids)).all()}
        sibling_forms = {fid: f for fid, f in form_by_id.items() if fid != form.id}

    shape_cache = {form.id: (fields, monthly_fields, explicit_result_fields)}
    result_cache = {}
    resolving = set()

    def shape_for(owner_form):
        if owner_form.id not in shape_cache:
            _version_id, owner_fields, owner_monthly, owner_results = _form_shape(owner_form)
            shape_cache[owner_form.id] = (owner_fields, owner_monthly, owner_results)
        return shape_cache[owner_form.id]

    def owner_forms_for_code(code, requesting_form_id):
        owners = []
        for owner_id, owner_form in sibling_forms.items():
            if owner_id == requesting_form_id:
                continue
            owner_fields, _owner_monthly, _owner_results = shape_for(owner_form)
            if any(field["field_code"] == code for field in owner_fields):
                owners.append(owner_form)
        return owners

    def results_for(owner_form):
        if owner_form.id in result_cache:
            return result_cache[owner_form.id]
        owner_fields, owner_monthly, owner_result_fields = shape_for(owner_form)
        _owner_fields_map, _owner_raw_fields, _owner_sample_by_id, _owner_monthly_calc, owner_rows, owner_workbook_values = (
            _synthetic_rows_and_preview(owner_fields, owner_monthly)
        )

        resolving.add(owner_form.id)
        owner_sheet_results = _compose_sheet_results(
            owner_result_fields,
            owner_monthly,
            owner_rows,
            resolve_external=lambda code: resolve_external(code, owner_form.id),
            own_sheet_label=owner_form.name,
            annual_fields=owner_fields,
            workbook_values=owner_workbook_values,
        )
        resolving.discard(owner_form.id)
        result_cache[owner_form.id] = {r["field_code"]: r for r in owner_sheet_results}
        return result_cache[owner_form.id]

    def resolve_external(code, requesting_form_id):
        owners = owner_forms_for_code(code, requesting_form_id)
        if not owners:
            return None
        if len(owners) > 1:
            return {
                "ok": False,
                "hard_error": True,
                "error_causes": [f"Ambiguous cross-sheet formula token '{code}' in synthetic workbook regression."],
            }
        owner = owners[0]
        if owner.id in resolving:
            return {
                "ok": False,
                "hard_error": True,
                "error_causes": [f"Circular cross-sheet formula dependency involving sheet '{owner.name}'."],
            }
        result = results_for(owner).get(code) or {}
        if result.get("status") in ("calculated", "partial"):
            return {"ok": True, "value": result.get("value"), "partial": result.get("status") == "partial"}
        if result.get("status") == "error":
            return {"ok": False, "hard_error": True, "error_causes": result.get("error_causes") or [result.get("message")]}
        owner_fields, _owner_monthly, _owner_results = shape_for(owner)
        owner_field = next((f for f in owner_fields if f["field_code"] == code), {})
        return {
            "ok": False,
            "hard_error": False,
            "blocking_causes": [(owner.name, owner_field.get("field_name") or code)],
        }

    sheet_results = (
        _compose_sheet_results(
            explicit_result_fields,
            monthly_fields,
            rows,
            annual_fields=fields,
            workbook_values=workbook_values,
            resolve_external=(
                (lambda code: resolve_external(code, form.id))
                if sibling_forms else None
            ),
            own_sheet_label=form.name,
        )
        if explicit_result_fields else []
    )
    sheet_results_by_code = {r["field_code"]: r for r in sheet_results}

    results = {}
    for code, info in fields_map.items():
        if info["field_type"] != "calculated":
            continue
        field_id = info["field_id"]
        if is_sheet_result_field(info):
            r = sheet_results_by_code.get(code, {})
            results[str(field_id)] = {
                "field_code": code,
                "kind": "sheet_result",
                "status": r.get("status"),
                "value": r.get("value"),
                "message": r.get("message"),
            }
        else:
            r = (monthly_calc_result or {}).get(code, {})
            results[str(field_id)] = {
                "field_code": code,
                "kind": "monthly_calculated",
                "status": r.get("status"),
                "value": r.get("value"),
                "error_message": r.get("error_message"),
            }

    return {
        "form_id": form.id,
        "form_code": form.code,
        "form_version_id": form_version_id,
        "generated_at": datetime.now().isoformat(),
        "sample_inputs_by_field_id": {
            str(f["field_id"]): {"field_code": f["field_code"], "sample_value": sample_by_field_id[f["field_id"]]}
            for f in raw_fields
        },
        "results": results,
    }


def default_output_path(label):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(label)).strip("_").lower() or "form"
    return f"/tmp/{safe}_{ts}_formula_regression.json"


def print_report(payload):
    print(f"Form: id={payload['form_id']} code={payload['form_code']!r} form_version_id={payload['form_version_id']}")

    inputs = payload["sample_inputs_by_field_id"]
    print(f"\nSample raw inputs ({len(inputs)}):")
    for field_id, info in sorted(inputs.items(), key=lambda kv: int(kv[0])):
        print(f"  field_id={field_id} code={info['field_code']!r} sample_value={info['sample_value']}")

    results = payload["results"]
    print(f"\nCalculated field results ({len(results)}):")
    for field_id, r in sorted(results.items(), key=lambda kv: int(kv[0])):
        print(
            f"  field_id={field_id} code={r['field_code']!r} kind={r['kind']} "
            f"status={r['status']} value={r['value']}"
        )


def values_equal(a, b, tol=1e-9):
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) < tol
    except (TypeError, ValueError):
        return a == b


def diff_reports(old, new):
    old_results = old.get("results", {})
    new_results = new.get("results", {})
    all_ids = sorted(set(old_results) | set(new_results), key=lambda x: int(x))

    lines = []
    mismatches = []
    for field_id in all_ids:
        o = old_results.get(field_id)
        n = new_results.get(field_id)
        if o is None:
            lines.append(f"  field_id={field_id}: ADDED (code={n['field_code']!r}, value={n['value']})")
            continue
        if n is None:
            lines.append(f"  field_id={field_id}: REMOVED (was code={o['field_code']!r}, value={o['value']})")
            mismatches.append(field_id)
            continue

        code_note = (
            "" if o["field_code"] == n["field_code"]
            else f" | code: {o['field_code']!r} -> {n['field_code']!r} (expected from rename)"
        )
        if values_equal(o.get("value"), n.get("value")) and o.get("status") == n.get("status"):
            lines.append(f"  field_id={field_id}: OK value={n['value']} status={n['status']!r}{code_note}")
        else:
            mismatches.append(field_id)
            lines.append(
                f"  field_id={field_id}: MISMATCH value {o.get('value')!r} -> {n.get('value')!r}, "
                f"status {o.get('status')!r} -> {n.get('status')!r}{code_note}"
            )
    return lines, mismatches


def run():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--form-id", type=int)
    target.add_argument("--form-code")
    parser.add_argument("--out", default=None, help="Default: /tmp/<form_code>_<timestamp>_formula_regression.json")
    parser.add_argument(
        "--diff-against", default=None,
        help="Path to a previous snapshot JSON; compares computed values/statuses matched by field_id.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        form = resolve_form(args.form_id, args.form_code)
        if not form:
            ident = f"id={args.form_id}" if args.form_id is not None else f"code={args.form_code!r}"
            print(f"No Form found with {ident}")
            return
        payload = compute_regression_snapshot(form)

    out_path = args.out or default_output_path(payload["form_code"])
    print_report(payload)
    Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\n(written to {out_path})")

    if args.diff_against:
        old = json.loads(Path(args.diff_against).read_text())
        print(f"\n=== Diff: {args.diff_against} vs {out_path} (matched by field_id, stable across a rename) ===")
        lines, mismatches = diff_reports(old, payload)
        for line in lines:
            print(line)
        if mismatches:
            print(f"\nFAIL: {len(mismatches)} calculated field(s) changed computed value/status.")
            sys.exit(1)
        print(f"\nPASS: all {len(lines)} calculated field(s) match.")


if __name__ == "__main__":
    run()
