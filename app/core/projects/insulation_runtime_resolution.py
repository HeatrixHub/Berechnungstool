"""Laufzeit-Resolver für projektbezogene Isolierungsquellen.

Diese Schicht entscheidet zentral, ob pro verwendeter Isolierung die eingebettete
Projektversion oder ein lokaler DB-Eintrag aktiv genutzt wird.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.isolierungen_db.logic import get_family_by_id

from .isolierung_embedding import SOURCE_EMBEDDED, SOURCE_LOCAL, normalize_resolution_entry


ISOLIERUNG_PLUGIN_ID = "isolierung"


@dataclass(frozen=True, slots=True)
class RuntimeResolvedInsulation:
    project_insulation_key: str
    requested_source: str
    effective_source: str
    linked_local: bool
    family_name: str
    variant_name: str | None
    warning: str | None


@dataclass(frozen=True, slots=True)
class RuntimeResolutionResult:
    plugin_states: dict[str, Any]
    embedded_isolierungen: dict[str, Any]
    insulation_resolution: dict[str, Any]
    resolved_items: list[RuntimeResolvedInsulation]
    is_legacy: bool


class InsulationRuntimeResolver:
    """Resolved Isolierungsdaten für den normalen Projektbetrieb."""

    def resolve_project_runtime(
        self,
        *,
        plugin_states: dict[str, Any],
        embedded_isolierungen: dict[str, Any] | None,
        insulation_resolution: dict[str, Any] | None,
    ) -> RuntimeResolutionResult:
        states_copy = _deep_copy_dict(plugin_states)
        embedded = _normalize_embedded(embedded_isolierungen)
        resolution = _normalize_resolution(insulation_resolution)
        is_legacy = not embedded.get("families") or not resolution.get("entries")
        if is_legacy:
            return RuntimeResolutionResult(
                plugin_states=states_copy,
                embedded_isolierungen=embedded,
                insulation_resolution=resolution,
                resolved_items=[],
                is_legacy=True,
            )

        plugin_state = states_copy.get(ISOLIERUNG_PLUGIN_ID)
        if not isinstance(plugin_state, dict):
            return RuntimeResolutionResult(
                plugin_states=states_copy,
                embedded_isolierungen=embedded,
                insulation_resolution=resolution,
                resolved_items=[],
                is_legacy=False,
            )

        embedded_by_key = _build_embedded_index(embedded)
        resolution_by_key = _build_resolution_index(resolution)
        local_family_cache: dict[int, dict[str, Any] | None] = {}
        items: list[RuntimeResolvedInsulation] = []

        for layer, project_key in _iter_isolierung_layers(plugin_state):
            entry = resolution_by_key.get(project_key)
            if entry is None:
                items.append(
                    RuntimeResolvedInsulation(
                        project_insulation_key=project_key,
                        requested_source=SOURCE_EMBEDDED,
                        effective_source="legacy_local",
                        linked_local=False,
                        family_name=str(layer.get("family", "")).strip(),
                        variant_name=_optional_text(layer.get("variant")),
                        warning="Kein Resolution-Eintrag gefunden.",
                    )
                )
                continue

            requested_source = entry.get("active_source", SOURCE_EMBEDDED)
            local_db = entry.get("local_db", {}) if isinstance(entry.get("local_db"), dict) else {}
            linked_local = isinstance(local_db.get("family_id"), int)
            warning: str | None = None
            effective_source = requested_source
            resolved = None

            if requested_source == SOURCE_LOCAL:
                resolved, warning = _resolve_local_target(
                    local_db=local_db,
                    embedded_target=embedded_by_key.get(project_key),
                    local_family_cache=local_family_cache,
                )
                if resolved is None:
                    resolved = embedded_by_key.get(project_key)
                    effective_source = SOURCE_EMBEDDED if resolved is not None else "unresolved"
                    if warning:
                        warning = f"{warning} Fallback auf eingebettet."
                    else:
                        warning = "Lokale Referenz ungültig. Fallback auf eingebettet."
            else:
                resolved = embedded_by_key.get(project_key)
                if resolved is None:
                    effective_source = "unresolved"
                    warning = "Eingebettete Referenz fehlt."

            if resolved is None:
                items.append(
                    RuntimeResolvedInsulation(
                        project_insulation_key=project_key,
                        requested_source=requested_source,
                        effective_source=effective_source,
                        linked_local=linked_local,
                        family_name=str(layer.get("family", "")).strip(),
                        variant_name=_optional_text(layer.get("variant")),
                        warning=warning or "Keine auflösbaren Daten vorhanden.",
                    )
                )
                continue

            layer["family_id"] = resolved.get("family_id")
            layer["variant_id"] = resolved.get("variant_id")
            layer["family"] = resolved.get("family_name", "")
            layer["variant"] = resolved.get("variant_name", "")

            items.append(
                RuntimeResolvedInsulation(
                    project_insulation_key=project_key,
                    requested_source=requested_source,
                    effective_source=effective_source,
                    linked_local=linked_local,
                    family_name=str(resolved.get("family_name", "")).strip(),
                    variant_name=_optional_text(resolved.get("variant_name")),
                    warning=warning,
                )
            )

        return RuntimeResolutionResult(
            plugin_states=states_copy,
            embedded_isolierungen=embedded,
            insulation_resolution=resolution,
            resolved_items=items,
            is_legacy=False,
        )

    def switch_active_source(
        self,
        *,
        insulation_resolution: dict[str, Any] | None,
        embedded_isolierungen: dict[str, Any] | None,
        project_insulation_key: str,
        target_source: str,
    ) -> tuple[dict[str, Any], str | None]:
        resolution = _normalize_resolution(insulation_resolution)
        target = str(target_source).strip().lower()
        if target not in {SOURCE_EMBEDDED, SOURCE_LOCAL}:
            return resolution, "Ungültige Zielquelle."
        entries = resolution.get("entries", [])
        if not isinstance(entries, list):
            return resolution, "Ungültige Resolution-Struktur."

        embedded_index = _build_embedded_index(_normalize_embedded(embedded_isolierungen))
        target_key = str(project_insulation_key).strip()
        for index, raw_entry in enumerate(entries):
            entry = normalize_resolution_entry(raw_entry if isinstance(raw_entry, dict) else {})
            if entry.get("project_insulation_key") != target_key:
                continue
            if target == SOURCE_LOCAL:
                _, warning = _resolve_local_target(
                    local_db=entry.get("local_db", {}),
                    embedded_target=embedded_index.get(target_key),
                    local_family_cache={},
                )
                if warning is not None:
                    return resolution, "Umschalten auf lokal nicht möglich: " + warning
            entry["active_source"] = target
            entries[index] = entry
            return {"entries": entries}, None
        return resolution, "Resolution-Eintrag nicht gefunden."


def _resolve_local_target(
    *,
    local_db: dict[str, Any],
    embedded_target: dict[str, Any] | None,
    local_family_cache: dict[int, dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, str | None]:
    family_id = _optional_int(local_db.get("family_id"))
    variant_id = _optional_int(local_db.get("variant_id"))
    if family_id is None:
        return None, "Keine lokale family_id hinterlegt."

    if family_id not in local_family_cache:
        try:
            local_family_cache[family_id] = get_family_by_id(family_id)
        except ValueError:
            local_family_cache[family_id] = None
    family = local_family_cache.get(family_id)
    if not isinstance(family, dict):
        return None, f"Lokale Materialfamilie #{family_id} existiert nicht mehr."

    family_name = str(family.get("name", "")).strip()
    variants = family.get("variants", []) if isinstance(family.get("variants"), list) else []

    needs_variant = False
    if isinstance(embedded_target, dict) and embedded_target.get("variant_key"):
        needs_variant = True
    if variant_id is not None:
        needs_variant = True

    resolved_variant: dict[str, Any] | None = None
    if needs_variant:
        if variant_id is None:
            return None, "Lokale variant_id fehlt."
        for item in variants:
            if isinstance(item, dict) and _optional_int(item.get("id")) == variant_id:
                resolved_variant = item
                break
        if resolved_variant is None:
            return None, f"Lokale Variante #{variant_id} existiert nicht mehr."

    return {
        "family_id": family_id,
        "variant_id": variant_id if resolved_variant is not None else None,
        "family_name": family_name,
        "variant_name": str(resolved_variant.get("name", "")).strip() if resolved_variant else "",
    }, None


def _iter_isolierung_layers(plugin_state: dict[str, Any]):
    inputs = plugin_state.get("inputs", {})
    if not isinstance(inputs, dict):
        return
    for section in ("berechnung", "schichtaufbau"):
        data = inputs.get(section, {})
        if not isinstance(data, dict):
            continue
        layers = data.get("layers", [])
        if not isinstance(layers, list):
            continue
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            family_id = _optional_int(layer.get("family_id"))
            variant_id = _optional_int(layer.get("variant_id"))
            project_key = _build_project_insulation_key(family_id, variant_id)
            if not project_key:
                continue
            yield layer, project_key


def _build_project_insulation_key(family_id: int | None, variant_id: int | None) -> str:
    if family_id is None:
        return ""
    if variant_id is None:
        return f"fam-{family_id}"
    return f"var-{family_id}-{variant_id}"


def _build_embedded_index(embedded_isolierungen: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families = embedded_isolierungen.get("families", [])
    if not isinstance(families, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for family in families:
        if not isinstance(family, dict):
            continue
        family_name = str(family.get("name", "")).strip()
        family_key = str(family.get("project_family_key", "")).strip()
        family_id = _extract_family_id_from_key(family_key)
        if family_key and family_id is not None:
            index[family_key] = {
                "family_key": family_key,
                "variant_key": None,
                "family_id": family_id,
                "variant_id": None,
                "family_name": family_name,
                "variant_name": "",
            }
        variants = family.get("variants", [])
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            variant_key = str(variant.get("project_variant_key", "")).strip()
            variant_id = _optional_int(variant.get("id"))
            if not variant_key or family_id is None or variant_id is None:
                continue
            index[variant_key] = {
                "family_key": family_key,
                "variant_key": variant_key,
                "family_id": family_id,
                "variant_id": variant_id,
                "family_name": family_name,
                "variant_name": str(variant.get("name", "")).strip(),
            }
    return index


def _build_resolution_index(resolution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    entries = resolution.get("entries", [])
    if not isinstance(entries, list):
        return out
    for raw_entry in entries:
        entry = normalize_resolution_entry(raw_entry if isinstance(raw_entry, dict) else {})
        key = str(entry.get("project_insulation_key", "")).strip()
        if key:
            out[key] = entry
    return out


def _extract_family_id_from_key(key: str) -> int | None:
    if not key.startswith("fam-"):
        return None
    return _optional_int(key[4:])


def _normalize_embedded(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"families": []}
    families = data.get("families", [])
    if not isinstance(families, list):
        families = []
    return {"families": families}


def _normalize_resolution(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"entries": []}
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    return {"entries": [normalize_resolution_entry(item if isinstance(item, dict) else {}) for item in entries]}


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _deep_copy_dict(data: dict[str, Any]) -> dict[str, Any]:
    # JSON-safe copy ohne Zusatzabhängigkeit.
    import json

    return json.loads(json.dumps(data, ensure_ascii=False)) if isinstance(data, dict) else {}
