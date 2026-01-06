import traceback
import tkinter as tk
from tkinter import ttk

from ..core.state_calculations import calculate_state
from .gui_utils import ToolTip, zeige_fehlermeldung

entries: dict[str, tk.Entry] = {}
entries_global = entries

labels: dict[str, ttk.Label] = {}

combo_var: tk.StringVar | None = None
normkubik_var: tk.BooleanVar | None = None
heatrix_normal_var: tk.BooleanVar | None = None
normkubikmenge_var: tk.BooleanVar | None = None
heat_priority_var: tk.BooleanVar | None = None
_handle_toggle_din_fn = None
_handle_toggle_heatrix_fn = None
_handle_toggle_normkubikmenge_fn = None


def update_cp_labels():
    if not labels:
        return
    if combo_var and combo_var.get() == "Isochor":
        labels["Spezifische Wärmekapazität Cp 1 (J/kg*K):"].config(
            text="Spezifische Wärmekapazität Cv 1 (J/kg*K):"
        )
        labels["Spezifische Wärmekapazität Cp 2 (J/kg*K):"].config(
            text="Spezifische Wärmekapazität Cv 2 (J/kg*K):"
        )
    else:
        labels["Spezifische Wärmekapazität Cp 1 (J/kg*K):"].config(
            text="Spezifische Wärmekapazität Cp 1 (J/kg*K):"
        )
        labels["Spezifische Wärmekapazität Cp 2 (J/kg*K):"].config(
            text="Spezifische Wärmekapazität Cp 2 (J/kg*K):"
        )


def update_normkubik_label():
    if not labels:
        return

    if normkubik_var and normkubik_var.get():
        labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (Nm³/h):")
    elif heatrix_normal_var and heatrix_normal_var.get():
        labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (HNm³/h):")
    else:
        labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (m³/h):")


def get_entries():
    return entries_global


def apply_norm_values(entries: dict[str, tk.Entry], values: dict[str, str], freeze: bool = True) -> None:
    for key, value in values.items():
        if key in entries:
            entry = entries[key]
            entry.config(state="normal")
            entry.delete(0, "end")
            entry.insert(0, value)
            if freeze:
                entry.config(state="readonly")


def toggle_normbedingungen(
    entries: dict[str, tk.Entry], norm_typ: str, normkubikmenge_aktiv: bool
) -> None:
    if norm_typ == "DIN":
        if not normkubikmenge_aktiv:
            apply_norm_values(
                entries,
                {
                    "Druck 1 (Pa):": "101325",
                    "Dichte 1 (kg/m³):": "1.29228",
                    "Temperatur 1 (°C):": "0",
                },
            )
    elif norm_typ == "HEATRIX":
        if not normkubikmenge_aktiv:
            apply_norm_values(
                entries,
                {
                    "Druck 1 (Pa):": "101325",
                    "Dichte 1 (kg/m³):": "1.20412",
                    "Temperatur 1 (°C):": "20",
                },
            )

    if normkubikmenge_aktiv:
        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
            entries[key].config(state="readonly")
        entries["Temperatur 1 (°C):"].config(state="normal")


def toggle_normkubikmenge(
    entries: dict[str, tk.Entry],
    aktiv: bool,
    normkubik_aktiv: bool,
    heatrix_aktiv: bool,
) -> None:
    if aktiv:
        entries["Normkubikmeter (m³/h):"].config(state="normal")
        # Feld für Volumenstrom 1 leeren und sperren
        entries["Volumenstrom 1 (m³/h):"].config(state="normal")
        entries["Volumenstrom 1 (m³/h):"].delete(0, "end")
        entries["Volumenstrom 1 (m³/h):"].config(state="readonly")

        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
            entries[key].config(state="normal")
            entries[key].delete(0, "end")
            entries[key].config(state="readonly")

        if normkubik_aktiv or heatrix_aktiv:
            entries["Temperatur 1 (°C):"].config(state="normal")
        else:
            entries["Temperatur 1 (°C):"].config(state="readonly")
    else:
        entries["Normkubikmeter (m³/h):"].delete(0, "end")
        entries["Normkubikmeter (m³/h):"].config(state="disabled")
        entries["Volumenstrom 1 (m³/h):"].config(state="normal")

        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
            entries[key].config(state="normal")
        # Wenn Normkubikmeter deaktiviert wurde, aber DIN oder HEATRIX aktiv ist:
        if normkubik_aktiv:
            toggle_normbedingungen(entries, "DIN", False)
        elif heatrix_aktiv:
            toggle_normbedingungen(entries, "HEATRIX", False)


