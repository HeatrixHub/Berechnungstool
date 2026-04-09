"""Importlogik für das externe Projekt-Austauschformat."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .export import EXPORT_FORMAT_NAME, EXPORT_FORMAT_VERSION
from .insulation_matching import InsulationImportMatchingService
from .isolierung_embedding import normalize_resolution_entry
from .store import ProjectRecord, ProjectStore


class ProjectImportError(ValueError):
    """Fachliche Ausnahme für valide Import-Fehlermeldungen."""


@dataclass(slots=True, frozen=True)
class PreparedProjectImport:
    """Zwischenmodell zwischen Parsing und finalem Speichern."""

    name: str
    author: str
    description: str
    metadata: dict[str, Any]
    created_at: str | None
    updated_at: str | None
    plugin_states: dict[str, Any]
    ui_state: dict[str, Any]
    embedded_isolierungen: dict[str, Any]
    insulation_resolution: dict[str, Any]
    insulation_matching_analysis: dict[str, Any]


class ProjectImportService:
    """Kapselt Dateilesen, Validierung und Import als neues lokales Projekt."""

    def __init__(self) -> None:
        self._matching_service = InsulationImportMatchingService()

    def prepare_import_from_file(self, source: Path) -> PreparedProjectImport:
        payload = self._read_payload(source)
        return self.prepare_import_payload(payload)

    def prepare_import_payload(self, payload: Any) -> PreparedProjectImport:
        root = self._require_dict(payload, "Ungültige Importdatei: Top-Level JSON muss ein Objekt sein.")

        export_format = self._require_dict(
            root.get("export_format"),
            "Ungültige Importdatei: export_format fehlt oder ist kein Objekt.",
        )
        export_name = str(export_format.get("name", "")).strip()
        if export_name != EXPORT_FORMAT_NAME:
            raise ProjectImportError(
                "Import nicht unterstützt: export_format.name muss "
                f"'{EXPORT_FORMAT_NAME}' sein (ist: '{export_name or 'leer'}')."
            )
        export_version = export_format.get("version")
        if export_version != EXPORT_FORMAT_VERSION:
            raise ProjectImportError(
                "Import nicht unterstützt: export_format.version muss "
                f"{EXPORT_FORMAT_VERSION} sein (ist: {export_version!r})."
            )

        project = self._require_dict(
            root.get("project"),
            "Ungültige Importdatei: project fehlt oder ist kein Objekt.",
        )
        master_data = self._require_dict(
            project.get("master_data"),
            "Ungültige Importdatei: project.master_data fehlt oder ist kein Objekt.",
        )
        plugin_states = self._require_dict(
            self._ensure_json_serializable(project.get("plugin_states")),
            "Ungültige Importdatei: project.plugin_states fehlt oder ist kein Objekt.",
        )
        ui_state = self._require_dict(
            self._ensure_json_serializable(project.get("ui_state")),
            "Ungültige Importdatei: project.ui_state fehlt oder ist kein Objekt.",
        )
        embedded_isolierungen = self._normalize_embedded_isolierungen(
            self._ensure_json_serializable(project.get("embedded_isolierungen"))
        )
        insulation_resolution = self._normalize_insulation_resolution(
            self._ensure_json_serializable(project.get("insulation_resolution"))
        )
        matching_analysis = self._matching_service.analyze(
            embedded_isolierungen=embedded_isolierungen,
            insulation_resolution=insulation_resolution,
        )

        name = str(master_data.get("name", "")).strip()
        if not name:
            raise ProjectImportError("Ungültige Importdatei: project.master_data.name fehlt oder ist leer.")
        author = str(master_data.get("author", "")).strip()
        description = str(master_data.get("description", "")).strip()

        metadata_value = master_data.get("metadata", {})
        metadata = self._normalize_metadata(metadata_value)
        metadata.setdefault("import", {})
        if isinstance(metadata["import"], dict):
            metadata["import"].update(
                {
                    "source": "project_exchange",
                    "source_format": EXPORT_FORMAT_NAME,
                    "source_version": EXPORT_FORMAT_VERSION,
                    "source_project_id": str(master_data.get("id", "")).strip() or None,
                    "imported_at": self._utc_now_iso(),
                }
            )

        created_at = self._as_optional_iso_timestamp(master_data.get("created_at"))
        updated_at = self._as_optional_iso_timestamp(master_data.get("updated_at"))

        return PreparedProjectImport(
            name=name,
            author=author,
            description=description,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            plugin_states=plugin_states,
            ui_state=ui_state,
            embedded_isolierungen=embedded_isolierungen,
            insulation_resolution=matching_analysis.annotated_insulation_resolution,
            insulation_matching_analysis={
                "summary": matching_analysis.summary,
                "warnings": matching_analysis.warnings,
                "errors": matching_analysis.errors,
            },
        )

    def persist_prepared_import(
        self,
        prepared: PreparedProjectImport,
        *,
        store: ProjectStore,
    ) -> ProjectRecord:
        return store.save_project(
            name=prepared.name,
            author=prepared.author,
            description=prepared.description,
            metadata=prepared.metadata,
            plugin_states=prepared.plugin_states,
            ui_state=prepared.ui_state,
            embedded_isolierungen=prepared.embedded_isolierungen,
            insulation_resolution=prepared.insulation_resolution,
            created_at_override=prepared.created_at,
            updated_at_override=prepared.updated_at,
        )

    def import_from_file(self, source: Path, *, store: ProjectStore) -> ProjectRecord:
        prepared = self.prepare_import_from_file(source)
        return self.persist_prepared_import(prepared, store=store)

    def _read_payload(self, source: Path) -> Any:
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectImportError(f"Import fehlgeschlagen: Datei konnte nicht gelesen werden ({exc}).") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProjectImportError(
                "Import fehlgeschlagen: Datei enthält kein gültiges JSON "
                f"(Zeile {exc.lineno}, Spalte {exc.colno})."
            ) from exc

    def _normalize_embedded_isolierungen(self, data: Any) -> dict[str, Any]:
        parsed = self._require_dict(
            data,
            "Ungültige Importdatei: project.embedded_isolierungen fehlt oder ist kein Objekt.",
        )
        families = parsed.get("families")
        if not isinstance(families, list):
            raise ProjectImportError(
                "Ungültige Importdatei: project.embedded_isolierungen.families muss eine Liste sein."
            )
        return {"families": families}

    def _normalize_insulation_resolution(self, data: Any) -> dict[str, Any]:
        parsed = self._require_dict(
            data,
            "Ungültige Importdatei: project.insulation_resolution fehlt oder ist kein Objekt.",
        )
        entries = parsed.get("entries")
        if not isinstance(entries, list):
            raise ProjectImportError(
                "Ungültige Importdatei: project.insulation_resolution.entries muss eine Liste sein."
            )

        normalized_entries = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ProjectImportError(
                    "Ungültige Importdatei: "
                    f"project.insulation_resolution.entries[{index}] muss ein Objekt sein."
                )
            normalized = normalize_resolution_entry(entry)
            normalized["active_source"] = "embedded"
            normalized["local_db"] = {
                "family_id": None,
                "variant_id": None,
                "origin": None,
            }
            normalized_entries.append(normalized)

        return {"entries": normalized_entries}

    def _normalize_metadata(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return self._ensure_json_serializable(value)
        if value in (None, ""):
            return {}
        raise ProjectImportError("Ungültige Importdatei: project.master_data.metadata muss ein Objekt sein.")

    def _as_optional_iso_timestamp(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text

    def _require_dict(self, value: Any, error_message: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ProjectImportError(error_message)
        return value

    def _ensure_json_serializable(self, value: Any) -> Any:
        try:
            serialized = json.dumps(value, ensure_ascii=False)
        except TypeError as exc:
            raise ProjectImportError("Importdatei enthält nicht serialisierbare Werte.") from exc
        return json.loads(serialized)

    def _utc_now_iso(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
