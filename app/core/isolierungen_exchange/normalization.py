"""Kanonische Normalisierung für portablen Isolierungs-Austausch."""
from __future__ import annotations

from typing import Any


def normalize_family_for_exchange(family: dict[str, Any]) -> dict[str, Any]:
    """Normalisiert eine Familie inkl. Varianten für den Dateiaustausch."""

    if not isinstance(family, dict):
        raise ValueError("Ungültige Familienstruktur für Export.")

    variants = family.get("variants", [])
    if not isinstance(variants, list):
        variants = []
    normalized_variants = [
        normalize_variant_for_exchange(variant)
        for variant in variants
        if isinstance(variant, dict)
    ]
    normalized_variants.sort(key=lambda item: item.get("name", "").casefold())

    return {
        "source_local": {
            "family_id": _as_optional_int(family.get("id")),
        },
        "family": {
            "name": str(family.get("name", "")).strip(),
            "classification_temp": _require_float(family.get("classification_temp"), "classification_temp"),
            "max_temp": _as_optional_float(family.get("max_temp")),
            "density": _require_float(family.get("density"), "density"),
            "temps": _normalize_float_list(family.get("temps")),
            "ks": _normalize_float_list(family.get("ks")),
            "variants": normalized_variants,
        },
    }


def normalize_variant_for_exchange(variant: dict[str, Any]) -> dict[str, Any]:
    """Normalisiert eine Variante für den Dateiaustausch."""

    if not isinstance(variant, dict):
        raise ValueError("Ungültige Variantenstruktur für Export.")

    return {
        "source_local": {
            "variant_id": _as_optional_int(variant.get("id")),
        },
        "name": str(variant.get("name", "")).strip(),
        "thickness": _require_float(variant.get("thickness"), "thickness"),
        "length": _as_optional_float(variant.get("length")),
        "width": _as_optional_float(variant.get("width")),
        "price": _as_optional_float(variant.get("price")),
    }


def normalize_family_portable_for_compare(family: dict[str, Any]) -> dict[str, Any]:
    """Portable Vergleichsnormalisierung einer Familie ohne lokale IDs."""

    exchange = normalize_family_for_exchange(family)
    portable = dict(exchange.get("family", {}))
    variants = portable.get("variants", [])
    if isinstance(variants, list):
        portable["variants"] = [
            normalize_variant_portable_for_compare(variant)
            for variant in variants
            if isinstance(variant, dict)
        ]
    return portable


def normalize_variant_portable_for_compare(variant: dict[str, Any]) -> dict[str, Any]:
    """Portable Vergleichsnormalisierung einer Variante ohne lokale IDs."""

    if not isinstance(variant, dict):
        return {}

    normalized = {
        "name": str(variant.get("name", "")).strip(),
        "thickness": _as_optional_float(variant.get("thickness")),
        "length": _as_optional_float(variant.get("length")),
        "width": _as_optional_float(variant.get("width")),
        "price": _as_optional_float(variant.get("price")),
    }
    return normalized


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


def _require_float(value: Any, label: str) -> float:
    parsed = _as_optional_float(value)
    if parsed is None:
        raise ValueError(f"Export abgebrochen: Feld '{label}' fehlt oder ist ungültig.")
    return parsed


def _normalize_float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    out: list[float] = []
    for item in value:
        parsed = _as_optional_float(item)
        if parsed is not None:
            out.append(parsed)
    return out
