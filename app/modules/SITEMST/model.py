from app.common.models import FullLifecycleMixin
from app.database import db


class Site(FullLifecycleMixin, db.Model):
    __tablename__ = "sites"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    company_name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("name", name="uq_sites_name"),
        db.UniqueConstraint("code", name="uq_sites_code"),
    )
