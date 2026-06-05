import os
from datetime import date, datetime, timezone
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
from app.modules.VALSET.model import ValueSet, ValueSetVersion, ValueSetEntry


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


PRE_BUILT_VALUE_SETS = [
    {
        "name": "India Grid Emission Factor",
        "code": "INDIA_GRID_EF",
        "description": (
            "CEA 2023-24 CO₂ emission factors for grid electricity by state/region (kg CO₂/kWh). "
            "Source: Central Electricity Authority, CO2 Baseline Database v19."
        ),
        "entries": [
            {"entry_code": "grid_ef_national", "entry_label": "0.82", "display_order": 1},
            {"entry_code": "grid_ef_northern", "entry_label": "0.85", "display_order": 2},
            {"entry_code": "grid_ef_southern", "entry_label": "0.74", "display_order": 3},
            {"entry_code": "grid_ef_western",  "entry_label": "0.89", "display_order": 4},
            {"entry_code": "grid_ef_eastern",  "entry_label": "0.98", "display_order": 5},
            {"entry_code": "grid_ef_northeastern", "entry_label": "0.57", "display_order": 6},
        ],
    },
    {
        "name": "Fuel Net Calorific Values",
        "code": "FUEL_NCV",
        "description": (
            "Net Calorific Values (NCV) for common fuels used in India. "
            "Source: Bureau of Energy Efficiency (BEE) / IPCC 2006 Guidelines. "
            "Units: GJ per unit (tonne, kL, thousand m³)."
        ),
        "entries": [
            {"entry_code": "ncv_diesel",      "entry_label": "34.2",   "display_order": 1},
            {"entry_code": "ncv_petrol",      "entry_label": "32.5",   "display_order": 2},
            {"entry_code": "ncv_png",         "entry_label": "38.0",   "display_order": 3},
            {"entry_code": "ncv_lpg",         "entry_label": "45.7",   "display_order": 4},
            {"entry_code": "ncv_coal",        "entry_label": "22.8",   "display_order": 5},
            {"entry_code": "ncv_furnace_oil", "entry_label": "40.19",  "display_order": 6},
            {"entry_code": "ncv_hfo",         "entry_label": "40.4",   "display_order": 7},
            {"entry_code": "ncv_biomass",     "entry_label": "11.0",   "display_order": 8},
        ],
    },
    {
        "name": "IPCC CO₂ Emission Factors by Fuel",
        "code": "IPCC_EF",
        "description": (
            "CO₂ emission factors (tCO₂/TJ) for stationary combustion by fuel type. "
            "Source: IPCC 2006 Guidelines for National GHG Inventories, Volume 2, Table 2.2."
        ),
        "entries": [
            {"entry_code": "ef_diesel",      "entry_label": "74.1",  "display_order": 1},
            {"entry_code": "ef_petrol",      "entry_label": "69.3",  "display_order": 2},
            {"entry_code": "ef_png",         "entry_label": "56.1",  "display_order": 3},
            {"entry_code": "ef_lpg",         "entry_label": "63.1",  "display_order": 4},
            {"entry_code": "ef_coal",        "entry_label": "98.3",  "display_order": 5},
            {"entry_code": "ef_furnace_oil", "entry_label": "77.4",  "display_order": 6},
            {"entry_code": "ef_hfo",         "entry_label": "77.4",  "display_order": 7},
            {"entry_code": "ef_biomass",     "entry_label": "0.0",   "display_order": 8},
        ],
    },
    {
        "name": "GHG Global Warming Potentials (AR5)",
        "code": "GHG_GWP",
        "description": (
            "100-year Global Warming Potential (GWP) values for Scope 1 GHG gases. "
            "Source: IPCC Fifth Assessment Report (AR5), Table 8.A.1."
        ),
        "entries": [
            {"entry_code": "gwp_co2",  "entry_label": "1",    "display_order": 1},
            {"entry_code": "gwp_ch4",  "entry_label": "28",   "display_order": 2},
            {"entry_code": "gwp_n2o",  "entry_label": "265",  "display_order": 3},
            {"entry_code": "gwp_hfc",  "entry_label": "1430", "display_order": 4},
            {"entry_code": "gwp_pfc",  "entry_label": "7390", "display_order": 5},
            {"entry_code": "gwp_sf6",  "entry_label": "23500","display_order": 6},
        ],
    },
    {
        "name": "Waste Emission Factors",
        "code": "WASTE_EF",
        "description": (
            "Emission factors for waste management activities. "
            "Source: GHG Protocol Scope 3 Standard, IPCC 2006 Vol. 5."
        ),
        "entries": [
            {"entry_code": "ef_msw_landfill",     "entry_label": "0.52",  "display_order": 1},
            {"entry_code": "ef_msw_incineration", "entry_label": "1.25",  "display_order": 2},
            {"entry_code": "ef_wastewater_aerobic","entry_label": "0.003", "display_order": 3},
            {"entry_code": "ef_wastewater_anaerobic","entry_label": "0.04","display_order": 4},
        ],
    },
]


def seed_value_sets(admin):
    """Seed pre-built GHG reference value sets and auto-approve them."""
    now = datetime.now(timezone.utc)
    today = date.today()

    for vs_data in PRE_BUILT_VALUE_SETS:
        existing = ValueSet.query.filter_by(code=vs_data["code"]).one_or_none()
        if existing:
            print(f"  Value set '{vs_data['code']}' already exists, skipping.")
            continue

        vs = ValueSet(
            name=vs_data["name"],
            code=vs_data["code"],
            description=vs_data.get("description", ""),
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add(vs)
        db.session.flush()

        # Create version 1 and auto-approve it (system default, no workflow needed)
        version = ValueSetVersion(
            value_set_id=vs.id,
            version_number=1,
            status="Approved",
            effective_from=today,
            submitted_by=admin.id,
            submitted_at=now,
            approved_by=admin.id,
            approved_at=now,
            created_by=admin.id,
        )
        db.session.add(version)
        db.session.flush()

        # Add entries
        for entry_data in vs_data["entries"]:
            entry = ValueSetEntry(
                value_set_version_id=version.id,
                entry_code=entry_data["entry_code"],
                entry_label=entry_data["entry_label"],
                display_order=entry_data["display_order"],
                is_active=True,
                created_by=admin.id,
                updated_by=admin.id,
            )
            db.session.add(entry)

        # Link current version
        vs.current_version_id = version.id
        db.session.flush()
        print(f"  Seeded value set: {vs_data['code']} ({len(vs_data['entries'])} entries)")


def run():
    app = create_app()
    with app.app_context():
        admin = seed_admin_user()
        seed_admin_access(admin)
        seed_sites(admin)
        db.session.flush()
        seed_reporting_periods(admin)
        seed_app_config(admin)
        print("Seeding pre-built GHG value sets...")
        seed_value_sets(admin)
        db.session.commit()
        print("Seed complete.")
        if app.config.get("FLASK_ENV") == "development":
            print(f"Dev admin email: {ADMIN_EMAIL}")
            print(f"Dev admin password: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    run()
