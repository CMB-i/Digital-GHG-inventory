import uuid

from app.modules.WFLWBLD.model import Workflow, WorkflowLevel, WorkflowLevelApprover, WorkflowVersion
from app.modules.WFLWBLD.service import save_site_chain_levels, validate_workflow_path_for_site


def test_site_chain_edit_does_not_delete_shared_level_used_by_another_site(
    make_user, make_site, db_session, created_objects, system_user,
):
    editor = make_user()
    site_a = make_site()
    site_b = make_site()
    approver_a = make_user()
    approver_b = make_user()

    workflow = Workflow(
        name="Shared Chain Test",
        code=f"shared-chain-{uuid.uuid4().hex[:10]}",
        created_by=system_user,
        updated_by=system_user,
    )
    db_session.add(workflow)
    db_session.flush()
    created_objects.append(workflow)

    version = WorkflowVersion(workflow_id=workflow.id, version_number=1, created_by=system_user)
    db_session.add(version)
    db_session.flush()
    created_objects.append(version)
    workflow.current_version_id = version.id

    level_one = WorkflowLevel(
        workflow_version_id=version.id,
        level_number=1,
        level_name="Level 1",
        approval_mode="ANY_ONE",
        created_by=system_user,
        updated_by=system_user,
    )
    level_two = WorkflowLevel(
        workflow_version_id=version.id,
        level_number=2,
        level_name="Level 2",
        approval_mode="ANY_ONE",
        created_by=system_user,
        updated_by=system_user,
    )
    db_session.add_all([level_one, level_two])
    db_session.flush()
    created_objects.extend([level_one, level_two])

    site_a_level_two = WorkflowLevelApprover(
        workflow_level_id=level_two.id,
        user_id=approver_a.id,
        scope_site_id=site_a.id,
        created_by=system_user,
        updated_by=system_user,
    )
    site_b_level_one = WorkflowLevelApprover(
        workflow_level_id=level_one.id,
        user_id=approver_b.id,
        scope_site_id=site_b.id,
        created_by=system_user,
        updated_by=system_user,
    )
    site_b_level_two = WorkflowLevelApprover(
        workflow_level_id=level_two.id,
        user_id=approver_b.id,
        scope_site_id=site_b.id,
        created_by=system_user,
        updated_by=system_user,
    )
    db_session.add_all([site_a_level_two, site_b_level_one, site_b_level_two])
    db_session.flush()
    created_objects.extend([site_a_level_two, site_b_level_one, site_b_level_two])

    save_site_chain_levels(
        version.id,
        site_a.id,
        [{"level_number": 1, "level_name": "Level 1", "user_id": approver_a.id}],
        editor.id,
    )
    db_session.flush()
    created_objects.extend(
        approver
        for approver in WorkflowLevelApprover.query.filter_by(
            workflow_level_id=level_one.id,
            scope_site_id=site_a.id,
            is_deleted=False,
        ).all()
        if approver not in created_objects
    )

    assert level_two.is_deleted is False
    assert site_b_level_one.is_deleted is False
    assert site_b_level_two.is_deleted is False
    assert site_a_level_two.is_deleted is True
    assert validate_workflow_path_for_site(version, site_b.id) is True
