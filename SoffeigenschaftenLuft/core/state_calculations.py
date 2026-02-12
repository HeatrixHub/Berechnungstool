"""Berechnungen für Zustandsgrößen der Luft."""
from __future__ import annotations

from .nasa_poly import nasa_cp, nasa_cv, berechne_waermeleistung
from .viscosity_lucas import dynamic_viscosity_air


def calculate_state(
    p1: float | None,
    rho1: float | None,
    T1_C: float,
    T2_C: float | None,
    V1: float | None,
    V_norm: float | None,
    Q_kW: float | None,
    zustand: str,
    normart: str | None,
) -> dict[str, float | None]:
    R_specific = 287.058
    K_Kelvin = 273.15
    T1 = T1_C + K_Kelvin
    T2 = T2_C + K_Kelvin if T2_C is not None else None
    if V_norm is None:
        if p1 is not None and rho1 is None:
            rho1 = p1 / (R_specific * T1)
        elif rho1 is not None and p1 is None:
            p1 = rho1 * R_specific * T1

    if normart == "DIN":
        T0 = 273.15
        p0 = 101325
        rho0 = 1.29228
    elif normart == "HEATRIX":
        T0 = 293.15
        p0 = 101325
        rho0 = 1.20412
    else:
        T0 = p0 = rho0 = None

    if V_norm is not None:
        if zustand == "Isobar":
            p1 = p0
            rho1 = p1 / (R_specific * T1)
        elif zustand == "Isochor":
            rho1 = rho0
            p1 = rho1 * R_specific * T1
        V1 = V_norm * (p0 / p1) * (T1 / T0)

    m_dot1 = (rho1 * V1) / 3600 if rho1 and V1 else None

    Q_current = None
    # Iterative Berechnung von T2 bei gegebener Wärmeleistung
    if Q_kW is not None and T2 is None and m_dot1:
        T2 = T1
        Q_target = Q_kW
        Q_current = 0
        while Q_current < Q_target:
            T2 += 1
            T_range = range(int(T1), int(T2) + 1)
            Cp_values = [nasa_cv(T) if zustand == "Isochor" else nasa_cp(T) for T in T_range]
            Cp_mean = sum(Cp_values) / len(Cp_values)
            Q_current = m_dot1 * Cp_mean * (T2 - T1) / 1000

    if zustand == "Isobar":
        p2 = p1
        V2 = V1 * (T2 / T1) if T2 else V1
    elif zustand == "Isochor":
        V2 = V1
        p2 = p1 * (T2 / T1) if T2 else p1
    else:
        p2, V2 = p1, V1

    rho2 = rho1 * (p2 / p1) * (T1 / T2) if T2 else rho1
    mu1 = dynamic_viscosity_air(T1)
    mu2 = dynamic_viscosity_air(T2) if T2 else mu1
    c1 = (1.4 * R_specific * T1) ** 0.5
    c2 = (1.4 * R_specific * T2) ** 0.5 if T2 else c1

    waermekap1 = nasa_cp(T1) if zustand == "Isobar" else nasa_cv(T1)
    waermekap2 = nasa_cp(T2) if T2 and zustand == "Isobar" else nasa_cv(T2) if T2 else waermekap1

    m_dot2 = (rho2 * V2) / 3600 if rho2 and V2 else None

    Q = Q_kW if Q_kW is not None else berechne_waermeleistung(T1, T2, m_dot1, use_cv=(zustand == "Isochor"))

    return {
        "p1": p1,
        "rho1": rho1,
        "V1": V1,
        "p2": p2,
        "rho2": rho2,
        "V2": V2,
        "mu1": mu1,
        "mu2": mu2,
        "c1": c1,
        "c2": c2,
        "cp1": waermekap1 if zustand == "Isobar" else None,
        "cp2": waermekap2 if zustand == "Isobar" else None,
        "cv1": waermekap1 if zustand == "Isochor" else None,
        "cv2": waermekap2 if zustand == "Isochor" else None,
        "m_dot1": m_dot1,
        "m_dot2": m_dot2,
        "Q": Q,
        "T2_C": T2 - K_Kelvin if T2 else None,
    }
