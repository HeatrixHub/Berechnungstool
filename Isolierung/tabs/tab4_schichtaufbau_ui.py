# tabs/tab4_schichtaufbau_ui.py
"""UI-Tab zur Berechnung des Schichtaufbaus der Isolierung."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List

import sv_ttk

from .scrollable import ScrollableFrame
from .tab4_schichtaufbau_logic import BuildResult, compute_plate_dimensions


class SchichtaufbauTab:
    def __init__(self, notebook):
        container = ttk.Frame(notebook)
        notebook.add(container, text="Schichtaufbau")

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)
        self.frame = self.scrollable.inner

        self.layer_rows: List[dict] = []
        self.build_ui()
        self.update_theme_colors()

    # ---------------------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.columnconfigure(1, weight=1)
        ttk.Label(self.frame, text="Schichtaufbau berechnen", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4)
        )

        # Eingabe: Maßart
        measure_frame = ttk.LabelFrame(self.frame, text="Maßvorgabe")
        measure_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.measure_type = tk.StringVar(value="outer")
        ttk.Radiobutton(measure_frame, text="Außenmaße gegeben", variable=self.measure_type, value="outer").grid(
            row=0, column=0, padx=6, pady=4, sticky="w"
        )
        ttk.Radiobutton(measure_frame, text="Innenmaße gegeben", variable=self.measure_type, value="inner").grid(
            row=0, column=1, padx=6, pady=4, sticky="w"
        )

        # Eingabe: Abmessungen
        dims_frame = ttk.LabelFrame(self.frame, text="Abmessungen")
        dims_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        for i in range(3):
            dims_frame.columnconfigure(i * 2 + 1, weight=1)

        ttk.Label(dims_frame, text="Länge [mm]:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.entry_L = ttk.Entry(dims_frame)
        self.entry_L.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(dims_frame, text="Breite [mm]:").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        self.entry_B = ttk.Entry(dims_frame)
        self.entry_B.grid(row=0, column=3, sticky="ew", padx=6, pady=4)

        ttk.Label(dims_frame, text="Höhe [mm]:").grid(row=0, column=4, sticky="w", padx=6, pady=4)
        self.entry_H = ttk.Entry(dims_frame)
        self.entry_H.grid(row=0, column=5, sticky="ew", padx=6, pady=4)

        # Schichtdicken
        layer_frame = ttk.LabelFrame(self.frame, text="Schichtdicken [mm]")
        layer_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ttk.Button(layer_frame, text="+ Schicht", command=self.add_layer_row).grid(
            row=0, column=0, padx=6, pady=4, sticky="w"
        )
        self.layer_table = ttk.Frame(layer_frame)
        self.layer_table.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        self.layer_table.columnconfigure(1, weight=1)

        ttk.Label(self.layer_table, text="#", width=4).grid(row=0, column=0, padx=4, sticky="w")
        ttk.Label(self.layer_table, text="Dicke [mm]").grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(self.layer_table, text="Aktionen").grid(row=0, column=2, padx=4, sticky="w")

        self.add_layer_row()

        # Buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=8, padx=10, sticky="ew")
        ttk.Button(btn_frame, text="Berechnen", command=self.calculate).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Felder leeren", command=self.reset_fields).pack(side=tk.LEFT, padx=4)

        # Ergebnisse
        self.summary_frame = ttk.LabelFrame(self.frame, text="Ergebnis")
        self.summary_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=10, pady=(4, 10))
        self.frame.rowconfigure(5, weight=1)
        self.summary_frame.columnconfigure(0, weight=1)
        self.summary_frame.rowconfigure(1, weight=1)

        # Ergebnisübersicht ohne Scrollen
        overview_frame = ttk.Frame(self.summary_frame)
        overview_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        overview_frame.columnconfigure(0, weight=1)
        overview_frame.columnconfigure(1, weight=1)
        overview_frame.columnconfigure(2, weight=1)

        self.given_section = ttk.LabelFrame(overview_frame, text="Gegebene Maße")
        self.given_section.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.calculated_section = ttk.LabelFrame(overview_frame, text="Berechnete Maße")
        self.calculated_section.grid(row=0, column=1, sticky="nsew", padx=6)

        for section in (self.given_section, self.calculated_section):
            section.columnconfigure(1, weight=1)

        self.layer_info = ttk.LabelFrame(overview_frame, text="Schichten")
        self.layer_info.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.layer_info.columnconfigure(0, weight=1)

        self.given_vars = {
            "L": tk.StringVar(value="–"),
            "B": tk.StringVar(value="–"),
            "H": tk.StringVar(value="–"),
        }
        self.calculated_vars = {
            "L": tk.StringVar(value="–"),
            "B": tk.StringVar(value="–"),
            "H": tk.StringVar(value="–"),
        }
        self.layer_count_var = tk.StringVar(value="–")

        self._build_dimension_rows(self.given_section, self.given_vars)
        self._build_dimension_rows(self.calculated_section, self.calculated_vars)
        ttk.Label(self.layer_info, textvariable=self.layer_count_var, anchor="center").grid(
            row=0, column=0, padx=8, pady=8, sticky="ew"
        )

        columns = ("layer", "plate", "L", "B", "H")
        tree_frame = ttk.Frame(self.summary_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        self.tree.heading("layer", text="Schicht")
        self.tree.heading("plate", text="Platte")
        self.tree.heading("L", text="L [mm]")
        self.tree.heading("B", text="B [mm]")
        self.tree.heading("H", text="H [mm]")
        self.tree.column("layer", width=70, anchor="center")
        self.tree.column("plate", width=90, anchor="w")
        self.tree.column("L", width=90, anchor="center")
        self.tree.column("B", width=90, anchor="center")
        self.tree.column("H", width=90, anchor="center")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns", padx=(4, 0))

    # ---------------------------------------------------------------
    # Schichtverwaltung
    # ---------------------------------------------------------------
    def add_layer_row(self, thickness: str | float = ""):
        row_index = len(self.layer_rows)
        grid_row = row_index + 1

        number_label = ttk.Label(self.layer_table, text=str(grid_row), width=4)
        number_label.grid(row=grid_row, column=0, padx=4, pady=2, sticky="w")

        entry = ttk.Entry(self.layer_table, width=10)
        entry.grid(row=grid_row, column=1, padx=4, pady=2, sticky="ew")
        if thickness != "":
            entry.insert(0, str(thickness))

        action_frame = ttk.Frame(self.layer_table)
        action_frame.grid(row=grid_row, column=2, padx=4, pady=2, sticky="e")
        btn_up = ttk.Button(action_frame, text="▲", width=3)
        btn_up.grid(row=0, column=0, padx=1)
        btn_down = ttk.Button(action_frame, text="▼", width=3)
        btn_down.grid(row=0, column=1, padx=1)
        btn_delete = ttk.Button(action_frame, text="✖", width=3)
        btn_delete.grid(row=0, column=2, padx=1)

        self.layer_rows.append(
            {
                "number": number_label,
                "entry": entry,
                "action_frame": action_frame,
                "btn_up": btn_up,
                "btn_down": btn_down,
                "btn_delete": btn_delete,
            }
        )
        self._refresh_layer_rows_layout()

    def move_layer(self, index: int, direction: int):
        target = index + direction
        if target < 0 or target >= len(self.layer_rows):
            return
        self.layer_rows[index], self.layer_rows[target] = (
            self.layer_rows[target],
            self.layer_rows[index],
        )
        self._refresh_layer_rows_layout()

    def remove_layer(self, index: int):
        if index < 0 or index >= len(self.layer_rows):
            return

        row = self.layer_rows.pop(index)
        row["number"].destroy()
        row["entry"].destroy()
        row["action_frame"].destroy()

        if not self.layer_rows:
            self.add_layer_row()
        else:
            self._refresh_layer_rows_layout()

    def _refresh_layer_rows_layout(self):
        for i, row in enumerate(self.layer_rows):
            grid_row = i + 1
            row["number"].grid_configure(row=grid_row)
            row["entry"].grid_configure(row=grid_row)
            row["action_frame"].grid_configure(row=grid_row)
            row["number"].configure(text=str(grid_row))

            row["btn_up"].state(["!disabled"] if i > 0 else ["disabled"])
            row["btn_down"].state(["!disabled"] if i < len(self.layer_rows) - 1 else ["disabled"])
            row["btn_up"].configure(command=lambda idx=i: self.move_layer(idx, -1))
            row["btn_down"].configure(command=lambda idx=i: self.move_layer(idx, 1))
            row["btn_delete"].configure(command=lambda idx=i: self.remove_layer(idx))

        self.layer_table.update_idletasks()

    def _build_dimension_rows(self, parent: ttk.Widget, variables: dict[str, tk.StringVar]):
        labels = [("Länge [mm]:", "L"), ("Breite [mm]:", "B"), ("Höhe [mm]:", "H")]
        for row_index, (label, key) in enumerate(labels):
            ttk.Label(parent, text=label).grid(row=row_index, column=0, padx=6, pady=3, sticky="w")
            ttk.Label(parent, textvariable=variables[key]).grid(
                row=row_index, column=1, padx=6, pady=3, sticky="e"
            )

    # ---------------------------------------------------------------
    # Aktionen
    # ---------------------------------------------------------------
    def reset_fields(self):
        for entry in (self.entry_L, self.entry_B, self.entry_H):
            entry.delete(0, tk.END)
        self.measure_type.set("outer")
        for row in self.layer_rows:
            row["number"].destroy()
            row["entry"].destroy()
            row["action_frame"].destroy()
        self.layer_rows.clear()
        self.add_layer_row()
        self.clear_results()

    def calculate(self):
        try:
            dims_type = self.measure_type.get()
            L = float(self.entry_L.get())
            B = float(self.entry_B.get())
            H = float(self.entry_H.get())

            thicknesses: List[float] = []
            for row in self.layer_rows:
                text = row["entry"].get().strip()
                if text == "":
                    continue
                thicknesses.append(float(text))

            if not thicknesses:
                raise ValueError("Bitte mindestens eine Schichtdicke angeben.")

            result = compute_plate_dimensions(thicknesses, dims_type, L, B, H)
            self.display_result(result)
        except ValueError as exc:
            messagebox.showerror("Eingabefehler", str(exc))
        except Exception as exc:  # pragma: no cover - GUI Fehlerdialog
            import traceback

            traceback.print_exc()
            messagebox.showerror("Fehler", f"Berechnung fehlgeschlagen: {exc}")

    def clear_results(self):
        for var in (*self.given_vars.values(), *self.calculated_vars.values()):
            var.set("–")
        self.layer_count_var.set("–")
        for item in self.tree.get_children():
            self.tree.delete(item)

    def display_result(self, result: BuildResult):
        self.clear_results()
        dims_type = self.measure_type.get()
        if dims_type == "outer":
            self.given_section.configure(text="Gegebene Außenmaße")
            self.calculated_section.configure(text="Berechnete Innenmaße")
            values_given = (result.la_l, result.la_b, result.la_h)
            values_calc = (result.li_l, result.li_b, result.li_h)
        else:
            self.given_section.configure(text="Gegebene Innenmaße")
            self.calculated_section.configure(text="Berechnete Außenmaße")
            values_given = (result.li_l, result.li_b, result.li_h)
            values_calc = (result.la_l, result.la_b, result.la_h)

        for var, value in zip(self.given_vars.values(), values_given):
            var.set(f"{value:.3f} mm")
        for var, value in zip(self.calculated_vars.values(), values_calc):
            var.set(f"{value:.3f} mm")
        self.layer_count_var.set(str(len(result.layers)))

        for layer in result.layers:
            for plate in layer.plates:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        f"{layer.layer_index}",
                        plate.name,
                        f"{plate.L:.3f}",
                        f"{plate.B:.3f}",
                        f"{plate.H:.3f}",
                    ),
                )

    # ---------------------------------------------------------------
    # Theme
    # ---------------------------------------------------------------
    def update_theme_colors(self):
        if not sv_ttk:
            return
        theme = sv_ttk.get_theme()
        fg_color = "white" if theme == "dark" else "black"

        style = ttk.Style()
        style.configure("ResultValue.TLabel", foreground=fg_color)

        for section in (self.given_section, self.calculated_section, self.layer_info):
            for child in section.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(style="ResultValue.TLabel")

