import numpy as np

# Globale Konstanten
R_universal = 8.314462618  # J/(mol*K)
mol_mass_air = 0.0289644  # kg/mol
R_spezifisch = R_universal / mol_mass_air  # ≈ 287.058 J/(kg*K)

def nasa_cp(T):
    """
    Berechnet die spezifische Wärmekapazität Cp basierend auf den NASA 7-Koeffizienten.
    :param T: Temperatur in Kelvin
    :return: Cp in J/(kg*K)
    """
    # NASA-Koeffizienten für 200 K - 1000 K und 1000 K - 6000 K
    db_low = {
        "a1": 10099.5016, "a2": -196.8276, "a3": 5.009155,
        "a4": -0.005761014, "a5": 1.06686e-05, "a6": -7.940298e-09, "a7": 2.185232e-12
    }

    db_high = {
        "a1": 241521.443, "a2": -1257.875, "a3": 5.144559,
        "a4": -0.0002138542, "a5": 7.065228e-08, "a6": -1.071483e-11, "a7": 6.577800e-16
    }

    coeffs = db_low if T < 1000 else db_high

    Cp_molar = (
        (coeffs["a1"] / T**2) +
        (coeffs["a2"] / T) +
        coeffs["a3"] +
        (coeffs["a4"] * T) +
        (coeffs["a5"] * T**2) +
        (coeffs["a6"] * T**3) +
        (coeffs["a7"] * T**4)
    ) * R_universal  # Ergebnis in J/(mol*K)

    return Cp_molar / mol_mass_air  # Umrechnung in J/(kg*K)

def nasa_cv(T):
    """
    Berechnet die spezifische Wärmekapazität Cv basierend auf Cp - R_spezifisch.
    :param T: Temperatur in Kelvin
    :return: Cv in J/(kg*K)
    """
    Cp = nasa_cp(T)
    return Cp - R_spezifisch

def berechne_waermeleistung(T1, T2, m_dot, use_cv=False):
    """
    Berechnet die benötigte Wärmeleistung (kW), um Luft von T1 auf T2 zu erwärmen.
    Falls T2 nicht gegeben ist, wird T2 so berechnet, dass die eingetragene Wärmeleistung genutzt wird.
    :param T1: Anfangstemperatur in Kelvin
    :param T2: Endtemperatur in Kelvin oder None
    :param m_dot: Massenstrom der Luft in kg/s
    :param use_cv: True = Cv verwenden (isochor), False = Cp verwenden (isobar)
    :return: Wärmeleistung in kW oder T2 in K
    """
    cp_func = nasa_cv if use_cv else nasa_cp

    if T2 is not None:
        # Schrittweise Integration von Cp oder Cv über das Temperaturintervall
        T_range = np.arange(T1, T2 + 1, 1)  # Schrittweite 1 K
        Cp_values = np.array([cp_func(T) for T in T_range])
        Cp_mean = np.mean(Cp_values)

        Q = m_dot * Cp_mean * (T2 - T1) / 1000  # Umwandlung in kW
        return Q

    else:
        # Falls T2 nicht gegeben ist, aber Q bekannt ist, bestimme T2 iterativ
        T2 = T1
        Q_current = 0
        while Q_current < m_dot * cp_func(T2) * (T2 - T1) / 1000:
            T2 += 1
            T_range = np.arange(T1, T2 + 1, 1)
            Cp_values = np.array([cp_func(T) for T in T_range])
            Cp_mean = np.mean(Cp_values)
            Q_current = m_dot * Cp_mean * (T2 - T1) / 1000

        return T2