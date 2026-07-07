from datetime import datetime, timezone

from app.database import db
from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter
from app.modules.FORMBLD.model import Form, FormVersion, FormSection, FieldVersion
from app.modules.SITEMST.model import Site
from app.modules.USRMGMT.model import User
from app.modules.ACCESS.model import AccessMatrix


def _form_stats(form_id):
    """Return (section_count, field_count) for a form's latest version."""
    latest = (
        FormVersion.query.filter_by(form_id=form_id)
        .order_by(FormVersion.version_number.desc())
        .first()
    )
    if not latest:
        return 0, 0
    sections = FormSection.query.filter_by(form_version_id=latest.id, is_deleted=False).count()
    fields = FieldVersion.query.filter_by(
        form_version_id=latest.id, is_deleted=False
    ).count()
    return sections, fields


def get_all_workbooks():
    workbooks = (
        Workbook.query.filter_by(is_active=True)
        .order_by(Workbook.created_at.desc())
        .all()
    )
    result = []
    for wb in workbooks:
        sheets = WorkbookForm.query.filter_by(workbook_id=wb.id).all()
        total_fields = sum(_form_stats(s.form_id)[1] for s in sheets)
        result.append({
            "id": wb.id,
            "name": wb.name,
            "code": wb.code,
            "status": wb.status,
            "description": wb.description,
            "sheet_count": len(sheets),
            "field_count": total_fields,
        })
    return result


def create_workbook(name, code, description, created_by):
    if not name or not name.strip():
        raise ValueError("Workbook name is required.")
    if not code or not code.strip():
        raise ValueError("Workbook code is required.")
    existing = Workbook.query.filter_by(code=code.strip()).first()
    if existing:
        raise ValueError(f"A workbook with code '{code}' already exists.")
    wb = Workbook(
        name=name.strip(),
        code=code.strip(),
        description=(description or "").strip() or None,
        status="draft",
        is_active=True,
        created_by=created_by,
    )
    db.session.add(wb)
    db.session.flush()
    return wb


def get_workbook(workbook_id):
    return Workbook.query.filter_by(id=workbook_id, is_active=True).one_or_none()


