"""Importlogik für das externe Projekt-Austauschformat."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any

from app.core.time_utils import normalize_timestamp, utc_now_iso_z
from .export import EXPORT_FORMAT_NAME, EXPORT_FORMAT_VERSION
from app.core.isolierungen_db.logic import create_family, create_variant, list_families
from .insulation_matching import InsulationImportMatchingService
from .isolierung_embedding import (
    normalize_family_core_for_compare,
    normalize_resolution_entry,
    normalize_variant_portable_for_compare,
)
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


@dataclass(slots=True, frozen=True)
class ImportDecisionReport:
    embedded_active: int
    local_active: int
    adopted_to_local: int


DECISION_USE_EMBEDDED = "use_embedded"
DECISION_USE_LOCAL = "use_local"
DECISION_ADOPT_TO_LOCAL = "adopt_to_local"


@dataclass(slots=True, frozen=True)
class InsulationImportDecision:
    """Explizite Benutzerentscheidung je verwendeter importierter Isolierung."""

    project_insulation_key: str
    decision: str
    local_family_id: int | None = None
    local_variant_id: int | None = None
    use_local_after_adopt: bool = False


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

    def apply_insulation_import_decisions(
        self,
        prepared: PreparedProjectImport,
        *,
        decisions: list[InsulationImportDecision],
    ) -> PreparedProjectImport:
        """Reichert das Prepared-Importmodell mit expliziten Benutzerentscheidungen an."""

        entries = prepared.insulation_resolution.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        decisions_by_key = {
            str(item.project_insulation_key).strip(): item
            for item in decisions
            if str(item.project_insulation_key).strip()
        }

        embedded_index = self._build_embedded_index(prepared.embedded_isolierungen)
        updated_entries: list[dict[str, Any]] = []
        for raw_entry in entries:
            entry = normalize_resolution_entry(raw_entry if isinstance(raw_entry, dict) else {})
            project_key = str(entry.get("project_insulation_key", "")).strip()
            decision = decisions_by_key.get(project_key)
            if decision is None:
                updated_entries.append(entry)
                continue
            updated_entries.append(
                self._apply_single_entry_decision(
                    entry=entry,
                    decision=decision,
                    embedded_index=embedded_index,
                )
            )

        return replace(
            prepared,
            insulation_resolution={"entries": updated_entries},
        )

    def import_from_file(self, source: Path, *, store: ProjectStore) -> ProjectRecord:
        prepared = self.prepare_import_from_file(source)
        return self.persist_prepared_import(prepared, store=store)

    def build_import_decision_report(self, prepared: PreparedProjectImport) -> ImportDecisionReport:
        entries = prepared.insulation_resolution.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        embedded_active = 0
        local_active = 0
        adopted_to_local = 0
        for raw_entry in entries:
            entry = normalize_resolution_entry(raw_entry if isinstance(raw_entry, dict) else {})
            if entry.get("active_source") == "local":
                local_active += 1
            else:
                embedded_active += 1
            local_db = entry.get("local_db", {})
            if isinstance(local_db, dict) and str(local_db.get("origin") or "").strip() == "project_import":
                adopted_to_local += 1
        return ImportDecisionReport(
            embedded_active=embedded_active,
            local_active=local_active,
            adopted_to_local=adopted_to_local,
        )

    def _apply_single_entry_decision(
        self,
        *,
        entry: dict[str, Any],
        decision: InsulationImportDecision,
        embedded_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        local_db = entry.get("local_db", {})
        if not isinstance(local_db, dict):
            local_db = {}
        decision_type = str(decision.decision).strip()

        if decision_type == DECISION_USE_EMBEDDED:
            local_db["family_id"] = None
            local_db["variant_id"] = None
            entry["active_source"] = "embedded"
            entry["local_db"] = local_db
            return entry

        if decision_type == DECISION_USE_LOCAL:
            family_id = self._require_int(
                decision.local_family_id,
                f"Lokaler family_id fehlt für {entry.get('project_insulation_key')!r}.",
            )
            local_db["family_id"] = family_id
            local_db["variant_id"] = self._as_optional_int(decision.local_variant_id)
            entry["active_source"] = "local"
            entry["local_db"] = local_db
            return entry

        if decision_type == DECISION_ADOPT_TO_LOCAL:
            created = self._adopt_embedded_target_to_local_db(entry=entry, embedded_index=embedded_index)
            local_db["family_id"] = created["family_id"]
            local_db["variant_id"] = created["variant_id"]
            local_db["origin"] = "project_import"
            entry["active_source"] = "local" if decision.use_local_after_adopt else "embedded"
            entry["local_db"] = local_db
            return entry

        raise ProjectImportError(
            f"Unbekannte Importentscheidung für {entry.get('project_insulation_key')!r}: {decision_type!r}."
        )

    def _adopt_embedded_target_to_local_db(
        self,
        *,
        entry: dict[str, Any],
        embedded_index: dict[str, dict[str, Any]],
    ) -> dict[str, int | None]:
        project_key = str(entry.get("project_insulation_key", "")).strip()
        family_key = str(entry.get("family_key", "")).strip()
        variant_key = str(entry.get("variant_key", "")).strip()
        target = embedded_index.get(variant_key or family_key)
        if target is None:
            raise ProjectImportError(
                "Übernahme in lokale DB nicht möglich: "
                f"keine eingebettete Referenz für {project_key or family_key!r} gefunden."
            )

        family = target["family"]
        family_name = str(family.get("name", "")).strip()
        conflicting_family = self._find_local_family_by_name(family_name)
        if conflicting_family is not None:
            embedded_core = normalize_family_core_for_compare(family)
            local_core = normalize_family_core_for_compare(conflicting_family)
            if embedded_core == local_core:
                raise ProjectImportError(
                    "Übernahme in lokale DB abgebrochen: Materialfamilie "
                    f"{family_name!r} existiert bereits identisch. Bitte lokalen Eintrag verknüpfen."
                )
            raise ProjectImportError(
                "Übernahme in lokale DB abgebrochen: Namenskonflikt bei Materialfamilie "
                f"{family_name!r} (lokale Struktur weicht vom Import ab)."
            )
        try:
            family_id = create_family(
                name=family_name,
                classification_temp=float(family.get("classification_temp")),
                max_temp=self._as_optional_float(family.get("max_temp")),
                density=float(family.get("density")),
                temps=[float(item) for item in family.get("temps", [])],
                ks=[float(item) for item in family.get("ks", [])],
            )
        except ValueError as exc:
            raise ProjectImportError(
                "Übernahme in lokale DB fehlgeschlagen: "
                f"{exc}"
            ) from exc
        variant = target.get("variant")
        if isinstance(variant, dict):
            variant_name = str(variant.get("name", "")).strip()
            self._assert_no_variant_name_conflict(
                family_id=family_id,
                family_name=family_name,
                variant_name=variant_name,
                embedded_variant=variant,
            )
            try:
                variant_id = create_variant(
                    family_id=family_id,
                    name=variant_name,
                    thickness=float(variant.get("thickness")),
                    length=self._as_optional_float(variant.get("length")),
                    width=self._as_optional_float(variant.get("width")),
                    price=self._as_optional_float(variant.get("price")),
                )
            except ValueError as exc:
                raise ProjectImportError(
                    "Übernahme in lokale DB fehlgeschlagen: "
                    f"{exc}"
                ) from exc
            return {"family_id": family_id, "variant_id": variant_id}
        return {"family_id": family_id, "variant_id": None}

    def _build_embedded_index(self, embedded_isolierungen: dict[str, Any]) -> dict[str, dict[str, Any]]:
        families = embedded_isolierungen.get("families", [])
        if not isinstance(families, list):
            return {}
        index: dict[str, dict[str, Any]] = {}
        for family in families:
            if not isinstance(family, dict):
                continue
            normalized_family = self._normalize_family_for_create(family)
            family_key = str(family.get("project_family_key", "")).strip()
            if family_key:
                index[family_key] = {"family": normalized_family, "variant": None}
            variants = family.get("variants", [])
            if not isinstance(variants, list):
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_key = str(variant.get("project_variant_key", "")).strip()
                if not variant_key:
                    continue
                index[variant_key] = {
                    "family": normalized_family,
                    "variant": self._normalize_variant_for_create(variant),
                }
        return index

    def _normalize_family_for_create(self, family: dict[str, Any]) -> dict[str, Any]:
        name = str(family.get("name", "")).strip()
        if not name:
            raise ProjectImportError("Übernahme in lokale DB nicht möglich: Familienname fehlt.")
        classification_temp = self._as_required_float(
            family.get("classification_temp"),
            "Klassifikationstemperatur fehlt.",
        )
        density = self._as_required_float(family.get("density"), "Dichte fehlt.")
        temps = self._as_float_list(family.get("temps"))
        ks = self._as_float_list(family.get("ks"))
        if len(temps) != len(ks):
            raise ProjectImportError("Übernahme in lokale DB nicht möglich: Temperatur-/k-Werte inkonsistent.")
        return {
            "name": name,
            "classification_temp": classification_temp,
            "max_temp": self._as_optional_float(family.get("max_temp")),
            "density": density,
            "temps": temps,
            "ks": ks,
        }

    def _normalize_variant_for_create(self, variant: dict[str, Any]) -> dict[str, Any]:
        name = str(variant.get("name", "")).strip()
        if not name:
            raise ProjectImportError("Übernahme in lokale DB nicht möglich: Variantenname fehlt.")
        thickness = self._as_required_float(variant.get("thickness"), "Variantendicke fehlt.")
        return {
            "name": name,
            "thickness": thickness,
            "length": self._as_optional_float(variant.get("length")),
            "width": self._as_optional_float(variant.get("width")),
            "price": self._as_optional_float(variant.get("price")),
        }

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
        return normalize_timestamp(value)

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
        return utc_now_iso_z()

    def _as_required_float(self, value: Any, error: str) -> float:
        parsed = self._as_optional_float(value)
        if parsed is None:
            raise ProjectImportError(f"Übernahme in lokale DB nicht möglich: {error}")
        return parsed

    def _as_optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _as_float_list(self, value: Any) -> list[float]:
        if not isinstance(value, list):
            return []
        out: list[float] = []
        for item in value:
            parsed = self._as_optional_float(item)
            if parsed is not None:
                out.append(parsed)
        return out

    def _as_optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _require_int(self, value: Any, error: str) -> int:
        parsed = self._as_optional_int(value)
        if parsed is None:
            raise ProjectImportError(error)
        return parsed

    def _find_local_family_by_name(self, family_name: str) -> dict[str, Any] | None:
        if not family_name:
            return None
        for family in list_families():
            if not isinstance(family, dict):
                continue
            if str(family.get("name", "")).strip().casefold() == family_name.casefold():
                return family
        return None

    def _assert_no_variant_name_conflict(
        self,
        *,
        family_id: int,
        family_name: str,
        variant_name: str,
        embedded_variant: dict[str, Any],
    ) -> None:
        if not variant_name:
            return
        local_family = next(
            (
                family
                for family in list_families()
                if isinstance(family, dict) and self._as_optional_int(family.get("id")) == family_id
            ),
            None,
        )
        if not isinstance(local_family, dict):
            return
        for local_variant in local_family.get("variants", []):
            if not isinstance(local_variant, dict):
                continue
            if str(local_variant.get("name", "")).strip().casefold() != variant_name.casefold():
                continue
            if normalize_variant_portable_for_compare(local_variant) == normalize_variant_portable_for_compare(
                embedded_variant
            ):
                raise ProjectImportError(
                    "Übernahme in lokale DB abgebrochen: Variante "
                    f"{variant_name!r} in Familie {family_name!r} existiert bereits identisch."
                )
            raise ProjectImportError(
                "Übernahme in lokale DB abgebrochen: Namenskonflikt bei Variante "
                f"{variant_name!r} in Familie {family_name!r}."
            )
