"""Base types for Qt UI plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from PyQt6.QtWidgets import QMainWindow, QTabWidget
    except ModuleNotFoundError:
        from PySide6.QtWidgets import QMainWindow, QTabWidget
else:
    QMainWindow = Any
    QTabWidget = Any


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
        """Optional hook to export plugin state."""
        return {}

    def import_state(self, state: dict[str, Any]) -> None:
        """Optional hook to restore plugin state."""
        return None
