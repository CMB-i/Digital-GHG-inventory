"""
rename_copied_sheet.py — Fixes the naming problem left by "copy sheet to
workbook" (FORMBLD.service.copy_sheet_to_workbook, clone_fields_with_formulas,
_next_available_form_code, _next_available_formula_code): copied
sheets/fields/formulas get auto-generated `*_COPY` / `*_copy` / `*_copy_2`
style codes that the UI can never rename afterward -- Field's dfCode and
dfName are both disabled once a field exists, and Formula has no code-update
endpoint at all.

Form.code and Formula.code/name are renamed directly: both are used only for
uniqueness checks and create-time lookup helpers (get_form_by_code,
get_formula_by_code), never for resolving a relationship at runtime, so a
plain column update is safe.

Field.field_code is different -- it's a live token embedded in
FormulaVersion.expression / FormulaVersion.tokens (dict keys) and in the
cached expression/tokens copy inside a calculated FieldVersion.field_config
(see clone_fields_with_formulas, which is where that cache is populated).
Renaming a field_code therefore means rewriting all three, not just the
Field row's own column.

Scope: only forms/fields/formulas *owned by the target form*
(Field.form_id == form.id, Formula.form_id == form.id) are touched. Formulas
are strictly sheet-scoped (clone_fields_with_formulas always sets
form_id = destination_form.id on a cloned Formula), so this covers every
formula this sheet copy created. Before any rename, every formula NOT owned
by this form (a genuine or legacy cross-sheet reference) is scanned for
tokens/expression already referencing one of the field codes about to be
renamed -- if any exist, the script aborts rather than silently leaving a
dangling reference.

Dry run by default (prints the full plan, touches nothing). Pass --apply to
execute; all mutations happen in one transaction, committed only at the end.

--backup (only meaningful with --apply) pg_dumps the whole dev DB to
backups/pre_rename_<form_code>_<timestamp>.sql before any write. This is a
full-database dump, not a scoped subset of the forms/fields/formulas tables
-- checked against the actual dev DB before choosing this (~14MB), a full
dump costs a fraction of a second, so there's no real time/size tradeoff
that would justify a more surgical dump that risks missing a table and
being harder to restore from. One command restores everything:
    psql "<DATABASE_URL>" -f backups/pre_rename_....sql

Usage:
    python scripts/rename_copied_sheet.py --workbook-code <code> \\
        --new-form-code <CODE> --site-suffix <suffix> \\
        [--form-code <code>] [--new-form-name <name>] \\
        [--field-map '{"old_code": "new_code"}'] \\
        [--formula-map '{"old_formula_code": "new_formula_code"}'] \\
        [--apply] [--backup] [--backup-path <path>]
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
from app.database import db
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.WKBK.model import Workbook, WorkbookForm


FORM_COPY_SUFFIX_RE = re.compile(r"_COPY\d*$")
FIELD_COPY_SUFFIX_RE = re.compile(r"_copy(_\d+)?$", re.IGNORECASE)
FORMULA_COPY_SUFFIX_RE = re.compile(r"_copy(_\d+)?$", re.IGNORECASE)
NAME_COPY_SUFFIX_RE = re.compile(r"\s*\(copy\)\s*$", re.IGNORECASE)


class RenameError(Exception):
    pass


def strip_copy_suffix(pattern, code):
    return pattern.sub("", code)


def default_form_name(name):
    stripped = NAME_COPY_SUFFIX_RE.sub("", name or "").strip()
    return stripped or name


def load_known_site_tags():
    """
    Lowercased Site.code values from SITEMST -- pulled from the table rather
    than hardcoded so this doesn't need updating every time a new site is
    added.
    """
    from app.modules.SITEMST.model import Site

    return {s.code.lower() for s in Site.query.filter_by(is_deleted=False).all() if s.code}


def strip_source_site_tag(base, known_site_tags):
    """
    Strips a trailing `_<tag>` from `base` if `<tag>` matches a known site
    code, so a formula's original site tag (baked in before '_copy' was
    appended by the copy feature) doesn't get stitched together with the
    destination --site-suffix. Longest tag first and anchored to the end of
    the string, so a short tag can't spuriously match inside a longer one.
    Leaves `base` untouched if no known tag matches at the end.
    """
    if not known_site_tags:
        return base
    pattern = re.compile(
        r"_(" + "|".join(re.escape(t) for t in sorted(known_site_tags, key=len, reverse=True)) + r")$"
    )
    stripped = pattern.sub("", base)
    return stripped or base


def rename_expression(expression, code_map):
    """
    Word-boundary-safe, single-pass substitution -- mirrors FORMBLD.service.
    _remap_formula_expression exactly (longest codes first, one regex over
    the original string) so a new code can never be re-matched by a
    different old code later in the same pass.
    """
    if not expression or not code_map:
        return expression
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(c) for c in sorted(code_map.keys(), key=len, reverse=True)) + r")\b"
    )
    return pattern.sub(lambda m: code_map[m.group(0)], expression)


def rename_tokens(tokens, code_map):
    if not tokens:
        return tokens
    return {code_map.get(key, key): value for key, value in tokens.items()}


def find_target_form(workbook_code, form_code):
    workbook = Workbook.query.filter_by(code=workbook_code).one_or_none()
    if not workbook:
        raise RenameError(f"No workbook found with code '{workbook_code}'.")

    attachments = WorkbookForm.query.filter_by(workbook_id=workbook.id).all()
    forms_by_id = {
        f.id: f
        for f in Form.query.filter(
            Form.id.in_([wf.form_id for wf in attachments] or [0]),
            Form.is_deleted == False,
        ).all()
    }
    attached_forms = [forms_by_id[wf.form_id] for wf in attachments if wf.form_id in forms_by_id]

    if form_code:
        matches = [f for f in attached_forms if f.code == form_code]
        if not matches:
            raise RenameError(
                f"No sheet with code '{form_code}' is attached to workbook '{workbook_code}'."
            )
        return workbook, matches[0]

    copy_matches = [f for f in attached_forms if FORM_COPY_SUFFIX_RE.search(f.code)]
    if not copy_matches:
        raise RenameError(
            f"No '*_COPY' sheet found attached to workbook '{workbook_code}'. "
            "Pass --form-code to target a specific sheet explicitly."
        )
    if len(copy_matches) > 1:
        codes = ", ".join(f.code for f in copy_matches)
        raise RenameError(
            f"Workbook '{workbook_code}' has more than one '*_COPY' sheet ({codes}). "
            "Disambiguate with --form-code."
        )
    return workbook, copy_matches[0]


def compute_field_code_map(form, field_map_override):
    active_fields = Field.query.filter_by(form_id=form.id, is_deleted=False).all()
    fields_by_code = {f.field_code: f for f in active_fields}

    code_map = {}
    for f in active_fields:
        if FIELD_COPY_SUFFIX_RE.search(f.field_code):
            base = strip_copy_suffix(FIELD_COPY_SUFFIX_RE, f.field_code)
            if base and base != f.field_code:
                code_map[f.field_code] = base

    for old_code, new_code in (field_map_override or {}).items():
        if old_code not in fields_by_code:
            raise RenameError(
                f"--field-map references '{old_code}', which is not an active field on this sheet."
            )
        code_map[old_code] = new_code

    # Drop no-op entries (override explicitly maps a code back to itself).
    code_map = {old: new for old, new in code_map.items() if old != new}

    # Validate the resulting set of field_codes for this form has no
    # collisions (uq_fields_code_per_form is per-form, not global).
    unchanged_codes = {f.field_code for f in active_fields if f.field_code not in code_map}
    new_codes = list(code_map.values())
    if len(set(new_codes)) != len(new_codes):
        seen = set()
        dupes = {c for c in new_codes if c in seen or seen.add(c)}
        raise RenameError(f"Field rename plan produces duplicate new field_code(s): {', '.join(dupes)}.")
    collisions = unchanged_codes & set(new_codes)
    if collisions:
        raise RenameError(
            f"New field_code(s) collide with existing, unrenamed field_code(s) on this "
            f"sheet: {', '.join(collisions)}."
        )
    for new_code in new_codes:
        if not new_code or not new_code.strip():
            raise RenameError("Computed/overridden field_code cannot be blank.")

    return code_map, fields_by_code


def compute_formula_renames(form, site_suffix, known_site_tags, formula_map_override=None):
    owned_formulas = Formula.query.filter_by(form_id=form.id, is_deleted=False).all()
    formula_map_override = formula_map_override or {}
    owned_codes = {f.code for f in owned_formulas}
    for old_code in formula_map_override:
        if old_code not in owned_codes:
            raise RenameError(
                f"--formula-map references '{old_code}', which is not a Formula owned by this sheet."
            )

    renames = {}
    for formula in owned_formulas:
        if formula.code in formula_map_override:
            new_code = formula_map_override[formula.code]
        else:
            base = strip_copy_suffix(FORMULA_COPY_SUFFIX_RE, formula.code).lower()
            base = strip_source_site_tag(base, known_site_tags)
            new_code = f"{base}_{site_suffix.lower()}"
        new_name = NAME_COPY_SUFFIX_RE.sub("", formula.name or "").strip() or formula.name
        renames[formula.id] = {
            "formula": formula,
            "old_code": formula.code,
            "new_code": new_code,
            "old_name": formula.name,
            "new_name": new_name,
        }

    new_codes = [r["new_code"] for r in renames.values()]
    if len(set(new_codes)) != len(new_codes):
        raise RenameError("Formula rename plan produces duplicate new Formula.code values.")

    for r in renames.values():
        conflict = Formula.query.filter(
            Formula.code == r["new_code"], Formula.id != r["formula"].id
        ).first()
        if conflict:
            raise RenameError(
                f"New Formula.code '{r['new_code']}' (for formula id={r['formula'].id}, "
                f"'{r['old_code']}') already exists (formula id={conflict.id})."
            )

    return renames


def check_cross_sheet_references(form, code_map):
    """
    Scans every Formula NOT owned by this form for a token/expression
    reference to a field_code about to be renamed.

    RPTBLD and APPROV are deliberately NOT scanned here: both reference
    Field/Formula only by numeric ID, never by code string --
    APPROV.Issue.field_id and RPTBLD's ReportTemplate.config_json
    (metric_aliases[*].field_ids, computed_columns[*].formula_id) are all
    plain FKs resolved by live join, and RPTBLD's one field_code in its
    export output (generate_report_data) is a display value computed fresh
    at read time, never cached. Field.id/Formula.id never change during a
    rename -- only the .field_code/.code columns do -- so neither module can
    go stale. (Confirmed by grepping field_code/formula usage across both
    modules' service.py/model.py; also, RPTBLD's validate_computed_columns
    requires context='report' formulas, while every formula this script
    touches has context='field', so a report computed column can't
    structurally point at one of these formulas anyway.)
    """
    if not code_map:
        return []
    old_codes = set(code_map.keys())
    conflicts = []
    other_formulas = Formula.query.filter(
        Formula.is_deleted == False,
        db.or_(Formula.form_id != form.id, Formula.form_id.is_(None)),
    ).all()
    for formula in other_formulas:
        if not formula.current_version_id:
            continue
        version = FormulaVersion.query.get(formula.current_version_id)
        if not version:
            continue
        token_hits = old_codes & set((version.tokens or {}).keys())
        expr_hits = set()
        if version.expression:
            for code in old_codes:
                if re.search(r"\b" + re.escape(code) + r"\b", version.expression):
                    expr_hits.add(code)
        hits = token_hits | expr_hits
        if hits:
            conflicts.append((formula, version, sorted(hits)))
    return conflicts


def build_plan(workbook, form, code_map, fields_by_code, new_form_code, new_form_name, formula_renames):
    calculated_versions = (
        FieldVersion.query.join(Field, Field.id == FieldVersion.field_id)
        .filter(
            Field.form_id == form.id,
            FieldVersion.is_deleted == False,
            FieldVersion.field_type == "calculated",
        )
        .all()
    )
    fv_updates = []
    for fv in calculated_versions:
        config = fv.field_config or {}
        old_expr = config.get("expression")
        old_tokens = config.get("tokens")
        new_expr = rename_expression(old_expr, code_map) if old_expr else old_expr
        new_tokens = rename_tokens(old_tokens, code_map) if old_tokens else old_tokens
        if new_expr != old_expr or new_tokens != old_tokens:
            fv_updates.append({
                "field_version": fv,
                "old_expression": old_expr,
                "new_expression": new_expr,
                "old_tokens": old_tokens,
                "new_tokens": new_tokens,
            })

    formula_version_updates = []
    for formula_id, r in formula_renames.items():
        versions = FormulaVersion.query.filter_by(formula_id=formula_id).all()
        for version in versions:
            new_expr = rename_expression(version.expression, code_map)
            new_tokens = rename_tokens(version.tokens, code_map)
            if new_expr != version.expression or new_tokens != version.tokens:
                formula_version_updates.append({
                    "formula_rename": r,
                    "version": version,
                    "old_expression": version.expression,
                    "new_expression": new_expr,
                    "old_tokens": version.tokens,
                    "new_tokens": new_tokens,
                })

    return {
        "workbook": workbook,
        "form": form,
        "new_form_code": new_form_code,
        "new_form_name": new_form_name,
        "code_map": code_map,
        "fields_by_code": fields_by_code,
        "formula_renames": formula_renames,
        "formula_version_updates": formula_version_updates,
        "fv_updates": fv_updates,
    }


def print_plan(plan, apply_mode):
    mode_label = "APPLY MODE" if apply_mode else "DRY RUN (no changes will be made)"
    print(f"=== {mode_label} ===\n")

    workbook, form = plan["workbook"], plan["form"]
    print(f"Workbook: {workbook.code} (id={workbook.id})")
    print(f"Target form: id={form.id}")
    print(f"  code: {form.code!r} -> {plan['new_form_code']!r}")
    print(f"  name: {form.name!r} -> {plan['new_form_name']!r}")

    code_map = plan["code_map"]
    print(f"\nFields ({len(code_map)} renamed, {len(plan['fields_by_code']) - len(code_map)} unchanged):")
    for old_code, new_code in sorted(code_map.items()):
        print(f"  {old_code!r} -> {new_code!r}")
    unchanged = sorted(set(plan["fields_by_code"].keys()) - set(code_map.keys()))
    if unchanged:
        print(f"  (unchanged): {', '.join(unchanged)}")

    formula_renames = plan["formula_renames"]
    print(f"\nFormulas ({len(formula_renames)} owned by this sheet):")
    for r in formula_renames.values():
        print(f"  formula id={r['formula'].id}")
        print(f"    code: {r['old_code']!r} -> {r['new_code']!r}")
        print(f"    name: {r['old_name']!r} -> {r['new_name']!r}")

    fvu = plan["formula_version_updates"]
    print(f"\nFormulaVersion expression/tokens rewrites ({len(fvu)}):")
    for u in fvu:
        v = u["version"]
        print(f"  FormulaVersion id={v.id} (formula id={v.formula_id}, version {v.version_number}):")
        print(f"    expression: {u['old_expression']!r} -> {u['new_expression']!r}")
        print(f"    tokens: {u['old_tokens']!r} -> {u['new_tokens']!r}")

    fv_updates = plan["fv_updates"]
    print(f"\nCalculated FieldVersion.field_config cache rewrites ({len(fv_updates)}):")
    for u in fv_updates:
        fv = u["field_version"]
        print(f"  FieldVersion id={fv.id} (field_id={fv.field_id}, form_version_id={fv.form_version_id}):")
        print(f"    expression: {u['old_expression']!r} -> {u['new_expression']!r}")
        print(f"    tokens: {u['old_tokens']!r} -> {u['new_tokens']!r}")


def apply_plan(plan, user_id=None):
    form = plan["form"]
    form.code = plan["new_form_code"]
    form.name = plan["new_form_name"]

    for old_code, new_code in plan["code_map"].items():
        plan["fields_by_code"][old_code].field_code = new_code

    for r in plan["formula_renames"].values():
        r["formula"].code = r["new_code"]
        r["formula"].name = r["new_name"]

    for u in plan["formula_version_updates"]:
        u["version"].expression = u["new_expression"]
        u["version"].tokens = u["new_tokens"]

    for u in plan["fv_updates"]:
        fv = u["field_version"]
        config = dict(fv.field_config or {})
        config["expression"] = u["new_expression"]
        config["tokens"] = u["new_tokens"]
        fv.field_config = config

    db.session.commit()


def run_pg_dump(db_uri, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pg_dump", db_uri, "-f", str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RenameError(f"pg_dump failed (exit {result.returncode}): {result.stderr.strip()}")


def default_backup_path(form_code):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", form_code).strip("_").lower() or "form"
    return PROJECT_ROOT / "backups" / f"pre_rename_{safe}_{ts}.sql"


def run():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workbook-code", required=True)
    parser.add_argument("--form-code", default=None, help="Disambiguates if the workbook has more than one *_COPY sheet.")
    parser.add_argument("--new-form-code", required=True)
    parser.add_argument("--new-form-name", default=None, help="Default: current name with ' (Copy)' stripped.")
    parser.add_argument("--site-suffix", required=True, help="Appended (lowercased) to every owned Formula.code.")
    parser.add_argument("--field-map", default=None, help='JSON override, e.g. \'{"old_field_code": "new_field_code"}\'.')
    parser.add_argument(
        "--formula-map", default=None,
        help='JSON override for Formula.code, e.g. \'{"old_formula_code": "new_formula_code"}\'. '
             "Use this when a formula's original code embeds a source-site tag that doesn't "
             "match any Site.code (so the automatic strip can't recognize it).",
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Before applying, pg_dump the whole dev DB to backups/pre_rename_<form_code>_<timestamp>.sql. "
             "Ignored (no-op) without --apply.",
    )
    parser.add_argument("--backup-path", default=None, help="Override the default backup file path.")
    parser.add_argument("--apply", action="store_true", help="Execute the plan. Omit for a dry run.")
    args = parser.parse_args()

    field_map_override = json.loads(args.field_map) if args.field_map else {}
    formula_map_override = json.loads(args.formula_map) if args.formula_map else {}

    app = create_app()
    with app.app_context():
        try:
            workbook, form = find_target_form(args.workbook_code, args.form_code)

            existing_target = Form.query.filter(
                Form.code == args.new_form_code, Form.id != form.id, Form.is_deleted == False
            ).first()
            if existing_target:
                raise RenameError(f"Form.code '{args.new_form_code}' is already in use (form id={existing_target.id}).")

            new_form_name = args.new_form_name or default_form_name(form.name)
            code_map, fields_by_code = compute_field_code_map(form, field_map_override)
            known_site_tags = load_known_site_tags()
            formula_renames = compute_formula_renames(
                form, args.site_suffix, known_site_tags, formula_map_override,
            )

            plan = build_plan(
                workbook, form, code_map, fields_by_code,
                args.new_form_code, new_form_name, formula_renames,
            )
            print_plan(plan, apply_mode=args.apply)

            conflicts = check_cross_sheet_references(form, code_map)
            if conflicts:
                print("\n=== ABORTED: cross-sheet reference conflict ===")
                for formula, version, hits in conflicts:
                    print(
                        f"  Formula id={formula.id} code={formula.code!r} "
                        f"(form_id={formula.form_id}) FormulaVersion id={version.id} "
                        f"already references field_code(s): {', '.join(hits)}"
                    )
                print(
                    "\nRenaming would leave these formulas dangling. Resolve the conflict "
                    "(e.g. via --field-map) before proceeding."
                )
                sys.exit(1)
            print("\nCross-sheet reference check: OK, no external formula references any of these field codes.")

            if args.apply:
                if args.backup:
                    backup_path = Path(args.backup_path) if args.backup_path else default_backup_path(form.code)
                    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
                    run_pg_dump(db_uri, backup_path)
                    print(f"\nBackup written to {backup_path}")
                    print(f'Restore with: psql "{db_uri}" -f {backup_path}')
                apply_plan(plan)
                print("\n=== APPLIED: changes committed. ===")
            else:
                if args.backup:
                    print("\n(--backup ignored: dry run makes no changes to back up.)")
                print("\n=== DRY RUN complete: no changes were made. Re-run with --apply to execute. ===")

        except RenameError as error:
            print(f"\nERROR: {error}")
            sys.exit(1)


if __name__ == "__main__":
    run()
