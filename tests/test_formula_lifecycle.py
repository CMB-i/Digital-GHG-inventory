"""
Formula lifecycle: once a Formula has ever been published, it is frozen --
changing its calculation logic means creating an entirely new Formula, never
a new version of the published one. create_new_formula_draft is the one
enforcement point for that rule.
"""
import pytest

from app.modules.FRMULA.model import Formula
from app.modules.FRMULA.service import create_new_formula_draft, publish_formula_version


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
