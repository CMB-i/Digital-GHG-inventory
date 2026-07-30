"""
reset_test_entries.py — Clears transactional/entry data accumulated from
testing submit -> approve flows, while leaving every structural/config table
and every user completely untouched.

Deletes (in FK-safe order): approval_actions, submission_value_issues,
submission_values, proof_documents, issue_comments, issues, notifications,
workbook_field_values, submissions, submission_packages (if present),
reporting_periods.

Never touches: users, access_matrix, workbooks/workbook_forms/workbook_sites/
workbook_site_submitters, sites, workflows/workflow_versions/workflow_levels/
workflow_level_approvers, forms/form_versions/form_sections/fields/
field_versions, value_sets/value_set_versions/value_set_entries,
formulas/formula_versions, report_templates, audit_logs, app_config,
alembic/migration tables.

Run manually:
    python scripts/reset_test_entries.py
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect as sa_inspect, text

from app import create_app
from app.database import db
from scripts._script_safety import add_safety_arguments, build_safety, guarded_commit


def delete(table: str, where: str = "", params: dict = None) -> int:
    sql = f"DELETE FROM {table}"
    if where:
        sql += f" WHERE {where}"
    result = db.session.execute(text(sql), params or {})
    return result.rowcount


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_arguments(parser)
    args = parser.parse_args()
    safety = build_safety(args)

    app = create_app()
    with app.app_context():
        print("\nStarting reset...\n")

        existing_tables = set(sa_inspect(db.engine).get_table_names())

        try:
            # ----------------------------------------------------------------
            # Delete in FK-safe order.
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

            # Reporting periods (parent of submissions/submission_packages)
            n = delete("reporting_periods");  print(f"  reporting_periods:        {n} rows")

            if guarded_commit(db.session, safety, "delete transactional and entry data"):
                print("\nReset complete. All structural/config tables and users untouched.")

        except Exception as exc:
            db.session.rollback()
            print(f"\nERROR: {exc}")
            print("All changes rolled back. Database unchanged.")
            raise


if __name__ == "__main__":
    run()
