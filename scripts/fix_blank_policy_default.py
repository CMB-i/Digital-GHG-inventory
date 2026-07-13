"""
fix_blank_policy_default.py — One-time cleanup: removes the leftover
"strict" blank_policy that normalize_calculated_field_config (and its JS
mirror in form_builder.js) used to hardcode onto every annual-result
calculated field at save time, before the "partial" blank_policy existed.

No UI has ever let a Sheet Builder user choose blank_policy deliberately --
it was purely `config.get("blank_policy") or "strict"`, an unconditional
default with nothing behind it. Every persisted "strict" value predating
this cleanup is therefore treated as an unintentional leftover, not a real
choice, and is removed so the field falls back to SUBMIT's new
DEFAULT_AGGREGATE_BLANK_POLICY ("partial"). The save-time hardcoding itself
has also been removed from normalize_calculated_field_config and
form_builder.js, so this doesn't get reintroduced the next time one of these
fields is edited and saved.

IMPORTANT: this targets every non-deleted FieldVersion row directly, NOT
Field.current_version_id. Field.current_version_id is set on every draft
save regardless of publish status (a documented, pre-existing inconsistency
-- see README's Consistency Guidelines, "current_version_id always means the
currently published version... Field.current_version_id is the one
exception"), so for a form with an in-progress unpublished Draft it points
at the DRAFT's FieldVersion, not the one actually served by
compose_annual_workbook_data (which reads Form.current_version_id, the
published version). An earlier version of this script used
Field.current_version_id and, on a form with a draft in progress, fixed the
draft's FieldVersion while leaving the live, published one -- the one
end users actually see -- untouched. Querying FieldVersion directly sidesteps
that distinction entirely: it's is_deleted=False that marks "the live row for
whichever FormVersion this belongs to" (draft, published, or archived), and
every FormVersion's own current FieldVersion needs the same fix regardless of
which FormVersion happens to be Form.current_version_id right now.

Checked the live dev database before writing this: of every non-deleted
calculated FieldVersion, 10 rows across 2 fields had "strict" persisted --
7 on field_1782362396474 (form 10, "Total Non Coastal": 1 on the then-Draft
form_version 66, 1 on the then-Published form_version 64, 5 on Archived
versions) and 3 on field_1781850201398 (form 14: all on Archived versions,
none on the live Published one). No other field had any non-default value
anywhere -- no evidence of a deliberate, non-default blank_policy choice.

Idempotent -- safe to re-run; a second run finds nothing left to fix.

Run manually:
    python scripts/fix_blank_policy_default.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.FORMBLD.model import Field, Form, FieldVersion, FormVersion


def run():
    app = create_app()
    with app.app_context():
        versions = (
            FieldVersion.query.filter(
                FieldVersion.is_deleted == False,
                FieldVersion.field_type == "calculated",
            )
            .all()
        )

        # For the report only: which FormVersion each row belongs to, and
        # whether that's the form's currently-published version.
        form_current_version_by_form_id = {
            form.id: form.current_version_id for form in Form.query.all()
        }
        form_id_by_form_version_id = {
            fv.id: fv.form_id for fv in FormVersion.query.all()
        }

        updated = []
        for version in versions:
            config = version.field_config or {}
            if config.get("blank_policy") != "strict":
                continue

            field = Field.query.get(version.field_id)
            form_id = form_id_by_form_version_id.get(version.form_version_id)
            is_live = form_current_version_by_form_id.get(form_id) == version.form_version_id

            new_config = dict(config)
            new_config.pop("blank_policy", None)
            version.field_config = new_config
            updated.append({
                "form_id": form_id,
                "field_code": field.field_code if field else "?",
                "field_version_id": version.id,
                "form_version_id": version.form_version_id,
                "display_region": config.get("display_region"),
                "is_live": is_live,
            })

        if updated:
            db.session.commit()

        if not updated:
            print("Nothing to update -- no calculated FieldVersion had a persisted 'strict' blank_policy.")
            return

        print(f"Removed leftover 'strict' blank_policy from {len(updated)} FieldVersion row(s):")
        for row in updated:
            live_tag = "LIVE (published)" if row["is_live"] else "not live"
            print(
                f"  form_id={row['form_id']} field_code={row['field_code']} "
                f"field_version_id={row['field_version_id']} form_version_id={row['form_version_id']} "
                f"display_region={row['display_region']} [{live_tag}]"
            )


if __name__ == "__main__":
    run()
