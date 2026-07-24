"""
reset_dev_data.py — One-time dev data reset script.

Deletes all rows from every app table in FK-safe order, preserving only the
initial admin user (admin@example.com) and their access_matrix rows.
app_config and alembic/migration tables are never touched.

Run manually:
    python scripts/reset_dev_data.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect as sa_inspect, text

from app import create_app
from app.database import db

ADMIN_EMAIL = "admin@example.com"


def delete(table: str, where: str = "", params: dict = None) -> int:
    sql = f"DELETE FROM {table}"
    if where:
        sql += f" WHERE {where}"
    result = db.session.execute(text(sql), params or {})
    return result.rowcount


def run() -> None:
    confirm = input(
        "\nThis will delete all data except the initial admin.\n"
        "Type CONFIRM to proceed: "
    ).strip()
    if confirm != "CONFIRM":
        print("Aborted.")
        return

    app = create_app()
    with app.app_context():
        # Locate admin user — abort if missing so we never delete everything.
        row = db.session.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": ADMIN_EMAIL},
        ).fetchone()
        if not row:
            print(f"\nERROR: No user found with email '{ADMIN_EMAIL}'. Aborting.")
            return
        admin_id = row[0]
        print(f"\nAdmin user confirmed: id={admin_id} ({ADMIN_EMAIL})")
        print("Starting reset...\n")

        existing_tables = set(sa_inspect(db.engine).get_table_names())

        try:
            # ----------------------------------------------------------------
            # Break circular FK loops before any deletions.
            # forms.current_version_id → form_versions.id  (and vice-versa)
            # fields.current_version_id → field_versions.id (and vice-versa)
            # ----------------------------------------------------------------
            db.session.execute(text("UPDATE forms SET current_version_id = NULL"))
            db.session.execute(text("UPDATE fields SET current_version_id = NULL"))

            # ----------------------------------------------------------------
            # Delete in FK-safe order.
            # Indented groups share a parent they depend on.
            # ----------------------------------------------------------------

            # Submission-level leaf tables
            n = delete("approval_actions");        print(f"  approval_actions:         {n} rows")
            n = delete("submission_value_issues"); print(f"  submission_value_issues:  {n} rows")
            n = delete("submission_values");       print(f"  submission_values:        {n} rows")
            n = delete("proof_documents");         print(f"  proof_documents:          {n} rows")
            n = delete("issue_comments");          print(f"  issue_comments:           {n} rows")
            n = delete("issues");                  print(f"  issues:                   {n} rows")
            n = delete("notifications");           print(f"  notifications:            {n} rows")
            n = delete("workbook_field_values");   print(f"  workbook_field_values:    {n} rows")

            # Submissions and packages
            n = delete("submissions");             print(f"  submissions:              {n} rows")
            if "submission_packages" in existing_tables:
                n = delete("submission_packages"); print(f"  submission_packages:      {n} rows")
            else:
                print(f"  submission_packages:      (table not found, skipped)")

            # Workflow hierarchy
            n = delete("workflow_level_approvers"); print(f"  workflow_level_approvers: {n} rows")
            n = delete("workflow_levels");          print(f"  workflow_levels:          {n} rows")
            db.session.execute(text("UPDATE workflows SET current_version_id = NULL"))
            db.session.execute(text("UPDATE forms SET current_version_id = NULL"))
            db.session.execute(text("UPDATE formulas SET current_version_id = NULL"))
            db.session.execute(text("UPDATE value_sets SET current_version_id = NULL"))
            db.session.execute(text("UPDATE fields SET current_version_id = NULL"))
            n = delete("workflow_versions");        print(f"  workflow_versions:        {n} rows")
            n = delete("workflows");               print(f"  workflows:                {n} rows")

            # Form/field hierarchy (circular FKs already nulled above)
            n = delete("field_versions");  print(f"  field_versions:           {n} rows")
            n = delete("form_sections");   print(f"  form_sections:            {n} rows")
            n = delete("fields");          print(f"  fields:                   {n} rows")
            n = delete("form_versions");   print(f"  form_versions:            {n} rows")
            n = delete("forms");           print(f"  forms:                    {n} rows")

            # Value sets
            n = delete("value_set_entries");  print(f"  value_set_entries:        {n} rows")
            n = delete("value_set_versions"); print(f"  value_set_versions:       {n} rows")
            n = delete("value_sets");         print(f"  value_sets:               {n} rows")

            # Formulas
            n = delete("formula_versions"); print(f"  formula_versions:         {n} rows")
            n = delete("formulas");         print(f"  formulas:                 {n} rows")

            # Reporting setup
            n = delete("report_templates");   print(f"  report_templates:         {n} rows")
            n = delete("reporting_periods");  print(f"  reporting_periods:        {n} rows")

            # audit_logs references users (nullable FK) — clear before users
            n = delete("audit_logs"); print(f"  audit_logs:               {n} rows")

            # Access matrix: keep admin's rows
            n = delete("access_matrix");           print(f"  access_matrix:            {n} rows")

            # Sites have no remaining dependents at this point
            n = delete("sites"); print(f"  sites:                    {n} rows")

            # Users: keep admin
            n = delete("users", "id != :admin_id", {"admin_id": admin_id})
            print(f"  users:                    {n} rows  (admin kept)")

            # Restore full admin permissions (one row per entity_type)
            db.session.execute(text("""
                INSERT INTO access_matrix (
                    user_id, scope_type, scope_site_id, scope_region_id,
                    entity_type, entity_id,
                    can_view, can_create, can_edit, can_delete,
                    can_submit, can_approve, can_reject, can_reopen, can_export,
                    can_manage_forms, can_manage_users,
                    created_at, updated_at, is_deleted
                ) VALUES
                (:uid,'global',NULL,NULL,'user',NULL,        true,true,true,true, false,false,false,false,false, false,true, NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'site',NULL,        true,true,true,true, false,false,false,false,true,  false,false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'form',NULL,        true,true,true,true, false,false,false,false,true,  true, false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'workflow',NULL,    true,true,true,true, false,false,false,false,false, true, false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'submission',NULL,  true,true,true,true, true,true,true,true,true,      false,false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'report',NULL,      true,true,true,true, false,false,false,false,true,  false,false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'period',NULL,      true,true,true,true, false,false,false,true, false,  false,false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'value_set',NULL,   true,true,true,true, false,true,true,false,false,   true, false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'formula',NULL,     true,true,true,true, false,false,false,false,false, true, false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'notification',NULL,true,false,false,false,false,false,false,false,false,false,false,NOW(),NOW(),false),
                (:uid,'global',NULL,NULL,'audit',NULL,       true,false,false,false,false,false,false,false,true, false,false,NOW(),NOW(),false)
            """), {"uid": admin_id})
            print("  access_matrix:            11 entity rows restored for admin")

            result = db.session.execute(
                text("""
                    SELECT COUNT(*) as cnt FROM access_matrix
                    WHERE user_id = :admin_id
                    AND is_deleted = false
                    AND scope_type = 'global'
                """),
                {"admin_id": admin_id}
            ).fetchone()
            if result and result.cnt == 11:
                print("  admin permissions verified  (11 rows)")
            else:
                print(f"  WARNING: expected 11 admin rows, got {result.cnt if result else 0}")

            db.session.commit()
            print("\nReset complete.")

        except Exception as exc:
            db.session.rollback()
            print(f"\nERROR: {exc}")
            print("All changes rolled back. Database unchanged.")
            raise


if __name__ == "__main__":
    run()
