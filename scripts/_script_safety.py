"""Shared safety helpers for operational scripts.

Mutable scripts should require an explicit environment and either run in
dry-run mode or get a deliberate confirmation before committing.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any


VALID_ENVIRONMENTS = ("staging", "production")


@dataclass(frozen=True)
class ScriptSafety:
    env: str
    dry_run: bool = False
    confirm: bool = False

    def confirm_commit(self, action: str = "commit database changes") -> bool:
        if self.dry_run:
            print(f"DRY RUN: would {action}; rolling back instead.")
            return False
        if self.confirm:
            print(f"Confirmed {action} in {self.env}.")
            return True
        response = input(f"About to {action} in {self.env}. Type {self.env} to continue: ").strip()
        if response != self.env:
            raise SystemExit("Aborted before commit.")
        return True

    def commit_or_rollback(self, db_session: Any, action: str = "commit database changes") -> bool:
        if not self.confirm_commit(action):
            db_session.rollback()
            return False
        db_session.commit()
        return True


def add_safety_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", choices=VALID_ENVIRONMENTS, required=True, help="Target environment.")
    parser.add_argument("--dry-run", action="store_true", help="Print intended mutations and roll back.")
    parser.add_argument("--confirm", action="store_true", help="Skip interactive confirmation before commit.")


def build_safety(args: argparse.Namespace) -> ScriptSafety:
    return ScriptSafety(env=args.env, dry_run=args.dry_run, confirm=args.confirm)


def guarded_commit(db_session: Any, safety: ScriptSafety, action: str = "commit database changes") -> bool:
    return safety.commit_or_rollback(db_session, action)


def validate_resolved_identity(row: Any, label: str, expected: dict[str, Any] | None = None) -> Any:
    if row is None:
        raise SystemExit(f"{label} was not found.")

    expected = expected or {}
    mismatches = []
    for attr, expected_value in expected.items():
        actual = getattr(row, attr, None)
        if str(actual) != str(expected_value):
            mismatches.append(f"{attr}: expected {expected_value!r}, got {actual!r}")
    if mismatches:
        raise SystemExit(f"{label} identity mismatch: " + "; ".join(mismatches))

    details = []
    for attr in ("id", "code", "name"):
        if hasattr(row, attr):
            details.append(f"{attr}={getattr(row, attr)!r}")
    print(f"Resolved {label}: " + ", ".join(details))
    return row


def validate_site(site_id: int, expected: dict[str, Any] | None = None) -> Any:
    from app.modules.SITEMST.model import Site

    return validate_resolved_identity(Site.query.get(site_id), "site", expected)


def validate_form(form_id: int, expected: dict[str, Any] | None = None) -> Any:
    from app.modules.FORMBLD.model import Form

    return validate_resolved_identity(Form.query.get(form_id), "form", expected)


def validate_workbook(workbook_id: int, expected: dict[str, Any] | None = None) -> Any:
    from app.modules.WKBK.model import Workbook

    return validate_resolved_identity(Workbook.query.get(workbook_id), "workbook", expected)
