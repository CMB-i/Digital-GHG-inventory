import io
import json
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from app.database import db
from app.modules.RPTBLD.model import ReportTemplate
from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite
from app.common.permissions import has_permission
from app.modules.ACCESS.service import get_user_permissions
from app.modules.SITEMST.model import Site
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.FORMBLD.model import Form, Field, FieldVersion
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument
from app.modules.SUBMIT.service import human_sheet_label
from app.modules.USRMGMT.model import User

def list_report_templates(user_id):
    """
    List report templates. Scoped by user access.
    """
    # Verify user has access to view reports. Uses get_user_permissions() (rather
    # than a hand-rolled AccessMatrix scan) so a blanket entity_type == "all" grant
    # is correctly honored, same as any other entity type.
    global_perms = get_user_permissions(user_id=user_id, scope_type="global", entity_type="report")
    is_global = bool(global_perms["can_view"] or global_perms["can_export"])

    if is_global:
        return ReportTemplate.query.filter_by(is_deleted=False).order_by(ReportTemplate.id.desc()).all()

    allowed_site_ids = set()
    for site in Site.query.filter_by(is_deleted=False).all():
        perms = get_user_permissions(user_id=user_id, scope_type="site", scope_site_id=site.id, entity_type="report")
        if perms["can_view"] or perms["can_export"]:
            allowed_site_ids.add(site.id)

    # Filter templates that match the user's allowed sites
    all_templates = ReportTemplate.query.filter_by(is_deleted=False).all()
    filtered = []
    for t in all_templates:
        # If template is global, or site matches user's allowed list
        if not t.scope_site_id or t.scope_site_id in allowed_site_ids:
            filtered.append(t)
    return filtered

def get_report_template(template_id):
    return ReportTemplate.query.filter_by(id=template_id, is_deleted=False).one_or_none()

