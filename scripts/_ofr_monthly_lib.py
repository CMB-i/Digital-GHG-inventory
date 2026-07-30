# Shared library, not a standalone operational entrypoint. Callers that persist
# changes must apply scripts/_script_safety.py before invoking mutating helpers.
"""
_ofr_monthly_lib.py -- shared helpers for converting an OFR sheet's raw
fields from frequency="annual" to "monthly" across multiple sites, following
the exact pattern established and verified for SWPL
(scripts/convert_swpl_ofr_to_monthly.py / scripts/verify_swpl_ofr_monthly.py).

Generic/introspective rather than hand-typed per site: reads the site's own
current field/formula/section structure from the DB and derives the
conversion from it, instead of re-transcribing each site's formulas by hand
into a script (the earlier per-site diagnosis already found real
field-code/formula-shape variance across sites -- letting the code read the
real structure avoids introducing a transcription bug on top of that).

Rule applied per calculated field: if its current formula's tokens include
one of this OFR form's own raw field codes, wrap every occurrence of that
code in the expression with SUM_MONTHS(...) and publish a new Formula (the
current one is already published/immutable). If a calculated field's formula
references only *other* calculated fields' codes (never a raw field
directly), it is carried through completely unchanged -- its inputs are
already correct FY totals once its own upstream fields are converted.
"""
import re

from app.database import db
from app.modules.FORMBLD.model import Form, Field, FieldVersion, FormSection
from app.modules.FORMBLD.service import (
    create_new_form_version_draft,
    save_form_draft_fields,
    publish_form_version,
    normalize_calculated_field_config,
    get_form_version_fields,
)
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.FRMULA.service import create_formula, publish_formula_version, validate_formula, evaluate_formula

USER_ID = 1


def unique_formula_code(base):
    code = base
    idx = 2
    while Formula.query.filter_by(code=code, is_deleted=False).one_or_none():
        code = f"{base}_v{idx}"
        idx += 1
    return code


def wrap_sum_months(expression, raw_codes):
    result = expression
    for code in raw_codes:
        result = re.sub(rf"\b{re.escape(code)}\b", f"SUM_MONTHS({code})", result)
    return result


def plan_ofr_conversion(form_code):
    """
    Read-only: returns (form, published_version_id, fields, raw_codes,
    sections_list, section_code_by_id, changed_calc_fields) without writing
    anything -- used both to preview a conversion and to drive it.
    """
    form = Form.query.filter_by(code=form_code, is_deleted=False).one()
    published_version_id = form.current_version_id
    fields = get_form_version_fields(published_version_id)

    raw_codes = {f.field_code for fv, f in fields if fv.field_type != "calculated"}

    section_rows = FormSection.query.filter_by(form_version_id=published_version_id, is_deleted=False).all()
    sections_list = [
        {"code": s.code, "name": s.name, "layout_type": "monthly_table", "display_order": s.display_order}
        for s in section_rows
    ]
    section_code_by_id = {s.id: s.code for s in section_rows}

    changed_calc_fields = []
    for fv, f in fields:
        if fv.field_type != "calculated":
            continue
        config = fv.field_config or {}
        tokens = config.get("tokens") or {}
        referenced_raw = sorted(t for t in tokens if t in raw_codes)
        if referenced_raw:
            expr = config.get("expression") or ""
            new_expr = wrap_sum_months(expr, referenced_raw)
            changed_calc_fields.append((f.field_code, expr, new_expr, referenced_raw))

    return form, published_version_id, fields, raw_codes, sections_list, section_code_by_id, changed_calc_fields


def print_plan(site_label, form_code):
    form, published_version_id, fields, raw_codes, sections_list, section_code_by_id, changed = plan_ofr_conversion(form_code)
    print(f"=== {site_label} ({form_code}) -- plan ===")
    print(f"  raw fields -> monthly: {sorted(raw_codes)}")
    print(f"  sections -> monthly_table: {[s['code'] for s in sections_list]}")
    for code, old_expr, new_expr, refs in changed:
        print(f"  {code}: '{old_expr}'  ->  '{new_expr}'")
    unchanged = [
        f.field_code for fv, f in fields
        if fv.field_type == "calculated" and f.field_code not in {c[0] for c in changed}
    ]
    print(f"  unchanged calculated fields (reference only other calc fields): {unchanged}")
    return form, raw_codes, changed


