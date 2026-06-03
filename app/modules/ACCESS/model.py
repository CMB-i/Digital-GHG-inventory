from app.common.models import FullLifecycleMixin
from app.database import db


class AccessMatrix(FullLifecycleMixin, db.Model):
    __tablename__ = "access_matrix"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scope_type = db.Column(db.String(20), nullable=False)
    scope_site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=True)
    scope_region_id = db.Column(db.Integer, nullable=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    can_view = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_create = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_delete = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_submit = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_approve = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_reject = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_reopen = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_export = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_manage_forms = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_manage_users = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        db.Index("idx_access_matrix_user", "user_id"),
        db.Index("idx_access_matrix_scope", "scope_type", "scope_site_id"),
    )