def get_workbook_with_sheets(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        return None, []
    sheets = (
        WorkbookForm.query.filter_by(workbook_id=workbook_id)
        .order_by(WorkbookForm.display_order.asc(), WorkbookForm.id.asc())
        .all()
    )
    sheet_data = []
    for s in sheets:
        form = Form.query.filter_by(id=s.form_id, is_deleted=False).first()
        if not form:
            continue
        latest = (
            FormVersion.query.filter_by(form_id=form.id)
            .order_by(FormVersion.version_number.desc())
            .first()
        )
        sections, fields = _form_stats(form.id)
        sheet_data.append({
            "workbook_form_id": s.id,
            "form_id": form.id,
            "form_name": form.name,
            "form_code": form.code,
            "sheet_label": s.sheet_label or form.name,
            "display_order": s.display_order,
            "latest_version_id": latest.id if latest else None,
            "latest_version_status": latest.status if latest else None,
            "section_count": sections,
            "field_count": fields,
        })
    return wb, sheet_data


def add_sheet_to_workbook(workbook_id, form_id, sheet_label=None, display_order=None):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")
    form = Form.query.filter_by(id=form_id, is_deleted=False).first()
    if not form:
        raise ValueError("Form not found.")
    existing = WorkbookForm.query.filter_by(workbook_id=workbook_id, form_id=form_id).first()
    if existing:
        raise ValueError("This form is already in the workbook.")
    if display_order is None:
        max_order = (
            db.session.query(db.func.max(WorkbookForm.display_order))
            .filter_by(workbook_id=workbook_id)
            .scalar()
        ) or 0
        display_order = max_order + 10
    wf = WorkbookForm(
        workbook_id=workbook_id,
        form_id=form_id,
        sheet_label=sheet_label or None,
        display_order=display_order,
    )
    db.session.add(wf)
    db.session.flush()
    return wf


def remove_sheet_from_workbook(workbook_id, form_id):
    wf = WorkbookForm.query.filter_by(workbook_id=workbook_id, form_id=form_id).first()
    if not wf:
        raise ValueError("Sheet not found in this workbook.")
    db.session.delete(wf)
    db.session.flush()


def reorder_sheets(workbook_id, ordered_form_ids):
    for idx, form_id in enumerate(ordered_form_ids):
        wf = WorkbookForm.query.filter_by(workbook_id=workbook_id, form_id=form_id).first()
        if wf:
            wf.display_order = (idx + 1) * 10
    db.session.flush()


IN_PROGRESS_SUBMISSION_STATUSES = ("Draft", "Submitted", "Resubmitted", "Under Review", "Changes Requested")


def deactivate_workbook(workbook_id):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")

    from app.modules.SUBMIT.model import Submission

    form_ids = [row.form_id for row in WorkbookForm.query.filter_by(workbook_id=workbook_id).all()]
    site_ids = [row.site_id for row in WorkbookSite.query.filter_by(workbook_id=workbook_id).all()]
    if form_ids and site_ids:
        in_progress_count = Submission.query.filter(
            Submission.form_id.in_(form_ids),
            Submission.site_id.in_(site_ids),
            Submission.status.in_(IN_PROGRESS_SUBMISSION_STATUSES),
            Submission.is_deleted == False,
        ).count()
        if in_progress_count > 0:
            raise ValueError(
                f"Cannot deactivate workbook: {in_progress_count} in-progress submission(s) "
                "still depend on it."
            )

    wb.is_active = False
    wb.updated_at = datetime.now(timezone.utc)
    db.session.flush()


def rename_workbook(workbook_id, name):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")
    if not name or not name.strip():
        raise ValueError("Workbook name is required.")
    wb.name = name.strip()
    wb.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return wb


def rename_workbook_sheet(workbook_id, form_id, sheet_label):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")
    wf = WorkbookForm.query.filter_by(workbook_id=workbook_id, form_id=form_id).first()
    if not wf:
        raise ValueError("Sheet not found in this workbook.")
    wf.sheet_label = sheet_label.strip() if sheet_label and sheet_label.strip() else None
    db.session.flush()
    return wf


def get_addable_forms(workbook_id):
    """Return forms not already in this workbook."""
    existing_ids = {
        wf.form_id
        for wf in WorkbookForm.query.filter_by(workbook_id=workbook_id).all()
    }
    forms = Form.query.filter_by(is_deleted=False).order_by(Form.name.asc()).all()
    result = []
    for f in forms:
        if f.id in existing_ids:
            continue
        latest = (
            FormVersion.query.filter_by(form_id=f.id)
            .order_by(FormVersion.version_number.desc())
            .first()
        )
        result.append({
            "id": f.id,
            "name": f.name,
            "code": f.code,
            "latest_version_status": latest.status if latest else None,
        })
    return result


def get_workbook_sites(workbook_id):
    rows = (
        WorkbookSite.query.filter_by(workbook_id=workbook_id)
        .order_by(WorkbookSite.created_at.asc())
        .all()
    )
    result = []
    for row in rows:
        site = Site.query.filter_by(id=row.site_id, is_deleted=False).first()
        if site:
            result.append({"id": site.id, "name": site.name, "code": site.code})
    return result


def get_assignable_sites(workbook_id):
    assigned_ids = {row.site_id for row in WorkbookSite.query.filter_by(workbook_id=workbook_id).all()}
    sites = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    return [{"id": s.id, "name": s.name, "code": s.code} for s in sites if s.id not in assigned_ids]


def add_site_to_workbook(workbook_id, site_id, created_by):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")
    site = Site.query.filter_by(id=site_id, is_deleted=False).first()
    if not site:
        raise ValueError("Site not found.")
    existing = WorkbookSite.query.filter_by(workbook_id=workbook_id, site_id=site_id).first()
    if existing:
        raise ValueError("This site is already assigned to this workbook.")
    row = WorkbookSite(workbook_id=workbook_id, site_id=site_id, created_by=created_by)
    db.session.add(row)
    db.session.flush()
    return row


def remove_site_from_workbook(workbook_id, site_id):
    row = WorkbookSite.query.filter_by(workbook_id=workbook_id, site_id=site_id).first()
    if not row:
        raise ValueError("Site is not assigned to this workbook.")
    WorkbookSiteSubmitter.query.filter_by(workbook_id=workbook_id, site_id=site_id).delete()
    db.session.delete(row)
    db.session.flush()


def get_site_submitters(workbook_id, site_id):
    rows = (
        WorkbookSiteSubmitter.query
        .filter_by(workbook_id=workbook_id, site_id=site_id)
        .order_by(WorkbookSiteSubmitter.created_at.asc())
        .all()
    )
    result = []
    for row in rows:
        user = User.query.filter_by(id=row.user_id, is_deleted=False, is_active=True).first()
        if user:
            result.append({"id": user.id, "full_name": user.full_name, "email": user.email})
    return result


def get_eligible_submitters(workbook_id, site_id):
    already_assigned = {
        row.user_id
        for row in WorkbookSiteSubmitter.query.filter_by(
            workbook_id=workbook_id, site_id=site_id
        ).all()
    }
    rows = AccessMatrix.query.filter(
        AccessMatrix.entity_type == "submission",
        AccessMatrix.can_submit == True,
        AccessMatrix.is_deleted == False,
        db.or_(
            db.and_(
                AccessMatrix.scope_type == "site",
                AccessMatrix.scope_site_id == site_id,
            ),
            AccessMatrix.scope_type == "global",
        ),
    ).all()
    seen = set()
    result = []
    for row in rows:
        if row.user_id in already_assigned or row.user_id in seen:
            continue
        seen.add(row.user_id)
        user = User.query.filter_by(id=row.user_id, is_deleted=False, is_active=True).first()
        if user:
            result.append({"id": user.id, "full_name": user.full_name, "email": user.email})
    result.sort(key=lambda u: u["full_name"].lower())
    return result


def add_site_submitter(workbook_id, site_id, user_id, created_by):
    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")
    site = Site.query.filter_by(id=site_id, is_deleted=False).first()
    if not site:
        raise ValueError("Site not found.")
    ws = WorkbookSite.query.filter_by(workbook_id=workbook_id, site_id=site_id).first()
    if not ws:
        raise ValueError("Site is not assigned to this workbook.")
    user = User.query.filter_by(id=user_id, is_deleted=False, is_active=True).first()
    if not user:
        raise ValueError("User not found or inactive.")
    existing = WorkbookSiteSubmitter.query.filter_by(
        workbook_id=workbook_id, site_id=site_id, user_id=user_id
    ).first()
    if existing:
        raise ValueError("User is already a submitter for this site.")
    row = WorkbookSiteSubmitter(
        workbook_id=workbook_id, site_id=site_id, user_id=user_id, created_by=created_by,
    )
    db.session.add(row)
    db.session.flush()
    return row


def remove_site_submitter(workbook_id, site_id, user_id):
    row = WorkbookSiteSubmitter.query.filter_by(
        workbook_id=workbook_id, site_id=site_id, user_id=user_id
    ).first()
    if not row:
        raise ValueError("Submitter assignment not found.")
    db.session.delete(row)
    db.session.flush()


def check_workbook_readiness(workbook_id):
    from app.modules.FORMBLD.model import Form
    from app.modules.WFLWBLD.model import Workflow

    wb = get_workbook(workbook_id)
    if not wb:
        raise ValueError("Workbook not found.")

    sheet_rows = WorkbookForm.query.filter_by(workbook_id=workbook_id).all()
    published_sheets = sum(
        1 for s in sheet_rows
        if Form.query.filter_by(id=s.form_id, is_deleted=False).first()
        and Form.query.filter_by(id=s.form_id, is_deleted=False).first().current_version_id is not None
    )
    sheets_ok = published_sheets > 0

    site_rows = WorkbookSite.query.filter_by(workbook_id=workbook_id).all()
    sites_ok = len(site_rows) > 0

    submitters_ok = sites_ok and all(
        WorkbookSiteSubmitter.query.filter_by(workbook_id=workbook_id, site_id=r.site_id).count() > 0
        for r in site_rows
    )

    approval_path_ok = False
    approval_path_detail = "Needs a published approval path"
    if wb.workflow_id:
        from app.modules.WFLWBLD.model import WorkflowVersion
        wf = Workflow.query.filter_by(id=wb.workflow_id, is_deleted=False).first()
        if wf and wf.current_version_id:
            wfv = WorkflowVersion.query.filter_by(id=wf.current_version_id).first()
            if wfv and wfv.published_at is not None:
                approval_path_ok = True
                approval_path_detail = "Published approval path assigned"
            else:
                approval_path_detail = "Approval path exists but is not yet published"
        elif wf:
            approval_path_detail = "Approval path has no current version"

    all_ok = sheets_ok and sites_ok and submitters_ok and approval_path_ok

    return {
        "sheets": {
            "ok": sheets_ok,
            "label": "Sheets",
            "detail": f"{published_sheets} published sheet(s)" if sheets_ok else "Needs at least one published sheet",
        },
        "sites": {
            "ok": sites_ok,
            "label": "Sites",
            "detail": f"{len(site_rows)} site(s) assigned" if sites_ok else "Needs at least one site",
        },
        "submitters": {
            "ok": submitters_ok,
            "label": "Submitters",
            "detail": "All sites have submitters" if submitters_ok else "Every assigned site needs at least one submitter",
        },
        "approval_path": {
            "ok": approval_path_ok,
            "label": "Approval Path",
            "detail": approval_path_detail,
        },
        "all_ok": all_ok,
    }
