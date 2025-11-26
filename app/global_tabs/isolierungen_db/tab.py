from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from Isolierung.tabs.scrollable import ScrollableFrame
from app.global_tabs.isolierungen_db.logic import (
    delete_insulation,
    get_all_insulations,
    interpolate_k,
    load_insulation,
    save_insulation,
)


class IsolierungenTab:
    def __init__(self, notebook: ttk.Notebook, tab_name: str = "Isolierungen"):
        container = ttk.Frame(notebook, padding=(14, 12, 14, 12))
        notebook.add(container, text=tab_name)

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)

        self.frame = self.scrollable.inner
        self.build_ui()

    def build_ui(self) -> None:
        self.frame.rowconfigure(4, weight=1)
        self.frame.columnconfigure(0, weight=1)

        ttk.Label(
            self.frame,
            text="Isolierungen verwalten",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        table_section = ttk.LabelFrame(
            self.frame, text="Isolierungen", padding=8, style="Section.TLabelframe"
        )
        table_section.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        table_section.rowconfigure(1, weight=1)
        table_section.columnconfigure(0, weight=1)

        columns = (
            "name",
            "classification_temp",
            "density",
            "length",
            "width",
            "height",
            "price",
        )
        self.tree = ttk.Treeview(
            table_section,
            columns=columns,
            show="headings",
            height=10,
            selectmode="browse",
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("classification_temp", text="Klass.-Temp [°C]")
        self.tree.heading("density", text="Dichte [kg/m³]")
        self.tree.heading("length", text="Länge [m]")
        self.tree.heading("width", text="Breite [m]")
        self.tree.heading("height", text="Höhe [m]")
        self.tree.heading("price", text="Preis [€]")
        for column in columns:
            self.tree.column(column, anchor="center", width=120)
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        scrollbar = ttk.Scrollbar(table_section, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=2, sticky="ns")

        action_bar = ttk.Frame(table_section)
        action_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        for i in range(3):
            action_bar.columnconfigure(i, weight=1)

        ttk.Button(action_bar, text="Neu", command=self.new_entry).grid(
            row=0, column=0, sticky="ew", padx=4
        )
        ttk.Button(action_bar, text="Bearbeiten", command=self.edit_entry).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(action_bar, text="Löschen", command=self.delete_entry).grid(
            row=0, column=2, sticky="ew", padx=4
        )

        form = ttk.LabelFrame(
            self.frame, text="Isolierung bearbeiten/erstellen", style="Section.TLabelframe"
        )
        form.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # Stammdaten
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(form)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Klass.-Temp [°C]:").grid(row=1, column=0, sticky="w")
        self.entry_class_temp = ttk.Entry(form)
        self.entry_class_temp.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Dichte [kg/m³]:").grid(row=2, column=0, sticky="w")
        self.entry_density = ttk.Entry(form)
        self.entry_density.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        # Abmessungen & Preis
        ttk.Label(form, text="Länge [m]:").grid(row=0, column=2, sticky="w")
        self.entry_length = ttk.Entry(form)
        self.entry_length.grid(row=0, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Breite [m]:").grid(row=1, column=2, sticky="w")
        self.entry_width = ttk.Entry(form)
        self.entry_width.grid(row=1, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Höhe [m]:").grid(row=2, column=2, sticky="w")
        self.entry_height = ttk.Entry(form)
        self.entry_height.grid(row=2, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Preis [€/Platte]:").grid(row=3, column=2, sticky="w")
        self.entry_price = ttk.Entry(form)
        self.entry_price.grid(row=3, column=3, sticky="ew", padx=5, pady=2)

        # Messwerte
        ttk.Label(form, text="Temperaturen [°C]:").grid(row=3, column=0, sticky="w")
        self.entry_temps = ttk.Entry(form)
        self.entry_temps.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(form, text="Wärmeleitfähigkeiten [W/mK]:").grid(row=4, column=0, sticky="w")
        self.entry_ks = ttk.Entry(form)
        self.entry_ks.grid(row=4, column=1, sticky="ew", padx=5, pady=2)

        ttk.Button(
            form, text="💾 Speichern", style="Accent.TButton", command=self.save_entry
        ).grid(row=5, column=0, columnspan=4, pady=10, sticky="e")

        self.plot_frame = ttk.LabelFrame(
            self.frame,
            text="Interpolierte Wärmeleitfähigkeit",
            style="Section.TLabelframe",
        )
        self.plot_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(0, 4))
        self.frame.rowconfigure(4, weight=1)
        self.refresh_table()

    def refresh_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for insulation in get_all_insulations():
            self.tree.insert(
                "",
                "end",
                values=(
                    insulation.get("name", ""),
                    insulation.get("classification_temp", ""),
                    insulation.get("density", ""),
                    insulation.get("length", ""),
                    insulation.get("width", ""),
                    insulation.get("height", ""),
                    insulation.get("price", ""),
                ),
            )

    def new_entry(self) -> None:
        self.clear_fields()

    def edit_entry(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte eine Isolierung auswählen.")
            return
        name = self.tree.item(selection[0])["values"][0]
        data = load_insulation(name)
        if not data:
            return
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, data["name"])
        self.entry_class_temp.delete(0, tk.END)
        if data.get("classification_temp") is not None:
            self.entry_class_temp.insert(0, str(data["classification_temp"]))
        self.entry_density.delete(0, tk.END)
        if data.get("density") is not None:
            self.entry_density.insert(0, str(data["density"]))
        self.entry_length.delete(0, tk.END)
        if data.get("length") is not None:
            self.entry_length.insert(0, str(data["length"]))
        self.entry_width.delete(0, tk.END)
        if data.get("width") is not None:
            self.entry_width.insert(0, str(data["width"]))
        self.entry_height.delete(0, tk.END)
        if data.get("height") is not None:
            self.entry_height.insert(0, str(data["height"]))
        self.entry_price.delete(0, tk.END)
        if data.get("price") is not None:
            self.entry_price.insert(0, str(data["price"]))
        self.entry_temps.delete(0, tk.END)
        self.entry_temps.insert(0, ", ".join(map(str, data["temps"])))
        self.entry_ks.delete(0, tk.END)
        self.entry_ks.insert(0, ", ".join(map(str, data["ks"])))
        self.update_plot(data["temps"], data["ks"], data["classification_temp"])

    def save_entry(self) -> None:
        try:
            name = self.entry_name.get().strip()
            if not name:
                messagebox.showwarning("Fehler", "Name darf nicht leer sein.")
                return
            class_temp = self._parse_required_float(self.entry_class_temp.get(), "Klass.-Temp")
            density = self._parse_required_float(self.entry_density.get(), "Dichte")
            length = self._parse_optional_float(self.entry_length.get())
            width = self._parse_optional_float(self.entry_width.get())
            height = self._parse_optional_float(self.entry_height.get())
            price = self._parse_optional_float(self.entry_price.get())
            temps = [float(x.strip()) for x in self.entry_temps.get().split(",") if x.strip()]
            ks = [float(x.strip()) for x in self.entry_ks.get().split(",") if x.strip()]
            if len(temps) != len(ks):
                messagebox.showerror(
                    "Fehler", "Temperatur- und k-Werte müssen gleich viele Einträge haben."
                )
                return
            save_insulation(name, class_temp, density, length, width, height, price, temps, ks)
            messagebox.showinfo("Gespeichert", f"Isolierung '{name}' wurde gespeichert.")
            self.refresh_table()
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Fehler", str(exc))

    def delete_entry(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte eine Isolierung auswählen.")
            return
        name = self.tree.item(selection[0])["values"][0]
        if messagebox.askyesno("Löschen", f"Soll '{name}' wirklich gelöscht werden?"):
            if delete_insulation(name):
                self.refresh_table()
                self.clear_fields()
            else:
                messagebox.showerror(
                    "Löschen nicht möglich",
                    "Die Isolierung konnte nicht gelöscht werden (wird vermutlich von Projekten verwendet).",
                )

    def on_select(self, event: tk.Event | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        name = self.tree.item(selection[0])["values"][0]
        data = load_insulation(name)
        if data:
            self.update_plot(data["temps"], data["ks"], data["classification_temp"])

    def clear_fields(self) -> None:
        for entry in [
            self.entry_name,
            self.entry_class_temp,
            self.entry_density,
            self.entry_length,
            self.entry_width,
            self.entry_height,
            self.entry_price,
            self.entry_temps,
            self.entry_ks,
        ]:
            entry.delete(0, tk.END)

    def _parse_required_float(self, value: str, label: str) -> float:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{label} darf nicht leer sein.")
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"{label} muss eine Zahl sein.")

    def _parse_optional_float(self, value: str) -> float | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError("Numerischer Wert erwartet (optional).")

    def update_plot(self, temps, ks, class_temp) -> None:
        try:
            max_temp = class_temp if class_temp is not None else (max(temps) if temps else 20)
            x = np.linspace(20, max_temp, 100)
            y = interpolate_k(temps, ks, x)
            plt.close("all")
            fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
            ax.plot(x, y, linewidth=2, label="Interpoliert")
            ax.scatter(temps, ks, color="red", zorder=5, label="Messpunkte")
            ax.set_xlabel("Temperatur [°C]")
            ax.set_ylabel("Wärmeleitfähigkeit [W/mK]")
            ax.set_title("Wärmeleitfähigkeit über Temperatur")
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.6)
            for widget in self.plot_frame.winfo_children():
                widget.destroy()
            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Fehler beim Plotten", str(exc))