def _read_required_float(entry: tk.Entry, label: str) -> float | None:
    raw = entry.get().strip()
    if not raw or raw == "Bitte eintragen!":
        zeige_fehlermeldung(entry)
        return None
    try:
        return float(raw)
    except ValueError:
        zeige_fehlermeldung(entry)
        return None


def start_calculation(
    entries: dict[str, tk.Entry],
    combo_var: tk.StringVar,
    normkubik_var: tk.BooleanVar,
    heatrix_normal_var: tk.BooleanVar,
    normkubikmenge_var: tk.BooleanVar,
    heat_priority_var: tk.BooleanVar,
) -> None:
    try:
        fehler = False

        T1_C = _read_required_float(entries["Temperatur 1 (°C):"], "Temperatur 1")
        if T1_C is None:
            fehler = True

        T2_C = None
        Q_kW = None
        heat_priority = heat_priority_var.get()

        T2_entry = entries["Temperatur 2 (°C):"]
        Q_entry = entries["Wärmeleistung (kW):"]

        if heat_priority:
            Q_kW = _read_required_float(Q_entry, "Wärmeleistung")
            if Q_kW is None:
                fehler = True
        else:
            T2_raw = T2_entry.get().strip()
            Q_raw = Q_entry.get().strip()
            if T2_raw and T2_raw != "Bitte eintragen!":
                try:
                    T2_C = float(T2_raw)
                except ValueError:
                    zeige_fehlermeldung(T2_entry)
                    fehler = True
            elif Q_raw and Q_raw != "Bitte eintragen!":
                try:
                    Q_kW = float(Q_raw)
                except ValueError:
                    zeige_fehlermeldung(Q_entry)
                    fehler = True
            else:
                zeige_fehlermeldung(T2_entry)
                fehler = True

        V1 = None
        V_norm = None
        if normkubikmenge_var.get():
            V_norm = _read_required_float(entries["Normkubikmeter (m³/h):"], "Normkubikmeter")
            if V_norm is None:
                fehler = True
        else:
            V1 = _read_required_float(entries["Volumenstrom 1 (m³/h):"], "Volumenstrom 1")
            if V1 is None:
                fehler = True

        p1 = None
        rho1 = None
        p1_entry = entries["Druck 1 (Pa):"]
        rho1_entry = entries["Dichte 1 (kg/m³):"]
        p1_raw = p1_entry.get().strip()
        rho1_raw = rho1_entry.get().strip()
        p1_valid = p1_raw and p1_raw != "Bitte eintragen!"
        rho1_valid = rho1_raw and rho1_raw != "Bitte eintragen!"

        if not normkubikmenge_var.get():
            if not p1_valid and not rho1_valid:
                zeige_fehlermeldung(p1_entry)
                zeige_fehlermeldung(rho1_entry)
                fehler = True

            if p1_valid:
                try:
                    p1 = float(p1_raw)
                except ValueError:
                    zeige_fehlermeldung(p1_entry)
                    fehler = True
            if rho1_valid:
                try:
                    rho1 = float(rho1_raw)
                except ValueError:
                    zeige_fehlermeldung(rho1_entry)
                    fehler = True

        if fehler:
            return

        zustand = combo_var.get()
        normart = "DIN" if normkubik_var.get() else "HEATRIX" if heatrix_normal_var.get() else None

        result = calculate_state(p1, rho1, T1_C, T2_C, V1, V_norm, Q_kW, zustand, normart)

        def set_readonly(key: str, val: float) -> None:
            entry = entries[key]
            entry.config(state="normal", foreground="black")
            entry.delete(0, "end")
            entry.insert(0, f"{val:.5e}" if abs(val) < 0.001 else f"{val:.5f}")
            entry.config(state="readonly")

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
            "Spezifische Wärmekapazität Cp 1 (J/kg*K):": result["cp1"]
            if zustand == "Isobar"
            else result["cv1"],
            "Spezifische Wärmekapazität Cp 2 (J/kg*K):": result["cp2"]
            if zustand == "Isobar"
            else result["cv2"],
            "Massenstrom 1 (kg/s):": result["m_dot1"],
            "Massenstrom 2 (kg/s):": result["m_dot2"],
        }.items():
            if val is None:
                continue

            if key == "Volumenstrom 1 (m³/h):" and not normkubikmenge_var.get():
                entry = entries[key]
                entry.config(state="normal", foreground="black")
                entry.delete(0, "end")
                entry.insert(0, f"{val:.5f}")
            elif key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
                if not normkubikmenge_var.get() and not normkubik_var.get() and not heatrix_normal_var.get():
                    entry = entries[key]
                    entry.config(state="normal", foreground="black")
                    entry.delete(0, "end")
                    entry.insert(0, f"{val:.5f}")
                else:
                    set_readonly(key, val)
            else:
                set_readonly(key, val)

        # Temperatur 2 & Wärmeleistung ausgeben
        e2 = entries["Temperatur 2 (°C):"]
        e2.config(state="normal", foreground="black")
        e2.delete(0, "end")
        if result["T2_C"] is not None:
            e2.insert(0, f"{result['T2_C']:.2f}")

        eq = entries["Wärmeleistung (kW):"]
        eq.config(state="normal", foreground="black")
        eq.delete(0, "end")
        if result["Q"] is not None:
            eq.insert(0, f"{result['Q']:.2f}")

    except Exception as exc:
        print("Fehler bei der Berechnung:", exc)
        traceback.print_exc()


