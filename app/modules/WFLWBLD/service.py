from datetime import datetime, timezone
from app.database import db
from app.modules.WFLWBLD.model import Workflow, WorkflowVersion, WorkflowLevel, WorkflowLevelApprover
from app.modules.USRMGMT.model import User

NO_ELIGIBLE_PATH_MESSAGE = (
    "This workflow has no eligible reviewer path for this submission site. "
    "Please contact setup support."
)


def list_workflows():
    return Workflow.query.filter_by(is_deleted=False).all()

def get_workflow(workflow_id):
    return Workflow.query.filter_by(id=workflow_id, is_deleted=False).one_or_none()

def get_workflow_by_code(code):
    return Workflow.query.filter_by(code=code, is_deleted=False).one_or_none()

def create_workflow(name, code, user_id):
    if not name or not name.strip():
        raise ValueError("Workflow name is required.")
    if not code or not code.strip():
        raise ValueError("Workflow code is required.")
        
    existing = get_workflow_by_code(code)
    if existing:
        raise ValueError(f"Workflow with code '{code}' already exists.")
        
    workflow = Workflow(
        name=name.strip(),
        code=code.strip(),
        created_by=user_id,
        updated_by=user_id
    )
    db.session.add(workflow)
    db.session.flush()
    
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        created_by=user_id
    )
    db.session.add(version)
    db.session.flush()
    
    return workflow

def get_workflow_version(version_id):
    return WorkflowVersion.query.get(version_id)

def get_workflow_version_levels(workflow_version_id):
    return (
        WorkflowLevel.query.filter_by(workflow_version_id=workflow_version_id, is_deleted=False)
        .order_by(WorkflowLevel.level_number.asc())
        .all()
    )


def get_eligible_level_approvers(level, site_id):
    return (
        WorkflowLevelApprover.query.join(
            User, User.id == WorkflowLevelApprover.user_id
        ).filter(
            WorkflowLevelApprover.workflow_level_id == level.id,
            WorkflowLevelApprover.is_deleted == False,
            User.is_deleted == False,
            User.is_active == True,
            (
                (WorkflowLevelApprover.scope_site_id.is_(None))
                | (WorkflowLevelApprover.scope_site_id == site_id)
            ),
        )
        .order_by(
            WorkflowLevelApprover.sequence_number.asc().nullslast(),
            WorkflowLevelApprover.id.asc(),
        )
        .all()
    )


def level_has_eligible_approver(level, site_id):
    return len(get_eligible_level_approvers(level, site_id)) > 0


def is_user_eligible_level_approver(level, user_id, site_id):
    return any(app.user_id == user_id for app in get_eligible_level_approvers(level, site_id))


def find_next_applicable_level(workflow_version, site_id, after_level_number):
    workflow_version_id = workflow_version.id if hasattr(workflow_version, "id") else workflow_version
    levels = (
        WorkflowLevel.query.filter(
            WorkflowLevel.workflow_version_id == workflow_version_id,
            WorkflowLevel.level_number > after_level_number,
            WorkflowLevel.is_deleted == False,
        )
        .order_by(WorkflowLevel.level_number.asc())
        .all()
    )

    for level in levels:
        if level_has_eligible_approver(level, site_id):
            return level
        if level.skip_if_empty:
            continue
        raise ValueError(
            f"Workflow level '{level.level_name}' has no eligible reviewer for this submission site."
        )

    return None


def validate_workflow_path_for_site(workflow_version, site_id):
    workflow_version_id = workflow_version.id if hasattr(workflow_version, "id") else workflow_version
    levels = get_workflow_version_levels(workflow_version_id)
    has_applicable_level = False

    for level in levels:
        if level_has_eligible_approver(level, site_id):
            has_applicable_level = True
            continue
        if not level.skip_if_empty:
            raise ValueError(NO_ELIGIBLE_PATH_MESSAGE)

    if not has_applicable_level:
        raise ValueError(NO_ELIGIBLE_PATH_MESSAGE)

    return True

