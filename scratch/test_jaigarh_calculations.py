import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.database import db
from app.modules.WKBK.model import Workbook, WorkbookSiteSubmitter
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form, Field
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.SUBMIT.service import compose_calculation_results
from app.modules.USRMGMT.model import User
from app.modules.WFLWBLD.model import WorkflowVersion

app = create_app()

with app.app_context():
    print("Verifying Jaigarh Energy & GHG Workbook calculations...")
    
    # 1. Fetch active user
    user = User.query.filter_by(is_active=True, is_deleted=False).first()
    assert user is not None, "No active user found"
    print(f"Using user: {user.full_name} (ID: {user.id})")
    
    # 2. Fetch Workbook and Site
    wkbk = Workbook.query.filter_by(code="wkbk_jaigarh").first()
    assert wkbk is not None, "Jaigarh workbook not found"
    
    site = Site.query.filter_by(is_deleted=False).first()
    assert site is not None, "No sites found"
    print(f"Using site: {site.name} (ID: {site.id})")

    # Add submitter role for user
    submitter = WorkbookSiteSubmitter.query.filter_by(
        workbook_id=wkbk.id,
        site_id=site.id,
        user_id=user.id
    ).first()
    if not submitter:
        submitter = WorkbookSiteSubmitter(
            workbook_id=wkbk.id,
            site_id=site.id,
            user_id=user.id,
            created_by=user.id
        )
        db.session.add(submitter)
        db.session.flush()
        print("Temporarily assigned user as submitter.")
    
    # 3. Get or create Reporting Period for April 2025
    period = ReportingPeriod.query.filter_by(site_id=site.id, year=2025, month=4, is_deleted=False).first()
    if not period:
        period = ReportingPeriod(site_id=site.id, year=2025, month=4, status="OPEN", created_by=user.id)
        db.session.add(period)
        db.session.flush()
        
    # 4. Get a valid workflow version
    wv = WorkflowVersion.query.first()
    assert wv is not None, "No workflow version found in database"
    
    # 5. Dummy Inputs mapping
    mock_values = {
        "elec_grid_mwh": "100.0",
        "elec_group_sourcing_mwh": "200.0",
        "diesel_stationary_kl": "10.0",
        "diesel_mobile_kl": "20.0",
        "petrol_qty_kl": "5.0",
        "hfhsd_qty_kl": "50.0",
        "ifo_qty_kl": "50.0",
        "acetylene_qty_t": "2.0",
        "lpg_qty_t": "0.0",
        "co2_fire_ext_qty_t": "0.0",
        "r32_qty_kg": "10.0",
        "r410a_qty_kg": "20.0",
        "r22_qty_kg": "0.0",
        "production_million_mt": "10.0"
    }
    
    # 6. Create Mock Submissions and Submission Values
    forms = Form.query.filter(Form.code.startswith("form_jaigarh_")).all()
    for form in forms:
        sub = Submission(
            site_id=site.id,
            form_id=form.id,
            form_version_id=form.current_version_id,
            reporting_period_id=period.id,
            workflow_version_id=wv.id,
            status="Draft",
            submitted_by=user.id,
            created_by=user.id
        )
        db.session.add(sub)
        db.session.flush()
        
        fields = Field.query.filter_by(form_id=form.id, is_deleted=False).all()
        for field in fields:
            if field.field_code in mock_values:
                val = SubmissionValue(
                    submission_id=sub.id,
                    field_id=field.id,
                    field_version_id=field.current_version_id,
                    raw_value=mock_values[field.field_code],
                    created_by=user.id
                )
                db.session.add(val)
                
    db.session.flush()
    print("Mock submissions and values created.")
    
    # 7. Run calculations
    print("Running calculations...")
    results = compose_calculation_results(
        site_id=site.id,
        workbook_id=wkbk.id,
        fy_start_year=2025,
        user_id=user.id
    )
    
    # Let's inspect the results
    print("\nCalculated Row values for April 2025:")
    print("-" * 60)
    
    # Find April row in results
    rows = results.get("rows", [])
    april_row = next((r for r in rows if r.get("month") == 4), None)
    if not april_row:
        print("Error: April row not found in results!")
    else:
        values = april_row.get("values", {})
        for field in results.get("fields", []):
            code = field["field_code"]
            name = field["field_name"]
            val_info = values.get(code, {})
            val = val_info.get("calculated_value")
            status = val_info.get("status")
            warnings = val_info.get("warnings", [])
            print(f"{name:<45} | {code:<30} = {val} ({status}) {warnings}")
            
    # Rollback to keep database clean
    db.session.rollback()
    print("\nDatabase transaction rolled back successfully. Database remains clean.")
