"""Plugin Manager : hot-reload, decouverte dynamique, isolation."""
from __future__ import annotations
import importlib
from pathlib import Path
from typing import Any

from omniagent.connectors.plugins.contract import Plugin, PluginMetadata, PluginError


class PluginManager:
    """Gere un catalogue de plugins et permet de les (re)charger a chaud."""

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._instances: dict[str, Any] = {}
        self._config: dict[str, dict] = {}

    def register(self, plugin: Plugin) -> None:
        if plugin.metadata.name in self._plugins:
            raise PluginError(f"Plugin deja enregistre: {plugin.metadata.name}")
        self._plugins[plugin.metadata.name] = plugin

    def unregister(self, name: str) -> None:
        if name in self._instances:
            try:
                self._plugins[name].shutdown(self._instances[name])
            except Exception:
                pass
            del self._instances[name]
        self._plugins.pop(name, None)
        self._config.pop(name, None)

    def reload(self, name: str) -> None:
        """Recharge un plugin (utile en dev)."""
        if name not in self._plugins:
            raise PluginError(f"Plugin inconnu: {name}")
        if name in self._instances:
            self._plugins[name].shutdown(self._instances[name])
            del self._instances[name]
        cfg = self._config.get(name, {})
        self._instances[name] = self._plugins[name].instantiate(cfg)

    def configure(self, name: str, config: dict) -> None:
        self._config[name] = config
        if name in self._plugins:
            if name in self._instances:
                self._plugins[name].shutdown(self._instances[name])
            self._instances[name] = self._plugins[name].instantiate(config)

    def get(self, name: str) -> Any:
        if name not in self._instances:
            if name not in self._plugins:
                raise PluginError(f"Plugin inconnu: {name}")
            self._instances[name] = self._plugins[name].instantiate(self._config.get(name, {}))
        return self._instances[name]

    def list(self) -> list[dict]:
        return [
            {
                "name": p.metadata.name,
                "version": p.metadata.version,
                "category": p.metadata.category,
                "author": p.metadata.author,
                "description": p.metadata.description,
                "instantiated": name in self._instances,
            }
            for name, p in self._plugins.items()
        ]

    async def health_check_all(self) -> dict[str, bool]:
        out = {}
        for name, p in self._plugins.items():
            if name in self._instances:
                try:
                    out[name] = await p.health_check(self._instances[name])
                except Exception:
                    out[name] = False
            else:
                out[name] = False
        return out

    def discover_from_directory(self, path: str) -> int:
        """Decouvre et enregistre les plugins d un dossier (chaque .py = 1 plugin)."""
        p = Path(path)
        if not p.exists():
            return 0
        count = 0
        for f in p.glob("*.py"):
            if f.name.startswith("_"):
                continue
            module_name = f.stem
            try:
                spec = importlib.util.spec_from_file_location(
                    f"omniagent_plugin_{module_name}", str(f)
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "PLUGIN"):
                    self.register(module.PLUGIN)
                    count += 1
            except Exception as e:
                print(f"[PluginManager] failed to load {f.name}: {e}")
        return count


plugin_manager = PluginManager()