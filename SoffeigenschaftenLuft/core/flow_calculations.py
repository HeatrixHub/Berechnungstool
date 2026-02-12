"""Berechnungen für Volumenstrom, Geschwindigkeit und Reynolds-Zahl."""
from __future__ import annotations

from .reynolds_berechnung import berechne_reynolds
from .viscosity_lucas import dynamic_viscosity_air


def compute_flow_properties(
    *,
    shape: str,
    flow: float,
    flow_unit: str,
    diameter_mm: float | None,
    side_a_mm: float | None,
    side_b_mm: float | None,
    temperature_c: float | None,
    density: float | None,
) -> dict[str, float | str | None]:
    if flow_unit == "m³/h":
        flow /= 3600

    area = None
    hydraulic_diameter = None

    if shape == "Rund":
        if diameter_mm is None:
            raise ValueError("Durchmesser fehlt.")
        diameter = diameter_mm / 1000
        area = 3.14159 * (diameter / 2) ** 2
        hydraulic_diameter = diameter
    elif shape == "Rechteckig":
        if side_a_mm is None or side_b_mm is None:
            raise ValueError("Seitenlängen fehlen.")
        a = side_a_mm / 1000
        b = side_b_mm / 1000
        area = a * b
        hydraulic_diameter = (4 * (a * b) / (2 * (a + b)))
    else:
        raise ValueError("Unbekannte Querschnittsform.")

    if area is None or area <= 0:
        raise ValueError("Ungültige Querschnittsfläche.")

    velocity = flow / area

    reynolds = None
    flow_type = ""
    if temperature_c is not None and density is not None:
        temperature = temperature_c + 273.15
        dynamic_viscosity = dynamic_viscosity_air(temperature)
        reynolds = berechne_reynolds(hydraulic_diameter, velocity, dynamic_viscosity, density)

        if reynolds < 2300:
            flow_type = "Laminar"
        elif reynolds < 11000:
            flow_type = "Übergang"
        else:
            flow_type = "Turbulent"

    return {
        "velocity": velocity,
        "reynolds": reynolds,
        "flow_type": flow_type,
    }
