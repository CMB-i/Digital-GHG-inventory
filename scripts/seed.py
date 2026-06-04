import os
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func

from app import create_app
import app.models  # noqa: F401
from app.common.permissions import PERMISSION_FLAGS
from app.database import db
from app.modules.ACCESS.model import AccessMatrix
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.RPTBLD.model import AppConfig
from app.modules.SITEMST.model import Site
from app.modules.USRMGMT.service import hash_password
from app.modules.USRMGMT.model import User


ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_ENTITY_TYPES = (
    "all",
    "audit",
    "form",
    "formula",
    "issue",
    "notification",
    "report",
    "period",
    "site",
    "submission",
    "user",
    "value_set",
    "workflow",
)


def seed_admin_user():
    existing = User.query.filter_by(email=ADMIN_EMAIL).one_or_none()
    if existing:
        if not existing.password_hash:
            existing.password_hash = hash_password(ADMIN_PASSWORD)
        existing.is_active = True
        return existing

    next_id = (db.session.query(func.max(User.id)).scalar() or 0) + 1
    admin = User(
        id=next_id,
        email=ADMIN_EMAIL.lower(),
        password_hash=hash_password(ADMIN_PASSWORD),
        full_name="Initial Admin",
        is_active=True,
        created_by=next_id,
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def seed_admin_access(admin):
    for entity_type in ADMIN_ENTITY_TYPES:
        existing = AccessMatrix.query.filter_by(
            user_id=admin.id,
            scope_type="global",
            scope_site_id=None,
            scope_region_id=None,
            entity_type=entity_type,
            entity_id=None,
            is_deleted=False,
        ).first()
        if existing:
            for flag in PERMISSION_FLAGS:
                setattr(existing, flag, True)
            continue

        values = {
            "user_id": admin.id,
            "scope_type": "global",
            "entity_type": entity_type,
            "created_by": admin.id,
        }
        values.update({flag: True for flag in PERMISSION_FLAGS})
        db.session.add(AccessMatrix(**values))


def seed_sites(admin):
    site_rows = [
        {
            "name": "Test Site 1",
            "code": "SITE1",
            "company_name": "Test Company",
            "description": "Initial test site 1",
        },
        {
            "name": "Test Site 2",
            "code": "SITE2",
            "company_name": "Test Company",
            "description": "Initial test site 2",
        },
    ]

    for site_data in site_rows:
        existing = Site.query.filter_by(code=site_data["code"]).one_or_none()
        if existing:
            continue
        db.session.add(Site(**site_data, created_by=admin.id))


def seed_reporting_periods(admin):
    today = date.today()
    current_year, current_month = today.year, today.month
    if current_month == 1:
        prev_year, prev_month = current_year - 1, 12
    else:
        prev_year, prev_month = current_year, current_month - 1

    periods_to_seed = [(current_year, current_month), (prev_year, prev_month)]
    sites = Site.query.filter_by(is_deleted=False).all()

    for site in sites:
        for year, month in periods_to_seed:
            existing = ReportingPeriod.query.filter_by(
                site_id=site.id,
                year=year,
                month=month,
                is_deleted=False,
            ).first()
            if existing:
                continue
            db.session.add(
                ReportingPeriod(
                    site_id=site.id,
                    year=year,
                    month=month,
                    status="OPEN",
                    created_by=admin.id,
                )
            )


def seed_app_config(admin):
    existing = AppConfig.query.filter_by(config_key="financial_year_start_month").one_or_none()
    if existing:
        return

    db.session.add(
        AppConfig(
            config_key="financial_year_start_month",
            config_value="4",
            config_type="integer",
            description="Financial year start month.",
            updated_by=admin.id,
        )
    )


def run():
    app = create_app()
    with app.app_context():
        admin = seed_admin_user()
        seed_admin_access(admin)
        seed_sites(admin)
        db.session.flush()
        seed_reporting_periods(admin)
        seed_app_config(admin)
        db.session.commit()
        print("Seed complete.")
        if app.config.get("FLASK_ENV") == "development":
            print(f"Dev admin email: {ADMIN_EMAIL}")
            print(f"Dev admin password: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    run()
