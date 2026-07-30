import io

from app.modules.AUDITL.model import AuditLog
from app.modules.SUBMIT.model import ProofDocument, Submission, WorkbookFieldValue


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_session_version"] = user.session_version


def _workbook_scoped_submission(
    make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_workbook, make_submission,
):
    submitter = make_user()
    unassigned = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    number_field, number_version = make_field(form, form_version, "field_a", field_type="number")
    file_field, file_version = make_field(form, form_version, "proof_doc", field_type="file")
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])
    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=site.id, can_edit=True, can_submit=True, can_create=True)
    make_access_grant(unassigned, "submission", scope_type="site", scope_site_id=site.id, can_edit=True, can_submit=True, can_create=True)
    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
    return {
        "submitter": submitter,
        "unassigned": unassigned,
        "site": site,
        "form": form,
        "form_version": form_version,
        "number_field": number_field,
        "number_version": number_version,
        "file_field": file_field,
        "file_version": file_version,
        "period": period,
        "workbook": workbook,
        "submission": submission,
    }


def _mock_save_file(monkeypatch):
    def fake_save_file(file_storage):
        return {
            "storage_key": "proofs/fake-proof.txt",
            "original_name": file_storage.filename,
            "mime_type": "text/plain",
            "file_size_bytes": 6,
        }

    monkeypatch.setattr("app.modules.SUBMIT.views.save_file", fake_save_file)


def test_site_authorized_unassigned_user_cannot_mutate_workbook_scoped_submission(
    client, monkeypatch, make_user, make_site, make_access_grant, make_form,
    make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
    )
    db_session.commit()
    _mock_save_file(monkeypatch)
    _login(client, ctx["unassigned"])

    autosave = client.put(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/autosave",
        json={"values": {"field_a": "10"}},
    )
    upload = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"secret"), "proof.txt")},
        content_type="multipart/form-data",
    )
    submit = client.post(f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/submit")

    assert autosave.status_code == 400
    assert upload.status_code == 403
    assert submit.status_code == 400


def test_workbook_with_zero_submitter_assignments_denies_site_permission_only_user(
    client, monkeypatch, make_user, make_site, make_access_grant, make_form,
    make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session,
):
    user = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a", field_type="number")
    make_field(form, form_version, "proof_doc", field_type="file")
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])
    make_workbook(form, site, workflow_version=workflow_version, submitters=[])
    make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, can_edit=True, can_submit=True, can_create=True)
    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
    db_session.commit()
    _mock_save_file(monkeypatch)
    _login(client, user)

    autosave = client.put(
        f"/module/SUBMIT/api/submissions/{submission.id}/autosave",
        json={"values": {"field_a": "10"}},
    )
    upload = client.post(
        f"/module/SUBMIT/api/submissions/{submission.id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"secret"), "proof.txt")},
        content_type="multipart/form-data",
    )
    submit = client.post(f"/module/SUBMIT/api/submissions/{submission.id}/submit")

    assert autosave.status_code == 400
    assert upload.status_code == 403
    assert submit.status_code == 400


def test_workbook_assigned_user_can_autosave_upload_proof_and_submit(
    client, monkeypatch, make_user, make_site, make_access_grant, make_form,
    make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session, created_objects,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
    )
    _mock_save_file(monkeypatch)
    _login(client, ctx["submitter"])

    autosave = client.put(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/autosave",
        json={"values": {"field_a": "10"}},
    )
    upload = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"secret"), "proof.txt")},
        content_type="multipart/form-data",
    )
    submit = client.post(f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/submit")

    assert autosave.status_code == 200
    assert upload.status_code == 200
    assert submit.status_code == 200

    proof = ProofDocument.query.filter_by(submission_id=ctx["submission"].id).one()
    created_objects.append(proof)
    db_session.flush()


def test_workbook_assigned_user_can_create_initial_draft(
    client, make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_workbook, db_session, created_objects,
):
    submitter = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a", field_type="number")
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])
    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=site.id, can_create=True, can_submit=True)
    _login(client, submitter)

    resp = client.post(
        "/module/SUBMIT/api/submissions",
        json={
            "site_id": site.id,
            "form_id": form.id,
            "reporting_period_id": period.id,
            "workbook_id": workbook.id,
        },
    )

    assert resp.status_code == 200
    submission = db_session.get(Submission, resp.get_json()["data"]["submission_id"])
    created_objects.append(submission)
    assert submission.site_id == site.id
    assert submission.form_id == form.id
    assert submission.reporting_period_id == period.id