def create_report_template(name, code, description, scope_type, scope_site_id, config_json, user_id):
    if not name or not name.strip():
        raise ValueError("Report name is required.")
    if not code or not code.strip():
        raise ValueError("Report code is required.")

    existing = ReportTemplate.query.filter_by(code=code, is_deleted=False).first()
    if existing:
        raise ValueError(f"Report template with code '{code}' already exists.")

    # Validation config
    if not config_json:
        config_json = {}

    template = ReportTemplate(
        name=name.strip(),
        code=code.strip(),
        description=description,
        scope_type=scope_type or "global",
        scope_site_id=scope_site_id,
        config_json=config_json,
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(template)
    db.session.flush()
    return template

def update_report_template(template_id, name, description, scope_type, scope_site_id, config_json, user_id):
    t = get_report_template(template_id)
    if not t:
        raise ValueError("Report template not found.")

    if name:
        t.name = name.strip()
    t.description = description
    t.scope_type = scope_type or "global"
    t.scope_site_id = scope_site_id
    if config_json is not None:
        t.config_json = config_json
    t.updated_by = user_id
    db.session.flush()
    return t

def delete_report_template(template_id, user_id):
    t = get_report_template(template_id)
    if not t:
        raise ValueError("Report template not found.")
    t.is_deleted = True
    t.deleted_by = user_id
    t.deleted_at = datetime.now(timezone.utc)
    t.delete_reason = "Deleted by user"
    return True

def _get_user_allowed_sites(user_id, entity_type="report"):
    # Uses get_user_permissions() (rather than a hand-rolled AccessMatrix scan) so
    # a blanket entity_type == "all" grant is correctly honored, same as any other
    # entity type.
    global_perms = get_user_permissions(user_id=user_id, scope_type="global", entity_type=entity_type)
    if global_perms["can_view"] or global_perms["can_export"] or global_perms["can_submit"] or global_perms["can_create"]:
        active_sites = Site.query.filter_by(is_deleted=False).all()
        return {s.id for s in active_sites}, True

    allowed_site_ids = set()
    for site in Site.query.filter_by(is_deleted=False).all():
        perms = get_user_permissions(user_id=user_id, scope_type="site", scope_site_id=site.id, entity_type=entity_type)
        if perms["can_view"] or perms["can_export"] or perms["can_submit"] or perms["can_create"]:
            allowed_site_ids.add(site.id)
    return allowed_site_ids, False

def generate_report_data(template_id, user_id):
    """
    Gathers approved data for the given template. Scopes by user permissions.
    """
    t = get_report_template(template_id)
    if not t:
        raise ValueError("Report template not found.")

    allowed_site_ids, is_global = _get_user_allowed_sites(user_id, "report")

    config = t.config_json or {}
    form_ids = config.get("form_ids", [])
    site_ids = config.get("site_ids", [])
    start_year = config.get("start_year")
    start_month = config.get("start_month")
    end_year = config.get("end_year")
    end_month = config.get("end_month")

    # Filter sites by user's permitted sites
    if site_ids:
        query_site_ids = [sid for sid in site_ids if sid in allowed_site_ids]
    else:
        query_site_ids = list(allowed_site_ids)

    if not query_site_ids:
        return []

    # Query approved submissions
    sub_query = Submission.query.filter(
        Submission.site_id.in_(query_site_ids),
        Submission.status == "Approved",
        Submission.is_locked == True,
        Submission.is_deleted == False
    )

    if form_ids:
        sub_query = sub_query.filter(Submission.form_id.in_(form_ids))

    submissions = sub_query.all()

    # Filter by date range (joining reporting period)
    filtered_subs = []
    for sub in submissions:
        p = ReportingPeriod.query.get(sub.reporting_period_id)
        if not p or p.is_deleted:
            continue

        p_val = p.year * 12 + p.month
        if start_year and start_month:
            if p_val < (start_year * 12 + start_month):
                continue
        if end_year and end_month:
            if p_val > (end_year * 12 + end_month):
                continue
        filtered_subs.append((sub, p))

    # Gather values
    results = []
    from app.modules.SUBMIT.service import format_period_label

    sites_cache = {s.id: s for s in Site.query.filter_by(is_deleted=False).all()}
    forms_cache = {f.id: f for f in Form.query.filter_by(is_deleted=False).all()}

    for sub, p in filtered_subs:
        site = sites_cache.get(sub.site_id)
        form = forms_cache.get(sub.form_id)
        if not site or not form:
            continue

        # Get field configurations
        fields = (
            FieldVersion.query.with_entities(FieldVersion, Field)
            .join(Field, Field.id == FieldVersion.field_id)
            .filter(
                FieldVersion.form_version_id == sub.form_version_id,
                FieldVersion.is_deleted == False,
                Field.is_deleted == False
            )
            .all()
        )

        # Load values
        vals = SubmissionValue.query.filter_by(submission_id=sub.id).all()
        vals_map = {v.field_id: v for v in vals}

        for fv, f in fields:
            val_obj = vals_map.get(f.id)
            if not val_obj:
                continue

            unit = fv.field_config.get("unit") or "—"

            # Decide display value
            if fv.field_type == "calculated":
                display_val = float(val_obj.calculated_value) if val_obj.calculated_value is not None else None
            elif fv.field_type == "file":
                proof = ProofDocument.query.filter_by(submission_id=sub.id, field_id=f.id, is_deleted=False).first()
                display_val = proof.original_name if proof else "No Upload"
            else:
                try:
                    display_val = float(val_obj.raw_value) if val_obj.raw_value is not None else None
                except ValueError:
                    display_val = val_obj.raw_value

            results.append({
                "period_label": format_period_label(p.year, p.month),
                "site_name": site.name,
                "form_name": human_sheet_label(form),
                "field_code": f.field_code,
                "field_name": fv.field_name,
                "field_type": fv.field_type,
                "value": display_val,
                "unit": unit
            })

    # Sort by Period, Site, Form, Display Order
    results.sort(key=lambda x: (x["period_label"], x["site_name"], x["form_name"], x["field_name"]))
    return results

def export_report_to_excel(template_id, user_id):
    """
    Generates report and writes to formatted Excel sheet.
    """
    t = get_report_template(template_id)
    if not t:
        raise ValueError("Report template not found.")

    data = generate_report_data(template_id, user_id)

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # 1. Cover Sheet
    ws_cover = wb.create_sheet(title="Overview")
    ws_cover.views.sheetView[0].showGridLines = True

    # Fonts & Fills
    title_font = Font(name="Segoe UI", size=16, bold=True, color="1E293B")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="334155")
    regular_font = Font(name="Segoe UI", size=10, color="334155")

    navy_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid") # Indigo 600
    gray_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Header Title
    ws_cover["B2"] = t.name
    ws_cover["B2"].font = title_font

    ws_cover["B3"] = "Digital GHG Inventory environmental reporting sheet."
    ws_cover["B3"].font = Font(name="Segoe UI", size=10, italic=True, color="64748B")

    # Metadata Block
    ws_cover["B5"] = "Report Template Metadata"
    ws_cover["B5"].font = bold_font
    ws_cover.merge_cells("B5:C5")

    metadata_rows = [
        ("Template Code", t.code),
        ("Description", t.description or "No description provided."),
        ("Scope Type", t.scope_type.upper()),
        ("Exported At", datetime.now().strftime("%d %b %Y, %I:%M %p")),
        ("Config Details", json.dumps(t.config_json))
    ]

    curr_row = 6
    for k, v in metadata_rows:
        ws_cover.cell(row=curr_row, column=2, value=k).font = bold_font
        ws_cover.cell(row=curr_row, column=2).fill = gray_fill
        ws_cover.cell(row=curr_row, column=2).border = thin_border

        ws_cover.cell(row=curr_row, column=3, value=str(v)).font = regular_font
        ws_cover.cell(row=curr_row, column=3).border = thin_border
        curr_row += 1

    ws_cover.column_dimensions['B'].width = 20
    ws_cover.column_dimensions['C'].width = 50

    # 2. Data Sheet
    ws_data = wb.create_sheet(title="Report Data")
    ws_data.views.sheetView[0].showGridLines = True

    headers = ["Period", "Site Name", "Form Name", "Field Code", "Field Name", "Field Type", "Value", "Unit"]
    for col_num, h in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_num, value=h)
        cell.font = header_font
        cell.fill = navy_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for row_idx, r in enumerate(data, 2):
        ws_data.cell(row=row_idx, column=1, value=r["period_label"]).font = regular_font
        ws_data.cell(row=row_idx, column=2, value=r["site_name"]).font = regular_font
        ws_data.cell(row=row_idx, column=3, value=r["form_name"]).font = regular_font
        ws_data.cell(row=row_idx, column=4, value=r["field_code"]).font = regular_font
        ws_data.cell(row=row_idx, column=5, value=r["field_name"]).font = regular_font
        ws_data.cell(row=row_idx, column=6, value=r["field_type"]).font = regular_font

        # Value alignment
        val_cell = ws_data.cell(row=row_idx, column=7, value=r["value"])
        val_cell.font = regular_font
        if isinstance(r["value"], (int, float)):
            val_cell.alignment = Alignment(horizontal="right")
        else:
            val_cell.alignment = Alignment(horizontal="left")

        ws_data.cell(row=row_idx, column=8, value=r["unit"]).font = regular_font

        for col_idx in range(1, 9):
            ws_data.cell(row=row_idx, column=col_idx).border = thin_border

    # Auto column sizing
    for col in ws_data.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws_data.column_dimensions[col_letter].width = max(max_len + 3, 12)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()

