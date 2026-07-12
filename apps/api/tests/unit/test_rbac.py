"""Tests RBAC : verification des permissions par role."""
from omniagent.core.security.rbac import has_permission, Role


def test_admin_has_all_access():
    for module in ("emploi", "marketing", "recouvrement"):
        for agent in ("agent_x", "agent_y", "agent_z"):
            assert has_permission(Role.ADMIN, module, agent)


def test_recruiter_only_emploi():
    assert has_permission(Role.RECRUITER, "emploi", "agent_emploi")
    assert not has_permission(Role.RECRUITER, "marketing", "agent_instagram")
    assert not has_permission(Role.RECRUITER, "recouvrement", "agent_vocal")


def test_finance_only_recouvrement():
    assert has_permission(Role.FINANCE, "recouvrement", "agent_analyse_impayes")
    assert not has_permission(Role.FINANCE, "emploi", "agent_linkedin")
    assert not has_permission(Role.FINANCE, "marketing", "agent_x")


def test_marketer_only_marketing():
    assert has_permission(Role.MARKETER, "marketing", "agent_instagram")
    assert not has_permission(Role.MARKETER, "emploi", "agent_emploi")