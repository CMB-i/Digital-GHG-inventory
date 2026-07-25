"""
Formula lifecycle: once a Formula has ever been published, it is frozen --
changing its calculation logic means creating an entirely new Formula, never
a new version of the published one. create_new_formula_draft is the one
enforcement point for that rule.
"""
from datetime import datetime, timezone

import pytest

from app.modules.FRMULA.model import Formula
from app.modules.FRMULA.service import create_new_formula_draft, delete_formula, publish_formula_version


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
