from nasa_poly import nasa_cp, nasa_cv, berechne_waermeleistung
from viscosity_lucas import dynamic_viscosity_air
import traceback

def berechne_zustand(p1, rho1, T1_C, T2_C, V1, V_norm, Q_kW, zustand, normart):
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

    m_dot2 = (rho2 * V2) / 3600

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
        "T2_C": T2 - K_Kelvin if T2 else None
    }

def apply_norm_values(entries, values, freeze=True):
    for key, value in values.items():
        if key in entries:
            entry = entries[key]
            entry.config(state="normal")
            entry.delete(0, 'end')
            entry.insert(0, value)
            if freeze:
                entry.config(state="readonly")

def toggle_normbedingungen(entries, norm_typ, normkubikmenge_aktiv):
    if norm_typ == "DIN":
        if not normkubikmenge_aktiv:
            apply_norm_values(entries, {
                "Druck 1 (Pa):": "101325",
                "Dichte 1 (kg/m³):": "1.29228",
                "Temperatur 1 (°C):": "0"
            })
    elif norm_typ == "HEATRIX":
        if not normkubikmenge_aktiv:
            apply_norm_values(entries, {
                "Druck 1 (Pa):": "101325",
                "Dichte 1 (kg/m³):": "1.20412",
                "Temperatur 1 (°C):": "20"
            })

    if normkubikmenge_aktiv:
        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
            entries[key].config(state="readonly")
        entries["Temperatur 1 (°C):"].config(state="normal")

def toggle_normkubikmenge(entries, aktiv, normkubik_aktiv, heatrix_aktiv):
    if aktiv:
        entries["Normkubikmeter (m³/h):"].config(state="normal")
        # Feld für Volumenstrom 1 leeren und sperren
        entries["Volumenstrom 1 (m³/h):"].config(state="normal")
        entries["Volumenstrom 1 (m³/h):"].delete(0, 'end')
        entries["Volumenstrom 1 (m³/h):"].config(state="readonly")

        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
            entries[key].config(state="normal")
            entries[key].delete(0, 'end')
            entries[key].config(state="readonly")

        if normkubik_aktiv or heatrix_aktiv:
            entries["Temperatur 1 (°C):"].config(state="normal")
        else:
            entries["Temperatur 1 (°C):"].config(state="readonly")
    else:
        entries["Normkubikmeter (m³/h):"].delete(0, 'end')
        entries["Normkubikmeter (m³/h):"].config(state="disabled")
        entries["Volumenstrom 1 (m³/h):"].config(state="normal")

        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
            entries[key].config(state="normal")
        # Wenn Normkubikmeter deaktiviert wurde, aber DIN oder HEATRIX aktiv ist:
        if normkubik_aktiv:
            toggle_normbedingungen(entries, "DIN", False)
        elif heatrix_aktiv:
            toggle_normbedingungen(entries, "HEATRIX", False)

