"""Adapter : permet d exposer un connecteur existant en plugin sans le reecrire."""
from __future__ import annotations
from typing import Any

from omniagent.connectors.plugins.contract import Plugin, PluginMetadata


class ConnectorAdapter(Plugin):
    """Wrap un Connector existant en Plugin hot-pluggable."""

    def __init__(self, name: str, category: str, connector_class, version: str = "1.0.0"):
        self.metadata = PluginMetadata(
            name=name, version=version, category=category,
            description=f"Adapter for {connector_class.__name__}",
        )
        self._cls = connector_class

    def instantiate(self, config: dict) -> Any:
        return self._cls(**config)

    async def health_check(self, instance: Any) -> bool:
        return await instance.health_check()

    def shutdown(self, instance: Any) -> None:
        import asyncio
        try:
            asyncio.get_event_loop().run_until_complete(instance.close())
        except Exception:
            pass