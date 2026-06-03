from app.common.models import FullLifecycleMixin
from app.database import db


class ReportingPeriod(FullLifecycleMixin, db.Model):
    __tablename__ = "reporting_periods"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="OPEN", server_default="OPEN")
    deadline = db.Column(db.Date, nullable=True)
    reopen_reason = db.Column(db.Text, nullable=True)
    reopened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reopened_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("site_id", "year", "month", name="uq_period_site_year_month"),
        db.Index("idx_periods_site_status", "site_id", "status"),
    )
