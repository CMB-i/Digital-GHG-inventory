import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import bcrypt
from sqlalchemy import func

from app import create_app
import app.models  # noqa: F401
from app.database import db
from app.modules.RPTBLD.model import AppConfig
from app.modules.SITEMST.model import Site
from app.modules.USRMGMT.model import User


ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_admin_user():
    existing = User.query.filter_by(email=ADMIN_EMAIL).one_or_none()
    if existing:
        return existing

    next_id = (db.session.query(func.max(User.id)).scalar() or 0) + 1
    admin = User(
        id=next_id,
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        full_name="Initial Admin",
        is_active=True,
        created_by=next_id,
    )
    db.session.add(admin)
    db.session.flush()
    return admin


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
        seed_sites(admin)
        seed_app_config(admin)
        db.session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    run()
