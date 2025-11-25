import numpy as np
from app.global_tabs.isolierungen_db.logic import interpolate_k  # nutzt deine Interpolationsfunktion

def compute_multilayer(thicknesses, k_tables, temps_tables, T_left, T_inf, h, tol=0.5, max_iter=100):
    """
    Mehrschichtige Wärmeleitung mit temperaturabhängigem k(T),
    inklusive 1-mm-Diskretisierung jeder Schicht.
    """

    n = len(thicknesses)
    thicknesses_m = np.array(thicknesses) / 1000.0  # [mm] → [m]
    ks = np.array([np.mean(k_tab) for k_tab in k_tables])  # Startwerte
    T_avg_old = np.full(n, T_left)

    for iteration in range(max_iter):
        # -----------------------------
        # 1. Wärmewiderstände und q
        # -----------------------------
        R_layers = thicknesses_m / ks
        R_total = np.sum(R_layers) + 1 / h
        q = (T_left - T_inf) / R_total

        # -----------------------------
        # 2. Grenzflächentemperaturen
        # -----------------------------
        T_interfaces = [T_left]
        for R in R_layers:
            T_interfaces.append(T_interfaces[-1] - q * R)
        T_interfaces = np.array(T_interfaces)

        # -----------------------------
        # 3. Diskretisierung pro Schicht (1 mm)
        # -----------------------------
        T_avg_new = []
        k_avg_new = []

        for i in range(n):
            T_l = T_interfaces[i]
            T_r = T_interfaces[i + 1]
            d_mm = max(1, int(round(thicknesses[i])))  # Anzahl der 1-mm-Teilstücke

            # lokale Temperaturen (linearer Verlauf)
            T_local = np.linspace(T_l, T_r, d_mm)
            k_local = interpolate_k(temps_tables[i], k_tables[i], T_local)

            T_avg_layer = float(np.mean(T_local))
            k_avg_layer = float(np.mean(k_local))

            T_avg_new.append(T_avg_layer)
            k_avg_new.append(k_avg_layer)

        T_avg_new = np.array(T_avg_new)
        k_avg_new = np.array(k_avg_new)

        # -----------------------------
        # 4. Prüfen, ob konvergiert
        # -----------------------------
        delta = np.max(np.abs(T_avg_new - T_avg_old))
        if delta <= tol:
            return {
                "q": q,
                "R_total": R_total,
                "interface_temperatures": T_interfaces.tolist(),
                "iterations": iteration + 1,
                "T_avg": T_avg_new.tolist(),
                "k_final": k_avg_new.tolist(),
            }

        # -----------------------------
        # 5. Vorbereitung für nächste Iteration
        # -----------------------------
        ks = k_avg_new
        T_avg_old = T_avg_new

    raise RuntimeError(
        f"Nicht konvergiert nach {max_iter} Iterationen (ΔT={delta:.3f} °C)"
    )