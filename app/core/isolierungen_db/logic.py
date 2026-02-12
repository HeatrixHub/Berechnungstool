"""Business logic for robust insulation DB CRUD using stable IDs.

Create/Update semantics in this module:

* Create operations are explicit and name-based (`create_family`, `create_variant`,
  `create_family_by_name`, `create_variant_by_name`).
* Update operations are explicit and id-based (`update_family`, `update_variant`).
* `save_family` and `save_variant` are kept for backwards compatibility and now only
  perform *create* semantics. They no longer upsert by name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import sqlite3

from .repository import IsolierungRepository

repo = IsolierungRepository()

_material_change_listeners: set[Callable[[], None]] = set()


def register_material_change_listener(callback: Callable[[], None]) -> None:
    _material_change_listeners.add(callback)


def unregister_material_change_listener(callback: Callable[[], None]) -> None:
    _material_change_listeners.discard(callback)


def _notify_material_change_listeners() -> None:
    for listener in list(_material_change_listeners):
        try:
            listener()
        except Exception:
            import traceback

            traceback.print_exc()


def list_families() -> list[dict]:
    return repo.list_families()


def get_family_by_id(family_id: int) -> dict:
    data = repo.get_family(family_id)
    if not data:
        raise ValueError("Materialfamilie nicht gefunden.")
    return data


def create_family(name: str, classification_temp: float, density: float, temps: list[float], ks: list[float]) -> int:
    _validate_family(name, classification_temp, density, temps, ks)
    try:
        family_id = repo.create_family(name, classification_temp, density, temps, ks)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Materialfamilie '{name}' existiert bereits.") from exc
    _notify_material_change_listeners()
    return family_id


def update_family(
    family_id: int,
    name: str,
    classification_temp: float,
    density: float,
    temps: list[float],
    ks: list[float],
) -> None:
    _validate_family(name, classification_temp, density, temps, ks)
    try:
        repo.update_family(family_id, name, classification_temp, density, temps, ks)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Materialfamilie '{name}' existiert bereits.") from exc
    _notify_material_change_listeners()


def delete_family_by_id(family_id: int) -> bool:
    deleted = repo.delete_family(family_id)
    if deleted:
        _notify_material_change_listeners()
    return deleted


def create_variant(
    family_id: int,
    name: str,
    thickness: float,
    length: float | None,
    width: float | None,
    price: float | None,
) -> int:
    _validate_variant(name, thickness)
    try:
        variant_id = repo.create_variant(family_id, name, thickness, length, width, price)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Variante '{name}' existiert in dieser Familie bereits.") from exc
    _notify_material_change_listeners()
    return variant_id


def update_variant(
    variant_id: int,
    name: str,
    thickness: float,
    length: float | None,
    width: float | None,
    price: float | None,
) -> None:
    _validate_variant(name, thickness)
    try:
        repo.update_variant(variant_id, name, thickness, length, width, price)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Variante '{name}' existiert in dieser Familie bereits.") from exc
    _notify_material_change_listeners()


def delete_variant_by_id(variant_id: int) -> bool:
    deleted = repo.delete_variant(variant_id)
    if deleted:
        _notify_material_change_listeners()
    return deleted


def _validate_family(
    name: str, classification_temp: float, density: float, temps: list[float], ks: list[float]
) -> None:
    if not name.strip():
        raise ValueError("Familienname darf nicht leer sein.")
    if classification_temp <= 0:
        raise ValueError("Klassifikationstemperatur muss größer als 0 sein.")
    if density <= 0:
        raise ValueError("Dichte muss größer als 0 sein.")
    if len(temps) != len(ks):
        raise ValueError("Temperatur- und k-Werte müssen gleich viele Einträge haben.")


def _validate_variant(name: str, thickness: float) -> None:
    if not name.strip():
        raise ValueError("Variantenname darf nicht leer sein.")
    if thickness <= 0:
        raise ValueError("Dicke muss größer als 0 sein.")


def get_all_insulations() -> list[dict]:
    return list_families()


def load_insulation(name: str) -> dict:
    data = repo.get_family_by_name(name)
    return data or {}


def save_family(
    name: str,
    classification_temp: float | None,
    density: float | None,
    temps: list[float],
    ks: list[float],
    *,
    notify: bool = True,
) -> bool:
    """Create a family by name.

    This helper is intentionally create-only for API clarity. To modify an
    existing family, call :func:`update_family` with a family id.
    """
    return create_family_by_name(
        name,
        classification_temp,
        density,
        temps,
        ks,
        notify=notify,
    )


def create_family_by_name(
    name: str,
    classification_temp: float | None,
    density: float | None,
    temps: list[float],
    ks: list[float],
    *,
    notify: bool = True,
) -> bool:
    """Create a family from user inputs.

    Raises:
        ValueError: If required fields are missing or a family with the same
            name already exists.
    """
    if classification_temp is None or density is None:
        raise ValueError("Klass.-Temp und Dichte sind Pflichtfelder.")
    existing = repo.get_family_by_name(name)
    if existing:
        raise ValueError(
            f"Materialfamilie '{name}' existiert bereits. "
            "Für Änderungen bitte update_family(family_id, ...) verwenden."
        )
    create_family(name, classification_temp, density, temps, ks)
    if not notify:
        return True
    return True


def save_variant(
    material_name: str,
    variant_name: str,
    thickness: float,
    length: float | None,
    width: float | None,
    price: float | None,
    *,
    notify: bool = True,
) -> bool:
    """Create a variant by names (`material_name`, `variant_name`).

    This helper is intentionally create-only for API clarity. To modify an
    existing variant, call :func:`update_variant` with a variant id.
    """
    return create_variant_by_name(
        material_name,
        variant_name,
        thickness,
        length,
        width,
        price,
        notify=notify,
    )


def create_variant_by_name(
    material_name: str,
    variant_name: str,
    thickness: float,
    length: float | None,
    width: float | None,
    price: float | None,
    *,
    notify: bool = True,
) -> bool:
    """Create a variant for an existing family identified by name.

    Raises:
        ValueError: If family/variant constraints are violated. Existing
            variants are not updated implicitly.
    """
    family = repo.get_family_by_name(material_name)
    if not family:
        return False
    existing = next((row for row in family["variants"] if row["name"] == variant_name), None)
    if existing:
        raise ValueError(
            f"Variante '{variant_name}' existiert in Familie '{material_name}' bereits. "
            "Für Änderungen bitte update_variant(variant_id, ...) verwenden."
        )
    create_variant(family["id"], variant_name, thickness, length, width, price)
    return True


def delete_insulation(name: str):
    family = repo.get_family_by_name(name)
    if not family:
        return False
    return delete_family_by_id(family["id"])


def delete_variant(material_name: str, variant_name: str) -> bool:
    family = repo.get_family_by_name(material_name)
    if not family:
        return False
    variant = next((row for row in family["variants"] if row["name"] == variant_name), None)
    if not variant:
        return False
    return delete_variant_by_id(variant["id"])


def rename_family(old_name: str, new_name: str) -> bool:
    family = repo.get_family_by_name(old_name)
    if not family:
        return False
    update_family(
        family["id"],
        new_name,
        family["classification_temp"],
        family["density"],
        family["temps"],
        family["ks"],
    )
    return True


def rename_variant(material_name: str, old_name: str, new_name: str) -> bool:
    family = repo.get_family_by_name(material_name)
    if not family:
        return False
    variant = next((row for row in family["variants"] if row["name"] == old_name), None)
    if not variant:
        return False
    update_variant(
        variant["id"],
        new_name,
        float(variant["thickness"]),
        variant.get("length"),
        variant.get("width"),
        variant.get("price"),
    )
    return True


def interpolate_k(temps: list[float], ks: list[float], x_range: np.ndarray):
    if len(temps) == 0 or len(ks) == 0:
        raise ValueError("Keine Temperatur- oder k-Werte übergeben.")

    temps_arr = np.array(temps, dtype=float)
    ks_arr = np.array(ks, dtype=float)
    order = np.argsort(temps_arr)
    temps_arr = temps_arr[order]
    ks_arr = ks_arr[order]

    unique_temps: list[float] = []
    unique_ks: list[float] = []
    i = 0
    n = len(temps_arr)
    while i < n:
        t = temps_arr[i]
        same_idx = np.where(np.isclose(temps_arr, t))[0]
        same_idx = same_idx[same_idx >= i]
        if same_idx.size > 1:
            mean_k = float(np.mean(ks_arr[same_idx]))
            unique_temps.append(float(t))
            unique_ks.append(mean_k)
            i = int(same_idx[-1] + 1)
        else:
            unique_temps.append(float(t))
            unique_ks.append(float(ks_arr[i]))
            i += 1

    temps_u = np.array(unique_temps)
    ks_u = np.array(unique_ks)

    if temps_u.size >= 3:
        coeffs = np.polyfit(temps_u, ks_u, 2)
        k_fit = np.polyval(coeffs, x_range)
    elif temps_u.size == 2:
        coeffs = np.polyfit(temps_u, ks_u, 1)
        k_fit = np.polyval(coeffs, x_range)
    else:
        k_fit = np.full_like(x_range, ks_u[0], dtype=float)

    return k_fit


CSV_HEADERS: list[str] = []
LEGACY_HEADERS: set[str] = set()
REQUIRED_HEADERS: set[str] = set()


@dataclass
class FileImportResult:
    file_path: str
    imported: int
    errors: list[str]
    skipped_reason: str | None = None


def export_insulations_to_csv(names: list[str], file_path: str):
    raise NotImplementedError("Export wurde in der Neufassung bewusst entfernt.")


def export_insulations_to_folder(names: list[str], target_directory: str):
    raise NotImplementedError("Export wurde in der Neufassung bewusst entfernt.")


def import_insulations_from_csv_files(file_paths: list[str]):
    raise NotImplementedError("Import wurde in der Neufassung bewusst entfernt.")


def import_insulations_from_csv(file_path: str):
    raise NotImplementedError("Import wurde in der Neufassung bewusst entfernt.")
