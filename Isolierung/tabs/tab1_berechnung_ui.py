# tabs/tab1_berechnung_ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import sv_ttk
from typing import Any, Dict, List, Tuple

from .tab1_berechnung_logic import (
    validate_inputs,
    perform_calculation,
    save_current_project,
    get_k_values_for_layers,
)
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

    # ---------------------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.columnconfigure(1, weight=1)

        # Projektname
        ttk.Label(self.frame, text="Projektname:").grid(row=0, column=0, sticky='w', padx=6, pady=4)
        self.entry_project_name = ttk.Entry(self.frame)
        self.entry_project_name.grid(row=0, column=1, sticky='ew', padx=6, pady=4)

        # Anzahl Schichten
        ttk.Label(self.frame, text="Anzahl Schichten:").grid(row=1, column=0, sticky='w', padx=6, pady=4)
        self.entry_layers = ttk.Entry(self.frame)
        self.entry_layers.grid(row=1, column=1, sticky='ew', padx=6, pady=4)
        self.entry_layers.bind("<KeyRelease>", lambda e: self.update_layers_ui())

        # Container für dynamische Schichtenfelder
        self.layers_frame = ttk.LabelFrame(self.frame, text="Schichten")
        self.layers_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=6, pady=4)
        self.layer_rows = []

        # Randbedingungen
        rand_frame = ttk.LabelFrame(self.frame, text="Randbedingungen")
        rand_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
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
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10, sticky='ew')
        ttk.Button(btn_frame, text="Berechnen", command=self.calculate).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Projekt speichern", command=self.save_project).pack(side=tk.LEFT, padx=3)

        # Ergebnisse
        self.output_frame = ttk.LabelFrame(self.frame, text="Ergebnisse")
        self.output_frame.grid(row=5, column=0, columnspan=2, pady=5, sticky='nsew', padx=6)
        self.output_text = tk.Text(self.output_frame, height=8, wrap='word', relief='flat')
        self.output_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Plotbereich
        self.plot_frame = ttk.LabelFrame(self.frame, text="Temperaturverlauf")
        self.plot_frame.grid(row=6, column=0, columnspan=2, pady=10, sticky='nsew', padx=6)

        self.update_theme_colors()

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

            self.entry_layers.delete(0, "end")
            self.entry_layers.insert(0, str(len(thicknesses)))

            # Dynamische Schichtzeilen erzeugen
            self.update_layers_ui()

            # Werte eintragen
            for i, (entry_d, combo_iso) in enumerate(self.layer_rows):
                if i < len(thicknesses):
                    entry_d.delete(0, tk.END)
                    entry_d.insert(0, str(thicknesses[i]))
                if i < len(isolierungen):
                    combo_iso.set(isolierungen[i])

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

    # ---------------------------------------------------------------
    # Dynamische Schichtsteuerung
    # ---------------------------------------------------------------
    def update_layers_ui(self):
        """Passt dynamisch die Anzahl der Schichten an, ohne bestehende Eingaben zu löschen."""
        try:
            new_n = int(self.entry_layers.get())
            if new_n <= 0:
                return
        except ValueError:
            return

        # --- Aktuelle Eingaben zwischenspeichern ---
        current_data = []
        for entry_d, combo_iso in self.layer_rows:
            t_val = entry_d.get().strip()
            iso_val = combo_iso.get().strip()
            current_data.append((t_val, iso_val))

        from app.global_tabs.isolierungen_db.logic import get_all_insulations
        isolierungen = [i["name"] for i in get_all_insulations()]

        current_n = len(self.layer_rows)

        # --- Wenn neue Schicht(en) hinzukommen ---
        if new_n > current_n:
            for i in range(current_n, new_n):
                ttk.Label(self.layers_frame, text=f"Schicht {i+1}:").grid(row=i, column=0, sticky='w', padx=5, pady=2)
                entry_d = ttk.Entry(self.layers_frame, width=10)
                entry_d.grid(row=i, column=1, padx=5, pady=2)
                combo_iso = ttk.Combobox(self.layers_frame, values=isolierungen, state="readonly")
                combo_iso.grid(row=i, column=2, sticky='ew', padx=5, pady=2)
                self.layer_rows.append((entry_d, combo_iso))

        # --- Wenn Schicht(en) gelöscht werden ---
        elif new_n < current_n:
            for i in range(current_n - 1, new_n - 1, -1):
                for widget in self.layers_frame.grid_slaves(row=i):
                    widget.destroy()
                self.layer_rows.pop()

        # --- Bestehende Eingaben wiederherstellen ---
        for i, (entry_d, combo_iso) in enumerate(self.layer_rows):
            if i < len(current_data):
                t_val, iso_val = current_data[i]
                entry_d.delete(0, tk.END)
                entry_d.insert(0, t_val)
                combo_iso.set(iso_val)
                
    # ---------------------------------------------------------------
    # Berechnung
    # ---------------------------------------------------------------
    def calculate(self):
        try:
            n = int(self.entry_layers.get())
            thicknesses = []
            isolierungen = []

            for entry_d, combo in self.layer_rows:
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
        isolierungsnamen = [combo.get() for (_, combo) in self.layer_rows]

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
        for entry_d, combo in self.layer_rows:
            thicknesses.append(self._safe_float(entry_d.get()))
            isolierungen.append(combo.get().strip())
        return thicknesses, isolierungen

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

            n = int(self.entry_layers.get())
            thicknesses = []
            isolierungen = []

            for entry_d, combo in self.layer_rows:
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
        try:
            layer_count = int(self.entry_layers.get())
        except ValueError:
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