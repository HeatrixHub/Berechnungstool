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
    delete_variant as delete_variant_entry,
    export_insulations_to_csv,
    export_insulations_to_folder,
    get_all_insulations,
    interpolate_k,
    import_insulations_from_csv_files,
    load_insulation,
    save_family,
    save_variant as save_variant_entry,
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
        self.frame.rowconfigure(6, weight=1)
        self.frame.columnconfigure(0, weight=1)

        ttk.Label(
            self.frame,
            text="Isolierungen verwalten",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        table_section = ttk.LabelFrame(
            self.frame, text="Materialfamilien", padding=8, style="Section.TLabelframe"
        )
        table_section.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        table_section.rowconfigure(1, weight=1)
        table_section.columnconfigure(0, weight=1)

        family_columns = (
            "name",
            "classification_temp",
            "density",
            "variant_count",
        )
        self.tree = ttk.Treeview(
            table_section,
            columns=family_columns,
            show="headings",
            height=8,
            selectmode="browse",
        )
        self.tree.heading("name", text="Familie")
        self.tree.heading("classification_temp", text="Klass.-Temp [°C]")
        self.tree.heading("density", text="Dichte [kg/m³]")
        self.tree.heading("variant_count", text="Varianten")
        for column in family_columns:
            width = 160 if column == "name" else 110
            self.tree.column(column, anchor="center", width=width)
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.on_family_select)

        scrollbar = ttk.Scrollbar(table_section, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=2, sticky="ns")

        action_bar = ttk.Frame(table_section)
        action_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        for i in range(5):
            action_bar.columnconfigure(i, weight=1)

        ttk.Button(action_bar, text="Neu", command=self.new_family).grid(
            row=0, column=0, sticky="ew", padx=4
        )
        ttk.Button(action_bar, text="Familie löschen", command=self.delete_family).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(
            action_bar, text="Exportieren (CSV)", command=self.export_selected
        ).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(action_bar, text="Importieren (CSV)", command=self.import_from_csv).grid(
            row=0, column=4, sticky="ew", padx=4
        )

        variants_section = ttk.LabelFrame(
            self.frame, text="Varianten", padding=8, style="Section.TLabelframe"
        )
        variants_section.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        variants_section.columnconfigure(0, weight=1)
        variants_section.rowconfigure(1, weight=1)

        variant_columns = ("variant_name", "thickness", "length", "width", "price")
        self.variant_tree = ttk.Treeview(
            variants_section,
            columns=variant_columns,
            show="headings",
            height=6,
            selectmode="browse",
        )
        self.variant_tree.heading("variant_name", text="Variante")
        self.variant_tree.heading("thickness", text="Dicke [mm]")
        self.variant_tree.heading("length", text="Länge [mm]")
        self.variant_tree.heading("width", text="Breite [mm]")
        self.variant_tree.heading("price", text="Preis [€]")
        for column in variant_columns:
            self.variant_tree.column(column, anchor="center", width=115)
        self.variant_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        self.variant_tree.bind("<<TreeviewSelect>>", self.on_variant_select)

        variant_scroll = ttk.Scrollbar(
            variants_section, orient="vertical", command=self.variant_tree.yview
        )
        self.variant_tree.configure(yscroll=variant_scroll.set)
        variant_scroll.grid(row=1, column=2, sticky="ns")

        variant_action_bar = ttk.Frame(variants_section)
        variant_action_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        for i in range(3):
            variant_action_bar.columnconfigure(i, weight=1)

        ttk.Button(variant_action_bar, text="Neue Variante", command=self.new_variant).grid(
            row=0, column=0, sticky="ew", padx=4
        )
        ttk.Button(
            variant_action_bar, text="Variante löschen", command=self.delete_variant
        ).grid(row=0, column=1, sticky="ew", padx=4)

        family_form = ttk.LabelFrame(
            self.frame, text="Stammdaten", style="Section.TLabelframe"
        )
        family_form.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        family_form.columnconfigure(1, weight=1)
        family_form.columnconfigure(3, weight=1)

        ttk.Label(family_form, text="Familienname:").grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(family_form)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(family_form, text="Klass.-Temp [°C]:").grid(row=1, column=0, sticky="w")
        self.entry_class_temp = ttk.Entry(family_form)
        self.entry_class_temp.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(family_form, text="Dichte [kg/m³]:").grid(row=2, column=0, sticky="w")
        self.entry_density = ttk.Entry(family_form)
        self.entry_density.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(family_form, text="Temperaturen [°C]:").grid(row=3, column=0, sticky="w")
        self.entry_temps = ttk.Entry(family_form)
        self.entry_temps.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(family_form, text="Wärmeleitfähigkeiten [W/mK]:").grid(
            row=4, column=0, sticky="w"
        )
        self.entry_ks = ttk.Entry(family_form)
        self.entry_ks.grid(row=4, column=1, sticky="ew", padx=5, pady=2)

        ttk.Button(
            family_form, text="Stammdaten speichern", command=self.save_family
        ).grid(row=5, column=0, columnspan=4, pady=8, sticky="e")

        variant_form = ttk.LabelFrame(
            self.frame, text="Variante bearbeiten", style="Section.TLabelframe"
        )
        variant_form.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        variant_form.columnconfigure(1, weight=1)
        variant_form.columnconfigure(3, weight=1)

        ttk.Label(variant_form, text="Variante:").grid(row=0, column=0, sticky="w")
        self.entry_variant_name = ttk.Entry(variant_form)
        self.entry_variant_name.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(variant_form, text="Dicke [mm]:").grid(row=1, column=0, sticky="w")
        self.entry_thickness = ttk.Entry(variant_form)
        self.entry_thickness.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(variant_form, text="Länge [mm]:").grid(row=0, column=2, sticky="w")
        self.entry_length = ttk.Entry(variant_form)
        self.entry_length.grid(row=0, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(variant_form, text="Breite [mm]:").grid(row=1, column=2, sticky="w")
        self.entry_width = ttk.Entry(variant_form)
        self.entry_width.grid(row=1, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(variant_form, text="Preis [€/Platte]:").grid(row=2, column=0, sticky="w")
        self.entry_price = ttk.Entry(variant_form)
        self.entry_price.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        ttk.Button(
            variant_form, text="Variante speichern", style="Accent.TButton", command=self.save_variant
        ).grid(row=3, column=0, columnspan=4, pady=10, sticky="e")

        self.plot_frame = ttk.LabelFrame(
            self.frame,
            text="Interpolierte Wärmeleitfähigkeit",
            style="Section.TLabelframe",
        )
        self.plot_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(0, 4))
        self.frame.rowconfigure(5, weight=1)
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
                    insulation.get("variant_count", 0),
                ),
            )
        self.variant_tree.delete(*self.variant_tree.get_children())

    def new_family(self) -> None:
        self.clear_fields()
        self.variant_tree.delete(*self.variant_tree.get_children())

    def on_family_select(self, event: tk.Event | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        name = self.tree.item(selection[0])["values"][0]
        data = load_insulation(name)
        if not data:
            return
        self._fill_family_form(data)
        self._populate_variants(data.get("variants", []))
        self.update_plot(data.get("temps", []), data.get("ks", []), data.get("classification_temp"))

    def _fill_family_form(self, data: dict) -> None:
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, data.get("name", ""))
        self.entry_class_temp.delete(0, tk.END)
        if data.get("classification_temp") is not None:
            self.entry_class_temp.insert(0, str(data["classification_temp"]))
        self.entry_density.delete(0, tk.END)
        if data.get("density") is not None:
            self.entry_density.insert(0, str(data["density"]))
        self.entry_temps.delete(0, tk.END)
        self.entry_temps.insert(0, ", ".join(map(str, data.get("temps", []))))
        self.entry_ks.delete(0, tk.END)
        self.entry_ks.insert(0, ", ".join(map(str, data.get("ks", []))))

    def _populate_variants(self, variants: list[dict]) -> None:
        self.variant_tree.delete(*self.variant_tree.get_children())
        for variant in variants:
            self.variant_tree.insert(
                "",
                "end",
                values=(
                    variant.get("name", ""),
                    variant.get("thickness", ""),
                    variant.get("length", ""),
                    variant.get("width", ""),
                    variant.get("price", ""),
                ),
            )

    def new_variant(self) -> None:
        self.entry_variant_name.delete(0, tk.END)
        self.entry_thickness.delete(0, tk.END)
        self.entry_length.delete(0, tk.END)
        self.entry_width.delete(0, tk.END)
        self.entry_price.delete(0, tk.END)

    def on_variant_select(self, event: tk.Event | None = None) -> None:
        selection = self.variant_tree.selection()
        if not selection:
            return
        values = self.variant_tree.item(selection[0])["values"]
        fields = [
            self.entry_variant_name,
            self.entry_thickness,
            self.entry_length,
            self.entry_width,
            self.entry_price,
        ]
        for entry, value in zip(fields, values):
            entry.delete(0, tk.END)
            if value not in (None, ""):
                entry.insert(0, str(value))

    def save_family(self) -> None:
        try:
            name = self.entry_name.get().strip()
            if not name:
                messagebox.showwarning("Fehler", "Familienname darf nicht leer sein.")
                return
            class_temp = self._parse_required_float(self.entry_class_temp.get(), "Klass.-Temp")
            density = self._parse_required_float(self.entry_density.get(), "Dichte")
            temps = [float(x.strip()) for x in self.entry_temps.get().split(",") if x.strip()]
            ks = [float(x.strip()) for x in self.entry_ks.get().split(",") if x.strip()]
            if len(temps) != len(ks):
                messagebox.showerror(
                    "Fehler", "Temperatur- und k-Werte müssen gleich viele Einträge haben."
                )
                return
            save_family(name, class_temp, density, temps, ks)
            messagebox.showinfo("Gespeichert", f"Familie '{name}' wurde gespeichert.")
            self.refresh_table()
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Fehler", str(exc))

    def save_variant(self) -> None:
        try:
            family_name = self.entry_name.get().strip()
            if not family_name:
                messagebox.showwarning("Fehler", "Bitte zuerst eine Familie auswählen.")
                return
            variant_name = self.entry_variant_name.get().strip() or "Standard"
            thickness = self._parse_required_float(
                self.entry_thickness.get(), "Dicke"
            )
            length = self._parse_optional_float(self.entry_length.get())
            width = self._parse_optional_float(self.entry_width.get())
            price = self._parse_optional_float(self.entry_price.get())
            saved = save_variant_entry(
                family_name, variant_name, thickness, length, width, price
            )
            if saved:
                messagebox.showinfo(
                    "Gespeichert",
                    f"Variante '{variant_name}' wurde für '{family_name}' gespeichert.",
                )
                self.on_family_select()
            else:
                messagebox.showerror(
                    "Fehler",
                    "Variante konnte nicht gespeichert werden. Bitte Familie prüfen.",
                )
        except Exception as exc:  # pragma: no cover - GUI Verarbeitung
            messagebox.showerror("Fehler", str(exc))

    def delete_family(self) -> None:
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

    def delete_variant(self) -> None:
        family_name = self.entry_name.get().strip()
        selection = self.variant_tree.selection()
        if not family_name or not selection:
            messagebox.showinfo(
                "Hinweis", "Bitte zuerst eine Familie und Variante auswählen."
            )
            return
        variant_name = self.variant_tree.item(selection[0])["values"][0]
        if messagebox.askyesno(
            "Variante löschen",
            f"Soll die Variante '{variant_name}' aus '{family_name}' gelöscht werden?",
        ):
            if delete_variant_entry(family_name, variant_name):
                self.on_family_select()
                self.new_variant()
            else:
                messagebox.showerror(
                    "Löschen fehlgeschlagen",
                    "Die Variante konnte nicht gelöscht werden.",
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

        ttk.Button(button_bar, text="Alle auswählen", command=_select_all).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(button_bar, text="Auswahl löschen", command=_deselect_all).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(button_bar, text="Export starten", command=_confirm).grid(
            row=0, column=2, padx=4, sticky="ew"
        )

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

    def clear_fields(self) -> None:
        for entry in [
            self.entry_name,
            self.entry_class_temp,
            self.entry_density,
            self.entry_length,
            self.entry_width,
            self.entry_price,
            self.entry_temps,
            self.entry_ks,
            self.entry_variant_name,
            self.entry_thickness,
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
            if not temps or not ks:
                for widget in self.plot_frame.winfo_children():
                    widget.destroy()
                return
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
