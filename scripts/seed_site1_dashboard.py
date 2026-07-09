#!/usr/bin/env python3
"""Configure Test Site 1 dashboard visualizations on the annual workbook."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.FORMBLD.model import Form
from app.modules.FORMBLD.service import (
    create_new_form_version_draft,
    get_form_version_fields,
    publish_form_version,
    save_form_draft_fields,
)
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.FRMULA.service import create_formula, get_formula_by_code, publish_formula_version
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SITEMST.model import Site
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.SUBMIT.service import _fy_months, compose_annual_workbook_data
from app.modules.USRMGMT.model import User
from app.modules.WKBK.model import Workbook

SITE_CODE = "SITE1"
WORKBOOK_CODE = "annual_workbook"
DIESEL_FORM_CODE = "DIESEL_CONS"
DASHBOARD_FORM_CODE = "API_TEST_FORM"
FY_START_YEAR = 2026

DIESEL_LITRES_BY_MONTH = {
    (2026, 4): "1000",
    (2026, 5): "25001",
    (2026, 6): "1500.5",
    (2026, 7): "5000",
    (2026, 8): "2000",
    (2026, 9): "3000",
    (2026, 10): "10091.9011131",
    (2026, 11): "4000",
    (2026, 12): "5000",
    (2027, 1): "6000",
    (2027, 2): "7000",
    (2027, 3): "8000",
}

FUEL_CONSUMPTION_VALUE = "100"

VIZ_KPI_HALF = {
    "visualization": {
        "widget": "kpi",
        "span": "half",
        "source_mode": "self",
        "show_unit": True,
        "show_formula_status": True,
    },
}

VIZ_LINE_TREND = {
    "visualization": {
        "widget": "line",
        "span": "full",
        "source_mode": "fields",
        "source_field_codes": ["diesel_litres", "fuel_consumption"],
    },
}

VIZ_DONUT_SPLIT = {
    "visualization": {
        "widget": "donut",
        "span": "half",
        "donut_segments": [
            {"field_code": "diesel_fy_total", "label": "Diesel"},
            {"field_code": "total_fuel_qa", "label": "Other fuel"},
        ],
    },
}

ANNUAL_RESULT_CONFIG = {
    "field_scope": "annual_result",
    "display_region": "under_input_column",
    "result_role": "aggregate_result",
}


def _admin_user():
    admin = User.query.filter_by(email="admin@example.com", is_deleted=False).first()
    if not admin:
        raise RuntimeError("admin@example.com not found — run scripts/seed.py first.")
    return admin


def _ensure_formula(admin, code, name, expression, tokens):
    formula = get_formula_by_code(code)
    if not formula:
        create_formula(name, code, expression, tokens, admin.id)
        formula = get_formula_by_code(code)

    version = FormulaVersion.query.filter_by(
        formula_id=formula.id,
        published_at=None,
    ).first()
    if not version:
        published = FormulaVersion.query.filter_by(formula_id=formula.id).filter(
            FormulaVersion.published_at.isnot(None)
        ).order_by(FormulaVersion.version_number.desc()).first()
        if published and published.expression == expression:
            return published
        max_ver = (
            db.session.query(db.func.max(FormulaVersion.version_number))
            .filter_by(formula_id=formula.id)
            .scalar()
            or 0
        )
        version = FormulaVersion(
            formula_id=formula.id,
            version_number=max_ver + 1,
            expression=expression,
            tokens=tokens,
            created_by=admin.id,
        )
        db.session.add(version)
        db.session.flush()
    else:
        version.expression = expression
        version.tokens = tokens

    if version.published_at is None:
        publish_formula_version(version.id, admin.id)
    formula.current_version_id = version.id
    db.session.flush()
    return version


def _field_snapshot(form_version_id):
    rows = []
    for fv, field in get_form_version_fields(form_version_id):
        section = fv.section
        rows.append({
            "field": field,
            "field_version": fv,
            "field_code": field.field_code,
            "field_name": fv.field_name,
            "field_type": fv.field_type,
            "field_config": dict(fv.field_config or {}),
            "frequency": fv.frequency or "monthly",
            "display_order": field.display_order,
            "section_code": section.code if section else "",
        })
    return rows


def _configure_diesel_form(admin):
    form = Form.query.filter_by(code=DIESEL_FORM_CODE, is_deleted=False).first()
    if not form:
        raise RuntimeError(f"Form {DIESEL_FORM_CODE} not found.")

    draft = create_new_form_version_draft(form.id, admin.id)
    existing = {row["field_code"]: row for row in _field_snapshot(form.current_version_id)}

    sections = [
        {
            "code": "sec_monthly",
            "name": "Monthly Inputs",
            "layout_type": "monthly_table",
            "display_order": 1,
        },
    ]

    fields = []
    diesel_cfg = existing.get("diesel_litres", {})
    proof_cfg = existing.get("diesel_proof", {})
    fuel_cfg = existing.get("fuel_consumption", {})

    fields.append({
        "field_code": "diesel_litres",
        "field_name": diesel_cfg.get("field_name") or "Diesel Litres",
        "field_type": "number",
        "section_code": "sec_monthly",
        "frequency": "monthly",
        "display_order": 10,
        "field_config": {**(diesel_cfg.get("field_config") or {}), "unit": "L"},
    })
    fields.append({
        "field_code": "diesel_proof",
        "field_name": proof_cfg.get("field_name") or "Diesel Proof",
        "field_type": "file",
        "section_code": "sec_monthly",
        "frequency": "monthly",
        "display_order": 20,
        "field_config": proof_cfg.get("field_config") or {},
    })
    fields.append({
        "field_code": "fuel_consumption",
        "field_name": fuel_cfg.get("field_name") or "Fuel Consumption",
        "field_type": "number",
        "section_code": "sec_monthly",
        "frequency": "monthly",
        "display_order": 30,
        "field_config": fuel_cfg.get("field_config") or {},
    })

    save_form_draft_fields(draft.id, fields, admin.id, sections)
    publish_form_version(draft.id, admin.id)
    db.session.flush()
    return form


def _configure_dashboard_form(admin, diesel_formula_version_id, qa_formula_version_id):
    form = Form.query.filter_by(code=DASHBOARD_FORM_CODE, is_deleted=False).first()
    if not form:
        raise RuntimeError(f"Form {DASHBOARD_FORM_CODE} not found.")

    draft = create_new_form_version_draft(form.id, admin.id)
    existing = {row["field_code"]: row for row in _field_snapshot(form.current_version_id)}
    total_cfg = existing.get("total_fuel_qa", {})

    sections = [
        {
            "code": "sec_dashboard",
            "name": "Site 1 Summary",
            "layout_type": "summary_dashboard",
            "display_order": 1,
        },
    ]

    fields = [
        {
            "field_code": "diesel_fy_total",
            "field_name": "Total Diesel (FY)",
            "field_type": "calculated",
            "section_code": "sec_dashboard",
            "frequency": "annual",
            "display_order": 10,
            "field_config": {
                **ANNUAL_RESULT_CONFIG,
                **VIZ_KPI_HALF,
                "unit": "L",
                "formula_version_id": diesel_formula_version_id,
            },
        },
        {
            "field_code": "total_fuel_qa",
            "field_name": total_cfg.get("field_name") or "Total Fuel QA",
            "field_type": "calculated",
            "section_code": "sec_dashboard",
            "frequency": "annual",
            "display_order": 20,
            "field_config": {
                **ANNUAL_RESULT_CONFIG,
                **VIZ_KPI_HALF,
                "formula_version_id": qa_formula_version_id,
            },
        },
        {
            "field_code": "site1_fuel_trend",
            "field_name": "Monthly Fuel Trend",
            "field_type": "calculated",
            "section_code": "sec_dashboard",
            "frequency": "annual",
            "display_order": 30,
            "field_config": {
                **ANNUAL_RESULT_CONFIG,
                **VIZ_LINE_TREND,
                "formula_version_id": diesel_formula_version_id,
            },
        },
        {
            "field_code": "site1_fuel_split",
            "field_name": "Diesel vs Other Fuel",
            "field_type": "calculated",
            "section_code": "sec_dashboard",
            "frequency": "annual",
            "display_order": 40,
            "field_config": {
                **ANNUAL_RESULT_CONFIG,
                **VIZ_DONUT_SPLIT,
                "formula_version_id": diesel_formula_version_id,
            },
        },
    ]

    save_form_draft_fields(draft.id, fields, admin.id, sections)
    publish_form_version(draft.id, admin.id)
    db.session.flush()
    return form


def _ensure_fy_periods(site, admin):
    for item in _fy_months(FY_START_YEAR):
        period = ReportingPeriod.query.filter_by(
            site_id=site.id,
            year=item["year"],
            month=item["month"],
            is_deleted=False,
        ).first()
        if period:
            if period.status not in ("OPEN", "DRAFT"):
                period.status = "OPEN"
            continue
        db.session.add(
            ReportingPeriod(
                site_id=site.id,
                year=item["year"],
                month=item["month"],
                status="OPEN",
                created_by=admin.id,
                updated_by=admin.id,
            )
        )
    db.session.flush()


def _workflow_version_for_workbook(workbook):
    if not workbook.workflow_id:
        return None
    from app.modules.WFLWBLD.model import Workflow

    workflow = Workflow.query.get(workbook.workflow_id)
    return workflow.current_version_id if workflow else None


def _load_monthly_data(admin, site, diesel_form, workflow_version_id):
    periods = {
        (p.year, p.month): p
        for p in ReportingPeriod.query.filter_by(site_id=site.id, is_deleted=False).all()
    }
    fields_map = {
        field.field_code: (field, fv)
        for fv, field in get_form_version_fields(diesel_form.current_version_id)
    }

    for (year, month), diesel_value in DIESEL_LITRES_BY_MONTH.items():
        period = periods.get((year, month))
        if not period:
            continue

        submission = Submission.query.filter_by(
            site_id=site.id,
            form_id=diesel_form.id,
            reporting_period_id=period.id,
            is_deleted=False,
        ).first()
        if not submission:
            submission = Submission(
                site_id=site.id,
                form_id=diesel_form.id,
                form_version_id=diesel_form.current_version_id,
                reporting_period_id=period.id,
                workflow_version_id=workflow_version_id,
                status="Draft",
                created_by=admin.id,
                updated_by=admin.id,
            )
            db.session.add(submission)
            db.session.flush()
        elif submission.status not in ("Draft", "Changes Requested"):
            submission.status = "Draft"
            submission.updated_by = admin.id
            db.session.flush()

        values = {
            "diesel_litres": diesel_value,
            "fuel_consumption": FUEL_CONSUMPTION_VALUE,
        }
        for field_code, raw_value in values.items():
            field, fv = fields_map[field_code]
            val_row = SubmissionValue.query.filter_by(
                submission_id=submission.id,
                field_id=field.id,
            ).first()
            if val_row:
                val_row.raw_value = str(raw_value)
                val_row.field_version_id = fv.id
                val_row.cell_state = "draft_filled"
                val_row.updated_by = admin.id
            else:
                db.session.add(
                    SubmissionValue(
                        submission_id=submission.id,
                        field_id=field.id,
                        field_version_id=fv.id,
                        raw_value=str(raw_value),
                        cell_state="draft_filled",
                        created_by=admin.id,
                        updated_by=admin.id,
                    )
                )
    db.session.flush()


def _verify(admin, site, workbook, dashboard_form):
    payload = compose_annual_workbook_data(
        admin.id,
        site.id,
        workbook.id,
        FY_START_YEAR,
        selected_form_id=dashboard_form.id,
    )
    viz = payload.get("visualization") or {}
    if viz.get("mode") != "dashboard":
        raise RuntimeError("Dashboard mode not active on API Test Form.")

    widgets = {w["field_code"]: w for w in viz.get("widgets", [])}
    diesel_kpi = widgets.get("diesel_fy_total", {})
    fuel_kpi = widgets.get("total_fuel_qa", {})
    line = widgets.get("site1_fuel_trend", {})
    donut = widgets.get("site1_fuel_split", {})

    expected_diesel = sum(Decimal(v) for v in DIESEL_LITRES_BY_MONTH.values())
    expected_fuel = Decimal(FUEL_CONSUMPTION_VALUE) * 12

    print("Verification:")
    print(f"  visualization.mode = {viz.get('mode')}")
    print(f"  widgets = {len(viz.get('widgets', []))}")
    print(f"  diesel_fy_total = {diesel_kpi.get('value')} (status={diesel_kpi.get('status')})")
    print(f"  total_fuel_qa = {fuel_kpi.get('value')} (status={fuel_kpi.get('status')})")
    print(f"  line series = {len(line.get('series', []))}")
    print(f"  donut segments = {len(donut.get('segments', []))}")
    print(f"  monthly_series keys = {list((viz.get('monthly_series') or {}).keys())}")

    if diesel_kpi.get("status") != "calculated":
        raise RuntimeError(f"diesel_fy_total not calculated: {diesel_kpi.get('message')}")
    if fuel_kpi.get("status") != "calculated":
        raise RuntimeError(f"total_fuel_qa not calculated: {fuel_kpi.get('message')}")
    if abs(Decimal(str(diesel_kpi.get("value"))) - expected_diesel) > Decimal("0.01"):
        raise RuntimeError("diesel_fy_total value mismatch.")
    if abs(Decimal(str(fuel_kpi.get("value"))) - expected_fuel) > Decimal("0.01"):
        raise RuntimeError("total_fuel_qa value mismatch.")
    if len(line.get("series", [])) < 2:
        raise RuntimeError("Line chart missing series.")
    if len(donut.get("segments", [])) < 2:
        raise RuntimeError("Donut chart missing segments.")

    print("PASS: Site 1 dashboard configured and verified.")


def run():
    app = create_app()
    with app.app_context():
        admin = _admin_user()
        site = Site.query.filter_by(code=SITE_CODE, is_deleted=False).first()
        if not site:
            raise RuntimeError(f"Site {SITE_CODE} not found.")
        workbook = Workbook.query.filter_by(code=WORKBOOK_CODE, is_active=True).first()
        if not workbook:
            raise RuntimeError(f"Workbook {WORKBOOK_CODE} not found.")

        print("Creating formulas...")
        diesel_formula = _ensure_formula(
            admin,
            "formula_site1_diesel_fy",
            "Site 1 Diesel FY Total",
            "SUM_MONTHS(diesel_litres)",
            {"diesel_litres": {"type": "field"}},
        )
        qa_formula = _ensure_formula(
            admin,
            "QA_TOTAL_FUEL_SUM",
            "QA Total Fuel",
            "SUM_MONTHS(fuel_consumption)",
            {"fuel_consumption": {"type": "field"}},
        )

        print("Configuring Diesel Consumption form (monthly entry)...")
        diesel_form = _configure_diesel_form(admin)

        print("Configuring API Test Form (summary dashboard)...")
        dashboard_form = _configure_dashboard_form(admin, diesel_formula.id, qa_formula.id)

        print("Ensuring FY reporting periods...")
        _ensure_fy_periods(site, admin)

        print("Loading monthly test data...")
        workflow_version_id = _workflow_version_for_workbook(workbook)
        _load_monthly_data(admin, site, diesel_form, workflow_version_id)

        db.session.commit()

        print("Running verification...")
        _verify(admin, site, workbook, dashboard_form)

        print("\nSite 1 dashboard ready.")
        print(f"  Site: {site.name} (id={site.id})")
        print(f"  Workbook: {workbook.name} (id={workbook.id})")
        print(f"  FY: {FY_START_YEAR}")
        print("  Open:")
        print(f"    /module/SUBMIT/annual?site_id={site.id}&workbook_id={workbook.id}&fy={FY_START_YEAR}")
        print("  Tabs:")
        print("    - Diesel Consumption → enter monthly data")
        print("    - API Test Form → KPI + line + donut dashboard")


if __name__ == "__main__":
    run()
