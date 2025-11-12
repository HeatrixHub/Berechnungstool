import tkinter as tk
from tkinter import ttk
from gui_utils import check_float, zeige_fehlermeldung, set_entry_value
from gui_utils import ToolTip
from tab1_logik import (
    starte_berechnung,
    toggle_normbedingungen,
    toggle_normkubikmenge
)

entries = {}  # Globales Dictionary für Zugriff außerhalb
entries_global = entries

labels = {}  # Für dynamisch beschriftbare Labels

combo_var = None
normkubik_var = None
heatrix_normal_var = None
normkubikmenge_var = None

def get_entries():
    return entries_global

def create_tab1(notebook):
    global combo_var, normkubik_var, heatrix_normal_var, normkubikmenge_var

    frame_tab1 = tk.Frame(notebook, padx=20, pady=10)
    notebook.add(frame_tab1, text="Zustandsgrößen")

    combo_var = tk.StringVar(value="Isobar")
    combo_box = ttk.Combobox(frame_tab1, textvariable=combo_var, values=["Isobar", "Isochor"], state="readonly", width=18)
    combo_box.grid(row=0, column=1, columnspan=2, pady=10, padx=(10, 0), sticky=tk.W)
    ToolTip(combo_box, "Wähle die Art der Zustandsänderung: isobar (konstanter Druck) oder isochor (konstantes Volumen).")

    def update_cp_labels(*args):
        if combo_var.get() == "Isochor":
            labels["Spezifische Wärmekapazität Cp 1 (J/kg*K):"].config(text="Spezifische Wärmekapazität Cv 1 (J/kg*K):")
            labels["Spezifische Wärmekapazität Cp 2 (J/kg*K):"].config(text="Spezifische Wärmekapazität Cv 2 (J/kg*K):")
        else:
            labels["Spezifische Wärmekapazität Cp 1 (J/kg*K):"].config(text="Spezifische Wärmekapazität Cp 1 (J/kg*K):")
            labels["Spezifische Wärmekapazität Cp 2 (J/kg*K):"].config(text="Spezifische Wärmekapazität Cp 2 (J/kg*K):")

    combo_var.trace_add("write", update_cp_labels)

    normkubik_var = tk.BooleanVar()
    heatrix_normal_var = tk.BooleanVar()
    normkubikmenge_var = tk.BooleanVar()

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
                entries["Volumenstrom 1 (m³/h):"].delete(0, 'end')
                entries["Volumenstrom 1 (m³/h):"].config(state="readonly")

        toggle_normkubikmenge(entries, normkubikmenge_var.get(), normkubik_var.get(), heatrix_normal_var.get())

    din_check = ttk.Checkbutton(
        frame_tab1,
        text="Normbedingungen DIN 1343",
        variable=normkubik_var,
        command=handle_toggle_din
    )
    din_check.grid(row=1, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(din_check, "Setzt Temperatur, Druck und Dichte auf DIN 1343 Normwerte (0°C, 101325 Pa, 1.29228 kg/m³).")

    heatrix_check = ttk.Checkbutton(
        frame_tab1,
        text="Heatrix Normalbedingungen",
        variable=heatrix_normal_var,
        command=handle_toggle_heatrix
    )
    heatrix_check.grid(row=2, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(heatrix_check, "Setzt Temperatur, Druck und Dichte auf Heatrix-Normalwerte (20°C, 101325 Pa, 1.20412 kg/m³).")

    norm_check = ttk.Checkbutton(
        frame_tab1,
        text="Normkubikmeter verwenden",
        variable=normkubikmenge_var,
        command=handle_toggle_normkubikmenge
    )
    norm_check.grid(row=1, column=2, columnspan=1, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(norm_check, "Aktiviert die Umrechnung von Normkubikmetern in tatsächlichen Volumenstrom.")

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
        ("Wärmeleistung (kW):", "", 12, 0)
    ]

    for text, default, row, col in fields:
        label = ttk.Label(frame_tab1, text=text)
        label.grid(row=row, column=col, padx=10, pady=5, sticky="w")
        labels[text] = label

        entry = ttk.Entry(frame_tab1)
        entry.insert(0, default)

        if text == "Normkubikmeter (m³/h):":
            entry.config(state="disabled")

        if text in ["Druck 2 (Pa):", "Dichte 2 (kg/m³):", "Volumenstrom 2 (m³/h):",
                    "Dynamische Viskosität 1 (Pa·s):", "Dynamische Viskosität 2 (Pa·s):",
                    "Schallgeschwindigkeit 1 (m/s):", "Schallgeschwindigkeit 2 (m/s):",
                    "Spezifische Wärmekapazität Cp1 (J/kg*K):", "Spezifische Wärmekapazität Cp2 (J/kg*K):",
                    "Massenstrom 1 (kg/s):", "Massenstrom 2 (kg/s):"]:
            entry.config(state="readonly")

        entry.grid(row=row, column=col + 1, padx=10, pady=5)
        entries[text] = entry

        if "Temperatur" in text:
            ToolTip(entry, "Temperatur in Grad Celsius eingeben.")
        elif "Volumenstrom" in text:
            ToolTip(entry, "Volumenstrom in m³/h eingeben. Wird automatisch berechnet, wenn Normkubikmeter aktiv ist.")
        elif "Druck" in text:
            ToolTip(entry, "Druck in Pascal (Pa) eingeben oder automatisch berechnen lassen.")
        elif "Dichte" in text:
            ToolTip(entry, "Dichte der Luft in kg/m³. Wird automatisch berechnet, wenn genügend Daten vorhanden sind.")
        elif "Wärmeleistung" in text:
            ToolTip(entry, "Gib eine bekannte Wärmeleistung ein oder lasse sie aus Temperaturdaten berechnen.")

    calculate_button = ttk.Button(
        frame_tab1,
        text="Berechnen",
        command=lambda: starte_berechnung(entries, combo_var, normkubik_var, heatrix_normal_var, normkubikmenge_var)
    )
    calculate_button.grid(row=13, column=0, columnspan=4, pady=15)
    ToolTip(calculate_button, "Startet die Berechnung basierend auf den eingegebenen Werten.")

    if not normkubik_var.get() and not heatrix_normal_var.get() and not normkubikmenge_var.get():
        for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
            entries[key].config(state="normal")

    def update_normkubik_label():
        if normkubik_var.get():
            labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (Nm³/h):")
        elif heatrix_normal_var.get():
            labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (HNm³/h):")
        else:
            labels["Normkubikmeter (m³/h):"].config(text="Normkubikmeter (m³/h):")

    return frame_tab1