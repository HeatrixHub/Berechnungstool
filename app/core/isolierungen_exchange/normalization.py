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


def normalize_import_family_for_prepare(family: dict[str, Any]) -> dict[str, Any]:
    """Normalisiert eingelesene Import-Familien für spätere Matching-Schritte."""

    if not isinstance(family, dict):
        raise ValueError("Importfehler: family-Block ist ungültig.")

    required_keys = ("name", "classification_temp", "max_temp", "density", "temps", "ks", "variants")
    for key in required_keys:
        if key not in family:
            raise ValueError(f"Importfehler: Pflichtfeld 'family.{key}' fehlt.")

    name = _require_non_empty_string(family.get("name"), "family.name")
    classification_temp = _require_float(family.get("classification_temp"), "family.classification_temp")
    max_temp = _as_optional_float(family.get("max_temp"))
    density = _require_float(family.get("density"), "family.density")

    temps = _require_float_list(family.get("temps"), "family.temps")
    ks = _require_float_list(family.get("ks"), "family.ks")
    if not temps or not ks:
        raise ValueError("Importfehler: family.temps und family.ks dürfen nicht leer sein.")
    if len(temps) != len(ks):
        raise ValueError("Importfehler: family.temps und family.ks müssen gleich lang sein.")
    if any(temps[index] >= temps[index + 1] for index in range(len(temps) - 1)):
        raise ValueError("Importfehler: family.temps muss streng aufsteigend sein.")

    variants_raw = family.get("variants")
    if not isinstance(variants_raw, list):
        raise ValueError("Importfehler: family.variants muss eine Liste sein.")

    normalized_variants: list[dict[str, Any]] = []
    for variant_index, raw_variant in enumerate(variants_raw):
        if not isinstance(raw_variant, dict):
            raise ValueError(f"Importfehler: family.variants[{variant_index}] ist kein Objekt.")
        normalized_variants.append(normalize_import_variant_for_prepare(raw_variant, variant_index=variant_index))
    normalized_variants.sort(key=lambda item: item.get("name", "").casefold())

    return {
        "name": name,
        "classification_temp": classification_temp,
        "max_temp": max_temp,
        "density": density,
        "temps": temps,
        "ks": ks,
        "variants": normalized_variants,
    }


def normalize_import_variant_for_prepare(variant: dict[str, Any], *, variant_index: int | None = None) -> dict[str, Any]:
    """Normalisiert Import-Varianten defensiv für spätere Matching-Schritte."""

    location = f"family.variants[{variant_index}]" if variant_index is not None else "family.variants[]"
    name = _require_non_empty_string(variant.get("name"), f"{location}.name")
    thickness = _require_float(variant.get("thickness"), f"{location}.thickness")
    if thickness <= 0:
        raise ValueError(f"Importfehler: {location}.thickness muss > 0 sein.")

    length = _as_optional_float(variant.get("length"))
    if length is not None and length <= 0:
        raise ValueError(f"Importfehler: {location}.length muss > 0 sein, falls gesetzt.")

    width = _as_optional_float(variant.get("width"))
    if width is not None and width <= 0:
        raise ValueError(f"Importfehler: {location}.width muss > 0 sein, falls gesetzt.")

    price = _as_optional_float(variant.get("price"))
    if price is not None and price < 0:
        raise ValueError(f"Importfehler: {location}.price darf nicht negativ sein.")

    return normalize_variant_portable_for_compare(
        {
            "name": name,
            "thickness": thickness,
            "length": length,
            "width": width,
            "price": price,
        }
    )


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


def _require_non_empty_string(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Importfehler: Feld '{label}' fehlt oder ist leer.")
    return text


def _normalize_float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    out: list[float] = []
    for item in value:
        parsed = _as_optional_float(item)
        if parsed is not None:
            out.append(parsed)
    return out


def _require_float_list(value: Any, label: str) -> list[float]:
    if not isinstance(value, list):
        raise ValueError(f"Importfehler: Feld '{label}' muss eine Liste sein.")
    out: list[float] = []
    for index, item in enumerate(value):
        parsed = _as_optional_float(item)
        if parsed is None:
            raise ValueError(f"Importfehler: Feld '{label}[{index}]' ist ungültig.")
        out.append(parsed)
    return out
