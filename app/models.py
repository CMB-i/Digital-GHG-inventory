"""Import all SQLAlchemy models for Alembic autogenerate."""

from app.modules.ACCESS import model as access_model  # noqa: F401
from app.modules.APPROV import model as approv_model  # noqa: F401
from app.modules.AUDITL import model as auditl_model  # noqa: F401
from app.modules.FORMBLD import model as formbld_model  # noqa: F401
from app.modules.FRMULA import model as frmula_model  # noqa: F401
from app.modules.NOTIFY import model as notify_model  # noqa: F401
from app.modules.PERIOD import model as period_model  # noqa: F401
from app.modules.RPTBLD import model as rptbld_model  # noqa: F401
from app.modules.SITEMST import model as sitemst_model  # noqa: F401
from app.modules.SUBMIT import model as submit_model  # noqa: F401
from app.modules.USRMGMT import model as usrmgmt_model  # noqa: F401
from app.modules.VALSET import model as valset_model  # noqa: F401
from app.modules.WFLWBLD import model as wflwbld_model  # noqa: F401