def starte_berechnung(entries, combo_var, normkubik_var, heatrix_normal_var, normkubikmenge_var):
    try:
        fehler = False

        # Temperatur 1 prüfen
        T1_raw = entries["Temperatur 1 (°C):"].get().strip()
        if not T1_raw or T1_raw == "Bitte eintragen!":
            zeige_fehlermeldung(entries["Temperatur 1 (°C):"])
            fehler = True
        else:
            try:
                T1_C = float(T1_raw)
            except ValueError:
                zeige_fehlermeldung(entries["Temperatur 1 (°C):"])
                fehler = True

        # Temperatur 2 und/oder Wärmeleistung prüfen
        T2_C = None
        Q_kW = None
        T2_raw = entries["Temperatur 2 (°C):"].get().strip()
        Q_raw = entries["Wärmeleistung (kW):"].get().strip()

        if T2_raw and T2_raw != "Bitte eintragen!":
            try:
                T2_C = float(T2_raw)
            except ValueError:
                zeige_fehlermeldung(entries["Temperatur 2 (°C):"])
                fehler = True
        elif Q_raw and Q_raw != "Bitte eintragen!":
            try:
                Q_kW = float(Q_raw)
            except ValueError:
                zeige_fehlermeldung(entries["Wärmeleistung (kW):"])
                fehler = True
        else:
            zeige_fehlermeldung(entries["Temperatur 2 (°C):"])
            fehler = True

        # Volumenstrom prüfen
        V1 = None
        V_norm = None
        if normkubikmenge_var.get():
            V_raw = entries["Normkubikmeter (m³/h):"].get().strip()
            if not V_raw or V_raw == "Bitte eintragen!":
                zeige_fehlermeldung(entries["Normkubikmeter (m³/h):"])
                fehler = True
            else:
                try:
                    V_norm = float(V_raw)
                except ValueError:
                    zeige_fehlermeldung(entries["Normkubikmeter (m³/h):"])
                    fehler = True
        else:
            V1_raw = entries["Volumenstrom 1 (m³/h):"].get().strip()
            if not V1_raw or V1_raw == "Bitte eintragen!":
                zeige_fehlermeldung(entries["Volumenstrom 1 (m³/h):"])
                fehler = True
            else:
                try:
                    V1 = float(V1_raw)
                except ValueError:
                    zeige_fehlermeldung(entries["Volumenstrom 1 (m³/h):"])
                    fehler = True

        # Druck und Dichte prüfen
        p1 = None
        rho1 = None
        p1_raw = entries["Druck 1 (Pa):"].get().strip()
        rho1_raw = entries["Dichte 1 (kg/m³):"].get().strip()
        p1_valid = p1_raw and p1_raw != "Bitte eintragen!"
        rho1_valid = rho1_raw and rho1_raw != "Bitte eintragen!"

        if not normkubikmenge_var.get():
            if not p1_valid and not rho1_valid:
                zeige_fehlermeldung(entries["Druck 1 (Pa):"])
                zeige_fehlermeldung(entries["Dichte 1 (kg/m³):"])
                fehler = True

            if p1_valid:
                try:
                    p1 = float(p1_raw)
                except ValueError:
                    zeige_fehlermeldung(entries["Druck 1 (Pa):"])
                    fehler = True
            if rho1_valid:
                try:
                    rho1 = float(rho1_raw)
                except ValueError:
                    zeige_fehlermeldung(entries["Dichte 1 (kg/m³):"])
                    fehler = True

        if fehler:
            return

        # Zustand & Normart
        zustand = combo_var.get()
        normart = "DIN" if normkubik_var.get() else "HEATRIX" if heatrix_normal_var.get() else None

        # Hauptberechnung
        result = berechne_zustand(p1, rho1, float(T1_raw), T2_C, V1, V_norm, Q_kW, zustand, normart)

        # Ergebnisfelder eintragen
        def set_readonly(key, val):
            e = entries[key]
            e.config(state="normal", foreground="black")
            e.delete(0, 'end')
            e.insert(0, f"{val:.5e}" if abs(val) < 0.001 else f"{val:.5f}")
            e.config(state="readonly")

        for key, val in {
            "Druck 1 (Pa):": result["p1"],
            "Dichte 1 (kg/m³):": result["rho1"],
            "Volumenstrom 1 (m³/h):": result["V1"],
            "Druck 2 (Pa):": result["p2"],
            "Dichte 2 (kg/m³):": result["rho2"],
            "Volumenstrom 2 (m³/h):": result["V2"],
            "Dynamische Viskosität 1 (Pa·s):": result["mu1"],
            "Dynamische Viskosität 2 (Pa·s):": result["mu2"],
            "Schallgeschwindigkeit 1 (m/s):": result["c1"],
            "Schallgeschwindigkeit 2 (m/s):": result["c2"],
            "Spezifische Wärmekapazität Cp 1 (J/kg*K):": result["cp1"] if zustand == "Isobar" else result["cv1"],
            "Spezifische Wärmekapazität Cp 2 (J/kg*K):": result["cp2"] if zustand == "Isobar" else result["cv2"],
            "Massenstrom 1 (kg/s):": result["m_dot1"],
            "Massenstrom 2 (kg/s):": result["m_dot2"],
        }.items():
            if val is None:
                continue

            if key == "Volumenstrom 1 (m³/h):" and not normkubikmenge_var.get():
                e = entries[key]
                e.config(state="normal", foreground="black")
                e.delete(0, 'end')
                e.insert(0, f"{val:.5f}")
            elif key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
                if not normkubikmenge_var.get() and not normkubik_var.get() and not heatrix_normal_var.get():
                    e = entries[key]
                    e.config(state="normal", foreground="black")
                    e.delete(0, 'end')
                    e.insert(0, f"{val:.5f}")
                else:
                    set_readonly(key, val)
            else:
                set_readonly(key, val)

        # Temperatur 2 & Wärmeleistung ausgeben
        e2 = entries["Temperatur 2 (°C):"]
        e2.config(state="normal", foreground="black")
        e2.delete(0, 'end')
        if result["T2_C"] is not None:
            e2.insert(0, f"{result['T2_C']:.2f}")

        eq = entries["Wärmeleistung (kW):"]
        eq.config(state="normal", foreground="black")
        eq.delete(0, 'end')
        if result["Q"] is not None:
            eq.insert(0, f"{result['Q']:.2f}")

    except Exception as e:
        print("Fehler bei der Berechnung:", e)
        traceback.print_exc()

def zeige_fehlermeldung(entry):
    entry.config(foreground="red")
    entry.delete(0, 'end')
    entry.insert(0, "Bitte eintragen!")

    def loesche_text(event):
        if entry.get() == "Bitte eintragen!":
            entry.delete(0, 'end')
            entry.config(foreground="black")

    entry.bind("<FocusIn>", loesche_text)
