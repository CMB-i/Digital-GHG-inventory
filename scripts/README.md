# Operational script safety

Any new or repeatable script that mutates application data must use
`scripts/_script_safety.py`.

Required convention:

- require `--env staging|production` with no default
- support `--dry-run` and roll back instead of committing
- require `--confirm` or an interactive typed confirmation before commit
- validate hardcoded or operator-supplied site, workbook, and form IDs with
  `validate_site()`, `validate_workbook()`, or `validate_form()` before writes

Historical one-off scripts are kept for reference and are marked at the top of
the file. Do not re-run those blindly; copy the safety pattern into any future
operational version first.

No file matching `test_*.py` may be added under `scripts/`. Real tests belong
in `tests/` only.

Manual smoke or operational scripts must be named without a `test_` prefix and
must use the shared script safety pattern in `_script_safety.py` before any
persisted mutation, including explicit environment selection, dry-run handling,
and confirmed commits.