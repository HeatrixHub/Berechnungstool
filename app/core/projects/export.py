"""Exportlogik für das externe Projekt-Austauschformat."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.time_utils import normalize_timestamp, utc_now_iso_z
from .isolierung_embedding import (
    build_embedded_isolierungen_from_plugin_states,
    normalize_resolution_entry,
)
from .store import ProjectRecord

EXPORT_FORMAT_NAME = "heatrix_project_exchange"
EXPORT_FORMAT_VERSION = 1
EXPORT_FILE_SUFFIX = ".hpxproj.json"


def build_project_export_payload(
    *,
    project: ProjectRecord,
    plugin_states: dict[str, Any] | None = None,
    ui_state: dict[str, Any] | None = None,
    name: str | None = None,
    author: str | None = None,
    description: str | None = None,
    app_version: str | None = None,
) -> dict[str, Any]:
    """Erzeugt ein stabiles Exportobjekt für genau ein Projekt."""

    if not project.id.strip():
        raise ValueError("Export abgebrochen: Projekt-ID fehlt.")

    effective_name = (name if name is not None else project.name).strip()
    if not effective_name:
        raise ValueError("Export abgebrochen: Projektname fehlt.")

    effective_author = author if author is not None else project.author
    effective_description = description if description is not None else project.description
    effective_plugin_states = _ensure_json_serializable(
        plugin_states if plugin_states is not None else project.plugin_states
    )
    if not isinstance(effective_plugin_states, dict):
        raise ValueError("Export abgebrochen: plugin_states ist ungültig.")
    effective_ui_state = _ensure_json_serializable(
        ui_state if ui_state is not None else project.ui_state
    )
    if not isinstance(effective_ui_state, dict):
        raise ValueError("Export abgebrochen: ui_state ist ungültig.")

    embedded_isolierungen, insulation_resolution = build_embedded_isolierungen_from_plugin_states(
        effective_plugin_states
    )
    normalized_embedded_isolierungen = _normalize_embedded_isolierungen(embedded_isolierungen)
    normalized_insulation_resolution = _normalize_insulation_resolution(insulation_resolution)

    payload: dict[str, Any] = {
        "export_format": {
            "name": EXPORT_FORMAT_NAME,
            "version": EXPORT_FORMAT_VERSION,
        },
        "exported_at": _utc_now_iso(),
        "project": {
            "master_data": {
                "id": project.id,
                "name": effective_name,
                "author": effective_author,
                "description": effective_description,
                "metadata": _ensure_json_serializable(project.metadata),
                "created_at": normalize_timestamp(project.created_at, default=str(project.created_at).strip()) or "",
                "updated_at": normalize_timestamp(project.updated_at, default=str(project.updated_at).strip()) or "",
            },
            "plugin_states": effective_plugin_states,
            "ui_state": effective_ui_state,
            "embedded_isolierungen": normalized_embedded_isolierungen,
            "insulation_resolution": normalized_insulation_resolution,
        },
    }
    if app_version:
        payload["app_version"] = app_version
    return payload


def export_project_to_file(payload: dict[str, Any], destination: Path) -> Path:
    """Schreibt ein Exportobjekt als Datei und gibt den finalen Pfad zurück."""

    if not isinstance(payload, dict):
        raise ValueError("Exportdaten sind ungültig.")

    target = destination
    if target.suffixes[-2:] != [".hpxproj", ".json"]:
        stem = target.name
        for suffix in target.suffixes:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        target = target.parent / f"{stem}{EXPORT_FILE_SUFFIX}"
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    target.write_text(serialized, encoding="utf-8")
    return target


def _utc_now_iso() -> str:
    return utc_now_iso_z()


def _ensure_json_serializable(value: Any) -> Any:
    try:
        serialized = json.dumps(value, ensure_ascii=False)
    except TypeError as exc:
        raise ValueError("Exportdaten enthalten nicht serialisierbare Werte.") from exc
    return json.loads(serialized)


def _normalize_embedded_isolierungen(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"families": []}
    families = data.get("families", [])
    if not isinstance(families, list):
        families = []
    return {"families": families}


def _normalize_insulation_resolution(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"entries": []}
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    return {"entries": [normalize_resolution_entry(entry) for entry in entries]}
