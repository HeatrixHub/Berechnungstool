"""Berechnungen für Heizleistungen."""
from __future__ import annotations


def compute_heater_power(
    *,
    electrical_kw: float | None,
    thermal_kw: float | None,
    efficiency_percent: float,
) -> dict[str, float]:
    if efficiency_percent <= 0:
        raise ValueError("Effizienz muss größer als 0 sein.")
    eta = efficiency_percent / 100

    if thermal_kw is not None:
        return {"electrical_kw": round(thermal_kw / eta, 2)}
    if electrical_kw is not None:
        return {"thermal_kw": round(electrical_kw * eta, 2)}

    raise ValueError("Elektrische oder thermische Leistung erforderlich.")
