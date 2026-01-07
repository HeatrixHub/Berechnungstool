"""Base types for Qt UI plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib.util
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from PyQt6.QtWidgets import QMainWindow, QTabWidget
    except ModuleNotFoundError:
        from PySide6.QtWidgets import QMainWindow, QTabWidget
else:
    QMainWindow = Any
    QTabWidget = Any

if importlib.util.find_spec("PyQt6") is not None:
    from PyQt6.QtCore import QObject as _QtQObject

    _QT_OBJECT_TYPES: tuple[type[object], ...] = (_QtQObject,)
elif importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QObject as _QtQObject

    _QT_OBJECT_TYPES = (_QtQObject,)
else:
    _QT_OBJECT_TYPES = ()


@dataclass
class QtAppContext:
    """Plain data container passed into Qt plugins."""

    main_window: QMainWindow
    tab_widget: QTabWidget


class QtPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""

    @property
    @abstractmethod
    def identifier(self) -> str:
        """Stable identifier for persistence."""

    @abstractmethod
    def attach(self, context: QtAppContext) -> None:
        """Hook to register plugin UI into the application."""

    def export_state(self) -> dict[str, Any]:
        """Export plugin state following the {"inputs": ..., "results": ..., "ui": ...} convention.

        The returned dictionary must be JSON-serialisable and is expected to use the top-level
        sections as follows:

        - "inputs": user-entered values or selections.
        - "results": calculated outputs or derived values.
        - "ui": UI-only concerns such as view toggles or active tabs.
        """
        return {}

    def validate_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize state dictionaries.

        Allowed value types are dict/list/str/int/float/bool/None, and Qt objects are rejected.
        """
        if not isinstance(state, dict):
            raise TypeError("State must be a dictionary.")
        allowed_sections = {"inputs", "results", "ui"}
        normalized: dict[str, Any] = {section: {} for section in allowed_sections}
        legacy_sections: dict[str, Any] = {}
        for key, value in state.items():
            if key not in allowed_sections:
                self._validate_json_value(value, path=key)
                legacy_sections[key] = value
                continue
            if not isinstance(value, dict):
                raise TypeError(f"State section {key!r} must be a dictionary.")
            self._validate_json_value(value, path=key)
            normalized[key] = value
        if legacy_sections:
            inputs = normalized.get("inputs") or {}
            if isinstance(inputs, dict):
                merged = dict(legacy_sections)
                merged.update(inputs)
                normalized["inputs"] = merged
        return normalized

    def _validate_json_value(self, value: Any, *, path: str) -> None:
        if _QT_OBJECT_TYPES and isinstance(value, _QT_OBJECT_TYPES):
            raise TypeError(f"Qt object detected at {path}.")
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(f"Non-string dict key at {path}: {key!r}.")
                self._validate_json_value(item, path=f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._validate_json_value(item, path=f"{path}[{index}]")
            return
        if value is None or isinstance(value, (str, int, float, bool)):
            return
        raise TypeError(f"Unsupported value at {path}: {type(value).__name__}.")

    def import_state(self, state: dict[str, Any]) -> None:
        """Restore plugin state following the {"inputs": ..., "results": ..., "ui": ...} convention.

        Implementations should update internal state and then trigger a UI refresh.
        """
        normalized = self.validate_state(state)
        self.apply_state(normalized)
        self.refresh_view()

    def apply_state(self, state: dict[str, Any]) -> None:
        """Apply state data after validation (override in subclasses)."""

    def refresh_view(self) -> None:
        """Hook to synchronise UI elements with the current internal state."""
