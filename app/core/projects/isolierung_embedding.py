"""Hilfslogik für projektinterne, eingebettete Isolierungsdaten."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.isolierungen_db.logic import get_family_by_id

ISOLIERUNG_PLUGIN_ID = "isolierung"

SOURCE_EMBEDDED = "embedded"
SOURCE_LINKED = "linked"
SOURCE_LOCAL = "local"
VALID_SOURCES = {SOURCE_EMBEDDED, SOURCE_LINKED, SOURCE_LOCAL}


@dataclass(frozen=True, slots=True)
class UsedInsulationRef:
    """Repräsentiert eine im Projekt tatsächlich referenzierte Isolierung."""

    family_id: int
    variant_id: int | None

    @property
    def family_key(self) -> str:
        return f"fam-{self.family_id}"

    @property
    def variant_key(self) -> str | None:
        if self.variant_id is None:
            return None
        return f"var-{self.family_id}-{self.variant_id}"

    @property
    def project_insulation_key(self) -> str:
        if self.variant_id is None:
            return self.family_key
        return self.variant_key or self.family_key


def build_embedded_isolierungen_from_plugin_states(
    plugin_states: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Erzeugt eingebettete Isolierungsdaten + Auflösungsdaten aus Plugin-State."""

    plugin_state = plugin_states.get(ISOLIERUNG_PLUGIN_ID, {}) if isinstance(plugin_states, dict) else {}
    used_refs = _collect_used_refs_from_isolierung_state(plugin_state)
    embedded = _build_embedded_block(used_refs)
    resolution = _build_resolution_block(used_refs)
    return embedded, resolution


def normalize_resolution_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalisiert einen Resolution-Eintrag für defensive Vergleiche."""

    if not isinstance(entry, dict):
        return {
            "project_insulation_key": "",
            "family_key": "",
            "variant_key": None,
            "active_source": SOURCE_EMBEDDED,
            "local_db": {},
        }
    active_source = str(entry.get("active_source", SOURCE_EMBEDDED)).strip().lower()
    if active_source not in VALID_SOURCES:
        active_source = SOURCE_EMBEDDED
    local_db = entry.get("local_db", {})
    if not isinstance(local_db, dict):
        local_db = {}
    return {
        "project_insulation_key": str(entry.get("project_insulation_key", "")).strip(),
        "family_key": str(entry.get("family_key", "")).strip(),
        "variant_key": _as_optional_str(entry.get("variant_key")),
        "active_source": active_source,
        "local_db": {
            "family_id": _as_optional_int(local_db.get("family_id")),
            "variant_id": _as_optional_int(local_db.get("variant_id")),
            # Vorbereitung: spätere Markierung lokal importierter Datensätze.
            "origin": _as_optional_str(local_db.get("origin")),
        },
    }


def normalize_family_for_compare(family: dict[str, Any]) -> dict[str, Any]:
    """Kanonische Struktur als Vergleichsbasis für späteren Deep-Compare."""

    if not isinstance(family, dict):
        return {}
    variants = family.get("variants", [])
    if not isinstance(variants, list):
        variants = []
    normalized_variants = [normalize_variant_for_compare(variant) for variant in variants if isinstance(variant, dict)]
    normalized_variants.sort(key=lambda item: (item.get("id") is None, item.get("id") or 0, item.get("name", "")))
    return {
        "id": _as_optional_int(family.get("id")),
        "name": str(family.get("name", "")).strip(),
        "classification_temp": _as_optional_float(family.get("classification_temp")),
        "max_temp": _as_optional_float(family.get("max_temp")),
        "density": _as_optional_float(family.get("density")),
        "temps": _normalize_float_list(family.get("temps")),
        "ks": _normalize_float_list(family.get("ks")),
        "variants": normalized_variants,
    }


def normalize_variant_for_compare(variant: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(variant, dict):
        return {}
    return {
        "id": _as_optional_int(variant.get("id")),
        "name": str(variant.get("name", "")).strip(),
        "thickness": _as_optional_float(variant.get("thickness")),
        "length": _as_optional_float(variant.get("length")),
        "width": _as_optional_float(variant.get("width")),
        "price": _as_optional_float(variant.get("price")),
    }


def _collect_used_refs_from_isolierung_state(plugin_state: Any) -> list[UsedInsulationRef]:
    if not isinstance(plugin_state, dict):
        return []
    inputs = plugin_state.get("inputs", {})
    if not isinstance(inputs, dict):
        return []

    refs: dict[tuple[int, int | None], UsedInsulationRef] = {}
    for section_key in ("berechnung", "schichtaufbau"):
        section = inputs.get(section_key, {})
        if not isinstance(section, dict):
            continue
        layers = section.get("layers", [])
        if not isinstance(layers, list):
            continue
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            family_id = _as_optional_int(layer.get("family_id"))
            if family_id is None:
                continue
            variant_id = _as_optional_int(layer.get("variant_id"))
            key = (family_id, variant_id)
            refs[key] = UsedInsulationRef(family_id=family_id, variant_id=variant_id)

    return sorted(refs.values(), key=lambda ref: (ref.family_id, ref.variant_id is None, ref.variant_id or 0))


def _build_embedded_block(used_refs: list[UsedInsulationRef]) -> dict[str, Any]:
    family_variant_ids: dict[int, set[int]] = {}
    for ref in used_refs:
        family_variant_ids.setdefault(ref.family_id, set())
        if ref.variant_id is not None:
            family_variant_ids[ref.family_id].add(ref.variant_id)

    families: list[dict[str, Any]] = []
    for family_id in sorted(family_variant_ids):
        try:
            raw_family = get_family_by_id(family_id)
        except ValueError:
            continue
        family = normalize_family_for_compare(raw_family)
        used_variant_ids = family_variant_ids[family_id]
        variants = family.get("variants", [])
        if used_variant_ids:
            variants = [
                variant
                for variant in variants
                if isinstance(variant, dict) and _as_optional_int(variant.get("id")) in used_variant_ids
            ]
        family["variants"] = variants
        family["project_family_key"] = f"fam-{family_id}"
        for variant in family["variants"]:
            variant_id = _as_optional_int(variant.get("id"))
            if variant_id is not None:
                variant["project_variant_key"] = f"var-{family_id}-{variant_id}"
        families.append(family)

    return {
        "families": families,
    }


def _build_resolution_block(used_refs: list[UsedInsulationRef]) -> dict[str, Any]:
    entries = [
        {
            "project_insulation_key": ref.project_insulation_key,
            "family_key": ref.family_key,
            "variant_key": ref.variant_key,
            "active_source": SOURCE_EMBEDDED,
            "local_db": {
                "family_id": None,
                "variant_id": None,
                "origin": None,
            },
        }
        for ref in used_refs
    ]
    return {"entries": entries}


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    out: list[float] = []
    for item in value:
        parsed = _as_optional_float(item)
        if parsed is not None:
            out.append(parsed)
    return out
