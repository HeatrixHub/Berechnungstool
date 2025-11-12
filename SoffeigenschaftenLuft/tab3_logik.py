def berechne_heizerleistung(eintraege):
    try:
        p_el_str = eintraege["Elektrische Leistung (kW):"].get()
        p_th_str = eintraege["Wärmeleistung (kW):"].get()
        eta_str = eintraege["Effizienz (%):"].get()

        if not eta_str:
            return

        eta = float(eta_str) / 100

        readonly = str(eintraege["Wärmeleistung (kW):"].cget("state")) == "readonly"

        if p_th_str:
            p_th = float(p_th_str)
            p_el = p_th / eta
            return {"Elektrische Leistung (kW):": round(p_el, 2)}

        elif p_el_str:
            p_el = float(p_el_str)
            p_th = p_el * eta
            return {"Wärmeleistung (kW):": round(p_th, 2)}

    except ValueError:
        return None
