"""Tests RBAC : verification des permissions par role."""
from omniagent.core.security.rbac import has_permission, Role


def test_admin_has_all_access_on_emploi():
    for agent in ("agent_x", "agent_emploi", "agent_followup"):
        assert has_permission(Role.ADMIN, "emploi", agent)
    assert not has_permission(Role.ADMIN, "marketing", "agent_x")


def test_recruiter_only_emploi():
    assert has_permission(Role.RECRUITER, "emploi", "agent_emploi")
    assert has_permission(Role.RECRUITER, "emploi", "agent_contact_enrichment")
    assert has_permission(Role.RECRUITER, "emploi", "agent_lettre_requirement")
    assert has_permission(Role.RECRUITER, "emploi", "agent_filtering_matching")
    assert has_permission(Role.RECRUITER, "emploi", "agent_mission_controller")
    assert has_permission(Role.RECRUITER, "emploi", "agent_application_sender")
    assert not has_permission(Role.RECRUITER, "marketing", "agent_instagram")
    assert not has_permission(Role.RECRUITER, "recouvrement", "agent_vocal")


def test_user_has_limited_emploi_scope():
    assert has_permission(Role.USER, "emploi", "agent_emploi")
    assert has_permission(Role.USER, "emploi", "agent_cv")
    assert has_permission(Role.USER, "emploi", "agent_contact_enrichment")
    assert has_permission(Role.USER, "emploi", "agent_lettre_requirement")
    assert has_permission(Role.USER, "emploi", "agent_filtering_matching")
    assert has_permission(Role.USER, "emploi", "agent_mission_controller")
    assert has_permission(Role.USER, "emploi", "agent_application_sender")
    assert not has_permission(Role.USER, "emploi", "agent_linkedin")
    assert not has_permission(Role.USER, "emploi", "agent_indeed")
    assert not has_permission(Role.USER, "marketing", "agent_x")


def test_unknown_role_or_module_is_denied():
    assert not has_permission(Role.RECRUITER, "transverse", "agent_memory")