from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import CreatedMixin, FullLifecycleMixin
from app.database import db


class Formula(FullLifecycleMixin, db.Model):
    __tablename__ = "formulas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey("formula_versions.id", use_alter=True, name="fk_formulas_current_version_id"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_formula_code"),
    )


class FormulaVersion(CreatedMixin, db.Model):
    __tablename__ = "formula_versions"

    id = db.Column(db.Integer, primary_key=True)
    formula_id = db.Column(db.Integer, db.ForeignKey("formulas.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    expression = db.Column(db.Text, nullable=False)
    tokens = db.Column(JSONB, nullable=False, default=dict, server_default=db.text("'{}'::jsonb"))
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("formula_id", "version_number", name="uq_formula_version_number"),
    )
