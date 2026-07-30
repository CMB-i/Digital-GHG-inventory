"""
Formula lifecycle: once a Formula has ever been published, it is frozen --
changing its calculation logic means creating an entirely new Formula, never
a new version of the published one. create_new_formula_draft is the one
enforcement point for that rule.
"""
import uuid
from datetime import date, datetime, timezone

import pytest

from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.FRMULA.service import (
    create_formula,
    create_new_formula_draft,
    delete_formula,
    publish_formula_version,
)
from app.modules.VALSET.model import ValueSet, ValueSetEntry, ValueSetVersion


class TestFormulaFreezeAfterPublish:
    def test_create_new_draft_refused_once_published(self, make_formula_version, make_user):
        version = make_formula_version("1 + 1", {})
        user = make_user()

        publish_formula_version(version.id, user.id)
        formula = Formula.query.get(version.formula_id)
        assert formula.current_version_id == version.id

        with pytest.raises(ValueError, match="cannot be revised"):
            create_new_formula_draft(formula.id, "2 + 2", {}, user.id)

    def test_create_new_draft_still_allowed_before_first_publish(
        self, make_formula_version, make_user, created_objects
    ):
        version = make_formula_version("1 + 1", {})
        user = make_user()
        formula = Formula.query.get(version.formula_id)
        assert formula.current_version_id is None

        new_version = create_new_formula_draft(formula.id, "2 + 2", {}, user.id)
        created_objects.append(new_version)
        assert new_version.expression == "2 + 2"


class TestFormulaDelete:
    """delete_formula's own reference guard is the inverse of FORMBLD's
    _formulas_referencing_field: instead of scanning tokens for a field code,
    it looks up field_config["formula_version_id"] directly against every
    FormulaVersion this Formula has ever had (not just current_version_id),
    since a draft (unpublished) FieldVersion can hold a formula_version_id
    that was never promoted to current."""

    def test_blocked_when_a_live_published_field_references_the_current_version(
        self, make_formula_version, make_form, make_field, make_user,
    ):
        version = make_formula_version("1 + 1", {})
        publisher = make_user()
        publish_formula_version(version.id, publisher.id)
        formula = Formula.query.get(version.formula_id)

        form, form_version = make_form()
        make_field(
            form, form_version, "calc_field", field_type="calculated",
            field_config={"formula_version_id": version.id},
        )
        actor = make_user()

        with pytest.raises(ValueError, match="calc_field"):
            delete_formula(formula.id, actor.id, "cleanup")

        assert Formula.query.filter_by(id=formula.id, is_deleted=False).first() is not None

    def test_blocked_when_only_a_draft_field_version_references_it(
        self, make_formula_version, make_form, make_field, make_user, created_objects, db_session,
    ):
        """The referencing FieldVersion here is never made current -- proves
        the guard scans every FieldVersion, not just each Field's
        current_version_id."""
        from app.modules.FORMBLD.model import FieldVersion

        version = make_formula_version("1 + 1", {})
        formula = Formula.query.get(version.formula_id)

        form, form_version = make_form()
        field, current_fv = make_field(form, form_version, "calc_field", field_type="number")
        actor = make_user()

        draft_fv = FieldVersion(
            field_id=field.id,
            version_number=2,
            field_name="Calc Field Draft",
            field_type="calculated",
            field_config={"formula_version_id": version.id},
            form_version_id=form_version.id,
            frequency="monthly",
            created_by=actor.id,
        )
        db_session.add(draft_fv)
        db_session.flush()
        created_objects.append(draft_fv)

        assert field.current_version_id == current_fv.id

        with pytest.raises(ValueError, match="calc_field"):
            delete_formula(formula.id, actor.id, "cleanup")

        assert Formula.query.filter_by(id=formula.id, is_deleted=False).first() is not None

    def test_allowed_once_the_blocking_field_is_soft_deleted(
        self, make_formula_version, make_form, make_field, make_user,
    ):
        version = make_formula_version("1 + 1", {})
        publisher = make_user()
        publish_formula_version(version.id, publisher.id)
        formula = Formula.query.get(version.formula_id)

        form, form_version = make_form()
        field, _fv = make_field(
            form, form_version, "calc_field", field_type="calculated",
            field_config={"formula_version_id": version.id},
        )
        actor = make_user()

        field.is_deleted = True
        field.deleted_by = actor.id
        field.deleted_at = datetime.now(timezone.utc)
        field.delete_reason = "Removed from form draft"

        deleted = delete_formula(formula.id, actor.id, "cleanup")
        assert deleted.is_deleted is True

    def test_allowed_when_nothing_references_it(self, make_formula_version, make_user):
        version = make_formula_version("1 + 1", {})
        formula = Formula.query.get(version.formula_id)
        actor = make_user()

        deleted = delete_formula(formula.id, actor.id, "No longer needed")

        assert deleted.is_deleted is True
        assert deleted.delete_reason == "No longer needed"
        assert Formula.query.filter_by(id=formula.id, is_deleted=False).first() is None

    def test_empty_reason_raises(self, make_formula_version, make_user):
        version = make_formula_version("1 + 1", {})
        formula = Formula.query.get(version.formula_id)
        actor = make_user()

        with pytest.raises(ValueError, match="reason"):
            delete_formula(formula.id, actor.id, "   ")

        assert Formula.query.filter_by(id=formula.id, is_deleted=False).first() is not None

    def test_nonexistent_formula_id_raises(self, make_user):
        actor = make_user()

        with pytest.raises(ValueError, match="Formula not found."):
            delete_formula(999999999, actor.id, "cleanup")

    def test_already_deleted_formula_raises(self, make_formula_version, make_user):
        version = make_formula_version("1 + 1", {})
        formula = Formula.query.get(version.formula_id)
        actor = make_user()
        delete_formula(formula.id, actor.id, "first delete")

        with pytest.raises(ValueError, match="Formula not found."):
            delete_formula(formula.id, actor.id, "second delete")


