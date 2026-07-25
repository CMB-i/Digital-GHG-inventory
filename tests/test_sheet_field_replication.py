"""
Sheet/field replication: every copy here is a fully independent, one-time
snapshot -- new Field/FieldVersion/Formula/FormulaVersion rows, never a
linked/synced reference back to the original. Feature 1 (copy_fields_to_sheet)
copies a hand-picked subset of fields onto an existing destination sheet's
current draft version. Feature 2 (copy_sheet_to_workbook) clones an entire
sheet (sections + every field) into a brand-new Form attached to a
destination workbook. Both share clone_fields_with_formulas() for the actual
field/formula clone + remap logic.
"""
import pytest

from app.modules.FORMBLD.model import Field, FieldVersion, Form, FormVersion
from app.modules.FORMBLD.service import copy_fields_to_sheet, copy_sheet_to_workbook
from app.modules.FRMULA.model import Formula, FormulaVersion
from app.modules.FRMULA.service import create_formula, publish_formula_version
from app.modules.WKBK.model import WorkbookForm
from app.modules.WKBK.service import create_workbook


def _publish_formula(user, form, expression, tokens, name, code):
    formula = create_formula(name, code, expression, tokens, user.id, form_id=form.id if form else None)
    version = FormulaVersion.query.filter_by(formula_id=formula.id, version_number=1).one()
    publish_formula_version(version.id, user.id)
    return formula, version


