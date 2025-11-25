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

        self.layer_rows: List[ttk.Entry] = []
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

        self.summary_text = tk.Text(self.summary_frame, height=5, wrap="word", relief="flat", borderwidth=0)
        self.summary_text.pack(fill="x", padx=6, pady=4)

        columns = ("layer", "plate", "L", "B", "H")
        self.tree = ttk.Treeview(self.summary_frame, columns=columns, show="headings", height=10)
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
        self.tree.pack(fill="both", expand=True, padx=6, pady=(0, 4))

    # ---------------------------------------------------------------
    # Schichtverwaltung
    # ---------------------------------------------------------------
    def add_layer_row(self, thickness: str | float = ""):
        row_idx = len(self.layer_rows) + 1
        ttk.Label(self.layer_table, text=str(row_idx), width=4).grid(
            row=row_idx, column=0, padx=4, pady=2, sticky="w"
        )
        entry = ttk.Entry(self.layer_table, width=10)
        entry.grid(row=row_idx, column=1, padx=4, pady=2, sticky="ew")
        if thickness != "":
            entry.insert(0, str(thickness))

        action_frame = ttk.Frame(self.layer_table)
        action_frame.grid(row=row_idx, column=2, padx=4, pady=2, sticky="e")
        ttk.Button(action_frame, text="▲", width=3, command=lambda: self.move_layer(row_idx - 1, -1)).grid(
            row=0, column=0, padx=1
        )
        ttk.Button(action_frame, text="▼", width=3, command=lambda: self.move_layer(row_idx - 1, 1)).grid(
            row=0, column=1, padx=1
        )
        ttk.Button(action_frame, text="✖", width=3, command=lambda: self.remove_layer(row_idx - 1)).grid(
            row=0, column=2, padx=1
        )

        self.layer_rows.append(entry)

    def move_layer(self, index: int, direction: int):
        target = index + direction
        if target < 0 or target >= len(self.layer_rows):
            return
        self.layer_rows[index], self.layer_rows[target] = self.layer_rows[target], self.layer_rows[index]
        self.refresh_layer_table()

    def remove_layer(self, index: int):
        if 0 <= index < len(self.layer_rows):
            self.layer_rows[index].destroy()
            del self.layer_rows[index]
            self.refresh_layer_table()

    def refresh_layer_table(self):
        # Alle Widgets entfernen
        for widget in self.layer_table.winfo_children():
            widget.destroy()

        ttk.Label(self.layer_table, text="#", width=4).grid(row=0, column=0, padx=4, sticky="w")
        ttk.Label(self.layer_table, text="Dicke [mm]").grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(self.layer_table, text="Aktionen").grid(row=0, column=2, padx=4, sticky="w")

        existing_values = [entry.get() for entry in self.layer_rows]
        self.layer_rows.clear()
        for val in existing_values:
            self.add_layer_row(val)

    # ---------------------------------------------------------------
    # Aktionen
    # ---------------------------------------------------------------
    def reset_fields(self):
        for entry in (self.entry_L, self.entry_B, self.entry_H):
            entry.delete(0, tk.END)
        self.measure_type.set("outer")
        for entry in self.layer_rows:
            entry.destroy()
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
            for entry in self.layer_rows:
                text = entry.get().strip()
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
        self.summary_text.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)

    def display_result(self, result: BuildResult):
        self.clear_results()
        summary_lines = [
            "Verwendete Außenmaße:",
            f"  Länge: {result.la_l:.3f} mm",  # Werte in mm belassen
            f"  Breite: {result.la_b:.3f} mm",
            f"  Höhe: {result.la_h:.3f} mm",
            "",
            "Resultierende Innenmaße:",
            f"  Länge: {result.li_l:.3f} mm",
            f"  Breite: {result.li_b:.3f} mm",
            f"  Höhe: {result.li_h:.3f} mm",
            "",
            f"Schichten: {len(result.layers)}",
        ]
        self.summary_text.insert("1.0", "\n".join(summary_lines))

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
        theme = sv_ttk.get_theme()
        if theme == "dark":
            bg_color = "#2D2D2D"
            fg_color = "white"
        else:
            bg_color = "#f9f9f9"
            fg_color = "black"

        self.summary_text.config(bg=bg_color, fg=fg_color, insertbackground=fg_color)

