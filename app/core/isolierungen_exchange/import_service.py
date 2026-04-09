"""Basis-Importservice für das Isolierungen-Austauschformat."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

from .export_service import EXPORT_FORMAT_NAME, EXPORT_FORMAT_VERSION
from .normalization import normalize_import_family_for_prepare


IssueLevel = Literal["warning", "error"]


@dataclass(frozen=True)
class ImportIssue:
    level: IssueLevel
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class PreparedInsulationFamilyImport:
    index: int
    family: dict[str, Any]
    source_local: dict[str, Any] | None


@dataclass(frozen=True)
class PreparedInsulationImport:
    source_path: Path
    export_format_name: str
    export_format_version: int
    exported_at: str | None
    app_version: str | None
    families: list[PreparedInsulationFamilyImport]
    issues: list[ImportIssue]


class InsulationExchangeImportService:
    """Liest Austauschdateien defensiv ein und bereitet sie für Matching vor."""

    def prepare_from_file(self, source: Path) -> PreparedInsulationImport:
        source_path = Path(source)
        payload = self._load_json(source_path)
        if not isinstance(payload, dict):
            raise ValueError("Importfehler: Top-Level-JSON muss ein Objekt sein.")

        export_format = payload.get("export_format")
        if not isinstance(export_format, dict):
            raise ValueError("Importfehler: Pflichtblock 'export_format' fehlt oder ist ungültig.")

        format_name = str(export_format.get("name", "")).strip()
        if not format_name:
            raise ValueError("Importfehler: export_format.name fehlt.")
        if format_name != EXPORT_FORMAT_NAME:
            raise ValueError(
                "Importfehler: Nicht unterstütztes Austauschformat "
                f"'{format_name}'. Erwartet: '{EXPORT_FORMAT_NAME}'."
            )

        version = export_format.get("version")
        try:
            version_number = int(version)
        except (TypeError, ValueError) as exc:
            raise ValueError("Importfehler: export_format.version fehlt oder ist ungültig.") from exc
        if version_number != EXPORT_FORMAT_VERSION:
            raise ValueError(
                "Importfehler: Nicht unterstützte Formatversion "
                f"'{version_number}'. Unterstützt wird nur Version {EXPORT_FORMAT_VERSION}."
            )

        isolierungen = payload.get("isolierungen")
        if not isinstance(isolierungen, list):
            raise ValueError("Importfehler: Pflichtblock 'isolierungen' fehlt oder ist keine Liste.")

        issues: list[ImportIssue] = []
        families = self._prepare_families(isolierungen, issues)

        exported_at = _as_optional_str(payload.get("exported_at"))
        app_version = _as_optional_str(payload.get("app_version"))

        return PreparedInsulationImport(
            source_path=source_path,
            export_format_name=format_name,
            export_format_version=version_number,
            exported_at=exported_at,
            app_version=app_version,
            families=families,
            issues=issues,
        )

    def _load_json(self, source: Path) -> Any:
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Importfehler: Datei konnte nicht gelesen werden: {exc}") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Importfehler: Ungültiges JSON ({exc.msg}, Zeile {exc.lineno}).") from exc

    def _prepare_families(
        self,
        isolierungen: list[Any],
        issues: list[ImportIssue],
    ) -> list[PreparedInsulationFamilyImport]:
        prepared: list[PreparedInsulationFamilyImport] = []
        family_name_index: dict[str, int] = {}

        for item_index, item in enumerate(isolierungen):
            if not isinstance(item, dict):
                raise ValueError(f"Importfehler: isolierungen[{item_index}] muss ein Objekt sein.")
            raw_family = item.get("family")
            if not isinstance(raw_family, dict):
                raise ValueError(f"Importfehler: isolierungen[{item_index}].family fehlt oder ist ungültig.")

            normalized_family = normalize_import_family_for_prepare(raw_family)
            family_name_key = normalized_family["name"].casefold()
            previous_index = family_name_index.get(family_name_key)
            if previous_index is not None:
                issues.append(
                    ImportIssue(
                        level="warning",
                        code="duplicate_family_name",
                        message=(
                            "Doppelter Familienname innerhalb der Datei: "
                            f"'{normalized_family['name']}' (Einträge {previous_index} und {item_index})."
                        ),
                        path=f"isolierungen[{item_index}].family.name",
                    )
                )
            else:
                family_name_index[family_name_key] = item_index

            variant_name_map: dict[str, int] = {}
            for variant_index, variant in enumerate(normalized_family.get("variants", [])):
                variant_name = str(variant.get("name", "")).strip()
                if not variant_name:
                    raise ValueError(
                        "Importfehler: Variantenname darf nicht leer sein "
                        f"(isolierungen[{item_index}].family.variants[{variant_index}])."
                    )

                variant_name_key = variant_name.casefold()
                previous_variant_index = variant_name_map.get(variant_name_key)
                if previous_variant_index is not None:
                    issues.append(
                        ImportIssue(
                            level="warning",
                            code="duplicate_variant_name",
                            message=(
                                "Doppelter Variantenname in Familie "
                                f"'{normalized_family['name']}': '{variant_name}' "
                                f"(Varianten {previous_variant_index} und {variant_index})."
                            ),
                            path=f"isolierungen[{item_index}].family.variants[{variant_index}].name",
                        )
                    )
                else:
                    variant_name_map[variant_name_key] = variant_index

            raw_source_local = item.get("source_local")
            source_local = raw_source_local if isinstance(raw_source_local, dict) else None

            prepared.append(
                PreparedInsulationFamilyImport(
                    index=item_index,
                    family=normalized_family,
                    source_local=source_local,
                )
            )

        return prepared



def prepare_insulation_exchange_import_from_file(source: Path) -> PreparedInsulationImport:
    """Funktionaler Einstiegspunkt für vorbereitenden Austausch-Import."""

    service = InsulationExchangeImportService()
    return service.prepare_from_file(source)



def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
