"""Grundlegende Plugin-Schnittstellen für die Host-Anwendung."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as exc:  # pragma: no cover - tkinter ist optional bei Tests
    raise RuntimeError("tkinter wird für die Host-Anwendung benötigt") from exc

from app.core.projects import ProjectManager
from app.core.resources import IsolationLibrary
from app.core.reporting import ReportManager


@dataclass(slots=True)
class AppContext:
    """Container für gemeinsam genutzte Tk-Widgets und Manager."""

    root: tk.Tk
    notebook: ttk.Notebook
    project_manager: ProjectManager
    isolation_library: IsolationLibrary
    report_manager: ReportManager


class Plugin(ABC):
    """Basisklasse für alle grafischen Plugins."""

    #: Anzeigename des Plugins im Host-Notebook.
    name: str = ""
    #: Optionaler Versionshinweis für Tooltips oder Überschriften.
    version: Optional[str] = None

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
