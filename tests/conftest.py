"""
Shared pytest fixtures for the whole suite.

Test database strategy
-----------------------
This project has no Flask-Migrate and no existing test infrastructure, and the
models use Postgres-specific features (JSONB columns, partial unique indexes
via postgresql_where) that an in-memory SQLite DB can't reproduce faithfully.
So tests run against a real, dedicated Postgres database:

- The URL is TEST_DATABASE_URL if set, otherwise it's derived from the normal
  DATABASE_URL / app/config.py by appending "_test" to the database name --
  never the dev database itself.
- The database is created (if missing) and its schema built once per test
  session via db.create_all() (not via Alembic -- for a fresh test database
  the current models ARE the schema; running every historical migration in
  order adds a lot of runtime for no benefit here).
- Isolation between tests is NOT SQLAlchemy-savepoint-based. Given this app's
  service functions call db.session.commit() themselves throughout (not just
  at the top level), a savepoint/rollback harness would have to intercept
  every one of those commits. Instead, fixtures create real rows with real
  commits and delete them again in a `finally`-equivalent teardown -- the same
  pattern used for every manual verification in this project's history, just
  reusable now instead of hand-rolled per script. Tests must only use the
  factory fixtures below (or clean up anything else they create) so re-running
  the suite never leaves stray rows behind.
"""
import os
import uuid
from datetime import date, datetime, timezone

import psycopg2
import pytest


def _test_database_url():
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    from app.config import Config

    base = Config.DATABASE_URL
    root, _, name = base.rpartition("/")
    if name.endswith("_test"):
        return base
    return f"{root}/{name}_test"


TEST_DATABASE_URL = _test_database_url()


