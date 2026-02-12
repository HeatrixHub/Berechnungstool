"""Central manager for Qt UI plugins."""
from __future__ import annotations

import logging
import importlib
from typing import Callable, Sequence

from app.core.plugin_registry import RegistryError
from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from app.ui_qt.plugins.registry import QtPluginSpec, get_plugins

logger = logging.getLogger(__name__)


class QtPluginManager:
    def __init__(
        self,
        context: QtAppContext,
        plugin_specs: Sequence[QtPluginSpec] | None = None,
    ) -> None:
        self._context = context
        self._plugin_specs = tuple(plugin_specs) if plugin_specs is not None else tuple(get_plugins())
        self._plugins: dict[str, QtPlugin] = {}

    @property
    def plugins(self) -> dict[str, QtPlugin]:
        return dict(self._plugins)

    @property
    def plugin_specs(self) -> tuple[QtPluginSpec, ...]:
        return self._plugin_specs

    def load_plugins(self) -> None:
        for plugin_spec in self._plugin_specs:
            if plugin_spec.identifier in self._plugins:
                logger.warning("Duplicate plugin identifier %s skipped.", plugin_spec.identifier)
                continue
            plugin = self._load_plugin_instance(plugin_spec)
            self._apply_identifier(plugin, plugin_spec.identifier)
            plugin.attach(self._context)
            self._plugins[plugin_spec.identifier] = plugin
            widget = getattr(plugin, "widget", None)
            if widget is not None and hasattr(self._context.tab_widget, "addTab"):
                self._context.tab_widget.addTab(widget, plugin.name)

    def export_all_states(self) -> dict[str, dict]:
        states: dict[str, dict] = {}
        for plugin_id, plugin in self._plugins.items():
            try:
                states[plugin_id] = plugin.export_state()
            except Exception:
                logger.exception("Failed to export state for plugin %s.", plugin_id)
        return states

    def import_all_states(self, states: dict[str, dict]) -> None:
        for plugin_id, plugin in self._plugins.items():
            if plugin_id not in states:
                logger.warning("No saved state for plugin %s.", plugin_id)
                continue
            state = states[plugin_id]
            if not isinstance(state, dict):
                logger.warning("Ignoring state for plugin %s because it is not a dict.", plugin_id)
                continue
            try:
                plugin.import_state(state)
            except Exception:
                logger.exception("Failed to import state for plugin %s.", plugin_id)
        for plugin_id in states:
            if plugin_id not in self._plugins:
                logger.warning("Ignoring state for unknown plugin %s.", plugin_id)

    @staticmethod
    def _apply_identifier(plugin: QtPlugin, identifier: str) -> None:
        if hasattr(plugin, "_identifier"):
            setattr(plugin, "_identifier", identifier)
            return
        if hasattr(plugin, "identifier"):
            try:
                setattr(plugin, "identifier", identifier)
            except AttributeError:
                setattr(plugin, "_identifier", identifier)
            return
        setattr(plugin, "_identifier", identifier)

    @staticmethod
    def _load_plugin_instance(plugin_spec: QtPluginSpec) -> QtPlugin:
        try:
            module = importlib.import_module(plugin_spec.module)
            plugin_factory = QtPluginManager._resolve_factory(module, plugin_spec)
            plugin = plugin_factory()
        except Exception as exc:
            logger.exception(
                "Failed to load Qt plugin %s from %s.%s.",
                plugin_spec.identifier,
                plugin_spec.module,
                plugin_spec.class_name or plugin_spec.factory_name,
            )
            raise RegistryError(
                f"Qt plugin {plugin_spec.identifier} konnte nicht geladen werden"
            ) from exc
        if not isinstance(plugin, QtPlugin):
            raise RegistryError(
                f"Qt plugin {plugin_spec.identifier} ist kein QtPlugin"
            )
        return plugin

    @staticmethod
    def _resolve_factory(
        module: object, plugin_spec: QtPluginSpec
    ) -> type[QtPlugin] | Callable[[], QtPlugin]:
        if plugin_spec.class_name:
            try:
                return getattr(module, plugin_spec.class_name)
            except AttributeError as exc:
                raise RegistryError(
                    f"Qt plugin {plugin_spec.identifier} hat keine Klasse {plugin_spec.class_name}"
                ) from exc
        if plugin_spec.factory_name:
            try:
                return getattr(module, plugin_spec.factory_name)
            except AttributeError as exc:
                raise RegistryError(
                    f"Qt plugin {plugin_spec.identifier} hat keine Factory {plugin_spec.factory_name}"
                ) from exc
        raise RegistryError(
            f"Qt plugin {plugin_spec.identifier} benötigt class_name oder factory_name"
        )
