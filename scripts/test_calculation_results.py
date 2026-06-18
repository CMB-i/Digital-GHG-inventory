import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.ACCESS.model import AccessMatrix
from app.modules.WFLWBLD.model import WorkflowVersion
from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter
from app.modules.SUBMIT.service import compose_calculation_results
from datetime import datetime, timezone

def run_test():
    app = create_app()
    with app.app_context():
        print("Starting Calculation Results integration test...")
        
        # Reset any aborted transaction from previous failed runs
        db.session.rollback()
        
        # Get admin user
        admin_user = User.query.filter_by(email="admin@example.com").first()
        if not admin_user:
            print("FAILED: Seed admin user not found. Run seed script first.")
            sys.exit(1)

        # 1. Clean up potential old test records
        old_wkbk = Workbook.query.filter_by(code="WKBK_CALC_TEST").first()
        if old_wkbk:
            WorkbookForm.query.filter_by(workbook_id=old_wkbk.id).delete()
            WorkbookSite.query.filter_by(workbook_id=old_wkbk.id).delete()
            WorkbookSiteSubmitter.query.filter_by(workbook_id=old_wkbk.id).delete()
            Workbook.query.filter_by(id=old_wkbk.id).delete()

        old_site = Site.query.filter_by(code="SITE_CALC_TEST").first()
        if old_site:
            # Delete dependent records
            AccessMatrix.query.filter_by(scope_site_id=old_site.id).delete()
            old_subs = Submission.query.filter_by(site_id=old_site.id).all()
            for s in old_subs:
                SubmissionValue.query.filter_by(submission_id=s.id).delete()
                Submission.query.filter_by(id=s.id).delete()
            ReportingPeriod.query.filter_by(site_id=old_site.id).delete()
            
        old_forms = Form.query.filter(Form.code.in_(["form_calc_source", "form_calc_result"])).all()
        for f in old_forms:
            f.current_version_id = None
        
        old_formula = Formula.query.filter_by(code="formula_test_calc").first()
        if old_formula:
            old_formula.current_version_id = None
        db.session.commit()

        for f in old_forms:
            old_fields = Field.query.filter_by(form_id=f.id).all()
            field_ids = [fd.id for fd in old_fields]
            if field_ids:
                FieldVersion.query.filter(FieldVersion.field_id.in_(field_ids)).delete()
                Field.query.filter(Field.id.in_(field_ids)).delete()
            FormVersion.query.filter_by(form_id=f.id).delete()
            Form.query.filter_by(id=f.id).delete()

        if old_formula:
            FormulaVersion.query.filter_by(formula_id=old_formula.id).delete()
            Formula.query.filter_by(id=old_formula.id).delete()

        if old_site:
            Site.query.filter_by(id=old_site.id).delete()
            
        db.session.commit()

        # Placeholders for IDs to clean up in finally
        site_id = None
        wkbk_id = None
        form_src_id = None
        form_res_id = None
        formula_id = None
        period_id = None
        sub_id = None
        f_elec_id = None
        f_factor_id = None
        f_calc_id = None

        try:
            # 2. Create test Site
            site = Site(
                name="Calculation Test Site",
                code="SITE_CALC_TEST",
                company_name="JSW Test Corp",
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(site)
            db.session.flush()
            site_id = site.id

            # 3. Create test Workbook
            wkbk = Workbook(
                name="Calculation Test Workbook",
                code="WKBK_CALC_TEST",
                status="published",
                created_by=admin_user.id
            )
            db.session.add(wkbk)
            db.session.flush()
            wkbk_id = wkbk.id

            # Map site and submitter for workbook access checks
            wkbk_site = WorkbookSite(
                workbook_id=wkbk.id,
                site_id=site.id,
                created_by=admin_user.id
            )
            db.session.add(wkbk_site)

            wkbk_submitter = WorkbookSiteSubmitter(
                workbook_id=wkbk.id,
                site_id=site.id,
                user_id=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(wkbk_submitter)

            # 4. Create test Forms
            form_src = Form(
                name="Source Input Form",
                code="form_calc_source",
                description='{"sites": [' + str(site.id) + ']}',
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(form_src)
            
            form_res = Form(
                name="Results Output Form",
                code="form_calc_result",
                description='{"sites": [' + str(site.id) + ']}',
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(form_res)
            db.session.flush()
            form_src_id = form_src.id
            form_res_id = form_res.id

            # Map forms to the workbook
            wkbk_form_src = WorkbookForm(
                workbook_id=wkbk.id,
                form_id=form_src.id,
                display_order=1,
                sheet_label="Source Input"
            )
            db.session.add(wkbk_form_src)
            
            wkbk_form_res = WorkbookForm(
                workbook_id=wkbk.id,
                form_id=form_res.id,
                display_order=2,
                sheet_label="Results Output"
            )
            db.session.add(wkbk_form_res)

            # 5. Create Fields
            f_elec = Field(
                form_id=form_src.id,
                field_code="src_electricity",
                display_order=1,
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(f_elec)

            f_factor = Field(
                form_id=form_src.id,
                field_code="src_factor",
                display_order=2,
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(f_factor)

            f_calc = Field(
                form_id=form_res.id,
                field_code="calc_emissions",
                display_order=1,
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(f_calc)
            db.session.flush()
            f_elec_id = f_elec.id
            f_factor_id = f_factor.id
            f_calc_id = f_calc.id

            # 6. Create Formula
            formula = Formula(
                name="Test Emission Calculation",
                code="formula_test_calc",
                created_by=admin_user.id,
                updated_by=admin_user.id
            )
            db.session.add(formula)
            db.session.flush()
            formula_id = formula.id

            formula_ver = FormulaVersion(
                formula_id=formula.id,
                version_number=1,
                expression="src_electricity * src_factor",
                tokens={"src_electricity": "field", "src_factor": "field"},
                published_at=datetime.now(timezone.utc),
                published_by=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(formula_ver)
            db.session.flush()

            formula.current_version_id = formula_ver.id
            db.session.flush()

            # 7. Create Form Versions
            fv_src = FormVersion(
                form_id=form_src.id,
                version_number=1,
                status="Approved",
                published_at=datetime.now(timezone.utc),
                published_by=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(fv_src)
            db.session.flush()

            fv_src_elec = FieldVersion(
                form_version_id=fv_src.id,
                field_id=f_elec.id,
                version_number=1,
                field_name="Electricity Input",
                field_type="number",
                field_config={},
                created_by=admin_user.id
            )
            db.session.add(fv_src_elec)

            fv_src_factor = FieldVersion(
                form_version_id=fv_src.id,
                field_id=f_factor.id,
                version_number=1,
                field_name="Emission Factor Input",
                field_type="number",
                field_config={},
                created_by=admin_user.id
            )
            db.session.add(fv_src_factor)

            fv_res = FormVersion(
                form_id=form_res.id,
                version_number=1,
                status="Approved",
                published_at=datetime.now(timezone.utc),
                published_by=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(fv_res)
            db.session.flush()

            fv_res_calc = FieldVersion(
                form_version_id=fv_res.id,
                field_id=f_calc.id,
                version_number=1,
                field_name="Calculated Emissions",
                field_type="calculated",
                field_config={"formula_version_id": formula_ver.id},
                created_by=admin_user.id
            )
            db.session.add(fv_res_calc)

            form_src.current_version_id = fv_src.id
            form_res.current_version_id = fv_res.id
            db.session.flush()

            # 8. Create Reporting Period
            period = ReportingPeriod(
                site_id=site.id,
                year=2026,
                month=4,  # April 2026
                status="OPEN",
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(period)
            db.session.flush()
            period_id = period.id

            # 9. Access Matrix permissions for admin user
            access = AccessMatrix(
                user_id=admin_user.id,
                scope_type="site",
                scope_site_id=site.id,
                entity_type="submission",
                can_create=True,
                can_submit=True,
                can_view=True,
                can_edit=True,
                created_by=admin_user.id
            )
            db.session.add(access)
            db.session.commit()

            # Get Workflow Version to satisfy non-null constraint
            wv = WorkflowVersion.query.first()
            wv_id = wv.id if wv else None
            if not wv_id:
                print("FAILED: No workflow version available in database.")
                sys.exit(1)

            # ---- TEST CASE 1: Missing Inputs ----
            print("Testing Case 1: Missing Inputs (no submission values yet)")
            res = compose_calculation_results(site.id, wkbk.id, 2026, admin_user.id)
            
            assert len(res["rows"]) == 12
            april_row = res["rows"][0]
            assert april_row["month"] == 4
            
            calc_cell = april_row["values"]["calc_emissions"]
            print("April Calc Cell State:", calc_cell)
            assert calc_cell["status"] == "missing_input"
            assert calc_cell["preview_value"] is None
            assert calc_cell["reportable_value"] is None
            
            warnings = calc_cell["warnings"]
            assert any("Source Input Form" in w for w in warnings)
            print("-> Case 1 Passed!")

            # ---- TEST CASE 2: Draft Submission (Preview Only) ----
            print("\nTesting Case 2: Draft Submission (Preview Only)")
            
            sub = Submission(
                site_id=site.id,
                form_id=form_src.id,
                form_version_id=fv_src.id,
                reporting_period_id=period.id,
                workflow_version_id=wv_id,
                status="Draft",
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(sub)
            db.session.flush()
            sub_id = sub.id

            val_elec = SubmissionValue(
                submission_id=sub.id,
                field_id=f_elec.id,
                field_version_id=fv_src_elec.id,
                raw_value="100.0",
                cell_state="draft",
                created_by=admin_user.id
            )
            db.session.add(val_elec)

            val_factor = SubmissionValue(
                submission_id=sub.id,
                field_id=f_factor.id,
                field_version_id=fv_src_factor.id,
                raw_value="0.5",
                cell_state="draft",
                created_by=admin_user.id
            )
            db.session.add(val_factor)
            db.session.commit()

            res2 = compose_calculation_results(site.id, wkbk.id, 2026, admin_user.id)
            april_row2 = res2["rows"][0]
            calc_cell2 = april_row2["values"]["calc_emissions"]
            print("April Calc Cell State (Draft):", calc_cell2)
            assert calc_cell2["status"] == "preview_only"
            assert float(calc_cell2["preview_value"]) == 50.0
            assert calc_cell2["reportable_value"] is None
            
            warnings2 = calc_cell2["warnings"]
            assert any("submitted but not approved, preview only" in w for w in warnings2)
            print("-> Case 2 Passed!")

            # ---- TEST CASE 3: Approved Submission (Calculable) ----
            print("\nTesting Case 3: Approved Submission (Calculable)")
            
            val_elec.cell_state = "approved_locked"
            val_factor.cell_state = "approved_locked"
            sub.status = "Approved"
            db.session.commit()

            res3 = compose_calculation_results(site.id, wkbk.id, 2026, admin_user.id)
            april_row3 = res3["rows"][0]
            calc_cell3 = april_row3["values"]["calc_emissions"]
            print("April Calc Cell State (Approved):", calc_cell3)
            assert calc_cell3["status"] == "calculable"
            assert float(calc_cell3["preview_value"]) == 50.0
            assert float(calc_cell3["reportable_value"]) == 50.0
            assert not calc_cell3["warnings"]
            print("-> Case 3 Passed!")

        finally:
            print("\nCleaning up test records...")
            # Nullify circular foreign keys
            try:
                db.session.rollback() # Reset transaction if aborted in try
                if form_src_id:
                    f_src = Form.query.get(form_src_id)
                    if f_src: f_src.current_version_id = None
                if form_res_id:
                    f_res = Form.query.get(form_res_id)
                    if f_res: f_res.current_version_id = None
                if formula_id:
                    forml = Formula.query.get(formula_id)
                    if forml: forml.current_version_id = None
                db.session.commit()
            except Exception as e:
                print(f"Error nulling current_version_id: {e}")
                db.session.rollback()

            if wkbk_id:
                WorkbookForm.query.filter_by(workbook_id=wkbk_id).delete()
                WorkbookSite.query.filter_by(workbook_id=wkbk_id).delete()
                WorkbookSiteSubmitter.query.filter_by(workbook_id=wkbk_id).delete()

            if site_id:
                AccessMatrix.query.filter_by(scope_site_id=site_id).delete()
            if sub_id:
                SubmissionValue.query.filter_by(submission_id=sub_id).delete()
                Submission.query.filter_by(id=sub_id).delete()
            if period_id:
                ReportingPeriod.query.filter_by(id=period_id).delete()
            
            field_ids = [fid for fid in [f_elec_id, f_factor_id, f_calc_id] if fid is not None]
            if field_ids:
                FieldVersion.query.filter(FieldVersion.field_id.in_(field_ids)).delete()
                Field.query.filter(Field.id.in_(field_ids)).delete()
                
            form_ids = [fid for fid in [form_src_id, form_res_id] if fid is not None]
            if form_ids:
                FormVersion.query.filter(FormVersion.form_id.in_(form_ids)).delete()
                Form.query.filter(Form.id.in_(form_ids)).delete()
                
            if formula_id:
                FormulaVersion.query.filter_by(formula_id=formula_id).delete()
                Formula.query.filter_by(id=formula_id).delete()
                
            if wkbk_id:
                Workbook.query.filter_by(id=wkbk_id).delete()

            if site_id:
                Site.query.filter_by(id=site_id).delete()
                
            db.session.commit()
            print("Cleanup completed successfully.")

if __name__ == "__main__":
    run_test()
