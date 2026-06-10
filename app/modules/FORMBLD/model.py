from sqlalchemy.dialects.postgresql import JSONB

from app.common.models import CreatedMixin, FullLifecycleMixin
from app.database import db


class Form(FullLifecycleMixin, db.Model):
    __tablename__ = "forms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey("form_versions.id", use_alter=True, name="fk_forms_current_version_id"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_forms_code"),
    )

    sections = db.relationship("FormSection", back_populates="form", lazy="select")


class FormVersion(CreatedMixin, db.Model):
    __tablename__ = "form_versions"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Draft", server_default="Draft")
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("form_id", "version_number", name="uq_form_version_number"),
        db.Index("idx_form_versions_form", "form_id"),
    )


class Field(FullLifecycleMixin, db.Model):
    __tablename__ = "fields"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    field_code = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey("field_versions.id", use_alter=True, name="fk_fields_current_version_id"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("form_id", "field_code", name="uq_fields_code_per_form"),
    )


class FormSection(FullLifecycleMixin, db.Model):
    __tablename__ = "form_sections"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    layout_type = db.Column(db.String(50), nullable=False, default="monthly_table", server_default="monthly_table")
    display_order = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)

    form = db.relationship("Form", back_populates="sections")
    field_versions = db.relationship("FieldVersion", back_populates="section")

    __table_args__ = (
        db.Index("idx_form_sections_form", "form_id"),
        db.Index(
            "uq_form_sections_code_per_form",
            "form_id",
            "code",
            unique=True,
            postgresql_where=db.text("is_deleted = false"),
        ),
    )


class FieldVersion(FullLifecycleMixin, db.Model):
    __tablename__ = "field_versions"

    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    field_name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)
    field_config = db.Column(JSONB, nullable=False, default=dict, server_default=db.text("'{}'::jsonb"))
    form_version_id = db.Column(db.Integer, db.ForeignKey("form_versions.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("form_sections.id"), nullable=True)
    frequency = db.Column(db.String(20), nullable=False, default="monthly", server_default="monthly")

    section = db.relationship("FormSection", back_populates="field_versions")

    __table_args__ = (
        db.UniqueConstraint("field_id", "version_number", name="uq_field_version_number"),
        db.Index("idx_field_versions_field", "field_id"),
        db.Index("idx_field_versions_section", "section_id"),
    )
