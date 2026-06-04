from datetime import datetime, timezone

from app.common.validators import ValidationError, validate_code, validate_text_length
from app.database import db
from app.modules.SITEMST.model import Site


def _utc_now():
    return datetime.now(timezone.utc)


def list_sites():
    active = Site.query.filter_by(is_deleted=False).order_by(Site.name.asc()).all()
    inactive = (
        Site.query.filter(Site.is_deleted.is_(True)).order_by(Site.name.asc()).all()
    )
    return active, inactive


def get_site(site_id):
    return Site.query.filter_by(id=site_id).one_or_none()


def _validate_site_fields(name, code, company_name, description):
    name = validate_text_length(name, "Name", 255, required=True)
    code = validate_code(code, "Code", 50)
    company_name = validate_text_length(company_name, "Company name", 255) or None
    description = validate_text_length(description, "Description", 10000) or None
    return name, code, company_name, description


def create_site(name, code, company_name, description, actor_id):
    name, code, company_name, description = _validate_site_fields(
        name, code, company_name, description
    )
    if Site.query.filter(
        Site.name == name, Site.is_deleted.is_(False)
    ).first():
        raise ValidationError("A site with this name already exists.")
    if Site.query.filter(
        Site.code == code, Site.is_deleted.is_(False)
    ).first():
        raise ValidationError("A site with this code already exists.")
    site = Site(
        name=name,
        code=code,
        company_name=company_name,
        description=description,
        created_by=actor_id,
    )
    db.session.add(site)
    return site


def update_site(site_id, name, code, company_name, description):
    site = Site.query.filter_by(id=site_id).one_or_none()
    if not site:
        return None
    name, code, company_name, description = _validate_site_fields(
        name, code, company_name, description
    )
    if Site.query.filter(
        Site.name == name, Site.id != site_id, Site.is_deleted.is_(False)
    ).first():
        raise ValidationError("A site with this name already exists.")
    if Site.query.filter(
        Site.code == code, Site.id != site_id, Site.is_deleted.is_(False)
    ).first():
        raise ValidationError("A site with this code already exists.")
    site.name = name
    site.code = code
    site.company_name = company_name
    site.description = description
    return site


def deactivate_site(site_id, actor_id):
    site = Site.query.filter_by(id=site_id, is_deleted=False).one_or_none()
    if not site:
        return None
    site.is_deleted = True
    site.deleted_at = _utc_now()
    site.deleted_by = actor_id
    return site


def reactivate_site(site_id, actor_id):
    site = Site.query.filter(
        Site.id == site_id, Site.is_deleted.is_(True)
    ).one_or_none()
    if not site:
        return None
    site.is_deleted = False
    site.deleted_at = None
    site.deleted_by = None
    return site