def _validate_level_definition(level_name, approval_mode, level_number):
    if not level_name or not level_name.strip():
        raise ValueError(f"Level name is required for level {level_number}.")
    if approval_mode not in ("ANY_ONE", "SEQUENTIAL"):
        raise ValueError(f"Invalid approval mode '{approval_mode}' for level {level_number}. Must be ANY_ONE or SEQUENTIAL.")


def _create_level_approver(level, user_id, sequence_number, scope_site_id, actor_user_id):
    """
    Validates and creates a single WorkflowLevelApprover row: the reviewer must be
    an existing, active user, and any site scope must reference a real site. Shared
    by the full workflow-level editor (save_workflow_draft_levels) and the
    workbook's site-scoped chain editor (save_site_chain_levels) so both enforce
    the same rules instead of each maintaining its own copy.
    """
    if not user_id:
        raise ValueError(f"User ID is required for reviewer in level {level.level_number}.")

    user = User.query.filter_by(id=user_id, is_deleted=False, is_active=True).first()
    if not user:
        raise ValueError(f"Reviewer user with ID {user_id} does not exist or is inactive.")

    if scope_site_id in ("", "null"):
        scope_site_id = None
    if scope_site_id is not None:
        try:
            scope_site_id = int(scope_site_id)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid site scope for reviewer in level {level.level_number}.")
        from app.modules.SITEMST.model import Site
        site = Site.query.filter_by(id=scope_site_id, is_deleted=False).first()
        if not site:
            raise ValueError(f"Site with ID {scope_site_id} does not exist or is inactive.")

    approver = WorkflowLevelApprover(
        workflow_level_id=level.id,
        user_id=user_id,
        scope_site_id=scope_site_id,
        sequence_number=sequence_number,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.session.add(approver)
    return approver


def save_workflow_draft_levels(workflow_version_id, levels_list, user_id):
    version = WorkflowVersion.query.get(workflow_version_id)
    if not version:
        raise ValueError("Workflow version not found.")
    if version.published_at is not None:
        raise ValueError("Only Draft versions can be modified.")

    # Soft-delete existing levels and approvers for this draft version instead of hard-deleting
    existing_levels = WorkflowLevel.query.filter_by(workflow_version_id=workflow_version_id, is_deleted=False).all()
    for lvl in existing_levels:
        existing_approvers = WorkflowLevelApprover.query.filter_by(workflow_level_id=lvl.id, is_deleted=False).all()
        for app in existing_approvers:
            app.is_deleted = True
            app.deleted_by = user_id
            app.deleted_at = datetime.now(timezone.utc)
            app.delete_reason = "Overwritten by new draft save"
        lvl.is_deleted = True
        lvl.deleted_by = user_id
        lvl.deleted_at = datetime.now(timezone.utc)
        lvl.delete_reason = "Overwritten by new draft save"
    db.session.flush()

    # Insert new levels and their approvers
    for idx, l_data in enumerate(levels_list):
        level_number = l_data.get("level_number", idx + 1)
        level_name = l_data.get("level_name")
        approval_mode = l_data.get("approval_mode")
        skip_if_empty = bool(l_data.get("skip_if_empty", False))
        approvers = l_data.get("approvers", [])

        _validate_level_definition(level_name, approval_mode, level_number)
        if not approvers:
            raise ValueError(f"At least one reviewer is required for level {level_number}.")

        lvl = WorkflowLevel(
            workflow_version_id=workflow_version_id,
            level_number=level_number,
            level_name=level_name.strip(),
            approval_mode=approval_mode,
            skip_if_empty=skip_if_empty,
            created_by=user_id,
            updated_by=user_id
        )
        db.session.add(lvl)
        db.session.flush()

        for seq, app_data in enumerate(approvers):
            if isinstance(app_data, dict):
                u_id = app_data.get("user_id")
                s_num = app_data.get("sequence_number")
                scope_site_id = app_data.get("scope_site_id")
            else:
                u_id = app_data
                s_num = None
                scope_site_id = None

            if approval_mode == "SEQUENTIAL":
                if s_num is None:
                    s_num = seq + 1
            else:
                s_num = None

            _create_level_approver(lvl, u_id, s_num, scope_site_id, user_id)

    db.session.flush()
    return True


def save_site_chain_levels(workflow_version_id, site_id, steps, user_id):
    """
    Site-scoped variant of the level/approver editor, backing the workbook's
    simplified per-site chain UI (WKBK). Levels are shared across every site
    assigned to a workflow; only approver assignments are site-scoped
    (WorkflowLevelApprover.scope_site_id). So unlike save_workflow_draft_levels
    (a full wholesale replace of every level and approver), this only replaces
    the approvers tagged to `site_id`, leaving other sites' approvers on the
    same levels untouched. It reuses the same level/approver validation as
    save_workflow_draft_levels (_validate_level_definition, _create_level_approver)
    rather than re-implementing weaker checks a second time. This simplified UI
    only supports ANY_ONE mode -- SEQUENTIAL chains require the standalone
    Approval Path Builder.
    """
    version = WorkflowVersion.query.get(workflow_version_id)
    if not version:
        raise ValueError("Workflow version not found.")
    if version.published_at is not None:
        raise ValueError("Only Draft versions can be modified.")

    now = datetime.now(timezone.utc)
    posted_level_numbers = {step["level_number"] for step in steps}

    existing_levels = WorkflowLevel.query.filter_by(
        workflow_version_id=workflow_version_id, is_deleted=False
    ).all()

    for level in existing_levels:
        if level.level_number not in posted_level_numbers:
            level.is_deleted = True
            level.deleted_by = user_id
            level.deleted_at = now
            level.delete_reason = "Removed from workbook chain editor"

    level_map = {lvl.level_number: lvl for lvl in existing_levels if not lvl.is_deleted}

    for step in steps:
        level_number = step.get("level_number")
        level_name = step.get("level_name")
        approval_mode = "ANY_ONE"
        _validate_level_definition(level_name, approval_mode, level_number)

        level = level_map.get(level_number)
        if level:
            if level.level_name != level_name.strip():
                level.level_name = level_name.strip()
                level.updated_by = user_id
        else:
            level = WorkflowLevel(
                workflow_version_id=workflow_version_id,
                level_number=level_number,
                level_name=level_name.strip(),
                approval_mode=approval_mode,
                skip_if_empty=False,
                created_by=user_id,
                updated_by=user_id,
            )
            db.session.add(level)
            db.session.flush()
            level_map[level_number] = level

    db.session.flush()

    # At least one approver is required per posted level for this site.
    steps_by_level = {}
    for step in steps:
        steps_by_level.setdefault(step["level_number"], []).append(step)
    for level_number, level_steps in steps_by_level.items():
        if not any(s.get("user_id") for s in level_steps):
            level_name = level_steps[0].get("level_name") or f"level {level_number}"
            raise ValueError(f"At least one reviewer is required for level '{level_name}'.")

    all_version_level_ids = [
        lvl.id for lvl in WorkflowLevel.query.filter_by(workflow_version_id=workflow_version_id).all()
    ]
    if all_version_level_ids:
        for approver in WorkflowLevelApprover.query.filter(
            WorkflowLevelApprover.workflow_level_id.in_(all_version_level_ids),
            WorkflowLevelApprover.scope_site_id == site_id,
            WorkflowLevelApprover.is_deleted == False,
        ).all():
            approver.is_deleted = True
            approver.deleted_by = user_id
            approver.deleted_at = now
            approver.delete_reason = "Overwritten by workbook chain editor save"

    db.session.flush()

    for step in steps:
        if step.get("user_id"):
            level = level_map.get(step["level_number"])
            if level:
                _create_level_approver(level, step["user_id"], None, site_id, user_id)

    db.session.flush()
    return True

def publish_workflow_version(workflow_version_id, user_id):
    version = WorkflowVersion.query.get(workflow_version_id)
    if not version:
        raise ValueError("Workflow version not found.")
    if version.published_at is not None:
        raise ValueError("Workflow version is already published.")
        
    levels = WorkflowLevel.query.filter_by(workflow_version_id=workflow_version_id, is_deleted=False).order_by(WorkflowLevel.level_number.asc()).all()
    if not levels:
        raise ValueError("Cannot publish workflow without any levels.")
        
    for lvl in levels:
        approvers = WorkflowLevelApprover.query.filter_by(workflow_level_id=lvl.id, is_deleted=False).all()
        if not approvers:
            raise ValueError(f"Level '{lvl.level_name}' has no reviewers assigned.")
            
        for app in approvers:
            user = User.query.filter_by(id=app.user_id, is_deleted=False, is_active=True).first()
            if not user:
                raise ValueError(f"Reviewer user with ID {app.user_id} in level '{lvl.level_name}' is inactive or deleted.")
                
        if lvl.approval_mode == "SEQUENTIAL":
            seq_nums = [app.sequence_number for app in approvers]
            if any(s is None for s in seq_nums):
                raise ValueError(f"All reviewers in sequential level '{lvl.level_name}' must have a sequence number.")
            if len(seq_nums) != len(set(seq_nums)):
                raise ValueError(f"Sequence numbers must be unique within sequential level '{lvl.level_name}'.")
                
    # Mark as published
    version.published_at = datetime.now(timezone.utc)
    version.published_by = user_id
    
    # Update parent workflow
    workflow = get_workflow(version.workflow_id)
    if workflow:
        workflow.current_version_id = version.id
        workflow.updated_by = user_id
        
    return version

def create_new_workflow_version_draft(workflow_id, user_id):
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise ValueError("Workflow not found.")
        
    pending_draft = WorkflowVersion.query.filter_by(
        workflow_id=workflow_id,
        published_at=None
    ).first()
    if pending_draft:
        raise ValueError("A Draft version already exists. Work on that version first.")
        
    max_ver = db.session.query(db.func.max(WorkflowVersion.version_number)).filter_by(
        workflow_id=workflow_id
    ).scalar() or 0
    
    new_version = WorkflowVersion(
        workflow_id=workflow_id,
        version_number=max_ver + 1,
        created_by=user_id
    )
    db.session.add(new_version)
    db.session.flush()
    
    # Copy from latest version
    latest_ver = WorkflowVersion.query.filter_by(
        workflow_id=workflow_id
    ).filter(WorkflowVersion.id != new_version.id).order_by(WorkflowVersion.version_number.desc()).first()
    
    if latest_ver:
        prev_levels = WorkflowLevel.query.filter_by(workflow_version_id=latest_ver.id, is_deleted=False).order_by(WorkflowLevel.level_number.asc()).all()
        for pl in prev_levels:
            new_level = WorkflowLevel(
                workflow_version_id=new_version.id,
                level_number=pl.level_number,
                level_name=pl.level_name,
                approval_mode=pl.approval_mode,
                skip_if_empty=pl.skip_if_empty,
                created_by=user_id,
                updated_by=user_id
            )
            db.session.add(new_level)
            db.session.flush()
            
            prev_approvers = WorkflowLevelApprover.query.filter_by(workflow_level_id=pl.id, is_deleted=False).all()
            for pa in prev_approvers:
                new_app = WorkflowLevelApprover(
                    workflow_level_id=new_level.id,
                    user_id=pa.user_id,
                    scope_site_id=pa.scope_site_id,
                    sequence_number=pa.sequence_number,
                    created_by=user_id,
                    updated_by=user_id
                )
                db.session.add(new_app)
                
    db.session.flush()
    return new_version

def delete_workflow(workflow_id, user_id):
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise ValueError("Workflow not found.")
    workflow.is_deleted = True
    workflow.deleted_by = user_id
    workflow.deleted_at = datetime.now(timezone.utc)
    workflow.delete_reason = "Deleted by user"
    return True
