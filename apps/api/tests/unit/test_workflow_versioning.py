"""Tests du workflow versioning + capability registry."""
import pytest


def test_register_and_get():
    from omniagent.core.workflow.versioning import (
        WorkflowRegistry, WorkflowDefinition, WorkflowVersion,
    )
    reg = WorkflowRegistry()
    reg.register(WorkflowDefinition(
        version=WorkflowVersion("search_job", "1.0.0"),
        steps=[{"agent": "agent_linkedin"}],
    ))
    d = reg.get("search_job")
    assert d.version.version == "1.0.0"


def test_get_specific_version():
    from omniagent.core.workflow.versioning import (
        WorkflowRegistry, WorkflowDefinition, WorkflowVersion,
    )
    reg = WorkflowRegistry()
    reg.register(WorkflowDefinition(version=WorkflowVersion("w", "1.0.0"), steps=[]))
    reg.register(WorkflowDefinition(version=WorkflowVersion("w", "2.0.0"), steps=[]))
    assert reg.get("w", "1.0.0").version.version == "1.0.0"
    assert reg.get("w", "2.0.0").version.version == "2.0.0"


def test_deprecate():
    from omniagent.core.workflow.versioning import (
        WorkflowRegistry, WorkflowDefinition, WorkflowVersion,
    )
    reg = WorkflowRegistry()
    reg.register(WorkflowDefinition(version=WorkflowVersion("w", "1.0.0"), steps=[]))
    reg.deprecate("w", "1.0.0")
    assert reg.get("w", "1.0.0").version.deprecated is True


def test_migration_registry():
    from omniagent.core.workflow.migrations import MigrationRegistry
    reg = MigrationRegistry()
    reg.register("w", "1.0.0", "2.0.0", lambda p: {**p, "new_field": "default"})
    result = reg.migrate("w", "1.0.0", "2.0.0", {"old": "data"})
    assert result["old"] == "data"
    assert result["new_field"] == "default"


def test_capability_registry_search_by_kind():
    from omniagent.core.capabilities.registry import (
        CapabilityRegistry, Capability, CapabilityKind,
    )
    reg = CapabilityRegistry()
    reg.register(Capability(name="c1", kind=CapabilityKind.SEARCH,
                             owner="agent_a", owner_kind="agent", description="Search A"))
    reg.register(Capability(name="c2", kind=CapabilityKind.SEND,
                             owner="agent_b", owner_kind="agent", description="Send B"))
    found = reg.find_by_kind(CapabilityKind.SEARCH)
    assert len(found) == 1
    assert found[0].name == "c1"


def test_capability_can_serve():
    from omniagent.core.capabilities.registry import (
        CapabilityRegistry, Capability, CapabilityKind,
    )
    reg = CapabilityRegistry()
    # La capability de base
    reg.register(Capability(name="base", kind=CapabilityKind.SEARCH,
                             owner="a", owner_kind="agent", description=""))
    # La capability avancee qui depend de base
    reg.register(Capability(name="advanced", kind=CapabilityKind.SEARCH,
                             owner="a", owner_kind="agent", description="",
                             requires=["base"]))
    assert reg.can_serve("a", "advanced") is True
    assert reg.can_serve("b", "advanced") is False
    # Un agent sans la capability de base ne peut pas servir advanced
    reg.register(Capability(name="solo", kind=CapabilityKind.SEARCH,
                             owner="c", owner_kind="agent", description="",
                             requires=["base"]))
    assert reg.can_serve("c", "solo") is False