import io
from pathlib import Path

from app.modules.AUDITL.model import AuditLog
from app.modules.SUBMIT.model import ProofDocument, Submission, WorkbookFieldValue


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_session_version"] = user.session_version


def _workbook_scoped_submission(
    make_user, make_site, make_access_grant, make_form, make_field,
    make_reporting_period, make_workflow, make_workbook, make_submission,
    file_field_config=None,
):
    submitter = make_user()
    unassigned = make_user()
    approver = make_user()
    site = make_site()
    form, form_version = make_form()
    number_field, number_version = make_field(form, form_version, "field_a", field_type="number")
    file_field, file_version = make_field(
        form,
        form_version,
        "proof_doc",
        field_type="file",
        field_config=file_field_config,
    )
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
    def fake_save_file(file_storage, **kwargs):
        return {
            "storage_key": "proofs/fake-proof.txt",
            "original_name": file_storage.filename,
            "mime_type": "text/plain",
            "file_size_bytes": 6,
        }

    monkeypatch.setattr("app.modules.SUBMIT.views.save_file", fake_save_file)


def _use_temp_upload_folder(monkeypatch, tmp_path):
    import app.common.file_storage as file_storage

    monkeypatch.setattr(file_storage, "UPLOAD_FOLDER", str(tmp_path))


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


def test_upload_to_non_file_field_is_rejected(
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
    _login(client, ctx["submitter"])

    resp = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/field_a",
        data={"file": (io.BytesIO(b"proof"), "proof.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "only allowed for file fields" in resp.get_json()["error"]
    assert ProofDocument.query.filter_by(submission_id=ctx["submission"].id).count() == 0


def test_upload_rejects_mime_allowed_globally_but_not_by_field_contract(
    client, monkeypatch, make_user, make_site, make_access_grant, make_form,
    make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
        file_field_config={"accepted_mime_types": ["application/pdf"]},
    )
    db_session.commit()
    _mock_save_file(monkeypatch)
    _login(client, ctx["submitter"])

    resp = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"a,b\n1,2\n"), "proof.csv", "text/csv")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "not allowed for this field" in resp.get_json()["error"]
    assert ProofDocument.query.filter_by(submission_id=ctx["submission"].id).count() == 0


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


def test_repeated_upload_keeps_one_active_proof_and_review_sees_newest(
    client, monkeypatch, tmp_path, make_user, make_site, make_access_grant,
    make_form, make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session, created_objects,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
        file_field_config={"accepted_mime_types": ["application/pdf"]},
    )
    make_access_grant(ctx["submitter"], "submission", scope_type="site", scope_site_id=ctx["site"].id, can_view=True, can_approve=True)
    db_session.commit()
    _use_temp_upload_folder(monkeypatch, tmp_path)
    _login(client, ctx["submitter"])

    first = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"first"), "first.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )
    second = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"second"), "second.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    proofs = ProofDocument.query.filter_by(
        submission_id=ctx["submission"].id,
        field_id=ctx["file_field"].id,
    ).order_by(ProofDocument.uploaded_at.asc(), ProofDocument.id.asc()).all()
    created_objects.extend(proofs)
    active = [proof for proof in proofs if not proof.is_deleted]
    superseded = [proof for proof in proofs if proof.is_deleted]
    assert len(active) == 1
    assert len(superseded) == 1
    assert active[0].original_name == "second.pdf"
    assert superseded[0].original_name == "first.pdf"

    details = client.get(f"/module/SUBMIT/api/submissions/{ctx['submission'].id}")
    review = client.get(f"/module/APPROV/api/submissions/{ctx['submission'].id}")
    download = client.get(f"/module/SUBMIT/submissions/download/{active[0].storage_key}")

    assert details.get_json()["values"]["proof_doc"]["original_name"] == "second.pdf"
    assert review.get_json()["data"]["proofs"][str(ctx["file_field"].id)]["original_name"] == "second.pdf"
    assert download.status_code == 200


def test_failed_metadata_commit_removes_newly_saved_file(
    client, monkeypatch, tmp_path, make_user, make_site, make_access_grant,
    make_form, make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
        file_field_config={"accepted_mime_types": ["application/pdf"]},
    )
    db_session.commit()
    _use_temp_upload_folder(monkeypatch, tmp_path)
    _login(client, ctx["submitter"])

    def fail_audit(*args, **kwargs):
        raise RuntimeError("forced metadata failure")

    monkeypatch.setattr("app.modules.AUDITL.service.log_audit", fail_audit)

    resp = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"orphan"), "orphan.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert list(Path(tmp_path).rglob("*.*")) == []


def test_field_specific_upload_size_limit_accepts_under_and_rejects_over(
    client, monkeypatch, tmp_path, make_user, make_site, make_access_grant,
    make_form, make_field, make_reporting_period, make_workflow, make_workbook,
    make_submission, db_session, created_objects,
):
    ctx = _workbook_scoped_submission(
        make_user, make_site, make_access_grant, make_form, make_field,
        make_reporting_period, make_workflow, make_workbook, make_submission,
        file_field_config={"accepted_mime_types": ["application/pdf"], "max_file_size_bytes": 6},
    )
    db_session.commit()
    _use_temp_upload_folder(monkeypatch, tmp_path)
    _login(client, ctx["submitter"])

    under = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"123456"), "under.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )
    over = client.post(
        f"/module/SUBMIT/api/submissions/{ctx['submission'].id}/proof/proof_doc",
        data={"file": (io.BytesIO(b"1234567"), "over.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )

    assert under.status_code == 200
    assert over.status_code == 400
    assert "too large" in over.get_json()["error"]
    proofs = ProofDocument.query.filter_by(submission_id=ctx["submission"].id).all()
    created_objects.extend(proofs)
    assert [proof.original_name for proof in proofs if not proof.is_deleted] == ["under.pdf"]


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
    assert upload.status_code == 200, upload.get_json()
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

    assert resp.status_code == 200, resp.get_json()
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
