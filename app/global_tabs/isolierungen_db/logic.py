"""
Gemeinsame Logik für die Verwaltung von Isolierungen.
Ermöglicht das Speichern, Laden, Bearbeiten und Löschen von Isolierungen
sowie die Interpolation der Wärmeleitfähigkeit.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import csv

import numpy as np

from Isolierung.core.database import (
    delete_material,
    list_materials,
    load_material,
    save_material,
)


def get_all_insulations() -> List[Dict]:
    materials = list_materials()
    return [
        {
            "name": material.name,
            "classification_temp": material.classification_temp,
            "density": material.density,
            "length": material.length,
            "width": material.width,
            "height": material.height,
            "price": material.price,
        }
        for material in materials
    ]


def load_insulation(name: str) -> Dict:
    material = load_material(name)
    if not material:
        return {}
    return material.to_dict(include_measurements=True)


def save_insulation(
    name: str,
    classification_temp: float,
    density: float,
    length: float | None,
    width: float | None,
    height: float | None,
    price: float | None,
    temps: List[float],
    ks: List[float],
):
    return save_material(
        name,
        classification_temp,
        density,
        length,
        width,
        height,
        price,
        temps,
        ks,
    )


def delete_insulation(name: str):
    return delete_material(name)


def interpolate_k(temps: List[float], ks: List[float], x_range: np.ndarray):
    """
    Interpoliert/approximiert Wärmeleitfähigkeit k(T) über x_range.
    - >=3 Messpunkte: quadratische Anpassung (Polyfit deg=2)
    - 2 Messpunkte: lineare Anpassung
    - 1 Messpunkt: konstante k
    Rückgabe: np.ndarray mit k-Werten für x_range (gleiche Länge)
    """
    if len(temps) == 0 or len(ks) == 0:
        raise ValueError("Keine Temperatur- oder k-Werte übergeben.")

    temps_arr = np.array(temps, dtype=float)
    ks_arr = np.array(ks, dtype=float)
    order = np.argsort(temps_arr)
    temps_arr = temps_arr[order]
    ks_arr = ks_arr[order]

    unique_temps: List[float] = []
    unique_ks: List[float] = []
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


CSV_HEADERS = [
    "name",
    "classification_temp",
    "density",
    "length",
    "width",
    "height",
    "price",
    "temps",
    "ks",
]


def export_insulations_to_csv(names: List[str], file_path: str) -> Tuple[int, List[str]]:
    """Exportiert ausgewählte Isolierungen nach CSV.

    Returns:
        Tuple[int, List[str]]: Anzahl erfolgreich exportierter Datensätze und Namen,
        die nicht geladen werden konnten.
    """

    failed: List[str] = []
    exported = 0
    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for name in names:
            data = load_insulation(name)
            if not data:
                failed.append(name)
                continue
            writer.writerow(
                {
                    "name": data.get("name", ""),
                    "classification_temp": data.get("classification_temp"),
                    "density": data.get("density"),
                    "length": data.get("length"),
                    "width": data.get("width"),
                    "height": data.get("height"),
                    "price": data.get("price"),
                    "temps": ";".join(map(str, data.get("temps", []))),
                    "ks": ";".join(map(str, data.get("ks", []))),
                }
            )
            exported += 1
    return exported, failed


def import_insulations_from_csv(file_path: str) -> Tuple[int, List[str]]:
    """Importiert Isolierungen aus einer CSV-Datei.

    Returns:
        Tuple[int, List[str]]: Anzahl erfolgreich importierter Datensätze und
        Zeilen, die fehlschlugen (nach Name gekennzeichnet).
    """

    imported = 0
    errors: List[str] = []
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = (row.get("name") or "").strip()
            try:
                class_temp = _parse_optional_float(row.get("classification_temp"))
                density = _parse_optional_float(row.get("density"))
                length = _parse_optional_float(row.get("length"))
                width = _parse_optional_float(row.get("width"))
                height = _parse_optional_float(row.get("height"))
                price = _parse_optional_float(row.get("price"))
                temps = _parse_numeric_list(row.get("temps", ""))
                ks = _parse_numeric_list(row.get("ks", ""))
                if len(temps) != len(ks):
                    raise ValueError("Temperatur- und k-Liste müssen gleich lang sein.")
                save_insulation(
                    name,
                    class_temp if class_temp is not None else 0.0,
                    density if density is not None else 0.0,
                    length,
                    width,
                    height,
                    price,
                    temps,
                    ks,
                )
                imported += 1
            except Exception:
                errors.append(name or "<unbenannt>")
    return imported, errors


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return float(cleaned)


def _parse_numeric_list(value: str) -> List[float]:
    cleaned = (value or "").strip()
    if not cleaned:
        return []
    return [float(item.strip()) for item in cleaned.split(";") if item.strip()]
