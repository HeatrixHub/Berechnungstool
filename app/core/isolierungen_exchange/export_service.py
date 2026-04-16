"""Services für Export von Isolierungen in ein portables Austauschformat."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.isolierungen_db.logic import get_family_by_id
from app.core.time_utils import utc_now_iso_z

from .normalization import normalize_family_for_exchange

EXPORT_FORMAT_NAME = "heatrix_insulation_exchange"
EXPORT_FORMAT_VERSION = 1
EXPORT_FILE_SUFFIX = ".hpxins.json"


def build_insulation_exchange_payload(
    *,
    family_ids: list[int],
    app_version: str | None = None,
) -> dict[str, Any]:
    """Erzeugt ein stabiles Austauschobjekt für ausgewählte Familien."""

    sanitized_family_ids = [int(family_id) for family_id in family_ids if family_id is not None]
    if not sanitized_family_ids:
        raise ValueError("Export abgebrochen: Keine Materialfamilie ausgewählt.")

    exported_items: list[dict[str, Any]] = []
    for family_id in sanitized_family_ids:
        family = get_family_by_id(family_id)
        exported_item = normalize_family_for_exchange(family)
        _validate_export_item(exported_item)
        exported_items.append(exported_item)

    payload: dict[str, Any] = {
        "export_format": {
            "name": EXPORT_FORMAT_NAME,
            "version": EXPORT_FORMAT_VERSION,
        },
        "exported_at": _utc_now_iso(),
        "isolierungen": exported_items,
    }
    app_version_text = str(app_version).strip() if app_version is not None else ""
    if app_version_text:
        payload["app_version"] = app_version_text
    return payload


def export_insulations_to_file(payload: dict[str, Any], destination: Path) -> Path:
    """Schreibt ein Isolierungs-Austauschobjekt in eine Datei."""

    if not isinstance(payload, dict):
        raise ValueError("Exportdaten sind ungültig.")

    target = _with_insulation_suffix(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    target.write_text(serialized, encoding="utf-8")
    return target


def _validate_export_item(item: dict[str, Any]) -> None:
    family = item.get("family") if isinstance(item, dict) else None
    if not isinstance(family, dict):
        raise ValueError("Export abgebrochen: Familiendaten fehlen.")
    family_name = str(family.get("name", "")).strip()
    if not family_name:
        raise ValueError("Export abgebrochen: Familienname fehlt.")

    temps = family.get("temps")
    ks = family.get("ks")
    if not isinstance(temps, list) or not isinstance(ks, list):
        raise ValueError("Export abgebrochen: Temperatur- und k-Werte sind ungültig.")
    if len(temps) != len(ks):
        raise ValueError("Export abgebrochen: Temperatur- und k-Werte sind inkonsistent.")

    variants = family.get("variants")
    if not isinstance(variants, list):
        raise ValueError("Export abgebrochen: Variantenliste ist ungültig.")


def _with_insulation_suffix(destination: Path) -> Path:
    if destination.suffixes[-2:] == [".hpxins", ".json"]:
        return destination

    stem = destination.name
    for suffix in destination.suffixes:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return destination.parent / f"{stem}{EXPORT_FILE_SUFFIX}"


def _utc_now_iso() -> str:
    return utc_now_iso_z()
