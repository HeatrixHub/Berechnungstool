"""Fachlogik für den Leistungsrechner."""
from __future__ import annotations

import math


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_single_phase(voltage: float, current: float) -> float:
    return voltage * current


def calculate_three_phase(voltage: float, current: float) -> float:
    return voltage * current * math.sqrt(3)
