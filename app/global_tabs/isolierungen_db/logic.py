"""
Gemeinsame Logik für die Verwaltung von Isolierungen.
Ermöglicht das Speichern, Laden, Bearbeiten und Löschen von Isolierungen
sowie die Interpolation der Wärmeleitfähigkeit.
"""
from __future__ import annotations

from typing import Dict, List

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
    temps: List[float],
    ks: List[float],
):
    return save_material(name, classification_temp, density, temps, ks)


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