def _ensure_database_exists(url):
    root, _, dbname = url.rpartition("/")
    maintenance_url = f"{root}/postgres"
    conn = psycopg2.connect(maintenance_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        conn.close()


class TestConfig:
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FLASK_ENV = "testing"
    TESTING = True


@pytest.fixture(scope="session")
def app():
    _ensure_database_exists(TEST_DATABASE_URL)
    from app import create_app
    from app.database import db as _db

    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        _db.drop_all()
        _db.create_all()
        yield flask_app
        _db.session.remove()


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        yield


@pytest.fixture(scope="session")
def system_user(app):
    """
    The bootstrap identity every fixture's created_by/updated_by points to.
    users.created_by is NOT NULL, so the very first user has to reference
    itself -- mirrors scripts/seed.py's admin-user bootstrap exactly.
    Session-scoped and never deleted: it's test infrastructure, not test data.
    """
    with app.app_context():
        from sqlalchemy import text

        from app.database import db as _db
        from app.modules.USRMGMT.model import User

        existing = User.query.filter_by(email="system@test.local").one_or_none()
        if existing:
            return existing.id

        # Pull the id from the real sequence (not MAX(id)+1) so the sequence's
        # internal counter stays in sync -- otherwise the next auto-assigned
        # id for a normal insert would collide with this one.
        next_id = _db.session.execute(text("SELECT nextval('users_id_seq')")).scalar()
        user = User(
            id=next_id,
            email="system@test.local",
            password_hash="x",
            full_name="Test System User",
            is_active=True,
            created_by=next_id,
            updated_by=next_id,
        )
        _db.session.add(user)
        _db.session.commit()
        return user.id


@pytest.fixture()
def db_session(app_context):
    from app.database import db as _db

    return _db.session


@pytest.fixture()
def created_objects(db_session):
    objects = []
    yield objects
    db_session.rollback()

    # Form/Field/Workflow/Formula/ValueSet all have a self-referential
    # current_version_id pointing at their own "version" child row (added via
    # use_alter=True to break the circular FK at table-creation time). That
    # reverses the usual child-before-parent delete order: the *parent* must
    # release its pointer before the *child* version row can be deleted. Null
    # them all out up front rather than special-casing each model.
    for obj in objects:
        if hasattr(obj, "current_version_id") and obj.current_version_id is not None:
            obj.current_version_id = None
    db_session.flush()

    # Service functions under test create their own rows as side effects that
    # were never explicitly registered here -- e.g. recalculate_submission_formulas
    # creating a SubmissionValue for a calculated field, approve_submission
    # recording an ApprovalAction, or any of them calling log_audit(). Sweep
    # those up first so they don't block deleting the Submission/User rows
    # they reference.
    from app.modules.APPROV.model import ApprovalAction
    from app.modules.AUDITL.model import AuditLog
    from app.modules.SUBMIT.model import Submission, SubmissionValue
    from app.modules.USRMGMT.model import User

    submission_ids = [obj.id for obj in objects if isinstance(obj, Submission)]
    user_ids = [obj.id for obj in objects if isinstance(obj, User)]

    if submission_ids:
        SubmissionValue.query.filter(SubmissionValue.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        ApprovalAction.query.filter(ApprovalAction.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        AuditLog.query.filter(
            AuditLog.entity_type == "submission",
            AuditLog.entity_id.in_([str(sid) for sid in submission_ids]),
        ).delete(synchronize_session=False)
        db_session.flush()

    if user_ids:
        AuditLog.query.filter(AuditLog.actor_user_id.in_(user_ids)).delete(synchronize_session=False)
        db_session.flush()

    # Delete in reverse creation order, retrying in passes: a single failed
    # delete (e.g. FK ordering) must not discard the deletes that already
    # succeeded earlier in the same pass, so each attempt runs in its own
    # SAVEPOINT that rolls back independently of the outer transaction.
    remaining = list(reversed(objects))
    for _ in range(len(remaining) + 1):
        if not remaining:
            break
        next_round = []
        progress = False
        for obj in remaining:
            try:
                with db_session.begin_nested():
                    db_session.delete(obj)
                    db_session.flush()
                progress = True
            except Exception:
                next_round.append(obj)
        remaining = next_round
        if not progress:
            break
    db_session.commit()


def _uid():
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def make_user(db_session, created_objects, system_user):
    def _make(email=None, full_name="Test User", is_active=True, **kwargs):
        from app.modules.USRMGMT.model import User

        user = User(
            email=email or f"test-{_uid()}@example.com",
            password_hash="x",
            full_name=full_name,
            is_active=is_active,
            created_by=system_user,
            updated_by=system_user,
            **kwargs,
        )
        db_session.add(user)
        db_session.flush()
        created_objects.append(user)
        return user

    return _make


@pytest.fixture()
def make_site(db_session, created_objects, system_user):
    def _make(name=None, code=None, **kwargs):
        from app.modules.SITEMST.model import Site

        suffix = _uid()
        site = Site(
            name=name or f"Test Site {suffix}",
            code=code or f"TS{suffix}",
            created_by=system_user,
            updated_by=system_user,
            **kwargs,
        )
        db_session.add(site)
        db_session.flush()
        created_objects.append(site)
        return site

    return _make


@pytest.fixture()
def make_access_grant(db_session, created_objects, system_user):
    def _make(user, entity_type, scope_type="global", scope_site_id=None, **flags):
        from app.modules.ACCESS.model import AccessMatrix

        grant = AccessMatrix(
            user_id=user.id,
            scope_type=scope_type,
            scope_site_id=scope_site_id,
            entity_type=entity_type,
            created_by=system_user,
            updated_by=system_user,
            **flags,
        )
        db_session.add(grant)
        db_session.flush()
        created_objects.append(grant)
        return grant

    return _make


@pytest.fixture()
def make_reporting_period(db_session, created_objects, system_user):
    def _make(site, year=2026, month=4, status="OPEN"):
        from app.modules.PERIOD.model import ReportingPeriod

        period = ReportingPeriod(
            site_id=site.id,
            year=year,
            month=month,
            status=status,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(period)
        db_session.flush()
        created_objects.append(period)
        return period

    return _make


@pytest.fixture()
def make_formula_version(db_session, created_objects, system_user):
    def _make(expression, tokens):
        from app.modules.FRMULA.model import Formula, FormulaVersion

        suffix = _uid()
        formula = Formula(name=f"Test Formula {suffix}", code=f"test-formula-{suffix}", created_by=system_user, updated_by=system_user)
        db_session.add(formula)
        db_session.flush()
        created_objects.append(formula)

        version = FormulaVersion(
            formula_id=formula.id,
            version_number=1,
            expression=expression,
            tokens=tokens,
            created_by=system_user,
        )
        db_session.add(version)
        db_session.flush()
        created_objects.append(version)
        return version

    return _make


@pytest.fixture()
def make_form(db_session, created_objects, system_user):
    """Creates a Form + one FormVersion. Returns (form, form_version)."""

    def _make():
        from app.modules.FORMBLD.model import Form, FormVersion

        suffix = _uid()
        form = Form(name=f"Test Form {suffix}", code=f"test-form-{suffix}", created_by=system_user, updated_by=system_user)
        db_session.add(form)
        db_session.flush()
        created_objects.append(form)

        version = FormVersion(form_id=form.id, version_number=1, status="Published", published_at=datetime.now(timezone.utc), created_by=system_user)
        db_session.add(version)
        db_session.flush()
        created_objects.append(version)

        form.current_version_id = version.id
        db_session.flush()
        return form, version

    return _make


@pytest.fixture()
def make_field(db_session, created_objects, system_user):
    """Creates a Field + FieldVersion under the given form_version. Returns (field, field_version)."""

    def _make(form, form_version, field_code, field_type="number", field_config=None, display_order=10, frequency="monthly"):
        from app.modules.FORMBLD.model import Field, FieldVersion

        field = Field(form_id=form.id, field_code=field_code, display_order=display_order, created_by=system_user, updated_by=system_user)
        db_session.add(field)
        db_session.flush()
        created_objects.append(field)

        version = FieldVersion(
            field_id=field.id,
            version_number=1,
            field_name=field_code.replace("_", " ").title(),
            field_type=field_type,
            field_config=field_config or {},
            form_version_id=form_version.id,
            frequency=frequency,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(version)
        db_session.flush()
        created_objects.append(version)

        field.current_version_id = version.id
        db_session.flush()
        return field, version

    return _make


@pytest.fixture()
def make_workflow(db_session, created_objects, system_user):
    """
    Creates a Workflow + WorkflowVersion + a single ANY_ONE WorkflowLevel, with
    the given approver(s) assigned globally (scope_site_id=None). Returns the
    WorkflowVersion (submission.workflow_version_id points at this).
    """

    def _make(approvers, approval_mode="ANY_ONE", scope_site_id=None):
        from app.modules.WFLWBLD.model import Workflow, WorkflowLevel, WorkflowLevelApprover, WorkflowVersion

        suffix = _uid()
        workflow = Workflow(name=f"Test Workflow {suffix}", code=f"test-wf-{suffix}", created_by=system_user, updated_by=system_user)
        db_session.add(workflow)
        db_session.flush()
        created_objects.append(workflow)

        version = WorkflowVersion(workflow_id=workflow.id, version_number=1, published_at=datetime.now(timezone.utc), created_by=system_user)
        db_session.add(version)
        db_session.flush()
        created_objects.append(version)

        workflow.current_version_id = version.id
        db_session.flush()

        level = WorkflowLevel(
            workflow_version_id=version.id,
            level_number=1,
            level_name="Level 1",
            approval_mode=approval_mode,
            skip_if_empty=False,
            created_by=system_user,
            updated_by=system_user,
        )
        db_session.add(level)
        db_session.flush()
        created_objects.append(level)

        for idx, approver in enumerate(approvers):
            wla = WorkflowLevelApprover(
                workflow_level_id=level.id,
                user_id=approver.id,
                scope_site_id=scope_site_id,
                sequence_number=idx + 1 if approval_mode == "SEQUENTIAL" else None,
                created_by=system_user,
                updated_by=system_user,
            )
            db_session.add(wla)
            db_session.flush()
            created_objects.append(wla)

        return version

    return _make


@pytest.fixture()
def make_workbook(db_session, created_objects, system_user):
    def _make(form, site, workflow_version=None, submitters=None):
        from app.modules.WKBK.model import Workbook, WorkbookForm, WorkbookSite, WorkbookSiteSubmitter

        suffix = _uid()
        workbook = Workbook(
            name=f"Test Workbook {suffix}",
            code=f"test-wbk-{suffix}",
            status="published",
            workflow_id=workflow_version.workflow_id if workflow_version else None,
            is_active=True,
            created_by=system_user,
        )
        db_session.add(workbook)
        db_session.flush()
        created_objects.append(workbook)

        wf_form = WorkbookForm(workbook_id=workbook.id, form_id=form.id, display_order=10)
        db_session.add(wf_form)
        db_session.flush()
        created_objects.append(wf_form)

        wf_site = WorkbookSite(workbook_id=workbook.id, site_id=site.id, created_by=system_user)
        db_session.add(wf_site)
        db_session.flush()
        created_objects.append(wf_site)

        for user in submitters or []:
            submitter = WorkbookSiteSubmitter(workbook_id=workbook.id, site_id=site.id, user_id=user.id, created_by=system_user)
            db_session.add(submitter)
            db_session.flush()
            created_objects.append(submitter)

        return workbook

    return _make


@pytest.fixture()
def make_submission(db_session, created_objects, system_user):
    def _make(site, form, form_version, reporting_period, workflow_version, status="Draft", submitted_by=None, current_level=1, **kwargs):
        from app.modules.SUBMIT.model import Submission

        submission = Submission(
            site_id=site.id,
            form_id=form.id,
            form_version_id=form_version.id,
            reporting_period_id=reporting_period.id,
            workflow_version_id=workflow_version.id if workflow_version else None,
            status=status,
            submitted_by=submitted_by.id if submitted_by else None,
            submitted_at=datetime.now(timezone.utc) if status != "Draft" else None,
            current_level=current_level,
            created_by=system_user,
            updated_by=system_user,
            **kwargs,
        )
        db_session.add(submission)
        db_session.flush()
        created_objects.append(submission)
        return submission

    return _make


@pytest.fixture()
def make_submission_value(db_session, created_objects, system_user):
    def _make(submission, field, field_version, raw_value=None, **kwargs):
        from app.modules.SUBMIT.model import SubmissionValue

        value = SubmissionValue(
            submission_id=submission.id,
            field_id=field.id,
            field_version_id=field_version.id,
            raw_value=raw_value,
            created_by=system_user,
            updated_by=system_user,
            **kwargs,
        )
        db_session.add(value)
        db_session.flush()
        created_objects.append(value)
        return value

    return _make
