import tkinter as tk
from tkinter import ttk
from tab3_logik import berechne_heizerleistung
from gui_utils import ToolTip

def create_tab3(notebook, get_thermal_power_from_tab1):
    frame_tab3 = tk.Frame(notebook, padx=20, pady=10)
    notebook.add(frame_tab3, text="Heizer Leistung")

    entries = {}
    use_tab1_power = tk.BooleanVar()

    def calculate_power():
        if use_tab1_power.get():
            # Wenn Leistung übernommen wurde, zwingen wir p_th aus Tab1 zu übernehmen
            p_th = get_thermal_power_from_tab1()
            if p_th is not None:
                entries["Wärmeleistung (kW):"].config(state="normal")
                entries["Wärmeleistung (kW):"].delete(0, tk.END)
                entries["Wärmeleistung (kW):"].insert(0, f"{p_th:.2f}")
                entries["Wärmeleistung (kW):"].config(state="readonly")
        result = berechne_heizerleistung(entries)
        if not result:
            return
        for key, value in result.items():
            entries[key].config(state="normal")
            entries[key].delete(0, tk.END)
            entries[key].insert(0, f"{value:.2f}")
            if key == "Wärmeleistung (kW):" and use_tab1_power.get():
                entries[key].config(state="readonly")

    def apply_thermal_power():
        if use_tab1_power.get():
            p_th = get_thermal_power_from_tab1()
            if p_th is not None:
                entries["Wärmeleistung (kW):"].config(state="normal")
                entries["Wärmeleistung (kW):"].delete(0, tk.END)
                entries["Wärmeleistung (kW):"].insert(0, f"{p_th:.2f}")
                entries["Wärmeleistung (kW):"].config(state="readonly")
        else:
            entries["Wärmeleistung (kW):"].config(state="normal")

    fields = [
        ("Elektrische Leistung (kW):", ""),
        ("Wärmeleistung (kW):", ""),
        ("Effizienz (%):", "90")
    ]

    for i, (label_text, default_value) in enumerate(fields):
        label = ttk.Label(frame_tab3, text=label_text)
        label.grid(row=i, column=0, padx=10, pady=5, sticky="w")

        entry = ttk.Entry(frame_tab3)
        entry.insert(0, default_value)
        entry.grid(row=i, column=1, padx=10, pady=5)

        entries[label_text] = entry

        # ToolTips hinzufügen
        if label_text == "Elektrische Leistung (kW):":
            ToolTip(entry, "Wird automatisch berechnet, wenn Wärmeleistung und Effizienz gegeben sind.")
        elif label_text == "Wärmeleistung (kW):":
            ToolTip(entry, "Kann manuell eingegeben oder aus Tab1 übernommen werden.")
        elif label_text == "Effizienz (%):":
            ToolTip(entry, "Effizienz des Heizers in Prozent. Wird zur Umrechnung verwendet.")

    def on_effizienz_change(*args):
        if use_tab1_power.get():
            calculate_power()

    entries["Effizienz (%):"].bind("<KeyRelease>", lambda event: on_effizienz_change())

    calculate_button = ttk.Button(frame_tab3, text="Berechnen", command=calculate_power)
    calculate_button.grid(row=4, column=1, columnspan=4, pady=15, padx=(45, 0), sticky=tk.W)
    ToolTip(calculate_button, "Berechnet elektrische oder thermische Leistung basierend auf Eingaben.")

    power_check = ttk.Checkbutton(
        frame_tab3,
        text="Leistung übernehmen",
        variable=use_tab1_power,
        command=apply_thermal_power
    )
    power_check.grid(row=3, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(power_check, "Wenn aktiviert, wird die Wärmeleistung aus Tab1 übernommen und gesperrt.")

    return frame_tab3