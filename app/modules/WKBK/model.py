from datetime import datetime, timezone

from app.database import db


class Workbook(db.Model):
    __tablename__ = "workbooks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False, unique=True)
    status = db.Column(db.String(50), nullable=False, server_default="draft", default="draft")
    description = db.Column(db.Text, nullable=True)
    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("workflows.id"),
        nullable=True,
    )
    is_active = db.Column(db.Boolean, nullable=False, server_default="true", default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sheets = db.relationship(
        "WorkbookForm",
        backref="workbook",
        lazy="dynamic",
        order_by="WorkbookForm.display_order",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_workbooks_code"),
    )


class WorkbookForm(db.Model):
    __tablename__ = "workbook_forms"

    id = db.Column(db.Integer, primary_key=True)
    workbook_id = db.Column(db.Integer, db.ForeignKey("workbooks.id"), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    sheet_label = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("workbook_id", "form_id", name="uq_workbook_form"),
        db.Index("idx_workbook_forms_workbook", "workbook_id", "display_order"),
    )
