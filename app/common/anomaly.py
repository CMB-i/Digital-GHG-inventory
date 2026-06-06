from app.database import db
from app.modules.SUBMIT.model import Submission, SubmissionValue
from app.modules.PERIOD.model import ReportingPeriod
from app.modules.FORMBLD.model import Field, FieldVersion

def get_numeric_value(val):
    if val.calculated_value is not None:
        return float(val.calculated_value)
    if val.raw_value is not None:
        try:
            return float(val.raw_value)
        except (ValueError, TypeError):
            return None
    return None

def check_anomalies(submission_id):
    """
    Compares field values to same field_code in previous month's approved submission.
    Returns: dict of {field_code: warning_message}
    """
    submission = Submission.query.get(submission_id)
    if not submission:
        return {}

    current_period = ReportingPeriod.query.get(submission.reporting_period_id)
    if not current_period:
        return {}

    # Calculate previous period (same site, previous month)
    if current_period.month == 1:
        prev_year = current_period.year - 1
        prev_month = 12
    else:
        prev_year = current_period.year
        prev_month = current_period.month - 1

    prev_period = ReportingPeriod.query.filter_by(
        site_id=submission.site_id,
        year=prev_year,
        month=prev_month,
        is_deleted=False
    ).first()

    if not prev_period:
        return {}

    # Query approved submission for that site + form + previous period
    prev_submission = Submission.query.filter_by(
        site_id=submission.site_id,
        form_id=submission.form_id,
        reporting_period_id=prev_period.id,
        status="Approved",
        is_deleted=False
    ).first()

    if not prev_submission:
        return {}

    # Skip if form version changed
    if prev_submission.form_version_id != submission.form_version_id:
        return {}

    # Fetch fields with their configs and codes for this form version
    fields_info = (
        db.session.query(Field.field_code, FieldVersion.field_config, Field.id)
        .join(FieldVersion, FieldVersion.field_id == Field.id)
        .filter(
            FieldVersion.form_version_id == submission.form_version_id,
            Field.is_deleted == False
        )
        .all()
    )

    # Load current and previous submission values
    curr_vals = SubmissionValue.query.filter_by(submission_id=submission.id).all()
    prev_vals = SubmissionValue.query.filter_by(submission_id=prev_submission.id).all()

    # Create mappings of field_id to value object
    curr_map = {v.field_id: v for v in curr_vals}
    prev_map = {v.field_id: v for v in prev_vals}

    anomalies = {}

    for field_code, field_config, field_id in fields_info:
        config = field_config or {}
        # Check if anomaly threshold is configured (either as a float/int or string)
        threshold_val = config.get("anomaly_threshold")
        if threshold_val is None:
            # Fallback keys just in case
            threshold_val = config.get("anomaly_threshold_percent") or config.get("threshold")
            
        if threshold_val is None:
            continue

        try:
            threshold = float(threshold_val)
        except (ValueError, TypeError):
            continue

        curr_val_obj = curr_map.get(field_id)
        prev_val_obj = prev_map.get(field_id)

        if not curr_val_obj or not prev_val_obj:
            continue

        curr_num = get_numeric_value(curr_val_obj)
        prev_num = get_numeric_value(prev_val_obj)

        if curr_num is None or prev_num is None:
            continue

        # Skip if previous value is 0
        if prev_num == 0.0:
            continue

        # Calculate percentage deviation
        deviation = abs(curr_num - prev_num) / prev_num * 100.0

        if deviation > threshold:
            anomalies[field_code] = (
                f"Value deviates by {deviation:.1f}% from previous month's approved value "
                f"(previous: {prev_num}, current: {curr_num})"
            )

    return anomalies