class TestCopyFieldsToSheet:
    def test_bulk_copy_including_calculated_field_remaps_formula_and_publishes_it(
        self, make_form, make_field, make_user, created_objects,
    ):
        source_form, source_version = make_form()
        dest_form, dest_version = make_form()
        actor = make_user()

        make_field(
            source_form, source_version, "diesel_liters", field_type="number",
            field_config={"unit": "L"}, display_order=10,
        )
        formula, formula_version = _publish_formula(
            actor, source_form, "diesel_liters * 2.68", {"diesel_liters": {}},
            "Diesel Emissions", "diesel-emissions-src",
        )
        created_objects.extend([formula, formula_version])
        make_field(
            source_form, source_version, "diesel_co2e", field_type="calculated",
            field_config={
                "formula_version_id": formula_version.id,
                "expression": "diesel_liters * 2.68",
                "tokens": {"diesel_liters": {}},
                "field_scope": "monthly",
                "result_role": "monthly_calculated",
                "display_region": "monthly_table",
            },
            display_order=20,
        )

        destination_form, destination_version, new_fields = copy_fields_to_sheet(
            source_version.id, ["diesel_liters", "diesel_co2e"], dest_form.id, actor.id,
        )
        created_objects.extend(new_fields)
        created_objects.append(destination_version)

        assert destination_form.id == dest_form.id
        # dest_form's fixture-created version is Published -- a new Draft
        # version must have been created via create_new_form_version_draft.
        assert destination_version.status == "Draft"
        assert destination_version.id != dest_version.id
        assert len(new_fields) == 2

        new_numeric = Field.query.filter_by(
            form_id=dest_form.id, field_code="diesel_liters_copy", is_deleted=False
        ).one()
        new_calc = Field.query.filter_by(
            form_id=dest_form.id, field_code="diesel_co2e_copy", is_deleted=False
        ).one()
        created_objects.append(new_numeric)
        created_objects.append(new_calc)

        new_numeric_fv = FieldVersion.query.filter_by(field_id=new_numeric.id, is_deleted=False).one()
        assert new_numeric_fv.field_config["unit"] == "L"

        new_calc_fv = FieldVersion.query.filter_by(field_id=new_calc.id, is_deleted=False).one()
        new_formula_version_id = new_calc_fv.field_config["formula_version_id"]
        assert new_formula_version_id != formula_version.id

        new_formula_version = FormulaVersion.query.get(new_formula_version_id)
        assert new_formula_version.published_at is not None
        assert new_formula_version.tokens == {"diesel_liters_copy": {}}
        assert new_formula_version.expression == "diesel_liters_copy * 2.68"
        assert new_calc_fv.field_config["expression"] == "diesel_liters_copy * 2.68"
        assert new_calc_fv.field_config["tokens"] == {"diesel_liters_copy": {}}

        new_formula = Formula.query.get(new_formula_version.formula_id)
        assert new_formula.form_id == dest_form.id
        assert new_formula.code != formula.code
        assert new_formula.current_version_id == new_formula_version.id

        # Original formula/field untouched.
        assert Formula.query.get(formula.id).code == formula.code
        assert FormulaVersion.query.get(formula_version.id).tokens == {"diesel_liters": {}}

    def test_bulk_copy_calculated_field_without_its_dependency_field_raises(
        self, make_form, make_field, make_user, created_objects,
    ):
        source_form, source_version = make_form()
        dest_form, _dest_version = make_form()
        actor = make_user()

        make_field(source_form, source_version, "diesel_liters", field_type="number")
        formula, formula_version = _publish_formula(
            actor, source_form, "diesel_liters * 2.68", {"diesel_liters": {}},
            "Diesel Emissions", "diesel-emissions-solo",
        )
        created_objects.extend([formula, formula_version])
        make_field(
            source_form, source_version, "diesel_co2e", field_type="calculated",
            field_config={"formula_version_id": formula_version.id},
            display_order=20,
        )

        # Only the calculated field is selected -- its dependency
        # ("diesel_liters") is not part of this copy batch.
        with pytest.raises(ValueError, match="diesel_liters"):
            copy_fields_to_sheet(source_version.id, ["diesel_co2e"], dest_form.id, actor.id)

        # Nothing should have been created on the destination sheet.
        assert Field.query.filter_by(form_id=dest_form.id, is_deleted=False).count() == 0

    def test_bulk_copy_plain_field_generates_unique_code_without_touching_formulas(
        self, make_form, make_field, make_user, created_objects,
    ):
        source_form, source_version = make_form()
        dest_form, _dest_version = make_form()
        actor = make_user()

        make_field(source_form, source_version, "diesel_liters", field_type="number", field_config={"unit": "L"})

        destination_form, destination_version, new_fields = copy_fields_to_sheet(
            source_version.id, ["diesel_liters"], dest_form.id, actor.id,
        )
        created_objects.extend(new_fields)
        created_objects.append(destination_version)

        assert len(new_fields) == 1
        assert new_fields[0].field_code == "diesel_liters_copy"
        assert Formula.query.count() == 0

    def test_bulk_copy_generates_next_available_code_when_first_candidate_taken(
        self, make_form, make_field, make_user, created_objects,
    ):
        source_form, source_version = make_form()
        dest_form, dest_version = make_form()
        actor = make_user()

        make_field(source_form, source_version, "diesel_liters", field_type="number")
        # Destination sheet already has a field code that would collide with
        # the first-choice generated code.
        make_field(dest_form, dest_version, "diesel_liters_copy", field_type="number")

        destination_form, destination_version, new_fields = copy_fields_to_sheet(
            source_version.id, ["diesel_liters"], dest_form.id, actor.id,
        )
        created_objects.extend(new_fields)
        created_objects.append(destination_version)

        assert new_fields[0].field_code == "diesel_liters_copy_2"

    def test_bulk_copy_remaps_legacy_null_form_id_formula_that_resolves(
        self, make_form, make_field, make_user, created_objects,
    ):
        """A formula with form_id = None predates that column and has no
        reliable owning-sheet attribution (see Formula.form_id's own model
        comment) -- but in the overwhelming majority of real cases it's still
        a genuine same-sheet formula. Its tokens resolving cleanly against
        the fields being copied here confirms it's remapped and republished
        like any explicitly-scoped formula, not left pointing at the
        original sheet (the bug this guards against)."""
        source_form, source_version = make_form()
        dest_form, _dest_version = make_form()
        actor = make_user()

        make_field(source_form, source_version, "diesel_liters", field_type="number")
        formula, formula_version = _publish_formula(
            actor, None, "diesel_liters * 2.68", {"diesel_liters": {}},
            "Diesel Emissions", "diesel-emissions-legacy",
        )
        assert formula.form_id is None
        created_objects.extend([formula, formula_version])
        make_field(
            source_form, source_version, "diesel_co2e", field_type="calculated",
            field_config={"formula_version_id": formula_version.id},
            display_order=20,
        )

        destination_form, destination_version, new_fields = copy_fields_to_sheet(
            source_version.id, ["diesel_liters", "diesel_co2e"], dest_form.id, actor.id,
        )
        created_objects.extend(new_fields)
        created_objects.append(destination_version)

        new_calc = Field.query.filter_by(
            form_id=dest_form.id, field_code="diesel_co2e_copy", is_deleted=False
        ).one()
        created_objects.append(new_calc)
        new_calc_fv = FieldVersion.query.filter_by(field_id=new_calc.id, is_deleted=False).one()

        new_formula_version_id = new_calc_fv.field_config["formula_version_id"]
        assert new_formula_version_id != formula_version.id
        new_formula_version = FormulaVersion.query.get(new_formula_version_id)
        assert new_formula_version.published_at is not None
        assert new_formula_version.tokens == {"diesel_liters_copy": {}}
        assert new_formula_version.expression == "diesel_liters_copy * 2.68"

        new_formula = Formula.query.get(new_formula_version.formula_id)
        assert new_formula.form_id == dest_form.id

    def test_bulk_copy_raises_when_formula_belongs_to_a_different_form_id(
        self, make_form, make_field, make_user, created_objects,
    ):
        """A formula with a form_id that IS set but doesn't match the source
        sheet is a genuine cross-sheet reference, which shouldn't be
        possible under the current formula-scoping rules -- this must raise,
        not silently copy the broken reference forward."""
        source_form, source_version = make_form()
        other_form, other_version = make_form()
        dest_form, _dest_version = make_form()
        actor = make_user()

        make_field(source_form, source_version, "diesel_liters", field_type="number")
        # The formula genuinely belongs to other_form -- give it a matching
        # field there too, so publish_formula_version's own token validation
        # (scoped to the formula's own form_id) succeeds during setup.
        make_field(other_form, other_version, "diesel_liters", field_type="number")
        formula, formula_version = _publish_formula(
            actor, other_form, "diesel_liters * 2.68", {"diesel_liters": {}},
            "Diesel Emissions", "diesel-emissions-other-sheet",
        )
        created_objects.extend([formula, formula_version])
        # Lower display_order than "diesel_liters" (default 10) -- processed
        # first, so the raise happens before any field is created, and the
        # "nothing created" assertion below holds without needing a mid-test
        # rollback (this suite never commits within a test, so a manual
        # rollback here would also wipe the fixture rows created above).
        make_field(
            source_form, source_version, "diesel_co2e", field_type="calculated",
            field_config={"formula_version_id": formula_version.id},
            display_order=5,
        )

        with pytest.raises(ValueError, match="different sheet"):
            copy_fields_to_sheet(
                source_version.id, ["diesel_liters", "diesel_co2e"], dest_form.id, actor.id,
            )

        assert Field.query.filter_by(form_id=dest_form.id, is_deleted=False).count() == 0


