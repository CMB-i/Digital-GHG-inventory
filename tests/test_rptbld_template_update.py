"""
update_report_template's description handling. Found via a real regression:
this template's description (set correctly earlier) had been silently
blanked to "" at some point -- traced to update_report_template
unconditionally doing `t.description = description`, unlike its own `name`
field a few lines above (`if name: t.name = name.strip()`). Any save where
the caller's description happened to be empty/blank at that moment wiped a
previously-set one with no warning. Fixed to mirror name's own guard.
"""
from app.modules.RPTBLD.service import create_report_template, update_report_template


class TestUpdateReportTemplateDescription:
    def _make_template(self, user_id, description="Original description"):
        template = create_report_template(
            "Description Test", f"test-desc-{user_id}", description,
            "global", None, {}, user_id,
        )
        return template

    def test_empty_string_description_does_not_wipe_existing_value(self, make_user, created_objects):
        user = make_user()
        template = self._make_template(user.id)
        created_objects.append(template)

        update_report_template(
            template_id=template.id, name=template.name, description="",
            scope_type=template.scope_type, scope_site_id=template.scope_site_id,
            config_json=None, user_id=user.id,
        )

        assert template.description == "Original description"

    def test_whitespace_only_description_does_not_wipe_existing_value(self, make_user, created_objects):
        user = make_user()
        template = self._make_template(user.id)
        created_objects.append(template)

        update_report_template(
            template_id=template.id, name=template.name, description="   ",
            scope_type=template.scope_type, scope_site_id=template.scope_site_id,
            config_json=None, user_id=user.id,
        )

        assert template.description == "Original description"

    def test_real_description_still_updates_correctly(self, make_user, created_objects):
        user = make_user()
        template = self._make_template(user.id)
        created_objects.append(template)

        update_report_template(
            template_id=template.id, name=template.name, description="Updated description",
            scope_type=template.scope_type, scope_site_id=template.scope_site_id,
            config_json=None, user_id=user.id,
        )

        assert template.description == "Updated description"

    def test_round_trip_survives_repeated_saves_with_same_value(self, make_user, created_objects):
        """Mirrors the wizard's actual usage: every "Save & Continue" click
        resends the same description across several steps -- it must not
        degrade or blank out across repeated identical saves."""
        user = make_user()
        template = self._make_template(user.id, description="Stable description")
        created_objects.append(template)

        for _ in range(5):
            update_report_template(
                template_id=template.id, name=template.name, description="Stable description",
                scope_type=template.scope_type, scope_site_id=template.scope_site_id,
                config_json=None, user_id=user.id,
            )

        assert template.description == "Stable description"
