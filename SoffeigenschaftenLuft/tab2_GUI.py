import tkinter as tk
from tkinter import ttk

from .gui_utils import ToolTip, set_entry_value
from .tab2_logik import berechne_tab2_werte

def create_tab2(notebook):
    frame_tab2 = tk.Frame(notebook, padx=20, pady=10)
    notebook.add(frame_tab2, text="Geschwindigkeitsberechnung & Reynolds-Zahl")

    entries = {}
    shape_var = tk.StringVar(value="Rund")
    flow_unit_var = tk.StringVar(value="m³/h")
    normkubik_var = tk.BooleanVar()

    # Formwahl
    shape_label = ttk.Label(frame_tab2, text="Querschnittsform:")
    shape_label.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
    ToolTip(shape_label, "Wählen Sie die Form des Querschnitts (rund oder rechteckig)")

    shape_dropdown = ttk.Combobox(frame_tab2, textvariable=shape_var, values=["Rund", "Rechteckig"], state="readonly", width=18)
    shape_dropdown.grid(row=0, column=1, columnspan=2, pady=10, padx=(10, 0), sticky=tk.W)
    ToolTip(shape_dropdown, "Auswahl der Querschnittsform (rund oder rechteckig)")

    # Felder Rund/Rechteckig
    label_diameter = ttk.Label(frame_tab2, text="Durchmesser (mm):")
    entry_diameter = ttk.Entry(frame_tab2)
    ToolTip(entry_diameter, "Innen- oder Hydraulikdurchmesser in mm")
    entries["Durchmesser (mm):"] = entry_diameter

    label_a = ttk.Label(frame_tab2, text="Seite a (mm):")
    entry_a = ttk.Entry(frame_tab2)
    ToolTip(entry_a, "Länge der Seite a bei rechteckigem Querschnitt")
    entries["Seite a (mm):"] = entry_a
    label_b = ttk.Label(frame_tab2, text="Seite b (mm):")
    entry_b = ttk.Entry(frame_tab2)
    ToolTip(entry_b, "Länge der Seite b bei rechteckigem Querschnitt")
    entries["Seite b (mm):"] = entry_b

    def update_fields(*args):
        if shape_var.get() == "Rund":
            label_diameter.grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
            entry_diameter.grid(row=1, column=1, padx=10, pady=5)
            label_a.grid_remove()
            entry_a.grid_remove()
            label_b.grid_remove()
            entry_b.grid_remove()
        else:
            label_diameter.grid_remove()
            entry_diameter.grid_remove()
            label_a.grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
            entry_a.grid(row=1, column=1, padx=10, pady=5)
            label_b.grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
            entry_b.grid(row=2, column=1, padx=10, pady=5)

    shape_var.trace_add("write", update_fields)
    update_fields()

    # Volumenstrom + Einheit
    ttk.Label(frame_tab2, text="Volumenstrom:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
    entry_flow = ttk.Entry(frame_tab2)
    entry_flow.grid(row=3, column=1, padx=10, pady=5)
    ToolTip(entry_flow, "Volumenstrom des Fluids")
    entries["Volumenstrom"] = entry_flow

    flow_unit_dropdown = ttk.Combobox(frame_tab2, textvariable=flow_unit_var, values=["m³/h", "m³/s"], state="readonly", width=5)
    flow_unit_dropdown.grid(row=3, column=2, padx=10, pady=5)
    ToolTip(flow_unit_dropdown, "Einheit des Volumenstroms (m³/h oder m³/s)")

    # Temperatur & Dichte
    for i, label in enumerate(["Temperatur (°C):", "Dichte (kg/m³):"]):
        ttk.Label(frame_tab2, text=label).grid(row=4 + i, column=0, sticky=tk.W, padx=10, pady=5)
        entry = ttk.Entry(frame_tab2)
        entry.grid(row=4 + i, column=1, padx=10, pady=5)
        ToolTip(entry, f"{label} des strömenden Mediums")
        entries[label] = entry

    # Ergebnisfelder
    ttk.Label(frame_tab2, text="Strömungsgeschwindigkeit (m/s):").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
    entry_velocity = ttk.Entry(frame_tab2, state="readonly")
    entry_velocity.grid(row=6, column=1, padx=10, pady=5)
    ToolTip(entry_velocity, "Geschwindigkeit des Fluids am Inlet")

    ttk.Label(frame_tab2, text="Reynolds-Zahl:").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
    entry_reynolds = ttk.Entry(frame_tab2, state="readonly")
    entry_reynolds.grid(row=7, column=1, padx=10, pady=5)
    ToolTip(entry_reynolds, "Reynolds-Zahl des Fluids am Inlet")

    ttk.Label(frame_tab2, text="Strömungsart:").grid(row=7, column=2, sticky=tk.W, padx=10, pady=5)
    entry_flowtype = ttk.Entry(frame_tab2, state="readonly")
    entry_flowtype.grid(row=7, column=3, padx=10, pady=5)
    ToolTip(entry_flowtype, "Strömungsart des Fluids am Inlet (Laminar <2300, Übergang >2300 <11000, Turbulent >11000)")

    # Checkbox für Normbedingungen
    def toggle_norm():
        if normkubik_var.get():
            entries["Temperatur (°C):"].config(state="normal")
            entries["Temperatur (°C):"].delete(0, tk.END)
            entries["Temperatur (°C):"].insert(0, "20")
            entries["Temperatur (°C):"].config(state="readonly")
            entries["Dichte (kg/m³):"].config(state="normal")
            entries["Dichte (kg/m³):"].delete(0, tk.END)
            entries["Dichte (kg/m³):"].insert(0, "1.20412")
            entries["Dichte (kg/m³):"].config(state="readonly")
        else:
            entries["Temperatur (°C):"].config(state="normal")
            entries["Dichte (kg/m³):"].config(state="normal")

    norm_check = ttk.Checkbutton(
        frame_tab2,
        text="Heatrix Normalbedingungen",
        variable=normkubik_var,
        command=toggle_norm
    )
    norm_check.grid(row=8, column=0, columnspan=2, sticky=tk.W, padx=10, pady=10)
    ToolTip(norm_check, "Setzt Temperatur auf 20°C und Dichte auf 1.20412 kg/m³")

    # Berechnen Button
    def calculate():
        result = berechne_tab2_werte(entries, shape_var, flow_unit_var)
        if result is None:
            return
        set_entry_value(entry_velocity, result["velocity"], readonly=True)
        if result["reynolds"] is not None:
            set_entry_value(entry_reynolds, result["reynolds"], readonly=True)
            entry_flowtype.config(state="normal")
            entry_flowtype.delete(0, tk.END)
            entry_flowtype.insert(0, result["flow_type"])
            entry_flowtype.config(state="readonly")

    calculate_btn = ttk.Button(frame_tab2, text="Berechnen", command=calculate)
    calculate_btn.grid(row=10, column=1, columnspan=2, pady=15)
    ToolTip(calculate_btn, "Startet die Berechnung der Geschwindigkeit und Reynolds-Zahl")

    return frame_tab2