def convert_ofr_form_to_monthly(form_code):
    form, published_version_id, fields, raw_codes, sections_list, section_code_by_id, changed_calc_fields = plan_ofr_conversion(form_code)
    changed_codes = {c[0] for c in changed_calc_fields}
    new_expr_by_code = {c[0]: c[2] for c in changed_calc_fields}

    draft = create_new_form_version_draft(form.id, USER_ID)

    entries = []
    formula_log = []
    for fv, f in fields:
        section_code = section_code_by_id.get(fv.section_id)
        if fv.field_type != "calculated":
            entries.append({
                "field_code": f.field_code, "field_name": fv.field_name, "field_type": fv.field_type,
                "field_config": fv.field_config or {}, "display_order": f.display_order,
                "frequency": "monthly", "section_code": section_code,
            })
            continue

        config = dict(fv.field_config or {})
        if f.field_code in changed_codes:
            tokens = config.get("tokens") or {}
            new_expr = new_expr_by_code[f.field_code]
            validate_formula(new_expr, set(tokens.keys()))
            base_code = f"{f.field_code}_{form_code.lower()}_monthly"
            formula = create_formula(fv.field_name, unique_formula_code(base_code), new_expr, tokens, USER_ID, form_id=form.id, context="field")
            version = FormulaVersion.query.filter_by(formula_id=formula.id).order_by(FormulaVersion.version_number.desc()).first()
            published_fv = publish_formula_version(version.id, USER_ID)
            seed = {**config, "formula_version_id": published_fv.id, "expression": new_expr, "tokens": tokens}
            new_config, _freq = normalize_calculated_field_config("calculated", seed, "annual")
            formula_log.append((f.field_code, config.get("expression"), new_expr, published_fv.id))
            config = new_config

        entries.append({
            "field_code": f.field_code, "field_name": fv.field_name, "field_type": "calculated",
            "field_config": config, "display_order": f.display_order,
            "frequency": "annual", "section_code": section_code,
        })

    save_form_draft_fields(draft.id, entries, USER_ID, sections_list=sections_list)
    published = publish_form_version(draft.id, USER_ID)
    return published, formula_log, raw_codes


def verify_formula_level(formula_log, raw_codes, value_set_snapshot, seed=0):
    """
    For every changed calculated field: evaluate the OLD (pre-conversion)
    formula against ANNUAL_VALUE = sum(synthetic monthly series), and the NEW
    (SUM_MONTHS-wrapped) formula against the full monthly series, via the
    real evaluate_formula() engine. Confirms the two are numerically
    identical -- the exact claim being verified ("SUM_MONTHS produces the
    same result the old annual formula would have").
    """
    import random
    rng = random.Random(seed)
    series = {code: [round(rng.uniform(0.05, 2.0), 4) for _ in range(12)] for code in raw_codes}

    results = []
    for field_code, old_expr, new_expr, _formula_version_id in formula_log:
        names_old = {code: sum(series[code]) for code in raw_codes}
        names_new = {code: list(series[code]) for code in raw_codes}
        old_val = evaluate_formula(old_expr, names_old, value_set_snapshot)
        new_val = evaluate_formula(new_expr, names_new, value_set_snapshot)
        match = abs(float(old_val) - float(new_val)) < 1e-9
        results.append((field_code, old_val, new_val, match))
    return results, series


