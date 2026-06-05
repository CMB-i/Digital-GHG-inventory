import os
import io
import json
from datetime import date, datetime, timezone
import bcrypt

from app import create_app
from app.database import db
from app.modules.USRMGMT.model import User
from app.modules.SITEMST.model import Site
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.FORMBLD.model import Form, FormVersion, Field, FieldVersion
from app.modules.WFLWBLD.model import Workflow, WorkflowVersion, WorkflowLevel, WorkflowLevelApprover
from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry
from app.modules.ACCESS.model import AccessMatrix
from app.modules.SUBMIT.model import Submission, SubmissionValue, ProofDocument
from app.modules.APPROV.model import ApprovalAction, Issue
from app.modules.AUDITL.model import AuditLog
from app.modules.NOTIFY.model import Notification
from app.modules.ACCESS.service import PERMISSION_FLAGS

def run_tests():
    print("Initializing Flask app for integration testing...")
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    client = app.test_client()
    
    with app.app_context():
        # Setup Test DB State
        print("\n=== STEP 1: Setting up clean test database environment ===")
        
        # Unlink current_version_id references to delete versions cleanly
        for f in db.session.query(Form).all():
            f.current_version_id = None
        for w in db.session.query(Workflow).all():
            w.current_version_id = None
        for v in db.session.query(ValueSet).all():
            v.current_version_id = None
        for fld in db.session.query(Field).all():
            fld.current_version_id = None
        db.session.flush()
        
        # Clean up old database records
        db.session.query(AuditLog).delete()
        db.session.query(Notification).delete()
        db.session.query(Issue).delete()
        db.session.query(ApprovalAction).delete()
        db.session.query(ProofDocument).delete()
        db.session.query(SubmissionValue).delete()
        db.session.query(Submission).delete()
        db.session.query(AccessMatrix).delete()
        db.session.query(ValueSetEntry).delete()
        db.session.query(ValueSetVersion).delete()
        db.session.query(ValueSet).delete()
        
        db.session.query(FieldVersion).delete()
        db.session.query(Field).delete()
        db.session.query(FormVersion).delete()
        db.session.query(Form).delete()
        
        db.session.query(WorkflowLevelApprover).delete()
        db.session.query(WorkflowLevel).delete()
        db.session.query(WorkflowVersion).delete()
        db.session.query(Workflow).delete()
        
        db.session.query(ReportingPeriod).delete()
        db.session.query(Site).delete()
        
        # Keep only admin@example.com, delete other users
        db.session.query(User).filter(User.email != "admin@example.com").delete()
        db.session.commit()
        
        # Create users
        pw_hash = bcrypt.hashpw("ChangeMe123!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        spoc = User(email="spoc@example.com", full_name="SPOC Test", password_hash=pw_hash, is_active=True, created_by=1, updated_by=1)
        approver = User(email="approver@example.com", full_name="Approver Test", password_hash=pw_hash, is_active=True, created_by=1, updated_by=1)
        db.session.add_all([spoc, approver])
        db.session.flush()
        
        # Create site
        site = Site(name="Test Site 1", code="SITE1", company_name="JSW", description="Test Site", created_by=1, updated_by=1)
        db.session.add(site)
        db.session.flush()
        
        # Create period
        period = ReportingPeriod(site_id=site.id, year=2026, month=6, status="OPEN", deadline=date(2026, 7, 5), created_by=1, updated_by=1)
        db.session.add(period)
        db.session.flush()
        
        # Create access matrix
        # SPOC data entry permissions
        for entity in ["user", "site", "form", "workflow", "submission", "report", "period", "value_set", "formula", "notification", "audit"]:
            flags = {flag: (flag in ["can_view", "can_create", "can_edit", "can_submit", "can_approve"]) for flag in PERMISSION_FLAGS}
            row = AccessMatrix(user_id=spoc.id, scope_type="site", scope_site_id=site.id, entity_type=entity, created_by=spoc.id, updated_by=spoc.id, **flags)
            db.session.add(row)
            
        # Approver review permissions
        for entity in ["user", "site", "form", "workflow", "submission", "report", "period", "value_set", "formula", "notification", "audit"]:
            flags = {flag: (flag in ["can_view", "can_approve", "can_reject"]) for flag in PERMISSION_FLAGS}
            row = AccessMatrix(user_id=approver.id, scope_type="site", scope_site_id=site.id, entity_type=entity, created_by=approver.id, updated_by=approver.id, **flags)
            db.session.add(row)
            
        # Create Value Set
        vs = ValueSet(name="Diesel Types", code="DIESEL_TYPES", description="Diesel category options", created_by=1, updated_by=1)
        db.session.add(vs)
        db.session.flush()
        
        vsv = ValueSetVersion(value_set_id=vs.id, version_number=1, status="Approved", effective_from=date(2026, 1, 1), created_by=1)
        db.session.add(vsv)
        db.session.flush()
        
        vs.current_version_id = vsv.id
        
        vse = ValueSetEntry(value_set_version_id=vsv.id, entry_code="HIGH_SPEED", entry_label="High Speed Diesel", display_order=1, is_active=True, created_by=1, updated_by=1)
        db.session.add(vse)
        db.session.flush()
        
        # Create Workflow
        wf = Workflow(name="Test Workflow", code="WF1", created_by=1, updated_by=1)
        db.session.add(wf)
        db.session.flush()
        
        wfv = WorkflowVersion(workflow_id=wf.id, version_number=1, published_at=datetime.now(timezone.utc), published_by=1, created_by=1)
        db.session.add(wfv)
        db.session.flush()
        
        wf.current_version_id = wfv.id
        
        wfl = WorkflowLevel(workflow_version_id=wfv.id, level_number=1, level_name="Manager Review", approval_mode="SEQUENTIAL", created_by=1, updated_by=1)
        db.session.add(wfl)
        db.session.flush()
        
        wfla = WorkflowLevelApprover(workflow_level_id=wfl.id, user_id=approver.id, sequence_number=1, created_by=1, updated_by=1)
        db.session.add(wfla)
        db.session.flush()
        
        # Create Form
        form_description = json.dumps({
            "sites": [site.id],
            "workflow_id": wf.id
        })
        form = Form(name="Diesel Consumption", code="DIESEL_CONS", description=form_description, created_by=1, updated_by=1)
        db.session.add(form)
        db.session.flush()
        
        fv = FormVersion(form_id=form.id, version_number=1, published_at=datetime.now(timezone.utc), published_by=1, created_by=1)
        db.session.add(fv)
        db.session.flush()
        
        form.current_version_id = fv.id
        
        # Form fields: numeric field, dropdown field, file upload field
        f_litres = Field(form_id=form.id, field_code="diesel_litres", display_order=1, created_by=1, updated_by=1)
        f_type = Field(form_id=form.id, field_code="diesel_type", display_order=2, created_by=1, updated_by=1)
        f_proof = Field(form_id=form.id, field_code="diesel_proof", display_order=3, created_by=1, updated_by=1)
        db.session.add_all([f_litres, f_type, f_proof])
        db.session.flush()
        
        fv_litres = FieldVersion(field_id=f_litres.id, version_number=1, form_version_id=fv.id, field_name="Diesel consumed (Litres)", field_type="number", field_config={"is_required": True}, created_by=1, updated_by=1)
        fv_type = FieldVersion(field_id=f_type.id, version_number=1, form_version_id=fv.id, field_name="Diesel Type", field_type="dropdown", field_config={"is_required": True, "value_set_version_id": vsv.id}, created_by=1, updated_by=1)
        fv_proof = FieldVersion(field_id=f_proof.id, version_number=1, form_version_id=fv.id, field_name="Invoice Copy", field_type="file", field_config={"is_required": True, "proof_required": True}, created_by=1, updated_by=1)
        db.session.add_all([fv_litres, fv_type, fv_proof])
        db.session.commit()
        
        print("Test environment setup complete.")
        
        # Cache variables for python tests
        spoc_id = spoc.id
        approver_id = approver.id
        site_id = site.id
        form_id = form.id
        period_id = period.id
        f_litres_id = f_litres.id
        f_type_id = f_type.id
        f_proof_id = f_proof.id

    # 1. Login as SPOC
    print("\n=== STEP 2: Logging in as SPOC ===")
    r = client.post("/login", data={"email": "spoc@example.com", "password": "ChangeMe123!"})
    assert r.status_code == 302
    print("  ✅ Logged in successfully.")

    # 2. Create Draft Submission
    print("\n=== STEP 3: Creating draft submission ===")
    r = client.post("/module/SUBMIT/api/submissions", json={
        "site_id": site_id,
        "form_id": form_id,
        "reporting_period_id": period_id
    })
    if r.status_code != 200:
        print("Draft creation failed. Code:", r.status_code)
        print("Data:", r.get_data(as_text=True))
    assert r.status_code == 200
    res_data = r.get_json()
    submission_id = res_data["data"]["submission_id"]
    print(f"  ✅ Draft created with ID: {submission_id}")

    # 3. File Whitelist Test
    print("\n=== STEP 4: Testing file upload whitelist ===")
    
    # Test 4.1: Reject invalid file type (.exe / application/x-msdownload)
    r = client.post(
        f"/module/SUBMIT/api/submissions/{submission_id}/proof/diesel_proof",
        data={"file": (io.BytesIO(b"dummy exe content"), "malware.exe", "application/x-msdownload")},
        content_type="multipart/form-data"
    )
    assert r.status_code == 400
    print("  ✅ Successfully rejected invalid .exe upload (HTTP 400).")

    # Test 4.2: Accept valid file type (.pdf / application/pdf)
    r = client.post(
        f"/module/SUBMIT/api/submissions/{submission_id}/proof/diesel_proof",
        data={"file": (io.BytesIO(b"dummy pdf content"), "invoice.pdf", "application/pdf")},
        content_type="multipart/form-data"
    )
    assert r.status_code == 200
    print("  ✅ Successfully allowed valid .pdf upload (HTTP 200).")

    # 4. Server-Side Submit Validation Test
    print("\n=== STEP 5: Testing server-side validations at submit ===")
    
    # Test 5.1: Submit empty form (should fail on required fields)
    r = client.post(f"/module/SUBMIT/api/submissions/{submission_id}/submit")
    assert r.status_code == 422
    errs = r.get_json()["validation_errors"]
    assert "diesel_litres" in errs
    assert "diesel_type" in errs
    print("  ✅ Successfully rejected empty submit with required field errors.")

    # Test 5.2: Submit with invalid numeric input
    client.put(f"/module/SUBMIT/api/submissions/{submission_id}/autosave", json={
        "values": {
            "diesel_litres": "not_a_number",
            "diesel_type": "HIGH_SPEED"
        }
    })
    r = client.post(f"/module/SUBMIT/api/submissions/{submission_id}/submit")
    assert r.status_code == 422
    errs = r.get_json()["validation_errors"]
    assert "diesel_litres" in errs
    assert "must be a valid number" in errs["diesel_litres"]
    print("  ✅ Successfully caught non-numeric value in numeric field at submit.")

    # Test 5.3: Submit with invalid dropdown selection code
    client.put(f"/module/SUBMIT/api/submissions/{submission_id}/autosave", json={
        "values": {
            "diesel_litres": "1500.50",
            "diesel_type": "INVALID_CODE"
        }
    })
    r = client.post(f"/module/SUBMIT/api/submissions/{submission_id}/submit")
    assert r.status_code == 422
    errs = r.get_json()["validation_errors"]
    assert "diesel_type" in errs
    assert "Invalid option" in errs["diesel_type"]
    print("  ✅ Successfully caught invalid option in dropdown field at submit.")

    # Test 5.4: Submit with valid values (should succeed)
    client.put(f"/module/SUBMIT/api/submissions/{submission_id}/autosave", json={
        "values": {
            "diesel_litres": "1500.50",
            "diesel_type": "HIGH_SPEED"
        }
    })
    r = client.post(f"/module/SUBMIT/api/submissions/{submission_id}/submit")
    assert r.status_code == 200
    print("  ✅ Submission succeeded with valid data!")

    # Verify status is Under Review
    with app.app_context():
        sub = Submission.query.get(submission_id)
        assert sub.status == "Under Review"
        print("  ✅ Submission status transitioned to: Under Review")

    # 5. Self-Approval Block Test
    print("\n=== STEP 6: Testing self-approval blocking ===")
    r = client.post(f"/module/APPROV/api/submissions/{submission_id}/approve", json={"comment": "approve myself"})
    # Should fail because SPOC is logged in, and SPOC is also the submitter
    assert r.status_code == 400
    print("  ✅ Self-approval blocked correctly (HTTP 400).")

    # Logout SPOC, Login Approver
    client.get("/logout")
    r = client.post("/login", data={"email": "approver@example.com", "password": "ChangeMe123!"})
    assert r.status_code == 302

    # 6. Approver Review Actions Test
    print("\n=== STEP 7: Testing approver queue and actions ===")
    
    # Test 7.1: Check queue
    r = client.get("/module/APPROV/api/queue")
    assert r.status_code == 200
    pending_items = r.get_json()["data"]["pending"]
    assert len(pending_items) == 1
    assert pending_items[0]["submission_id"] == submission_id
    print("  ✅ Submission successfully visible in Approver Review Queue.")

    # Test 7.2: Raise Review Issue
    r = client.post(f"/module/APPROV/api/submissions/{submission_id}/raise-issue", json={
        "field_id": f_litres_id,
        "title": "Litres out of range",
        "description": "Please verify if 1500.50 litres is accurate."
    })
    if r.status_code != 200:
        print("Raise issue failed. Code:", r.status_code)
        print("Data:", r.get_data(as_text=True))
    assert r.status_code == 200
    issue_id = r.get_json()["data"]["issue_id"]
    print(f"  ✅ Review issue raised successfully with ID: {issue_id}")

    # Test 7.3: Approve blocked by open issue
    r = client.post(f"/module/APPROV/api/submissions/{submission_id}/approve", json={"comment": "approve with issue"})
    if r.status_code != 400:
        print("Approve with issue failed to be blocked. Code:", r.status_code)
        print("Data:", r.get_data(as_text=True))
    assert r.status_code == 400
    assert "open issues blocking approval" in r.get_json()["error"]
    print("  ✅ Final approval successfully blocked by open review issue.")

    # Test 7.4: Resolve issue
    r = client.post(f"/module/APPROV/api/issues/{issue_id}/resolve")
    assert r.status_code == 200
    print("  ✅ Review issue resolved successfully.")

    # Test 7.5: Approve Submission
    r = client.post(f"/module/APPROV/api/submissions/{submission_id}/approve", json={"comment": "looks good"})
    assert r.status_code == 200
    
    with app.app_context():
        sub = Submission.query.get(submission_id)
        assert sub.status == "Approved"
        assert sub.is_locked == True
        print("  ✅ Submission successfully approved and locked!")

    # 7. Audit Log Verification
    print("\n=== STEP 8: Verifying database audit log ===")
    with app.app_context():
        logs = AuditLog.query.order_by(AuditLog.created_at.asc()).all()
        print(f"Found {len(logs)} audit entries in database:")
        actions = [log.action for log in logs]
        for idx, log in enumerate(logs):
            print(f"  [{idx}] User {log.actor_user_id} - Entity: {log.entity_type}#{log.entity_id} - Action: {log.action}")
            
        assert "CREATE_DRAFT" in actions
        assert "SUBMIT" in actions
        assert "APPROVE_LEVEL" in actions
        assert "FINAL_APPROVE" in actions
        print("  ✅ All required workflow actions verified in database audit log table.")

    print("\n==============================================")
    print("🎉 ALL STAGE 6 & 7 INTEGRATION TESTS PASSED 🎉")
    print("==============================================")

if __name__ == "__main__":
    run_tests()
