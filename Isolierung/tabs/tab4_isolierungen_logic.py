"""
tab4_isolierungen_logic.py
Logik für den Isolierungen-Tab.
Verwaltet das Speichern, Laden, Bearbeiten und Löschen von Isolierungen.
"""

import sqlite3
import json
import numpy as np
from typing import List, Dict

DB_PATH = "heatrix_data.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS insulations (
            name TEXT PRIMARY KEY,
            classification_temp REAL,
            density REAL,
            temps TEXT,
            ks TEXT
        )
    """)
    return conn


def get_all_insulations() -> List[Dict]:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, classification_temp, density FROM insulations ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [{"name": r[0], "classification_temp": r[1], "density": r[2]} for r in rows]


def load_insulation(name: str) -> Dict:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM insulations WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    return {
        "name": row[0],
        "classification_temp": row[1],
        "density": row[2],
        "temps": json.loads(row[3]),
        "ks": json.loads(row[4]),
    }


def save_insulation(name: str, classification_temp: float, density: float, temps: List[float], ks: List[float]):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO insulations (name, classification_temp, density, temps, ks)
        VALUES (?, ?, ?, ?, ?)
    """, (name, classification_temp, density, json.dumps(temps), json.dumps(ks)))
    conn.commit()
    conn.close()


def delete_insulation(name: str):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM insulations WHERE name=?", (name,))
    conn.commit()
    conn.close()


def interpolate_k(temps: List[float], ks: List[float], x_range: np.ndarray):
    """
    Interpoliert/approximiert Wärmeleitfähigkeit k(T) über x_range.
    - >=3 Messpunkte: quadratische Anpassung (Polyfit deg=2)
    - 2 Messpunkte: lineare Anpassung
    - 1 Messpunkt: konstante k
    Rückgabe: np.ndarray mit k-Werten für x_range (gleiche Länge)
    """
    # Robustheitschecks
    if len(temps) == 0 or len(ks) == 0:
        raise ValueError("Keine Temperatur- oder k-Werte übergeben.")

    # Konvertiere zu numpy und sortiere nach Temperatur
    temps_arr = np.array(temps, dtype=float)
    ks_arr = np.array(ks, dtype=float)
    order = np.argsort(temps_arr)
    temps_arr = temps_arr[order]
    ks_arr = ks_arr[order]

    # Entferne exakte Duplikate in temps (mittelwert der ks für gleiche temp)
    unique_temps = []
    unique_ks = []
    i = 0
    n = len(temps_arr)
    while i < n:
        t = temps_arr[i]
        same_idx = np.where(np.isclose(temps_arr, t))[0]
        same_idx = same_idx[same_idx >= i]
        if same_idx.size > 1:
            mean_k = np.mean(ks_arr[same_idx])
            unique_temps.append(t)
            unique_ks.append(mean_k)
            i = same_idx[-1] + 1
        else:
            unique_temps.append(t)
            unique_ks.append(ks_arr[i])
            i += 1

    temps_u = np.array(unique_temps)
    ks_u = np.array(unique_ks)

    # Fallunterscheidung nach Anzahl Datenpunkte
    if temps_u.size >= 3:
        # Quadratische Anpassung
        coeffs = np.polyfit(temps_u, ks_u, 2)  # a*x^2 + b*x + c
        k_fit = np.polyval(coeffs, x_range)
    elif temps_u.size == 2:
        # Lineare Anpassung (2 Punkte)
        coeffs = np.polyfit(temps_u, ks_u, 1)
        k_fit = np.polyval(coeffs, x_range)
    else:
        # Ein Punkt -> konstant
        k_fit = np.full_like(x_range, ks_u[0], dtype=float)

    return k_fit