def verify_pipeline_level(site, workbook, form_code, series, user_id=USER_ID, fy_start_year=2023):
    """
    Rollback-only, real-pipeline confirmation that the converted OFR sheet's
    calculated fields resolve correctly through the actual SUBMIT engine
    (frequency reclassification into monthly_table_fields, section grouping,
    synthesize_automatic_fy_totals, formula evaluation) -- not just isolated
    formula math. Creates real Submissions/SubmissionValues for the OFR form
    only, on a FY with zero existing periods for this site so it can never
    collide with real data, then rolls everything back unconditionally.

    Returns {field_code: value} from sheet_results, plus the rows list for
    diagnostics. Caller must not commit; this only flushes within the
    caller's own transaction and expects the caller to roll back.
    """
    from app.modules.PERIOD.model import ReportingPeriod
    from app.modules.SUBMIT.model import Submission
    from app.modules.SUBMIT import service as submit_svc
    from app.modules.WKBK.model import WorkbookSite, WorkbookSiteSubmitter
    from sqlalchemy import tuple_

    # create_draft_submission gates on Workbook.status via
    # _require_workbook_runtime_access, same as compose_annual_workbook_data.
    # In-memory only within this (never-committed) transaction -- restored by
    # the caller's db.session.rollback(), never persisted.
    workbook.status = "published"
    site_link = WorkbookSite.query.filter_by(workbook_id=workbook.id, site_id=site.id).one()
    if not WorkbookSiteSubmitter.query.filter_by(workbook_id=workbook.id, site_id=site.id, user_id=user_id).first():
        db.session.add(WorkbookSiteSubmitter(workbook_id=workbook.id, site_id=site.id, user_id=user_id, created_by=user_id))
    db.session.flush()

    form = Form.query.filter_by(code=form_code, is_deleted=False).one()
    fields = submit_svc._field_payload(form.current_version_id)
    explicit_result_fields = [f for f in fields if submit_svc.is_sheet_result_field(f)]
    sections = submit_svc._sections_payload(form.current_version_id)
    monthly_fields = submit_svc.monthly_table_fields(fields, sections)
    sheet_result_fields = explicit_result_fields + submit_svc.synthesize_automatic_fy_totals(monthly_fields, explicit_result_fields)

    months = submit_svc._fy_months(fy_start_year)
    month_keys = [(m["year"], m["month"]) for m in months]
    existing = ReportingPeriod.query.filter(
        ReportingPeriod.site_id == site.id, ReportingPeriod.is_deleted == False,
        tuple_(ReportingPeriod.year, ReportingPeriod.month).in_(month_keys),
    ).count()
    assert existing == 0, f"FY{fy_start_year} already has real periods for this site -- pick a different verification FY."

    periods = []
    for item in months:
        period = ReportingPeriod(site_id=site.id, year=item["year"], month=item["month"], status="OPEN", created_by=user_id)
        db.session.add(period)
        db.session.flush()
        periods.append(period)

    for idx, period in enumerate(periods):
        submission = submit_svc.create_draft_submission(site.id, form.id, period.id, user_id, workbook_id=workbook.id)
        values = {code: vals[idx] for code, vals in series.items()}
        submit_svc.autosave_submission_values(submission.id, values, user_id)

    rows = []
    sub_by_period = {
        s.reporting_period_id: s
        for s in Submission.query.filter(
            Submission.site_id == site.id, Submission.form_id == form.id, Submission.is_deleted == False,
            Submission.reporting_period_id.in_([p.id for p in periods]),
        ).all()
    }
    for item in months:
        period = next(p for p in periods if p.year == item["year"] and p.month == item["month"])
        submission = sub_by_period.get(period.id)
        values = submit_svc._submission_values_payload(submission, monthly_fields)
        rows.append({**item, "submission_id": submission.id if submission else None, "values": values})

    sheet_rows = submit_svc._workbook_sheet_rows(workbook.id)
    resolver = submit_svc._CrossSheetResolver(site.id, fy_start_year, sheet_rows)
    resolve_ext = resolver.resolve_external_for(form)
    wbvals = submit_svc.workbook_values_payload(site.id, form.id, fy_start_year, fields)
    results = submit_svc._compose_sheet_results(
        sheet_result_fields, monthly_fields, rows, resolve_external=resolve_ext,
        own_sheet_label=form.name, annual_fields=fields, workbook_values=wbvals,
    )
    resolver.finish_external_for(form, results)
    return {r["field_code"]: r for r in results}
