from .gui_utils import check_float, zeige_fehlermeldung
from .reynolds_berechnung import berechne_reynolds
from .viscosity_lucas import dynamic_viscosity_air

def berechne_tab2_werte(entries, shape_var, flow_unit_var):
    fehler = False

    flow = check_float(entries["Volumenstrom"])
    if flow is None:
        fehler = True
    elif flow_unit_var.get() == "m³/h":
        flow /= 3600

    area = None
    durchmesser = None

    if shape_var.get() == "Rund":
        durchmesser = check_float(entries["Durchmesser (mm):"])
        if durchmesser is None:
            fehler = True
        else:
            durchmesser /= 1000
            area = 3.14159 * (durchmesser / 2) ** 2
    else:
        a = check_float(entries["Seite a (mm):"])
        b = check_float(entries["Seite b (mm):"])
        if a is None or b is None:
            fehler = True
        else:
            a /= 1000
            b /= 1000
            durchmesser = (4 * (a * b) / (2 * (a + b)))
            area = a * b

    if fehler or area == 0:
        return None

    velocity = flow / area

    # Optionalwerte für Reynolds-Zahl
    try:
        temp_raw = entries["Temperatur (°C):"].get().strip()
        rho_raw = entries["Dichte (kg/m³):"].get().strip()

        if temp_raw and rho_raw:
            temperature = float(temp_raw) + 273.15
            density = float(rho_raw)
            dynamic_viscosity = dynamic_viscosity_air(temperature)
            reynolds = berechne_reynolds(durchmesser, velocity, dynamic_viscosity, density)

            if reynolds < 2300:
                flow_type = "Laminar"
            elif reynolds < 11000:
                flow_type = "Übergang"
            else:
                flow_type = "Turbulent"
        else:
            reynolds = None
            flow_type = ""
    except Exception as e:
        print("Fehler bei Reynolds-Berechnung:", e)
        reynolds = None
        flow_type = ""

    return {
        "velocity": velocity,
        "reynolds": reynolds,
        "flow_type": flow_type
    }