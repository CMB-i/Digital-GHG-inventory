from flask import Flask, jsonify, redirect, render_template
from sqlalchemy import text

from app.config import Config
from app.database import db
from app.modules.ACCESS import bp as access_bp
from app.modules.APPROV import bp as approv_bp
from app.modules.AUDITL import bp as auditl_bp
from app.modules.FORMBLD import bp as formbld_bp
from app.modules.FRMULA import bp as frmula_bp
from app.modules.NOTIFY import bp as notify_bp
from app.modules.PERIOD import bp as period_bp
from app.modules.RPTBLD import bp as rptbld_bp
from app.modules.SITEMST import bp as sitemst_bp
from app.modules.SUBMIT import bp as submit_bp
from app.modules.USRMGMT import bp as usrmgmt_bp
from app.modules.VALSET import bp as valset_bp
from app.modules.WFLWBLD import bp as wflwbld_bp


MODULE_BLUEPRINTS = [
    access_bp,
    usrmgmt_bp,
    sitemst_bp,
    formbld_bp,
    frmula_bp,
    valset_bp,
    wflwbld_bp,
    submit_bp,
    approv_bp,
    rptbld_bp,
    auditl_bp,
    notify_bp,
    period_bp,
]


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    db.init_app(app)

    for blueprint in MODULE_BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/db-health")
    def db_health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"database": "connected"})
        except Exception as error:
            return jsonify({"database": "unavailable", "error": str(error)}), 503

    @app.route("/no-access")
    def no_access():
        return render_template("no_access.html"), 403

    return app
