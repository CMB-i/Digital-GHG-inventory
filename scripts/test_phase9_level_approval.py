# NOTE: This test script requires a seeded development database to run successfully.
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, FormVersion
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.ACCESS.model import AccessMatrix
from app.modules.WFLWBLD.model import Workflow, WorkflowVersion, WorkflowLevel, WorkflowLevelApprover
from app.modules.NOTIFY.model import Notification
from app.modules.APPROV.service import approve_submission
from app.modules.SUBMIT.service import get_spoc_sheets_buckets, submit_submission
from datetime import datetime, timezone, date

def run_tests():
    app = create_app()
    with app.app_context():
        print("Starting Level Approval & Status Badge tests...")

        # 1. Retrieve or create test users
        admin_user = User.query.filter_by(email="admin@example.com").first()
        if not admin_user:
            print("FAILED: admin@example.com user not found. Run seed script first.")
            sys.exit(1)

        from app.modules.USRMGMT.service import hash_password

        spoc_user = User.query.filter_by(email="spoc_test_level@example.com").first()
        if not spoc_user:
            spoc_user = User(
                email="spoc_test_level@example.com",
                full_name="SPOC Test User",
                password_hash=hash_password("Password123!"),
                is_active=True,
                created_by=admin_user.id
            )
            db.session.add(spoc_user)
            db.session.flush()

        approver_user = User.query.filter_by(email="approver_test_level@example.com").first()
        if not approver_user:
            approver_user = User(
                email="approver_test_level@example.com",
                full_name="Approver Test User",
                password_hash=hash_password("Password123!"),
                is_active=True,
                created_by=admin_user.id
            )
            db.session.add(approver_user)
            db.session.flush()

        # Clean up any prior test sub for this email/site
        test_site = Site.query.filter_by(code="SITE_LVL").first()
        if not test_site:
            test_site = Site(
                name="Level Notification Site",
                code="SITE_LVL",
                company_name="Test Corp",
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(test_site)
            db.session.flush()

        test_form = Form.query.filter_by(code="form_lvl").first()
        if not test_form:
            test_form = Form(
                name="Level Notification Form",
                code="form_lvl",
                description='{"sites": [' + str(test_site.id) + ']}',
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(test_form)
            db.session.flush()

        # Form Version
        fv = FormVersion.query.filter_by(form_id=test_form.id).first()
        if not fv:
            fv = FormVersion(
                form_id=test_form.id,
                version_number=1,
                status="Approved",
                published_at=datetime.now(timezone.utc),
                published_by=admin_user.id,
                created_by=admin_user.id
            )
            db.session.add(fv)
            db.session.flush()
            test_form.current_version_id = fv.id

        test_period = ReportingPeriod.query.filter_by(site_id=test_site.id, year=2026, month=6).first()
        if not test_period:
            test_period = ReportingPeriod(
                site_id=test_site.id,
                year=2026,
                month=6,
                status="OPEN",
                is_deleted=False,
                created_by=admin_user.id
            )
            db.session.add(test_period)
            db.session.flush()

        # Clean up old submissions for this combo to prevent unique constraint error
        old_subs = Submission.query.filter_by(site_id=test_site.id, form_id=test_form.id, reporting_period_id=test_period.id).all()
        from app.modules.APPROV.model import ApprovalAction
        for osb in old_subs:
            ApprovalAction.query.filter_by(submission_id=osb.id).delete(synchronize_session=False)
            Notification.query.filter_by(entity_type="submission", entity_id=osb.id).delete(synchronize_session=False)
            Submission.query.filter_by(id=osb.id).delete(synchronize_session=False)
        db.session.commit()

        # Set up access permissions
        # SPOC can submit/edit
        AccessMatrix.query.filter_by(user_id=spoc_user.id, scope_site_id=test_site.id).delete()
        AccessMatrix.query.filter_by(user_id=approver_user.id, scope_site_id=test_site.id).delete()

        spoc_access = AccessMatrix(
            user_id=spoc_user.id,
            scope_type="site",
            scope_site_id=test_site.id,
            entity_type="submission",
            can_create=True,
            can_submit=True,
            can_view=True,
            can_edit=True,
            created_by=admin_user.id
        )
        db.session.add(spoc_access)

        # Approver can approve/reject
        approver_access = AccessMatrix(
            user_id=approver_user.id,
            scope_type="site",
            scope_site_id=test_site.id,
            entity_type="submission",
            can_approve=True,
            can_reject=True,
            can_view=True,
            created_by=admin_user.id
        )
        db.session.add(approver_access)
        db.session.flush()

        # Create a 2-Level Workflow
        wf = Workflow.query.filter_by(code="WF_LVL").first()
        if wf:
            wf.current_version_id = None
            db.session.commit()
            # Delete levels and workflow versions to start fresh
            WorkflowLevelApprover.query.filter(WorkflowLevelApprover.workflow_level_id.in_(
                db.session.query(WorkflowLevel.id).filter(WorkflowLevel.workflow_version_id.in_(
                    db.session.query(WorkflowVersion.id).filter_by(workflow_id=wf.id)
                ))
            )).delete(synchronize_session=False)
            WorkflowLevel.query.filter(WorkflowLevel.workflow_version_id.in_(
                db.session.query(WorkflowVersion.id).filter_by(workflow_id=wf.id)
            )).delete(synchronize_session=False)
            WorkflowVersion.query.filter_by(workflow_id=wf.id).delete(synchronize_session=False)
            Workflow.query.filter_by(id=wf.id).delete(synchronize_session=False)
            db.session.commit()

        wf = Workflow(
            name="2-Level Workflow",
            code="WF_LVL",
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(wf)
        db.session.flush()

        wfv = WorkflowVersion(
            workflow_id=wf.id,
            version_number=1,
            created_by=admin_user.id
        )
        db.session.add(wfv)
        db.session.flush()

        # Level 1
        lvl1 = WorkflowLevel(
            workflow_version_id=wfv.id,
            level_number=1,
            level_name="Level 1 Approver",
            approval_mode="ANY_ONE",
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(lvl1)
        db.session.flush()

        lvl1_app = WorkflowLevelApprover(
            workflow_level_id=lvl1.id,
            user_id=approver_user.id,
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(lvl1_app)

        # Level 2
        lvl2 = WorkflowLevel(
            workflow_version_id=wfv.id,
            level_number=2,
            level_name="Level 2 Approver",
            approval_mode="ANY_ONE",
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(lvl2)
        db.session.flush()

        lvl2_app = WorkflowLevelApprover(
            workflow_level_id=lvl2.id,
            user_id=admin_user.id,
            created_by=admin_user.id,
            updated_by=admin_user.id
        )
        db.session.add(lvl2_app)
        db.session.flush()

        # Publish Workflow
        wfv.published_at = datetime.now(timezone.utc)
        wfv.published_by = admin_user.id
        wf.current_version_id = wfv.id
        db.session.commit()

        # Create Draft Submission
        sub = Submission(
            site_id=test_site.id,
            form_id=test_form.id,
            form_version_id=fv.id,
            reporting_period_id=test_period.id,
            workflow_version_id=wfv.id,
            status="Draft",
            submitted_by=spoc_user.id,
            current_level=1,
            created_by=spoc_user.id
        )
        db.session.add(sub)
        db.session.flush()
        db.session.commit()

        print(f"Created Submission ID: {sub.id}")

        # Submit the sheet
        submit_submission(sub.id, spoc_user.id)
        db.session.commit()

        # Verify initial submit status is 'Submitted' and level is 1
        sub = Submission.query.get(sub.id)
        assert sub.status == "Submitted", f"Expected status 'Submitted', got {sub.status}"
        assert sub.current_level == 1, f"Expected current level 1, got {sub.current_level}"

        # 2. Level 1 Approve: Approver approves submission
        # We expect a LEVEL_APPROVED notification for spoc_user
        print("Approving Level 1...")
        approve_submission(sub.id, approver_user.id, comment="Approved Level 1")
        db.session.commit()

        # Check DB State: Should be Under Review at Level 2
        sub = Submission.query.get(sub.id)
        assert sub.status == "Under Review", f"Expected 'Under Review', got {sub.status}"
        assert sub.current_level == 2, f"Expected current level 2, got {sub.current_level}"

        # Check Notification
        notif = Notification.query.filter_by(
            user_id=spoc_user.id,
            event_type="LEVEL_APPROVED"
        ).order_by(Notification.id.desc()).first()

        assert notif is not None, "SPOC did not receive LEVEL_APPROVED notification!"
        print(f"Received Notification Message: {notif.message}")
        expected_msg = f"Your submission for {test_form.name} ({test_site.name}) has been approved at Level 1."
        assert notif.message == expected_msg, f"Message mismatch: expected '{expected_msg}', got '{notif.message}'"

        # 3. Check dashboard data representation
        # Get SPOC sheets buckets
        buckets = get_spoc_sheets_buckets(spoc_user.id)
        submitted_list = buckets["submitted"]
        test_sub_item = next((item for item in submitted_list if item["submission_id"] == sub.id), None)
        assert test_sub_item is not None, "Test submission not found in SPOC sheets submitted bucket"
        assert test_sub_item["status"] == "Under Review", f"Status in bucket mismatch: {test_sub_item['status']}"
        assert test_sub_item["status_text"] == "Under Review (Level 2)", f"Status text mismatch: {test_sub_item['status_text']}"
        print("SPOC Sheets bucket status_text verified: Under Review (Level 2)")

        # Get Recent activities from Admin dashboard endpoint logic
        from app.modules.RPTBLD.service import _get_user_allowed_sites
        allowed_site_ids, is_global = _get_user_allowed_sites(admin_user.id, "submission")
        recent_submissions = Submission.query.filter(
            Submission.site_id.in_(list(allowed_site_ids)),
            Submission.is_deleted == False
        ).order_by(Submission.updated_at.desc()).limit(5).all()

        recent_act_item = next((s for s in recent_submissions if s.id == sub.id), None)
        assert recent_act_item is not None, "Submission not found in recent submissions"
        # Format status_text
        status_text = recent_act_item.status
        if recent_act_item.status in ("Submitted", "Resubmitted", "Under Review") and recent_act_item.current_level is not None:
            status_text = f"{recent_act_item.status} (Level {recent_act_item.current_level})"

        assert status_text == "Under Review (Level 2)", f"Admin activity status text mismatch: {status_text}"
        print("Admin recent activity status text verified: Under Review (Level 2)")

        # 4. Final approval (Level 2 approval)
        print("Approving Level 2 (Final Approval)...")
        approve_submission(sub.id, admin_user.id, comment="Approved Level 2 (Final)")
        db.session.commit()

        sub = Submission.query.get(sub.id)
        assert sub.status == "Approved", f"Expected final status 'Approved', got {sub.status}"
        assert sub.is_locked is True, "Expected submission to be locked on final approval"

        # Check final approved notification
        final_notif = Notification.query.filter_by(
            user_id=spoc_user.id,
            event_type="APPROVED"
        ).order_by(Notification.id.desc()).first()
        assert final_notif is not None, "SPOC did not receive APPROVED notification on final approve!"
        print(f"Final approved notification: {final_notif.message}")

        # Clean up database records created for testing
        from app.modules.APPROV.model import ApprovalAction
        ApprovalAction.query.filter_by(submission_id=sub.id).delete(synchronize_session=False)
        Notification.query.filter(Notification.user_id.in_([spoc_user.id, approver_user.id])).delete(synchronize_session=False)
        Submission.query.filter_by(id=sub.id).delete(synchronize_session=False)
        AccessMatrix.query.filter(AccessMatrix.user_id.in_([spoc_user.id, approver_user.id])).delete(synchronize_session=False)
        
        # Clean up workflow
        wf.current_version_id = None
        db.session.commit()
        WorkflowLevelApprover.query.filter(WorkflowLevelApprover.workflow_level_id.in_([lvl1.id, lvl2.id])).delete(synchronize_session=False)
        WorkflowLevel.query.filter(WorkflowLevel.id.in_([lvl1.id, lvl2.id])).delete(synchronize_session=False)
        WorkflowVersion.query.filter_by(id=wfv.id).delete(synchronize_session=False)
        Workflow.query.filter_by(id=wf.id).delete(synchronize_session=False)
        
        # Clean up site/form/period
        test_form.current_version_id = None
        db.session.commit()
        ReportingPeriod.query.filter_by(id=test_period.id).delete(synchronize_session=False)
        FormVersion.query.filter_by(id=fv.id).delete(synchronize_session=False)
        Form.query.filter_by(id=test_form.id).delete(synchronize_session=False)
        Site.query.filter_by(id=test_site.id).delete(synchronize_session=False)
        db.session.commit()
        print("All Level Approval & Status Badge tests PASSED successfully!")

if __name__ == "__main__":
    run_tests()