def create_tab1(notebook):
    global combo_var
    global normkubik_var
    global heatrix_normal_var
    global normkubikmenge_var
    global heat_priority_var
    global _handle_toggle_din_fn
    global _handle_toggle_heatrix_fn
    global _handle_toggle_normkubikmenge_fn

    frame_tab1 = tk.Frame(notebook, padx=20, pady=10)
    notebook.add(frame_tab1, text="Zustandsgrößen")

    combo_var = tk.StringVar(value="Isobar")
    combo_box = ttk.Combobox(
        frame_tab1,
        textvariable=combo_var,
        values=["Isobar", "Isochor"],
        state="readonly",
        width=18,
    )
    combo_box.grid(row=0, column=1, columnspan=2, pady=10, padx=(10, 0), sticky=tk.W)
    ToolTip(
        combo_box,
        "Wähle die Art der Zustandsänderung: isobar (konstanter Druck) oder isochor (konstantes Volumen).",
    )

    combo_var.trace_add("write", lambda *args: update_cp_labels())

    normkubik_var = tk.BooleanVar()
    heatrix_normal_var = tk.BooleanVar()
    normkubikmenge_var = tk.BooleanVar()
    heat_priority_var = tk.BooleanVar()

    def handle_toggle_din():
        if normkubik_var.get():
            heatrix_normal_var.set(False)
            toggle_normbedingungen(entries, "DIN", normkubikmenge_var.get())
        else:
            if not heatrix_normal_var.get() and not normkubikmenge_var.get():
                for key in ["Temperatur 1 (°C):", "Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
                    entries[key].config(state="normal")
        update_normkubik_label()

    def handle_toggle_heatrix():
        if heatrix_normal_var.get():
            normkubik_var.set(False)
            toggle_normbedingungen(entries, "HEATRIX", normkubikmenge_var.get())
        else:
            if not normkubik_var.get() and not normkubikmenge_var.get():
                for key in ["Temperatur 1 (°C):", "Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
                    entries[key].config(state="normal")
        update_normkubik_label()

    def handle_toggle_normkubikmenge():
        if normkubikmenge_var.get() and not normkubik_var.get() and not heatrix_normal_var.get():
            heatrix_normal_var.set(True)
            toggle_normbedingungen(entries, "HEATRIX", True)
            update_normkubik_label()

        if not normkubikmenge_var.get() and not normkubik_var.get() and not heatrix_normal_var.get():
            for key in ["Temperatur 1 (°C):", "Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
                entries["Volumenstrom 1 (m³/h):"].config(state="normal")
                entries["Volumenstrom 1 (m³/h):"].delete(0, "end")
                entries["Volumenstrom 1 (m³/h):"].config(state="readonly")

        toggle_normkubikmenge(
            entries,
            normkubikmenge_var.get(),
            normkubik_var.get(),
            heatrix_normal_var.get(),
        )

    _handle_toggle_din_fn = handle_toggle_din
    _handle_toggle_heatrix_fn = handle_toggle_heatrix
    _handle_toggle_normkubikmenge_fn = handle_toggle_normkubikmenge

    din_check = ttk.Checkbutton(
        frame_tab1,
        text="Normbedingungen DIN 1343",
        variable=normkubik_var,
        command=handle_toggle_din,
    )
    din_check.grid(row=1, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(
        din_check,
        "Setzt Temperatur, Druck und Dichte auf DIN 1343 Normwerte (0°C, 101325 Pa, 1.29228 kg/m³).",
    )

    heatrix_check = ttk.Checkbutton(
        frame_tab1,
        text="Heatrix Normalbedingungen",
        variable=heatrix_normal_var,
        command=handle_toggle_heatrix,
    )
    heatrix_check.grid(row=2, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(
        heatrix_check,
        "Setzt Temperatur, Druck und Dichte auf Heatrix-Normalwerte (20°C, 101325 Pa, 1.20412 kg/m³).",
    )

    norm_check = ttk.Checkbutton(
        frame_tab1,
        text="Normkubikmeter verwenden",
        variable=normkubikmenge_var,
        command=handle_toggle_normkubikmenge,
    )
    norm_check.grid(row=1, column=2, columnspan=1, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(
        norm_check,
        "Aktiviert die Umrechnung von Normkubikmetern in tatsächlichen Volumenstrom.",
    )

    fields = [
        ("Normkubikmeter (m³/h):", "", 3, 2),
        ("Temperatur 1 (°C):", "20", 4, 0),
        ("Volumenstrom 1 (m³/h):", "", 5, 0),
        ("Druck 1 (Pa):", "101325", 6, 0),
        ("Dichte 1 (kg/m³):", "1.20412", 7, 0),
        ("Temperatur 2 (°C):", "", 4, 2),
        ("Volumenstrom 2 (m³/h):", "", 5, 2),
        ("Druck 2 (Pa):", "", 6, 2),
        ("Dichte 2 (kg/m³):", "", 7, 2),
        ("Dynamische Viskosität 1 (Pa·s):", "", 8, 0),
        ("Dynamische Viskosität 2 (Pa·s):", "", 8, 2),
        ("Schallgeschwindigkeit 1 (m/s):", "", 9, 0),
        ("Schallgeschwindigkeit 2 (m/s):", "", 9, 2),
        ("Spezifische Wärmekapazität Cp 1 (J/kg*K):", "", 10, 0),
        ("Spezifische Wärmekapazität Cp 2 (J/kg*K):", "", 10, 2),
        ("Massenstrom 1 (kg/s):", "", 11, 0),
        ("Massenstrom 2 (kg/s):", "", 11, 2),
        ("Wärmeleistung (kW):", "", 12, 0),
    ]

    for text, default, row, col in fields:
        label = ttk.Label(frame_tab1, text=text)
        label.grid(row=row, column=col, padx=10, pady=5, sticky="w")
        labels[text] = label

        entry = ttk.Entry(frame_tab1)
        entry.insert(0, default)

        if text == "Normkubikmeter (m³/h):":
            entry.config(state="disabled")

        if text in [
            "Druck 2 (Pa):",
            "Dichte 2 (kg/m³):",
            "Volumenstrom 2 (m³/h):",
            "Dynamische Viskosität 1 (Pa·s):",
            "Dynamische Viskosität 2 (Pa·s):",
            "Schallgeschwindigkeit 1 (m/s):",
            "Schallgeschwindigkeit 2 (m/s):",
            "Spezifische Wärmekapazität Cp1 (J/kg*K):",
            "Spezifische Wärmekapazität Cp2 (J/kg*K):",
            "Massenstrom 1 (kg/s):",
            "Massenstrom 2 (kg/s):",
        ]:
            entry.config(state="readonly")

        entry.grid(row=row, column=col + 1, padx=10, pady=5)
        entries[text] = entry

        if "Temperatur" in text:
            ToolTip(entry, "Temperatur in Grad Celsius eingeben.")
        elif "Volumenstrom" in text:
            ToolTip(
                entry,
                "Volumenstrom in m³/h eingeben. Wird automatisch berechnet, wenn Normkubikmeter aktiv ist.",
            )
        elif "Druck" in text:
            ToolTip(entry, "Druck in Pascal (Pa) eingeben oder automatisch berechnen lassen.")
        elif "Dichte" in text:
            ToolTip(
                entry,
                "Dichte der Luft in kg/m³. Wird automatisch berechnet, wenn genügend Daten vorhanden sind.",
            )
        elif "Wärmeleistung" in text:
            ToolTip(entry, "Gib eine bekannte Wärmeleistung ein oder lasse sie aus Temperaturdaten berechnen.")

            heat_priority_check = ttk.Checkbutton(
                frame_tab1,
                text="Wärmeleistung priorisieren",
                variable=heat_priority_var,
            )
            heat_priority_check.grid(row=row, column=col + 2, padx=10, pady=5, sticky=tk.W)
            ToolTip(
                heat_priority_check,
                "Wenn aktiviert, wird Temperatur 2 immer aus der Wärmeleistung berechnet.",
            )

    calculate_button = ttk.Button(
        frame_tab1,
        text="Berechnen",
        command=lambda: start_calculation(
            entries,
            combo_var,
            normkubik_var,
            heatrix_normal_var,
            normkubikmenge_var,
            heat_priority_var,
        ),
    )
    calculate_button.grid(row=13, column=0, columnspan=4, pady=15)
    ToolTip(calculate_button, "Startet die Berechnung basierend auf den eingegebenen Werten.")

    if not normkubik_var.get() and not heatrix_normal_var.get() and not normkubikmenge_var.get():
        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
            entries[key].config(state="normal")

    return frame_tab1


def _write_entry_preserve_state(entry: tk.Entry, value: str | None) -> None:
    current_state = entry.cget("state")
    entry.config(state="normal")
    entry.delete(0, tk.END)
    entry.insert(0, "" if value is None else value)
    entry.config(state=current_state)


def export_state_tab1() -> dict[str, object]:
    return {
        "zustand": combo_var.get() if combo_var else None,
        "normkubik": normkubik_var.get() if normkubik_var else False,
        "heatrix": heatrix_normal_var.get() if heatrix_normal_var else False,
        "normkubikmenge": normkubikmenge_var.get() if normkubikmenge_var else False,
        "heat_priority": heat_priority_var.get() if heat_priority_var else False,
        "entries": {key: entry.get() for key, entry in entries.items()},
    }


def import_state_tab1(state: dict[str, object]) -> None:
    if (
        combo_var is None
        or normkubik_var is None
        or heatrix_normal_var is None
        or normkubikmenge_var is None
        or heat_priority_var is None
    ):
        return

    zustand_value = state.get("zustand")
    if isinstance(zustand_value, str) and zustand_value:
        combo_var.set(zustand_value)
        update_cp_labels()

    normkubik_var.set(bool(state.get("normkubik", False)))
    heatrix_normal_var.set(bool(state.get("heatrix", False)))
    normkubikmenge_var.set(bool(state.get("normkubikmenge", False)))
    heat_priority_var.set(bool(state.get("heat_priority", False)))

    if normkubik_var.get() and _handle_toggle_din_fn:
        _handle_toggle_din_fn()
    if heatrix_normal_var.get() and _handle_toggle_heatrix_fn:
        _handle_toggle_heatrix_fn()
    if _handle_toggle_normkubikmenge_fn:
        _handle_toggle_normkubikmenge_fn()

    for key, value in state.get("entries", {}).items():
        entry = entries.get(key)
        if entry is None:
            continue
        _write_entry_preserve_state(entry, value)
