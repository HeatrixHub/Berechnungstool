from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from Isolierung.tabs.scrollable import ScrollableFrame
from app.global_tabs.isolierungen_db.logic import (
    FileImportResult,
    delete_insulation,
    export_insulations_to_csv,
    export_insulations_to_folder,
    get_all_insulations,
    interpolate_k,
    import_insulations_from_csv_files,
    load_insulation,
    save_insulation,
    register_material_change_listener,
)


class IsolierungenTab:
    def __init__(self, notebook: ttk.Notebook, tab_name: str = "Isolierungen"):
        container = ttk.Frame(notebook, padding=(14, 12, 14, 12))
        notebook.add(container, text=tab_name)

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)

        self.frame = self.scrollable.inner
        self.build_ui()
        register_material_change_listener(self.refresh_table)

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
        for i in range(5):
            action_bar.columnconfigure(i, weight=1)

        ttk.Button(
            action_bar, text="Neu", command=self.new_entry, style="Neutral.TButton"
        ).grid(row=0, column=0, sticky="ew", padx=4)
        ttk.Button(
            action_bar,
            text="Bearbeiten",
            command=self.edit_entry,
            style="Neutral.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            action_bar,
            text="Löschen",
            command=self.delete_entry,
            style="Danger.TButton",
        ).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(
            action_bar,
            text="Exportieren (CSV)",
            command=self.export_selected,
            style="Neutral.TButton",
        ).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(
            action_bar,
            text="Importieren (CSV)",
            command=self.import_from_csv,
            style="Warning.TButton",
        ).grid(row=0, column=4, sticky="ew", padx=4)

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
            form,
            text="💾 Speichern",
            style="Neutral.TButton",
            command=self.save_entry,
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
        if messagebox.askyesno(
            "Löschen bestätigen",
            (
                f"Soll das Material '{name}' endgültig gelöscht werden?\n"
                "Dieser Vorgang kann nicht rückgängig gemacht werden."
            ),
        ):
            if delete_insulation(name):
                self.refresh_table()
                self.clear_fields()
            else:
                messagebox.showerror(
                    "Löschen fehlgeschlagen",
                    "Das Material konnte nicht gelöscht werden.",
                )

    def export_selected(self) -> None:
        preselected = set()
        if self.tree.selection():
            preselected.add(self.tree.item(self.tree.selection()[0])["values"][0])

        dialog = tk.Toplevel(self.frame)
        dialog.title("Isolierungen exportieren")
        dialog.transient(self.frame)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Bitte wählen Sie ein oder mehrere Isolierungen für den Export aus:",
        ).pack(anchor="w", padx=12, pady=(12, 6))

        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=12)

        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0, height=240)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        selection_vars: list[tuple[str, tk.BooleanVar]] = []
        for insulation in get_all_insulations():
            var = tk.BooleanVar(value=insulation["name"] in preselected)
            cb = ttk.Checkbutton(inner, text=insulation["name"], variable=var)
            cb.pack(anchor="w", padx=6, pady=2)
            selection_vars.append((insulation["name"], var))

        def _on_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_configure)

        button_bar = ttk.Frame(dialog)
        button_bar.pack(fill="x", padx=12, pady=12)
        for i in range(3):
            button_bar.columnconfigure(i, weight=1)

        def _select_all() -> None:
            for _, var in selection_vars:
                var.set(True)

        def _deselect_all() -> None:
            for _, var in selection_vars:
                var.set(False)

        def _confirm() -> None:
            chosen = [name for name, var in selection_vars if var.get()]
            if not chosen:
                messagebox.showinfo(
                    "Hinweis", "Bitte mindestens eine Isolierung zum Export auswählen."
                )
                return
            dialog.destroy()
            self._export_to_files(chosen)

        ttk.Button(
            button_bar,
            text="Alle auswählen",
            command=_select_all,
            style="Neutral.TButton",
        ).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(
            button_bar,
            text="Auswahl löschen",
            command=_deselect_all,
            style="Danger.TButton",
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(
            button_bar, text="Export starten", command=_confirm, style="Neutral.TButton"
        ).grid(row=0, column=2, padx=4, sticky="ew")

    def _export_to_files(self, names: list[str]) -> None:
        try:
            if len(names) == 1:
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    initialfile=f"{names[0]}.csv",
                    filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
                    title="Isolierung exportieren",
                )
                if not file_path:
                    return
                exported, failed = export_insulations_to_csv(names, file_path)
                message = f"{exported} Isolierung exportiert nach\n{file_path}"
            else:
                target_dir = filedialog.askdirectory(
                    mustexist=True,
                    title="Zielordner für Export wählen",
                )
                if not target_dir:
                    return
                exported, failed, export_dir = export_insulations_to_folder(
                    names, target_dir
                )
                message = (
                    f"{exported} Isolierungen wurden exportiert.\n"
                    f"Speicherort: {export_dir}"
                )

            if failed:
                message += "\nNicht exportiert: " + ", ".join(failed)
            messagebox.showinfo("Export abgeschlossen", message)
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Export fehlgeschlagen", str(exc))

    def import_from_csv(self) -> None:
        file_paths = filedialog.askopenfilenames(
            filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
            title="Isolierungen importieren",
        )
        if not file_paths:
            return
        try:
            imported, results = import_insulations_from_csv_files(list(file_paths))
            self.refresh_table()
            message = self._build_import_summary(imported, results)
            messagebox.showinfo("Import abgeschlossen", message)
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Import fehlgeschlagen", str(exc))

    def _build_import_summary(
        self, imported: int, results: list[FileImportResult]
    ) -> str:
        lines = [f"{imported} Isolierung(en) importiert."]
        skipped = [r for r in results if r.skipped_reason]
        per_file_errors = [r for r in results if r.errors]

        if skipped:
            lines.append("Übersprungene Dateien:")
            for result in skipped:
                lines.append(f"- {Path(result.file_path).name}: {result.skipped_reason}")

        if per_file_errors:
            lines.append("Fehlerhafte Zeilen:")
            for result in per_file_errors:
                lines.append(f"- {Path(result.file_path).name}:")
                lines.extend([f"    * {err}" for err in result.errors])

        return "\n".join(lines)

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
