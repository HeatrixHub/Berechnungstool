"""
tab1_berechnung_logic.py
Logische Steuerung des Berechnungs-Tabs.
Validiert Eingaben, ruft Berechnungen auf, lädt Isolierungen aus der DB.
"""

from ..core.computation import compute_multilayer
from ..core.database import save_project
from .tab4_isolierungen_logic import load_insulation
from typing import Dict, List


def validate_inputs(n: int, thicknesses: List[float], isolierungen: List[str], T_left: float, T_inf: float, h: float):
    if len(thicknesses) != n or len(isolierungen) != n:
        raise ValueError("Anzahl der Schichten stimmt nicht mit Eingaben überein.")
    if any(t <= 0 for t in thicknesses):
        raise ValueError("Alle Schichtdicken müssen > 0 sein.")
    if h <= 0:
        raise ValueError("Wärmeübergangskoeffizient h muss > 0 sein.")
    return True


def get_k_values_for_layers(isolierungen: List[str], T_mean: float) -> List[float]:
    """
    Holt für jede Isolierung den k-Wert (W/mK) aus der Tab4-Datenbank.
    Für den gegebenen mittleren Temperaturbereich (z.B. Mittel zwischen T_left und T_inf).
    """
    from numpy import interp

    ks = []
    for iso_name in isolierungen:
        if not iso_name:
            ks.append(0.0)
            continue
        data = load_insulation(iso_name)
        temps = data.get("temps", [])
        vals = data.get("ks", [])
        if len(temps) >= 2:
            # Interpolation innerhalb der Messdaten
            k_val = float(interp(T_mean, temps, vals))
        elif len(vals) == 1:
            k_val = float(vals[0])
        else:
            k_val = 0.0
        ks.append(k_val)
    return ks

def perform_calculation(thicknesses: List[float], isolierungen: List[str], T_left: float, T_inf: float, h: float) -> Dict:
    """
    Führt die eigentliche Berechnung durch, mit temperaturabhängigem k(T).
    Holt zu jeder Isolierung die Messdaten (T, k) aus der Datenbank und ruft
    die iterative Mehrschichtberechnung auf.
    """
    k_tables = []
    temps_tables = []

    for iso_name in isolierungen:
        if not iso_name:
            raise ValueError("Eine Schicht hat keine Isolierung ausgewählt.")
        data = load_insulation(iso_name)
        if not data:
            raise ValueError(f"Isolierung '{iso_name}' wurde in der Datenbank nicht gefunden.")
        temps_tables.append(data["temps"])
        k_tables.append(data["ks"])

    # Aufruf der neuen iterativen Berechnung:
    result = compute_multilayer(
        thicknesses=thicknesses,
        k_tables=k_tables,
        temps_tables=temps_tables,
        T_left=T_left,
        T_inf=T_inf,
        h=h
    )

    return result

def save_current_project(name: str, thicknesses, isolierungen, T_left, T_inf, h, result) -> bool:
    """Speichert das aktuelle Projekt in der Datenbank."""
    if not name:
        raise ValueError("Projektnamen angeben, um speichern zu können.")
    # Wir speichern jetzt die Isolierungsnamen anstelle direkter k-Werte
    return save_project(name, thicknesses, isolierungen, T_left, T_inf, h, result)