class TestFormulaFormIdScoping:
    """form_id is decided once at formula-creation time by whether the Formula
    Builder's "Form context" selector was left on the sheet it opened from (the
    original sheet's form_id is sent) or changed away from it (form_id is sent
    as None, signalling cross-sheet intent -- see the Save Draft handler in
    static/js/formula_builder.js). This exercises what publish_formula_version
    does with each of those two persisted states."""

    def test_form_id_set_still_rejects_a_different_sheets_field_code(
        self, make_form, make_field, make_user, created_objects,
    ):
        """Selector left untouched -> form_id is the original sheet's id ->
        publish stays scoped to that sheet's fields, so a token that only
        exists on a different sheet is still rejected (the per-form
        uq_fields_code_per_form safety net this scoping exists for)."""
        sheet_a, sheet_a_version = make_form()
        sheet_b, sheet_b_version = make_form()
        make_field(sheet_a, sheet_a_version, "diesel_liters", field_type="number")
        make_field(sheet_b, sheet_b_version, "petrol_liters", field_type="number")

        user = make_user()
        code = f"same-sheet-{uuid.uuid4().hex[:10]}"
        formula = create_formula(
            "Same Sheet Formula", code, "petrol_liters + 1",
            {"petrol_liters": "petrol_liters"}, user.id, form_id=sheet_a.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id).order_by(
            FormulaVersion.version_number.desc()
        ).first()
        created_objects.append(version)

        assert formula.form_id == sheet_a.id

        with pytest.raises(ValueError, match="petrol_liters"):
            publish_formula_version(version.id, user.id)

    def test_form_id_null_after_selector_changed_publishes_across_sheets(
        self, make_form, make_field, make_user, created_objects,
    ):
        """Selector changed away from the original sheet -> form_id is sent
        as None -> publish falls back to the unscoped, system-wide field
        check, so a formula referencing fields from two different sheets
        publishes successfully."""
        sheet_a, sheet_a_version = make_form()
        sheet_b, sheet_b_version = make_form()
        make_field(sheet_a, sheet_a_version, "diesel_liters", field_type="number")
        make_field(sheet_b, sheet_b_version, "petrol_liters", field_type="number")

        user = make_user()
        code = f"cross-sheet-{uuid.uuid4().hex[:10]}"
        formula = create_formula(
            "Cross Sheet Formula", code, "diesel_liters + petrol_liters",
            {"diesel_liters": "diesel_liters", "petrol_liters": "petrol_liters"},
            user.id, form_id=None,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id).order_by(
            FormulaVersion.version_number.desc()
        ).first()
        created_objects.append(version)

        assert formula.form_id is None

        publish_formula_version(version.id, user.id)

        assert version.published_at is not None


