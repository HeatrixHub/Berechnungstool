"""Projektverwaltung für alle Plugins."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ProjectSnapshot:
    """Einfache Datenstruktur für einen Projektzustand."""

    name: str
    data: Dict[str, Any] = field(default_factory=dict)


class ProjectManager:
    """Verwaltet Projekte und plugin-spezifische Zustände."""

    def __init__(self) -> None:
        self._projects: Dict[str, ProjectSnapshot] = {}
        self._current: Optional[str] = None
        self._listeners: List[Callable[[], None]] = []
        self.create_project("Unbenanntes Projekt")

    def create_project(self, name: str, data: Optional[Dict[str, Any]] = None) -> ProjectSnapshot:
        if name in self._projects:
            raise ValueError(f"Projekt '{name}' existiert bereits")
        snapshot = ProjectSnapshot(name=name, data=data or {})
        self._projects[name] = snapshot
        self._current = name
        self._notify_listeners()
        return snapshot

    def list_projects(self) -> List[ProjectSnapshot]:
        return list(self._projects.values())

    def set_current(self, name: str) -> None:
        if name not in self._projects:
            raise KeyError(f"Projekt '{name}' nicht gefunden")
        self._current = name
        self._notify_listeners()

    def get_current(self) -> ProjectSnapshot:
        if not self._current:
            raise RuntimeError("Kein Projekt ausgewählt")
        return self._projects[self._current]

    def update_plugin_state(self, plugin_name: str, state: Dict[str, Any]) -> None:
        project = self.get_current()
        project.data.setdefault("plugins", {})[plugin_name] = state
        self._notify_listeners()

    def get_plugin_state(self, plugin_name: str) -> Dict[str, Any]:
        project = self.get_current()
        return project.data.get("plugins", {}).get(plugin_name, {})

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                continue