class TestCopySheetToWorkbook:
    def test_copy_sheet_creates_new_workbook_form_draft_and_leaves_original_untouched(
        self, make_form, make_field, make_site, make_user, make_workbook, created_objects,
    ):
        source_form, source_version = make_form()  # Published, per fixture
        assert source_version.status == "Published"

        make_field(source_form, source_version, "diesel_liters", field_type="number", field_config={"unit": "L"})
        site = make_site()
        actor = make_user()
        source_workbook = make_workbook(source_form, site)

        dest_workbook = create_workbook(
            "Destination Workbook", f"dest-wbk-{actor.id}", "", actor.id,
        )
        created_objects.append(dest_workbook)

        new_form, new_version, workbook_form = copy_sheet_to_workbook(
            source_form.id, dest_workbook.id, actor.id,
        )
        created_objects.extend([new_form, new_version, workbook_form])

        # New, independent Form -- different id and code.
        assert new_form.id != source_form.id
        assert new_form.code != source_form.code

        # New sheet always starts Draft, even though the source is Published.
        assert new_version.status == "Draft"
        assert new_version.form_id == new_form.id

        # New WorkbookForm row links the new Form to the destination workbook.
        assert workbook_form.workbook_id == dest_workbook.id
        assert workbook_form.form_id == new_form.id
        assert WorkbookForm.query.filter_by(workbook_id=dest_workbook.id, form_id=new_form.id).first() is not None

        # The original sheet's own WorkbookForm rows are untouched -- still
        # exactly the one row from make_workbook(), still pointing at the
        # original workbook.
        original_links = WorkbookForm.query.filter_by(form_id=source_form.id).all()
        assert len(original_links) == 1
        assert original_links[0].workbook_id == source_workbook.id

        # Fields were cloned onto the new sheet with fresh codes.
        new_fields = Field.query.filter_by(form_id=new_form.id, is_deleted=False).all()
        assert len(new_fields) == 1
        assert new_fields[0].field_code == "diesel_liters_copy"
        new_fv = FieldVersion.query.filter_by(field_id=new_fields[0].id, is_deleted=False).one()
        assert new_fv.field_config["unit"] == "L"
        assert new_fv.form_version_id == new_version.id

    def test_copy_sheet_clones_sections_and_resolves_field_section_by_code(
        self, make_form, make_field, make_user, created_objects, db_session,
    ):
        from app.modules.FORMBLD.model import FormSection

        source_form, source_version = make_form()
        actor = make_user()

        section = FormSection(
            form_id=source_form.id,
            form_version_id=source_version.id,
            name="Fuel",
            code="fuel",
            layout_type="monthly_table",
            display_order=1,
            description="",
            created_by=actor.id,
            updated_by=actor.id,
        )
        db_session.add(section)
        db_session.flush()
        created_objects.append(section)

        field, field_version = make_field(source_form, source_version, "diesel_liters", field_type="number")
        field_version.section_id = section.id
        db_session.flush()

        dest_workbook = create_workbook("Fuel Destination", f"fuel-dest-{actor.id}", "", actor.id)
        created_objects.append(dest_workbook)

        new_form, new_version, workbook_form = copy_sheet_to_workbook(source_form.id, dest_workbook.id, actor.id)
        created_objects.extend([new_form, new_version, workbook_form])

        new_section = FormSection.query.filter_by(
            form_version_id=new_version.id, code="fuel", is_deleted=False
        ).one()
        created_objects.append(new_section)
        assert new_section.name == "Fuel"

        new_field = Field.query.filter_by(form_id=new_form.id, field_code="diesel_liters_copy").one()
        new_fv = FieldVersion.query.filter_by(field_id=new_field.id, is_deleted=False).one()
        assert new_fv.section_id == new_section.id