class TestFormulaValueSetPublishValidation:
    def _make_value_set(self, db_session, created_objects, system_user, author, status, entry_code):
        suffix = uuid.uuid4().hex[:10]
        value_set = ValueSet(
            name=f"Test Value Set {suffix}",
            code=f"test-vs-{suffix}",
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(value_set)
        db_session.flush()
        created_objects.append(value_set)

        version = ValueSetVersion(
            value_set_id=value_set.id,
            version_number=1,
            status=status,
            effective_from=date.today(),
            created_by=author.id,
        )
        db_session.add(version)
        db_session.flush()
        created_objects.append(version)

        entry = ValueSetEntry(
            value_set_version_id=version.id,
            entry_code=entry_code,
            entry_label=entry_code,
            display_order=1,
            is_active=True,
            created_by=author.id,
            updated_by=author.id,
        )
        db_session.add(entry)
        db_session.flush()
        created_objects.append(entry)
        value_set.current_version_id = version.id
        db_session.flush()
        return value_set, version, entry

    @pytest.mark.parametrize("status", ["Draft", "Rejected"])
    def test_publish_rejects_value_set_entries_from_unapproved_versions(
        self, db_session, created_objects, system_user, make_user, status,
    ):
        author = make_user()
        entry_code = f"VS_TOKEN_{uuid.uuid4().hex[:8]}"
        self._make_value_set(db_session, created_objects, system_user, author, status, entry_code)
        formula = create_formula(
            "Unapproved Value Set Formula",
            f"unapproved-vs-{uuid.uuid4().hex[:10]}",
            f"{entry_code} + 1",
            {entry_code: entry_code},
            author.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id).one()
        created_objects.append(version)

        with pytest.raises(ValueError, match=entry_code):
            publish_formula_version(version.id, author.id)

    def test_publish_accepts_value_set_entries_from_approved_version(
        self, db_session, created_objects, system_user, make_user,
    ):
        author = make_user()
        entry_code = f"VS_TOKEN_{uuid.uuid4().hex[:8]}"
        self._make_value_set(db_session, created_objects, system_user, author, "Approved", entry_code)
        formula = create_formula(
            "Approved Value Set Formula",
            f"approved-vs-{uuid.uuid4().hex[:10]}",
            f"{entry_code} + 1",
            {entry_code: entry_code},
            author.id,
        )
        created_objects.append(formula)
        version = FormulaVersion.query.filter_by(formula_id=formula.id).one()
        created_objects.append(version)

        publish_formula_version(version.id, author.id)

        assert version.published_at is not None


class TestFormulaBuilderFormVersionOptions:
    """The "Form context" selector's option list (FRMULA/views.py's index(),
    form_versions) is scoped to sheets in the SAME workbook as the sheet the
    builder was opened from -- cross-sheet formulas are only ever meant to
    span sheets within one workbook (cross-site aggregation is RPTBLD's job,
    not FRMULA's). form.name is rendered exactly once in
    formula_builder.html, inside this selector's <option> loop, so checking
    for it in the response body is an unambiguous stand-in for "is this Form
    an option in the dropdown"."""

    def test_only_includes_sibling_sheets_from_the_same_workbook(
        self, client, make_site, make_form, make_workbook, make_user,
        make_access_grant, db_session, created_objects,
    ):
        from app.modules.WKBK.model import WorkbookForm

        site = make_site()
        form_a, form_a_version = make_form()
        form_b, form_b_version = make_form()
        form_c, _form_c_version = make_form()

        workbook = make_workbook(form_a, site)
        wf_b = WorkbookForm(workbook_id=workbook.id, form_id=form_b.id, display_order=20)
        db_session.add(wf_b)
        db_session.flush()
        created_objects.append(wf_b)
        # form_c is left unattached to this (or any) workbook -- an unrelated sheet.

        user = make_user()
        make_access_grant(user, "formula", scope_type="global", can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get(f"/module/FRMULA/?form_id={form_a.id}&version_id={form_a_version.id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        assert form_a.name in html
        assert form_b.name in html
        assert form_c.name not in html

    def test_sheet_with_no_workbook_falls_back_to_itself_only(
        self, client, make_form, make_user, make_access_grant,
    ):
        form_a, form_a_version = make_form()
        form_b, _form_b_version = make_form()  # unrelated sheet, also no workbook

        user = make_user()
        make_access_grant(user, "formula", scope_type="global", can_view=True)
        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        resp = client.get(f"/module/FRMULA/?form_id={form_a.id}&version_id={form_a_version.id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        assert form_a.name in html
        assert form_b.name not in html
