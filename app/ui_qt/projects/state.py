"""Project state coordination for Qt plugins."""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import logging
from typing import Any, Callable, Iterable, Sequence

from app.ui_qt.plugins.base import QtPlugin
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.plugins.registry import QtPluginSpec

logger = logging.getLogger(__name__)


class PluginStateCoordinator:
    """Collects and applies plugin states in a deterministic order."""

    def __init__(
        self,
        plugin_manager: QtPluginManager,
        plugin_specs: Sequence[QtPluginSpec] | None = None,
    ) -> None:
        self._plugin_manager = plugin_manager
        self._plugin_specs = tuple(plugin_specs or plugin_manager.plugin_specs)

    def collect_states(self) -> tuple[dict[str, dict[str, Any]], list[str]]:
        states: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        for plugin_id, plugin in self._iter_plugins_in_order():
            try:
                raw_state = plugin.export_state()
                normalized = plugin.validate_state(raw_state)
            except Exception as exc:  # pragma: no cover - logging guard
                logger.exception("Failed to export state for plugin %s.", plugin_id)
                errors.append(f"{plugin_id}: {exc}")
                continue
            states[plugin_id] = normalized
        logger.info("Collected plugin states for %s plugins.", len(states))
        return states, errors

    def apply_states(
        self, states: dict[str, dict[str, Any]]
    ) -> tuple[list[str], list[str], list[str]]:
        missing: list[str] = []
        unknown: list[str] = []
        errors: list[str] = []
        for plugin_id, plugin in self._iter_plugins_in_order():
            if plugin_id not in states:
                missing.append(plugin_id)
                continue
            state = states.get(plugin_id)
            if not isinstance(state, dict):
                errors.append(f"{plugin_id}: state is not a dict")
                continue
            try:
                plugin.import_state(state)
            except Exception as exc:  # pragma: no cover - logging guard
                logger.exception("Failed to import state for plugin %s.", plugin_id)
                errors.append(f"{plugin_id}: {exc}")
        for plugin_id in states:
            if plugin_id not in self._plugin_manager.plugins:
                unknown.append(plugin_id)
        logger.info(
            "Applied plugin states. Missing=%s Unknown=%s Errors=%s",
            len(missing),
            len(unknown),
            len(errors),
        )
        return missing, unknown, errors

    def _iter_plugins_in_order(self) -> Iterable[tuple[str, QtPlugin]]:
        for spec in self._plugin_specs:
            plugin = self._plugin_manager.plugins.get(spec.identifier)
            if plugin is None:
                continue
            yield spec.identifier, plugin


class DirtyStateTracker:
    """Observes Qt widgets and raises a dirty flag on user changes."""

    _SIGNAL_NAMES = (
        "textChanged",
        "currentIndexChanged",
        "currentTextChanged",
        "valueChanged",
        "toggled",
        "stateChanged",
        "editingFinished",
        "itemChanged",
        "itemSelectionChanged",
        "currentChanged",
        "dateChanged",
        "timeChanged",
        "dateTimeChanged",
    )

    def __init__(self, on_dirty: Callable[[], None]) -> None:
        self._on_dirty = on_dirty
        self._paused = 0
        self._connections: set[tuple[int, str]] = set()
        self._qt_available, self._QObject = _resolve_qt_core()

    @contextmanager
    def paused(self) -> Iterable[None]:
        self.pause()
        try:
            yield
        finally:
            self.resume()

    def pause(self) -> None:
        self._paused += 1

    def resume(self) -> None:
        self._paused = max(0, self._paused - 1)

    def attach_widget(self, widget: object | None) -> None:
        if not self._qt_available or widget is None:
            return
        self._attach_object(widget)
        if hasattr(widget, "findChildren"):
            try:
                children = widget.findChildren(self._QObject)
            except Exception:  # pragma: no cover - safety guard
                children = []
            for child in children:
                self._attach_object(child)

    def _attach_object(self, obj: object) -> None:
        for signal_name in self._SIGNAL_NAMES:
            if not hasattr(obj, signal_name):
                continue
            signal = getattr(obj, signal_name)
            if not hasattr(signal, "connect"):
                continue
            key = (id(obj), signal_name)
            if key in self._connections:
                continue
            try:
                signal.connect(self._handle_dirty_signal)
            except Exception:  # pragma: no cover - safety guard
                continue
            self._connections.add(key)

    def _handle_dirty_signal(self, *_args: object, **_kwargs: object) -> None:
        if self._paused:
            return
        self._on_dirty()


def _resolve_qt_core() -> tuple[bool, type[object] | None]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtCore import QObject

        return True, QObject
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtCore import QObject

        return True, QObject
    return False, None
