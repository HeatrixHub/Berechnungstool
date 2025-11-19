"""Dateibasierte Ablage für Projekte und Plugin-Zustände."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


@dataclass(slots=True)
class ProjectRecord:
    """Beschreibt einen gespeicherten Projektzustand."""

    id: str
    name: str
    author: str
    created_at: str
    updated_at: str
    plugin_states: Dict[str, Any]


class ProjectStore:
    """Verwaltet das Lesen und Schreiben von Projektzuständen."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).with_name("projects.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {"projects": []}
        self._load()

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------
    def list_projects(self) -> List[ProjectRecord]:
        """Liefert alle Projekte, sortiert nach Aktualisierungsdatum."""

        projects = [self._to_record(item) for item in self._data.get("projects", [])]
        projects.sort(key=lambda record: record.updated_at, reverse=True)
        return projects

    def load_project(self, project_id: str) -> Optional[ProjectRecord]:
        """Lädt ein Projekt anhand seiner ID."""

        for entry in self._data.get("projects", []):
            if entry.get("id") == project_id:
                return self._to_record(entry)
        return None

    def save_project(
        self,
        *,
        name: str,
        author: str,
        plugin_states: Dict[str, Any],
        project_id: str | None = None,
    ) -> ProjectRecord:
        """Erstellt oder aktualisiert einen Projekt-Datensatz."""

        sanitized_states = self._ensure_json_serializable(plugin_states)
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        if project_id:
            record = self._update_project(
                project_id,
                name=name,
                author=author,
                plugin_states=sanitized_states,
                updated_at=now,
            )
        else:
            record = self._create_project(
                name=name,
                author=author,
                plugin_states=sanitized_states,
                created_at=now,
                updated_at=now,
            )
        self._persist()
        return record

    def delete_project(self, project_id: str) -> bool:
        """Löscht einen Datensatz. Gibt True zurück, wenn er existierte."""

        projects: List[Dict[str, Any]] = self._data.get("projects", [])
        before = len(projects)
        projects[:] = [p for p in projects if p.get("id") != project_id]
        if len(projects) != before:
            self._persist()
            return True
        return False

    # ------------------------------------------------------------------
    # Interne Helfer
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            self._persist()
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            # Fallback auf leere Struktur, wenn Datei beschädigt ist
            self._data = {"projects": []}

    def _persist(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _to_record(self, data: Dict[str, Any]) -> ProjectRecord:
        return ProjectRecord(
            id=str(data.get("id")),
            name=str(data.get("name", "")),
            author=str(data.get("author", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            plugin_states=data.get("plugin_states", {}) or {},
        )

    def _ensure_json_serializable(self, states: Dict[str, Any]) -> Dict[str, Any]:
        try:
            serialized = json.dumps(states, ensure_ascii=False)
        except TypeError as exc:
            raise ValueError(
                "Plugin-Zustände enthalten nicht serialisierbare Daten"
            ) from exc
        return json.loads(serialized)

    def _create_project(
        self,
        *,
        name: str,
        author: str,
        plugin_states: Dict[str, Any],
        created_at: str,
        updated_at: str,
    ) -> ProjectRecord:
        if not name:
            raise ValueError("Projektname darf nicht leer sein")
        project = {
            "id": uuid4().hex,
            "name": name,
            "author": author,
            "created_at": created_at,
            "updated_at": updated_at,
            "plugin_states": plugin_states,
        }
        self._data.setdefault("projects", []).append(project)
        return self._to_record(project)

    def _update_project(
        self,
        project_id: str,
        *,
        name: str,
        author: str,
        plugin_states: Dict[str, Any],
        updated_at: str,
    ) -> ProjectRecord:
        for project in self._data.get("projects", []):
            if project.get("id") == project_id:
                project.update(
                    {
                        "name": name,
                        "author": author,
                        "plugin_states": plugin_states,
                        "updated_at": updated_at,
                    }
                )
                return self._to_record(project)
        raise ValueError(f"Projekt mit ID {project_id} existiert nicht")