def get_missing_submissions(user_id):
    """
    Analyzes site, reporting period and applicable forms to track missing sheets.
    """
    allowed_site_ids, is_global = _get_user_allowed_sites(user_id, "submission")

    if not allowed_site_ids:
        return []

    # Get all active open periods
    periods = ReportingPeriod.query.filter(
        ReportingPeriod.site_id.in_(list(allowed_site_ids)),
        ReportingPeriod.status.in_(("OPEN", "REOPENED")),
        ReportingPeriod.is_deleted == False
    ).order_by(ReportingPeriod.year.desc(), ReportingPeriod.month.desc()).all()

    # Load all published forms
    published_forms = Form.query.filter_by(is_deleted=False).filter(Form.current_version_id.is_not(None)).all()

    sites_map = {s.id: s for s in Site.query.filter_by(is_deleted=False).all()}
    from app.modules.SUBMIT.service import format_period_label

    missing_list = []

    for p in periods:
        site = sites_map.get(p.site_id)
        if not site:
            continue

        period_label = format_period_label(p.year, p.month)

        # Check form applicability using WorkbookSite as authoritative source
        for f in published_forms:
            is_assigned = (
                db.session.query(WorkbookForm.id)
                .join(Workbook, Workbook.id == WorkbookForm.workbook_id)
                .join(WorkbookSite, WorkbookSite.workbook_id == Workbook.id)
                .filter(
                    WorkbookForm.form_id == f.id,
                    WorkbookSite.site_id == p.site_id,
                    Workbook.is_active == True,
                )
                .first()
            )
            if not is_assigned:
                continue

            # Query actual submission
            sub = Submission.query.filter_by(
                site_id=p.site_id,
                form_id=f.id,
                reporting_period_id=p.id,
                is_deleted=False
            ).first()

            status_desc = "Not Started"
            sub_id = None
            if sub:
                sub_id = sub.id
                status_desc = sub.status

            # If not Approved, it is "missing" (either Not Started, Draft or In Review)
            is_missing = not sub or sub.status != "Approved"

            missing_list.append({
                "site_id": site.id,
                "site_name": site.name,
                "form_id": f.id,
                "form_name": human_sheet_label(f),
                "period_id": p.id,
                "period_label": period_label,
                "submission_id": sub_id,
                "status": status_desc,
                "is_missing": is_missing
            })

    # Sort: Period desc, Site asc, Form Name asc
    missing_list.sort(key=lambda x: (x["period_label"], x["site_name"], x["form_name"]))
    return missing_list