def test_non_workbook_scoped_submission_still_uses_site_permission_only(
    client, make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_submission,
):
    user = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    make_field(form, form_version, "field_a", field_type="number")
    period = make_reporting_period(site)
    workflow_version = make_workflow([approver])
    submission = make_submission(site, form, form_version, period, workflow_version, status="Draft")
    make_access_grant(user, "submission", scope_type="site", scope_site_id=site.id, can_edit=True, can_submit=True)
    _login(client, user)

    autosave = client.put(
        f"/module/SUBMIT/api/submissions/{submission.id}/autosave",
        json={"values": {"field_a": "10"}},
    )
    submit = client.post(f"/module/SUBMIT/api/submissions/{submission.id}/submit")

    assert autosave.status_code == 200
    assert submit.status_code == 200


def test_autosave_creates_traceable_audit_entry(
    client, make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_workbook, make_submission,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
    )
    _login(client, ctx["submitter"])

    resp = client.put(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/autosave",
        json={"values": {"field_a": "42"}},
    )

    assert resp.status_code == 200
    audit = AuditLog.query.filter_by(
        actor_user_id=ctx["submitter"].id,
        entity_type="submission",
        entity_id=str(ctx["submission"].id),
        action="AUTOSAVE_VALUE",
    ).one()
    assert audit.created_at is not None
    assert audit.metadata_json["field_id"] == ctx["number_field"].id
    assert audit.metadata_json["field_code"] == "field_a"
    assert audit.new_values["raw_value"] == {"present": True, "type": "str"}
    assert "42" not in str(audit.old_values)
    assert "42" not in str(audit.new_values)
    assert "42" not in str(audit.metadata_json)


def test_annual_workbook_value_save_creates_traceable_audit_entry(
    make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_workbook, db_session,
    created_objects,
):
    from app.modules.SUBMIT.service import save_annual_workbook_values

    submitter = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    annual_field, _field_version = make_field(form, form_version, "annual_qty", field_type="number", frequency="annual")
    make_reporting_period(site, year=2026, month=4)
    workflow_version = make_workflow([approver])
    workbook = make_workbook(form, site, workflow_version=workflow_version, submitters=[submitter])
    make_access_grant(submitter, "submission", scope_type="site", scope_site_id=site.id, can_edit=True, can_submit=True)

    result = save_annual_workbook_values(submitter.id, site.id, workbook.id, form.id, 2026, {"annual_qty": "12.5"})
    db_session.commit()

    assert result["saved_fields"] == ["annual_qty"]
    value = WorkbookFieldValue.query.filter_by(site_id=site.id, form_id=form.id, field_id=annual_field.id).one()
    created_objects.append(value)
    audit = AuditLog.query.filter_by(
        actor_user_id=submitter.id,
        entity_type="workbook_field_value",
        entity_id=str(value.id),
        action="SAVE_WORKBOOK_VALUE",
    ).one()
    assert audit.created_at is not None
    assert audit.metadata_json["workbook_id"] == workbook.id
    assert audit.metadata_json["field_code"] == "annual_qty"
    assert audit.new_values["raw_value"] == {"present": True, "type": "str"}
    assert "12.5" not in str(audit.old_values)
    assert "12.5" not in str(audit.new_values)
    assert "12.5" not in str(audit.metadata_json)


def test_proof_upload_creates_audit_entry_without_file_bytes(
    client, monkeypatch, make_user, make_site, make_access_grant, make_form,
    make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, created_objects,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
    )
    _mock_save_file(monkeypatch)
    _login(client, ctx["submitter"])

    resp = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"secret"), "proof.txt")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    proof = ProofDocument.query.filter_by(submission_id=ctx["submission"].id).one()
    created_objects.append(proof)
    audit = AuditLog.query.filter_by(
        actor_user_id=ctx["submitter"].id,
        entity_type="proof_document",
        entity_id=str(proof.id),
        action="UPLOAD_PROOF",
    ).one()
    assert audit.created_at is not None
    assert audit.new_values["original_name"] == "proof.txt"
    assert audit.metadata_json["submission_id"] == ctx["submission"].id
    assert "secret" not in str(audit.old_values)
    assert "secret" not in str(audit.new_values)
    assert "secret" not in str(audit.metadata_json)
