from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import CreatedMixin, FullLifecycleMixin
from app.database import db


class Formula(FullLifecycleMixin, db.Model):
    __tablename__ = "formulas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    # Sheet this formula was built for, from the Formula Builder's sheet context
    # at creation time. Nullable: formulas created before this column existed
    # have no reliable way to attribute a single owning sheet (see migration).
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=True)
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
