"""Tests du plugin system."""
import pytest


class _FakeConnector:
    def __init__(self, name: str):
        self.name = name
        self.healthy = True

    async def health_check(self) -> bool:
        return self.healthy

    def close(self) -> None:
        self.healthy = False


class _FakePlugin:
    from omniagent.connectors.plugins.contract import PluginMetadata
    metadata = PluginMetadata(
        name="fake_connector", version="1.0.0", category="comptabilite",
        description="Un faux connecteur",
    )

    def instantiate(self, config):
        return _FakeConnector(config.get("name", "test"))

    async def health_check(self, instance):
        return await instance.health_check()

    def shutdown(self, instance):
        instance.close()


def test_register_and_get_plugin():
    from omniagent.connectors.plugins.manager import plugin_manager
    plugin_manager._plugins.clear()
    plugin_manager._instances.clear()
    plugin_manager.register(_FakePlugin())
    inst = plugin_manager.get("fake_connector")
    assert inst.name == "test"


def test_configure_recreates_instance():
    from omniagent.connectors.plugins.manager import plugin_manager
    plugin_manager._plugins.clear()
    plugin_manager._instances.clear()
    plugin_manager.register(_FakePlugin())
    plugin_manager.configure("fake_connector", {"name": "configured"})
    inst = plugin_manager.get("fake_connector")
    assert inst.name == "configured"


@pytest.mark.asyncio
async def test_health_check_all():
    from omniagent.connectors.plugins.manager import plugin_manager
    plugin_manager._plugins.clear()
    plugin_manager._instances.clear()
    plugin_manager.register(_FakePlugin())
    plugin_manager.get("fake_connector")
    health = await plugin_manager.health_check_all()
    assert health["fake_connector"] is True


def test_unregister_removes_plugin():
    from omniagent.connectors.plugins.manager import plugin_manager
    plugin_manager._plugins.clear()
    plugin_manager._instances.clear()
    plugin_manager.register(_FakePlugin())
    plugin_manager.unregister("fake_connector")
    assert "fake_connector" not in plugin_manager._plugins