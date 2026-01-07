"""Grundlegende Plugin-Schnittstellen für die Host-Anwendung."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as exc:  # pragma: no cover - tkinter ist optional bei Tests
    raise RuntimeError("tkinter wird für die Host-Anwendung benötigt") from exc

if TYPE_CHECKING:  # pragma: no cover - nur für Typprüfungen
    from app.core.projects.store import ProjectStore


@dataclass(slots=True)
class AppContext:
    """Container für gemeinsam genutzte Tk-Widgets."""

    root: tk.Tk
    notebook: ttk.Notebook
    project_store: "ProjectStore"


class Plugin(ABC):
    """Basisklasse für alle grafischen Plugins."""

    #: Anzeigename des Plugins im Host-Notebook.
    name: str = ""
    #: Optionaler Versionshinweis für Tooltips oder Überschriften.
    version: Optional[str] = None
    #: Technischer Identifier aus der Plugin-Registry.
    identifier: Optional[str] = None

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(
                f"{self.__class__.__name__} muss ein 'name'-Attribut definieren"
            )

    @abstractmethod
    def attach(self, context: AppContext) -> None:
        """Erzeuge die Oberfläche innerhalb des Host-Notebooks."""

    def on_theme_changed(self, theme: str) -> None:  # pragma: no cover - optionale Hooks
        """Wird vom Host aufgerufen, wenn sich das sv_ttk-Theme ändert."""
        del theme

    def export_state(self) -> Dict[str, Any]:  # pragma: no cover - optionaler Hook
        """Liefert den aktuellen Zustand für den Projekte-Tab."""

        return {}

    def import_state(self, state: Dict[str, Any]) -> None:  # pragma: no cover
        """Stellt einen zuvor gespeicherten Zustand wieder her."""

        del state
