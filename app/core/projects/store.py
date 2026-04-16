"""Dateibasierte Ablage für Projekte und Plugin-Zustände."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .isolierung_embedding import (
    build_embedded_isolierungen_from_plugin_states,
    normalize_resolution_entry,
)
from uuid import uuid4


@dataclass(slots=True)
class ProjectRecord:
    """Beschreibt einen gespeicherten Projektzustand."""

    id: str
    name: str
    author: str
    description: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    plugin_states: Dict[str, Any]
    ui_state: Dict[str, Any]
    embedded_isolierungen: Dict[str, Any]
    insulation_resolution: Dict[str, Any]


class ProjectStore:
    """Verwaltet das Lesen und Schreiben von Projektzuständen."""

    FORMAT_VERSION = 1

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).with_name("projects.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {
            "format_version": self.FORMAT_VERSION,
            "projects": [],
        }
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
        description: str = "",
        metadata: Dict[str, Any] | None = None,
        plugin_states: Dict[str, Any],
        ui_state: Dict[str, Any] | None = None,
        embedded_isolierungen: Dict[str, Any] | None = None,
        insulation_resolution: Dict[str, Any] | None = None,
        project_id: str | None = None,
        created_at_override: str | None = None,
        updated_at_override: str | None = None,
    ) -> ProjectRecord:
        """Erstellt oder aktualisiert einen Projekt-Datensatz."""

        sanitized_states = self._ensure_json_serializable(plugin_states)
        sanitized_ui_state = self._ensure_json_serializable(ui_state or {})
        sanitized_metadata = self._ensure_json_serializable(metadata or {})
        auto_embedded, auto_resolution = build_embedded_isolierungen_from_plugin_states(sanitized_states)
        selected_embedded = auto_embedded if embedded_isolierungen is None else embedded_isolierungen
        selected_resolution = auto_resolution if insulation_resolution is None else insulation_resolution
        sanitized_embedded = self._normalize_embedded_isolierungen(
            self._ensure_json_serializable(selected_embedded)
        )
        sanitized_resolution = self._normalize_insulation_resolution(
            self._ensure_json_serializable(selected_resolution)
        )
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        effective_created_at = created_at_override or now
        effective_updated_at = updated_at_override or now

        if project_id:
            record = self._update_project(
                project_id,
                name=name,
                author=author,
                description=description,
                metadata=sanitized_metadata,
                plugin_states=sanitized_states,
                ui_state=sanitized_ui_state,
                updated_at=effective_updated_at,
                embedded_isolierungen=sanitized_embedded,
                insulation_resolution=sanitized_resolution,
            )
        else:
            record = self._create_project(
                name=name,
                author=author,
                description=description,
                metadata=sanitized_metadata,
                plugin_states=sanitized_states,
                ui_state=sanitized_ui_state,
                created_at=effective_created_at,
                updated_at=effective_updated_at,
                embedded_isolierungen=sanitized_embedded,
                insulation_resolution=sanitized_resolution,
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
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = self._normalize_root_data(loaded)
        except Exception:
            # Fallback auf leere Struktur, wenn Datei beschädigt ist
            self._data = {
                "format_version": self.FORMAT_VERSION,
                "projects": [],
            }

    def _persist(self) -> None:
        self._data["format_version"] = self.FORMAT_VERSION
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _to_record(self, data: Dict[str, Any]) -> ProjectRecord:
        metadata = self._normalize_metadata(data.get("metadata", {}) or {})
        plugin_states = data.get("plugin_states", {})
        ui_state = data.get("ui_state", {})
        if not isinstance(plugin_states, dict):
            plugin_states = {}
        if not isinstance(ui_state, dict):
            ui_state = {}
        embedded_isolierungen = self._normalize_embedded_isolierungen(
            data.get("embedded_isolierungen", {})
        )
        insulation_resolution = self._normalize_insulation_resolution(data.get("insulation_resolution", {}))
        return ProjectRecord(
            id=str(data.get("id")),
            name=str(data.get("name", "")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            metadata=metadata,
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            plugin_states=plugin_states,
            ui_state=ui_state,
            embedded_isolierungen=embedded_isolierungen,
            insulation_resolution=insulation_resolution,
        )

    def _normalize_root_data(self, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {"format_version": self.FORMAT_VERSION, "projects": []}
        projects = raw.get("projects")
        normalized_projects = projects if isinstance(projects, list) else []
        return {
            "format_version": self.FORMAT_VERSION,
            "projects": normalized_projects,
        }

    def _ensure_json_serializable(self, states: Dict[str, Any]) -> Dict[str, Any]:
        try:
            serialized = json.dumps(states, ensure_ascii=False)
        except TypeError as exc:
            raise ValueError(
                "Plugin-Zustände enthalten nicht serialisierbare Daten"
            ) from exc
        return json.loads(serialized)

    def _normalize_insulation_resolution(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {"entries": []}
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        return {"entries": [normalize_resolution_entry(entry) for entry in entries]}

    def _normalize_embedded_isolierungen(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {"families": []}
        families = data.get("families", [])
        if not isinstance(families, list):
            families = []
        return {"families": families}

    def _normalize_metadata(self, metadata: Any) -> Dict[str, Any]:
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            raw = metadata.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _create_project(
        self,
        *,
        name: str,
        author: str,
        description: str,
        metadata: Dict[str, Any],
        plugin_states: Dict[str, Any],
        ui_state: Dict[str, Any],
        created_at: str,
        updated_at: str,
        embedded_isolierungen: Dict[str, Any],
        insulation_resolution: Dict[str, Any],
    ) -> ProjectRecord:
        if not name:
            raise ValueError("Projektname darf nicht leer sein")
        project = {
            "id": uuid4().hex,
            "name": name,
            "author": author,
            "description": description,
            "metadata": metadata,
            "created_at": created_at,
            "updated_at": updated_at,
            "plugin_states": plugin_states,
            "ui_state": ui_state,
            "embedded_isolierungen": embedded_isolierungen,
            "insulation_resolution": insulation_resolution,
        }
        self._data.setdefault("projects", []).append(project)
        return self._to_record(project)

    def _update_project(
        self,
        project_id: str,
        *,
        name: str,
        author: str,
        description: str,
        metadata: Dict[str, Any],
        plugin_states: Dict[str, Any],
        ui_state: Dict[str, Any],
        updated_at: str,
        embedded_isolierungen: Dict[str, Any],
        insulation_resolution: Dict[str, Any],
    ) -> ProjectRecord:
        for project in self._data.get("projects", []):
            if project.get("id") == project_id:
                project.update(
                    {
                        "name": name,
                        "author": author,
                        "description": description,
                        "metadata": metadata,
                        "plugin_states": plugin_states,
                        "ui_state": ui_state,
                        "embedded_isolierungen": embedded_isolierungen,
                        "insulation_resolution": insulation_resolution,
                        "updated_at": updated_at,
                    }
                )
                return self._to_record(project)
        raise ValueError(f"Projekt mit ID {project_id} existiert nicht")
