import datetime
import io
from flask import Blueprint, render_template, jsonify, request, send_file

from app.common.decorators import require_permission
from app.common.auth import current_user
from app.database import db
from app.modules.RPTBLD.service import (
    list_report_templates,
    get_report_template,
    create_report_template,
    update_report_template,
    delete_report_template,
    generate_report_data,
    export_report_to_excel,
    _get_user_allowed_sites,
)
from app.modules.SITEMST.model import Site
from app.modules.FORMBLD.model import Form

MODULE_CODE = "RPTBLD"
bp = Blueprint(MODULE_CODE.lower(), __name__, url_prefix=f"/module/{MODULE_CODE}")


@bp.route("/")
@require_permission("report", ("export", "view"))
def index():
    user = current_user()

    # List templates for the user
    templates = list_report_templates(user.id)

    # Get allowed sites for the user
    allowed_site_ids, is_global = _get_user_allowed_sites(user.id, "report")
    sites = Site.query.filter(Site.id.in_(list(allowed_site_ids)), Site.is_deleted == False).order_by(Site.name.asc()).all()

    # Active forms
    forms = Form.query.filter_by(is_deleted=False).order_by(Form.name.asc()).all()

    # Year & Month options for dynamic date range selection
    today = datetime.date.today()
    years = list(range(today.year - 5, today.year + 2))
    months = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    return render_template(
        "modules/RPTBLD/reports.html",
        module_code=MODULE_CODE,
        templates=templates,
        sites=sites,
        forms=forms,
        years=years,
        months=months,
    )


@bp.route("/api/templates")
@require_permission("report", "view")
def api_list_templates():
    user = current_user()
    templates = list_report_templates(user.id)
    return jsonify([{
        "id": t.id,
        "name": t.name,
        "code": t.code,
        "description": t.description,
        "scope_type": t.scope_type,
        "scope_site_id": t.scope_site_id,
        "config_json": t.config_json
    } for t in templates])


@bp.route("/api/templates", methods=["POST"])
@require_permission("report", "create")
def api_create_template():
    user = current_user()
    data = request.json or {}
    try:
        t = create_report_template(
            name=data.get("name"),
            code=data.get("code"),
            description=data.get("description"),
            scope_type=data.get("scope_type"),
            scope_site_id=data.get("scope_site_id"),
            config_json=data.get("config_json"),
            user_id=user.id
        )
        db.session.commit()
        return jsonify({
            "status": "success",
            "template": {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "description": t.description,
                "scope_type": t.scope_type,
                "scope_site_id": t.scope_site_id,
                "config_json": t.config_json
            }
        }), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to create template."}), 500


@bp.route("/api/templates/<int:template_id>")
@require_permission("report", "view")
def api_get_template(template_id):
    t = get_report_template(template_id)
    if not t:
        return jsonify({"status": "error", "message": "Template not found."}), 404
    return jsonify({
        "id": t.id,
        "name": t.name,
        "code": t.code,
        "description": t.description,
        "scope_type": t.scope_type,
        "scope_site_id": t.scope_site_id,
        "config_json": t.config_json
    })


@bp.route("/api/templates/<int:template_id>", methods=["PUT"])
@require_permission("report", "edit")
def api_update_template(template_id):
    user = current_user()
    data = request.json or {}
    try:
        t = update_report_template(
            template_id=template_id,
            name=data.get("name"),
            description=data.get("description"),
            scope_type=data.get("scope_type"),
            scope_site_id=data.get("scope_site_id"),
            config_json=data.get("config_json"),
            user_id=user.id
        )
        db.session.commit()
        return jsonify({
            "status": "success",
            "template": {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "description": t.description,
                "scope_type": t.scope_type,
                "scope_site_id": t.scope_site_id,
                "config_json": t.config_json
            }
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to update template."}), 500


@bp.route("/api/templates/<int:template_id>", methods=["DELETE"])
@require_permission("report", "delete")
def api_delete_template(template_id):
    user = current_user()
    try:
        delete_report_template(template_id, user.id)
        db.session.commit()
        return jsonify({"status": "success", "message": "Template deleted."})
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to delete template."}), 500


@bp.route("/api/templates/<int:template_id>/preview")
@require_permission("report", "view")
def api_preview_template(template_id):
    user = current_user()
    try:
        data = generate_report_data(template_id, user.id)
        return jsonify({"status": "success", "data": data})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to generate preview."}), 500


@bp.route("/api/templates/<int:template_id>/export")
@require_permission("report", "export")
def api_export_template(template_id):
    user = current_user()
    try:
        excel_data = export_report_to_excel(template_id, user.id)
        t = get_report_template(template_id)
        filename = f"report_{t.code}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            io.BytesIO(excel_data),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to export report."}), 500