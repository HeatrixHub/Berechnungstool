import math

def dynamic_viscosity_air(temperature):
    """
    Berechnet die dynamische Viskosität nach der Lucas-Gleichung aus dem VDI Wärmeatlas.
    
    Parameters:
    -----------
    temperature: float (in Kelvin)

    Returns:
    --------
    mu: dynamische Viskosität in Pa·s
    """

    # Kritische Werte für trockene Luft (aus VDI-Wärmeatlas)
    T_crit = 132.63   # K  (kritische Temperatur)
    p_crit = 37.858   # bar (kritischer Druck)
    M_dryAir = 28.9644  # g/mol (molare Masse trockene Luft)

    # Lucas-Faktoren:
    F_p = 1  # kein Dipolmoment, daher F_p = 1
    theta = 0.176 * (T_crit ** (1/6)) * (M_dryAir ** -0.5) * (p_crit ** -0.667)  # 2/3 = 0.667

    T_r = temperature / T_crit  # reduzierte Temperatur

    # Lucas-Korrelation für μ (in Pa·s)
    mu = (F_p / theta) * (
        0.807 * (T_r ** 0.618)
        - 0.357 * math.exp(-0.449 * T_r)
        + 0.340 * math.exp(-4.058 * T_r)
        + 0.018
    ) * 1e-7

    return mu  # Ergebnis in Pa·s
