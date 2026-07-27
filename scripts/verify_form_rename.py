"""
verify_form_rename.py — Read-only, independent dump of the current DB state
for a given form, used to sanity-check scripts/rename_copied_sheet.py's
claims against the actual database rather than trusting its own printed
plan. Deliberately does not import or call anything from
rename_copied_sheet.py -- every query here is written from scratch against
the models directly.

Read-only: no db.session.add/commit/flush anywhere in this file.

Usage:
    python scripts/verify_form_rename.py --form-code CARGO_MCT
    python scripts/verify_form_rename.py --form-id 21 --out /tmp/before.txt
    python scripts/verify_form_rename.py --form-code CARGO_MCT --diff-against /tmp/cargo_mct_before.txt
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.modules.FORMBLD.model import Form, Field, FieldVersion
from app.modules.FRMULA.model import Formula, FormulaVersion


def dump(form):
    lines = []

    def emit(text=""):
        lines.append(text)

    emit("=== Form ===")
    emit(f"id={form.id} code={form.code!r} name={form.name!r} is_deleted={form.is_deleted}")

    fields = Field.query.filter_by(form_id=form.id).order_by(Field.display_order.asc(), Field.id.asc()).all()
    emit("\n=== Fields (form_id=%s) ===" % form.id)
    if not fields:
        emit("(none)")
    for f in fields:
        emit(f"id={f.id} field_code={f.field_code!r} is_deleted={f.is_deleted} display_order={f.display_order}")

    formulas = Formula.query.filter_by(form_id=form.id).order_by(Formula.id.asc()).all()
    emit("\n=== Formulas (form_id=%s) ===" % form.id)
    if not formulas:
        emit("(none)")
    for formula in formulas:
        emit(
            f"id={formula.id} code={formula.code!r} name={formula.name!r} "
            f"is_deleted={formula.is_deleted}"
        )

    formula_ids = [formula.id for formula in formulas]
    versions = (
        FormulaVersion.query.filter(FormulaVersion.formula_id.in_(formula_ids or [0]))
        .order_by(FormulaVersion.formula_id.asc(), FormulaVersion.version_number.asc())
        .all()
    )
    emit("\n=== FormulaVersions (for formulas owned by form_id=%s) ===" % form.id)
    if not versions:
        emit("(none)")
    for v in versions:
        emit(
            f"id={v.id} formula_id={v.formula_id} version_number={v.version_number} "
            f"published_at={v.published_at}"
        )
        emit(f"  expression={v.expression!r}")
        emit(f"  tokens={json.dumps(v.tokens, sort_keys=True)}")

    field_ids = [f.id for f in fields]
    calc_versions = (
        FieldVersion.query.filter(
            FieldVersion.field_id.in_(field_ids or [0]),
            FieldVersion.field_type == "calculated",
        )
        .order_by(FieldVersion.field_id.asc(), FieldVersion.version_number.asc())
        .all()
    )
    emit("\n=== Calculated FieldVersions (field_type='calculated', for fields on form_id=%s) ===" % form.id)
    if not calc_versions:
        emit("(none)")
    for fv in calc_versions:
        config = fv.field_config or {}
        emit(f"id={fv.id} field_id={fv.field_id} version_number={fv.version_number} is_deleted={fv.is_deleted}")
        emit(f"  field_config.expression={config.get('expression')!r}")
        emit(f"  field_config.tokens={json.dumps(config.get('tokens'), sort_keys=True)}")

    return lines


def default_output_path(label):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(label)).strip("_").lower() or "form"
    return f"/tmp/{safe}_{ts}.txt"


def run():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--form-id", type=int)
    target.add_argument("--form-code")
    parser.add_argument("--out", default=None, help="Default: /tmp/<form_code>_<timestamp>.txt")
    parser.add_argument(
        "--diff-against", default=None,
        help="Path to a previous dump; after saving the current dump, prints `diff -u <path> <new dump path>`.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.form_id is not None:
            form = Form.query.filter_by(id=args.form_id).one_or_none()
            if not form:
                print(f"No Form found with id={args.form_id}")
                return
        else:
            form = Form.query.filter_by(code=args.form_code).one_or_none()
            if not form:
                print(f"No Form found with code={args.form_code!r}")
                return

        lines = dump(form)
        out_path = args.out or default_output_path(form.code)

    output = "\n".join(lines) + "\n"
    print(output, end="")
    Path(out_path).write_text(output)
    print(f"\n(written to {out_path})")

    if args.diff_against:
        print(f"\n=== diff -u {args.diff_against} {out_path} ===")
        result = subprocess.run(
            ["diff", "-u", args.diff_against, out_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("(no differences)")
        elif result.returncode == 1:
            print(result.stdout, end="")
        else:
            print(result.stderr, end="")


if __name__ == "__main__":
    run()
