# tabs/tab1_berechnung_ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import sv_ttk
from typing import Any, Callable, Dict, List, Tuple

from .tab1_berechnung_logic import (
    validate_inputs,
    perform_calculation,
    save_current_project,
    get_k_values_for_layers,
)
from app.global_tabs.isolierungen_db import logic as insulation_logic
from .scrollable import ScrollableFrame


class BerechnungTab:
    def __init__(self, notebook):
        container = ttk.Frame(notebook)
        notebook.add(container, text="Berechnung")

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)

        self.frame = self.scrollable.inner
        self.build_ui()
        self.last_result: Dict[str, Any] | None = None
        self.layer_importer: Callable[[], Tuple[List[float], List[str]]] | None = None
        insulation_logic.register_material_change_listener(
            self._refresh_material_choices
        )

    # ---------------------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.columnconfigure(1, weight=1)

        # Projektname
        ttk.Label(self.frame, text="Projektname:").grid(row=0, column=0, sticky='w', padx=6, pady=4)
        self.entry_project_name = ttk.Entry(self.frame)
        self.entry_project_name.grid(row=0, column=1, sticky='ew', padx=6, pady=4)

        # Container für Schichttabelle
        self.layers_frame = ttk.LabelFrame(self.frame, text="Schichten")
        self.layers_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=6, pady=4)
        self._build_layers_table()

        # Randbedingungen
        rand_frame = ttk.LabelFrame(self.frame, text="Randbedingungen")
        rand_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(rand_frame, text="T_links [°C]:").grid(row=0, column=0, sticky='w', padx=6, pady=4)
        self.entry_T_left = ttk.Entry(rand_frame)
        self.entry_T_left.grid(row=0, column=1, sticky='ew', padx=6, pady=4)

        ttk.Label(rand_frame, text="T_∞ [°C]:").grid(row=1, column=0, sticky='w', padx=6, pady=4)
        self.entry_T_inf = ttk.Entry(rand_frame)
        self.entry_T_inf.grid(row=1, column=1, sticky='ew', padx=6, pady=4)

        ttk.Label(rand_frame, text="h [W/m²K]:").grid(row=2, column=0, sticky='w', padx=6, pady=4)
        self.entry_h = ttk.Entry(rand_frame)
        self.entry_h.grid(row=2, column=1, sticky='ew', padx=6, pady=4)

        # Buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky='ew')
        ttk.Button(btn_frame, text="Berechnen", command=self.calculate).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Projekt speichern", command=self.save_project).pack(side=tk.LEFT, padx=3)

        # Ergebnisse
        self.output_frame = ttk.LabelFrame(self.frame, text="Ergebnisse")
        self.output_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky='nsew', padx=6)
        self.output_text = tk.Text(self.output_frame, height=8, wrap='word', relief='flat')
        self.output_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Plotbereich
        self.plot_frame = ttk.LabelFrame(self.frame, text="Temperaturverlauf")
        self.plot_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky='nsew', padx=6)

        self.update_theme_colors()

    def _build_layers_table(self):
        control_frame = ttk.Frame(self.layers_frame)
        control_frame.grid(row=0, column=0, sticky='ew', padx=6, pady=(4, 2))
        control_frame.columnconfigure(0, weight=1)

        ttk.Label(control_frame, text="Schichten verwalten:").grid(row=0, column=0, sticky="w")
        ttk.Button(control_frame, text="+ Schicht hinzufügen", command=self.add_layer_row).grid(row=0, column=1, padx=4)
        ttk.Button(control_frame, text="Übernehmen", command=self._import_layers_from_other).grid(row=0, column=2, padx=4)

        self.layers_table = ttk.Frame(self.layers_frame)
        self.layers_table.grid(row=1, column=0, sticky='ew', padx=6)
        for col, weight in enumerate((0, 0, 1, 0)):
            self.layers_table.columnconfigure(col, weight=weight)

        ttk.Label(self.layers_table, text="#", width=4).grid(row=0, column=0, padx=4, sticky="w")
        ttk.Label(self.layers_table, text="Dicke [mm]").grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(self.layers_table, text="Material").grid(row=0, column=2, padx=4, sticky="w")
        ttk.Label(self.layers_table, text="Aktionen").grid(row=0, column=3, padx=4, sticky="w")

        self.layer_rows: List[dict] = []
        self.add_layer_row()

    def _get_insulation_names(self) -> List[str]:
        from app.global_tabs.isolierungen_db.logic import get_all_insulations

        return [i["name"] for i in get_all_insulations()]

    def _refresh_material_choices(self) -> None:
        """Aktualisiert alle Dropdowns, sobald neue Materialien verfügbar sind."""

        options = self._get_insulation_names()
        for row in self.layer_rows:
            combo = row["combo"]
            current_value = combo.get()
            combo.configure(values=options)
            if current_value and current_value not in options:
                combo.set("")

    def _clear_layers(self):
        for row in self.layer_rows:
            row["number"].destroy()
            row["entry"].destroy()
            row["combo"].destroy()
            row["action_frame"].destroy()
        self.layer_rows.clear()

    # ---------------------------------------------------------------
    # Projekt laden
    # ---------------------------------------------------------------
    def load_project_into_ui(self, project):
        """
        Lädt ein Projekt aus Tab 2 in die Eingabefelder dieses Tabs.
        Unterstützt die neue dynamische Struktur mit Isolierungen & Dicken.
        """
        try:
            def val(obj, name, default=None):
                if hasattr(obj, name):
                    return getattr(obj, name)
                if isinstance(obj, dict):
                    return obj.get(name, default)
                return default

            name = val(project, "name", "")
            thicknesses = val(project, "thicknesses", [])
            isolierungen = val(project, "ks", [])  # Fallback falls altes Format
            if isinstance(isolierungen, list) and len(isolierungen) > 0 and isinstance(isolierungen[0], (float, int)):
                # Alte Projekte mit reinen k-Werten -> Dummy-Namen
                isolierungen = ["" for _ in thicknesses]
            else:
                isolierungen = val(project, "isolierungen", isolierungen)

            T_left = val(project, "T_left", 0.0)
            T_inf = val(project, "T_inf", 0.0)
            h = val(project, "h", 0.0)
            result = val(project, "result", None)

            # Eingabefelder setzen
            self.entry_project_name.delete(0, "end")
            self.entry_project_name.insert(0, name)

            self._clear_layers()
            for i, thickness in enumerate(thicknesses):
                material = isolierungen[i] if i < len(isolierungen) else ""
                self.add_layer_row(thickness, material)

            if not self.layer_rows:
                self.add_layer_row()

            self.entry_T_left.delete(0, tk.END)
            self.entry_T_left.insert(0, str(T_left))
            self.entry_T_inf.delete(0, tk.END)
            self.entry_T_inf.insert(0, str(T_inf))
            self.entry_h.delete(0, tk.END)
            self.entry_h.insert(0, str(h))

            # Falls Ergebnis vorhanden, anzeigen
            if result:
                self.display_result(result)
                temps = result.get("interface_temperatures", [])
                if temps and thicknesses:
                    self.plot_temperature_profile(thicknesses, temps)
                self.last_result = result
            else:
                self.last_result = None

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Fehler beim Laden", str(e))

    def register_layer_importer(self, importer: Callable[[], Tuple[List[float], List[str]]]):
        """Ermöglicht das Übernehmen der Schichten aus einem anderen Tab."""

        self.layer_importer = importer

    def _import_layers_from_other(self):
        if self.layer_importer is None:
            messagebox.showwarning("Keine Quelle", "Kein Tab zum Übernehmen verbunden.")
            return
        try:
            thicknesses, isolierungen = self.layer_importer()
            self.apply_layers(thicknesses, isolierungen)
        except Exception as exc:  # pragma: no cover - GUI Fehlermeldung
            messagebox.showerror("Übernehmen fehlgeschlagen", str(exc))

    # ---------------------------------------------------------------
    # Schichtverwaltung
    # ---------------------------------------------------------------
    def add_layer_row(self, thickness: str | float = "", material: str = ""):
        row_index = len(self.layer_rows)
        grid_row = row_index + 1

        number_label = ttk.Label(self.layers_table, text=f"{row_index + 1}", width=4)
        number_label.grid(row=grid_row, column=0, padx=4, pady=2, sticky="w")

        entry_d = ttk.Entry(self.layers_table, width=10)
        entry_d.grid(row=grid_row, column=1, padx=4, pady=2, sticky="ew")
        if thickness != "":
            entry_d.insert(0, str(thickness))

        combo_iso = ttk.Combobox(self.layers_table, values=self._get_insulation_names(), state="readonly")
        combo_iso.grid(row=grid_row, column=2, padx=4, pady=2, sticky="ew")
        combo_iso.set(material)

        action_frame = ttk.Frame(self.layers_table)
        action_frame.grid(row=grid_row, column=3, padx=4, pady=2, sticky="e")
        btn_up = ttk.Button(action_frame, text="▲", width=3, command=lambda: self.move_layer(row_index, -1))
        btn_up.grid(row=0, column=0, padx=1)
        btn_down = ttk.Button(action_frame, text="▼", width=3, command=lambda: self.move_layer(row_index, 1))
        btn_down.grid(row=0, column=1, padx=1)
        btn_delete = ttk.Button(action_frame, text="✕", width=3, command=lambda: self.delete_layer(row_index))
        btn_delete.grid(row=0, column=2, padx=1)

        self.layer_rows.append({
            "number": number_label,
            "entry": entry_d,
            "combo": combo_iso,
            "action_frame": action_frame,
            "btn_up": btn_up,
            "btn_down": btn_down,
            "btn_delete": btn_delete,
        })
        self._refresh_layer_rows_layout()

    def delete_layer(self, index: int):
        if index < 0 or index >= len(self.layer_rows):
            return
        if len(self.layer_rows) <= 1:
            messagebox.showwarning("Aktion nicht möglich", "Mindestens eine Schicht wird benötigt.")
            return
        row = self.layer_rows.pop(index)
        row["number"].destroy()
        row["entry"].destroy()
        row["combo"].destroy()
        row["action_frame"].destroy()
        self._refresh_layer_rows_layout()

    def move_layer(self, index: int, direction: int):
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.layer_rows):
            return
        self.layer_rows[index], self.layer_rows[new_index] = self.layer_rows[new_index], self.layer_rows[index]
        self._refresh_layer_rows_layout()

    def _refresh_layer_rows_layout(self):
        for i, row in enumerate(self.layer_rows):
            grid_row = i + 1
            row["number"].grid_configure(row=grid_row)
            row["entry"].grid_configure(row=grid_row)
            row["combo"].grid_configure(row=grid_row)
            row["action_frame"].grid_configure(row=grid_row)
            row["number"].configure(text=f"{i + 1}")

            row["btn_up"].state(["!disabled"] if i > 0 else ["disabled"])
            row["btn_down"].state(["!disabled"] if i < len(self.layer_rows) - 1 else ["disabled"])
            row["btn_up"].configure(command=lambda idx=i: self.move_layer(idx, -1))
            row["btn_down"].configure(command=lambda idx=i: self.move_layer(idx, 1))
            row["btn_delete"].configure(command=lambda idx=i: self.delete_layer(idx))
        self.layers_table.update_idletasks()

    def apply_layers(self, thicknesses: List[float], isolierungen: List[str] | None = None):
        self._clear_layers()
        isolierungen = isolierungen or []

        for index, thickness in enumerate(thicknesses):
            material = isolierungen[index] if index < len(isolierungen) else ""
            self.add_layer_row(thickness, material)

        if not self.layer_rows:
            self.add_layer_row()

    # ---------------------------------------------------------------
    # Berechnung
    # ---------------------------------------------------------------
    def calculate(self):
        try:
            n = len(self.layer_rows)
            thicknesses = []
            isolierungen = []

            for row in self.layer_rows:
                entry_d = row["entry"]
                combo = row["combo"]
                t = float(entry_d.get()) if entry_d.get().strip() else 0.0
                iso = combo.get().strip()
                thicknesses.append(t)
                isolierungen.append(iso)

            T_left = float(self.entry_T_left.get())
            T_inf = float(self.entry_T_inf.get())
            h = float(self.entry_h.get())

            validate_inputs(n, thicknesses, isolierungen, T_left, T_inf, h)

            T_mean = 0.5 * (T_left + T_inf)
            ks = get_k_values_for_layers(isolierungen, T_mean)

            result = perform_calculation(thicknesses, isolierungen, T_left, T_inf, h)
            self.display_result(result)
            self.last_result = result

            if "interface_temperatures" in result and result["interface_temperatures"]:
                self.plot_temperature_profile(thicknesses, result["interface_temperatures"])
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    # ---------------------------------------------------------------
    # Ergebnisdarstellung
    # ---------------------------------------------------------------
    def display_result(self, result: dict):
        self.last_result = result
        # Vorherigen Textbereich löschen und ersetzen
        for widget in self.output_frame.winfo_children():
            widget.destroy()

        # --- Obere Zusammenfassung ---
        summary_frame = ttk.Frame(self.output_frame)
        summary_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(summary_frame, text=f"Wärmestromdichte q = {result['q']:.3f} W/m²").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(summary_frame, text=f"Gesamtwiderstand R_total = {result['R_total']:.5f} m²K/W").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(summary_frame, text=f"Iteration: {result.get('iterations', '–')}").grid(row=2, column=0, sticky="w", padx=4, pady=2)

        ttk.Label(self.output_frame, text="Temperaturen und Materialeigenschaften pro Schicht:").pack(anchor="w", padx=5, pady=(5, 2))

        # --- Tabelle erstellen ---
        cols = ("schicht", "T_links", "T_rechts", "T_mittel", "k_mittel")
        tree = ttk.Treeview(self.output_frame, columns=cols, show="headings", height=8)
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        headers = ["Schicht", "T_links [°C]", "T_rechts [°C]", "T_mittel [°C]", "k_mittel [W/mK]"]
        widths = [180, 120, 120, 120, 130]
        for col, head, w in zip(cols, headers, widths):
            tree.heading(col, text=head)
            tree.column(col, anchor="center", width=w)

        # --- Daten aus result extrahieren ---
        T_if = result.get("interface_temperatures", [])
        T_avg = result.get("T_avg", [])
        k_avg = result.get("k_final", [])

        n_layers = len(T_if) - 1
        isolierungsnamen = [row["combo"].get() for row in self.layer_rows]

        for i in range(n_layers):
            iso_name = isolierungsnamen[i] if i < len(isolierungsnamen) else f"Schicht {i+1}"
            T_l = T_if[i]
            T_r = T_if[i + 1]
            T_m = T_avg[i] if i < len(T_avg) else (T_l + T_r) / 2
            k_m = k_avg[i] if i < len(k_avg) else 0.0

            tree.insert(
                "",
                "end",
                values=(f"{i+1} ({iso_name})", f"{T_l:.2f}", f"{T_r:.2f}", f"{T_m:.2f}", f"{k_m:.4f}")
            )

        # Theme-kompatible Farben (hell/dunkel)
        theme = sv_ttk.get_theme()

    # ---------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------
    def plot_temperature_profile(self, thicknesses, temperatures):
        theme = sv_ttk.get_theme()
        plot_bg_color = '#1e1e1e' if theme == "dark" else '#fefefe'
        fg_color = 'white' if theme == "dark" else 'black'

        fig, ax = plt.subplots(figsize=(9, 6), dpi=100, facecolor=plot_bg_color)
        ax.set_facecolor(plot_bg_color)

        total_x = [0]
        for t in thicknesses:
            total_x.append(total_x[-1] + t)

        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("custom_cmap", colors, N=256)
        ax.plot(total_x, temperatures, linewidth=2, marker="o", color=fg_color)

        x_pos = 0
        for i, t in enumerate(thicknesses):
            color_value = i / (len(thicknesses) - 1) if len(thicknesses) > 1 else 0.5
            color = cmap(color_value)
            ax.axvspan(x_pos, x_pos + t, color=color, alpha=0.4)
            x_pos += t

        for x, T in zip(total_x, temperatures):
            ax.text(x, T + 10, f"{T:.0f}°C", ha="center", fontsize=9,
                    bbox=dict(facecolor=plot_bg_color, alpha=0.7, edgecolor="none"), color=fg_color)

        ax.set_xlabel("Dicke [mm]", color=fg_color)
        ax.set_ylabel("Temperatur [°C]", color=fg_color)
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=11, color=fg_color)
        ax.grid(True, linestyle="--", alpha=0.6, color='gray')
        ax.tick_params(axis='x', colors=fg_color, labelsize=9)
        ax.tick_params(axis='y', colors=fg_color, labelsize=9)

        # Ersetze den Inhalt des Plot-Frames
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _collect_layer_data(self) -> Tuple[List[float], List[str]]:
        thicknesses: List[float] = []
        isolierungen: List[str] = []
        for row in self.layer_rows:
            entry_d = row["entry"]
            combo = row["combo"]
            thicknesses.append(self._safe_float(entry_d.get()))
            isolierungen.append(combo.get().strip())
        return thicknesses, isolierungen

    def export_layer_data(self) -> Tuple[List[float], List[str]]:
        """Gibt die aktuellen Schichten (Dicken & Materialien) zurück."""

        return self._collect_layer_data()

    def _safe_float(self, value: str) -> float:
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return 0.0

    # ---------------------------------------------------------------
    # Projekt speichern
    # ---------------------------------------------------------------
    def save_project(self):
        try:
            name = self.entry_project_name.get().strip()
            if not name:
                messagebox.showerror("Fehler", "Bitte einen Projektnamen angeben.")
                return

            n = len(self.layer_rows)
            thicknesses = []
            isolierungen = []

            for row in self.layer_rows:
                entry_d = row["entry"]
                combo = row["combo"]
                t = float(entry_d.get()) if entry_d.get().strip() else 0.0
                iso = combo.get().strip()
                thicknesses.append(t)
                isolierungen.append(iso)

            T_left = float(self.entry_T_left.get())
            T_inf = float(self.entry_T_inf.get())
            h = float(self.entry_h.get())

            validate_inputs(n, thicknesses, isolierungen, T_left, T_inf, h)
            T_mean = 0.5 * (T_left + T_inf)
            ks = get_k_values_for_layers(isolierungen, T_mean)

            result = perform_calculation(thicknesses, isolierungen, T_left, T_inf, h)
            save_current_project(name, thicknesses, isolierungen, T_left, T_inf, h, result)

            messagebox.showinfo("Gespeichert", f"Projekt '{name}' wurde gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler beim Speichern", str(e))

    def export_state(self) -> Dict[str, Any]:
        thicknesses, isolierungen = self._collect_layer_data()
        layer_count = len(thicknesses)
        state: Dict[str, Any] = {
            "name": self.entry_project_name.get().strip(),
            "layer_count": layer_count,
            "thicknesses": thicknesses,
            "isolierungen": isolierungen,
            "T_left": self._safe_float(self.entry_T_left.get()),
            "T_inf": self._safe_float(self.entry_T_inf.get()),
            "h": self._safe_float(self.entry_h.get()),
        }
        if self.last_result is not None:
            state["result"] = self.last_result
        return state

    # ---------------------------------------------------------------
    # Theme
    # ---------------------------------------------------------------
    def update_theme_colors(self):
        theme = sv_ttk.get_theme()
        bg_color = '#2D2D2D' if theme == "dark" else '#f9f9f9'
        fg_color = 'white' if theme == "dark" else 'black'
        self.output_text.config(bg=bg_color, fg=fg_color)
