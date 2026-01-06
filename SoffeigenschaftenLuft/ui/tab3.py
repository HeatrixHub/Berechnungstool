import tkinter as tk
from tkinter import ttk

from ..core.heater_calculations import compute_heater_power
from .gui_utils import ToolTip, zeige_fehlermeldung

entries: dict[str, tk.Entry] = {}
use_tab1_power: tk.BooleanVar | None = None
_apply_thermal_power_fn = None


def _optional_float(entry: tk.Entry) -> float | None:
    raw = entry.get().strip()
    if not raw or raw == "Bitte eintragen!":
        return None
    try:
        return float(raw)
    except ValueError:
        zeige_fehlermeldung(entry)
        return None


def create_tab3(notebook, get_thermal_power_from_tab1):
    global entries, use_tab1_power, _apply_thermal_power_fn

    frame_tab3 = tk.Frame(notebook, padx=20, pady=10)
    notebook.add(frame_tab3, text="Heizer Leistung")

    entries = {}
    use_tab1_power = tk.BooleanVar()

    def calculate_power():
        if use_tab1_power.get():
            p_th = get_thermal_power_from_tab1()
            if p_th is not None:
                entries["Wärmeleistung (kW):"].config(state="normal")
                entries["Wärmeleistung (kW):"].delete(0, tk.END)
                entries["Wärmeleistung (kW):"].insert(0, f"{p_th:.2f}")
                entries["Wärmeleistung (kW):"].config(state="readonly")

        electrical_kw = _optional_float(entries["Elektrische Leistung (kW):"])
        thermal_kw = _optional_float(entries["Wärmeleistung (kW):"])

        efficiency_entry = entries["Effizienz (%):"]
        efficiency_raw = efficiency_entry.get().strip()
        if not efficiency_raw or efficiency_raw == "Bitte eintragen!":
            zeige_fehlermeldung(efficiency_entry)
            return
        try:
            efficiency_percent = float(efficiency_raw)
        except ValueError:
            zeige_fehlermeldung(efficiency_entry)
            return

        try:
            result = compute_heater_power(
                electrical_kw=electrical_kw,
                thermal_kw=thermal_kw,
                efficiency_percent=efficiency_percent,
            )
        except ValueError:
            return

        for key, value in result.items():
            label = "Elektrische Leistung (kW):" if key == "electrical_kw" else "Wärmeleistung (kW):"
            entries[label].config(state="normal")
            entries[label].delete(0, tk.END)
            entries[label].insert(0, f"{value:.2f}")
            if label == "Wärmeleistung (kW):" and use_tab1_power.get():
                entries[label].config(state="readonly")

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

    _apply_thermal_power_fn = apply_thermal_power

    fields = [
        ("Elektrische Leistung (kW):", ""),
        ("Wärmeleistung (kW):", ""),
        ("Effizienz (%):", "90"),
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
        command=apply_thermal_power,
    )
    power_check.grid(row=3, column=0, columnspan=2, pady=5, padx=(10, 0), sticky=tk.W)
    ToolTip(power_check, "Wenn aktiviert, wird die Wärmeleistung aus Tab1 übernommen und gesperrt.")

    return frame_tab3


def _write_entry_preserve_state(entry: tk.Entry, value: str | None) -> None:
    current_state = entry.cget("state")
    entry.config(state="normal")
    entry.delete(0, tk.END)
    entry.insert(0, "" if value is None else value)
    entry.config(state=current_state)


def export_state_tab3() -> dict[str, object]:
    return {
        "use_tab1_power": use_tab1_power.get() if use_tab1_power else False,
        "entries": {key: entry.get() for key, entry in entries.items()},
    }


def import_state_tab3(state: dict[str, object]) -> None:
    if use_tab1_power is None:
        return

    use_tab1_power.set(bool(state.get("use_tab1_power", False)))
    if _apply_thermal_power_fn:
        _apply_thermal_power_fn()

    for key, value in state.get("entries", {}).items():
        entry = entries.get(key)
        if entry is None:
            continue
        _write_entry_preserve_state(entry, value)
