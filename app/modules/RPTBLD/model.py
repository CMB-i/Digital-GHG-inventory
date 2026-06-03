from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import FullLifecycleMixin, utc_now
from app.database import db


class ReportTemplate(FullLifecycleMixin, db.Model):
    __tablename__ = "report_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scope_type = db.Column(db.String(20), nullable=True)
    scope_site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=True)
    config_json = db.Column(JSONB, nullable=False, default=dict, server_default=db.text("'{}'::jsonb"))

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_report_template_code"),
    )


class AppConfig(db.Model):
    __tablename__ = "app_config"

    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(100), nullable=False)
    config_value = db.Column(db.Text, nullable=False)
    config_type = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.UniqueConstraint("config_key", name="uq_app_config_key"),
    )
