"""
Fails if the Alembic migration chain has more than one head.

This project has no Flask-Migrate and no CI-enforced check that the migration
chain stays linear -- it forked into two heads once before and had to be
reconciled by hand with a merge migration. Run this before pushing a new
migration:

    python scripts/check_alembic_heads.py
"""
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    config = Config(str(REPO_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    if len(heads) > 1:
        print(f"ERROR: Alembic migration chain has {len(heads)} heads (expected 1):")
        for head in heads:
            print(f"  - {head}")
        print("Reconcile with a merge migration (`alembic merge heads`) before proceeding.")
        return 1

    print(f"OK: single Alembic head ({heads[0] if heads else 'none'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
