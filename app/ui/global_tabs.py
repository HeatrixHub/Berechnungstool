"""Globale Tabs für Projekte, Isolierungen und Berichte."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app.core.projects import ProjectManager
from app.core.reporting import ReportManager, ReportContribution
from app.core.resources import IsolationLibrary, IsolationRecord


class ProjectsTab:
    """Zeigt und verwaltet alle Projekte der Anwendung."""

    def __init__(self, notebook: ttk.Notebook, manager: ProjectManager) -> None:
        self._manager = manager
        self.frame = ttk.Frame(notebook, padding=(16, 12))
        notebook.add(self.frame, text="Projekte")
        self._build()
        manager.add_listener(self.refresh)
        self.refresh()

    def _build(self) -> None:
        header = ttk.Label(
            self.frame,
            text="Projektverwaltung",
            font=("Segoe UI", 16, "bold"),
        )
        header.grid(row=0, column=0, sticky="w")

        body = ttk.Frame(self.frame)
        body.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        self._projects_list = tk_listbox = ttk.Treeview(
            body,
            columns=("plugins",),
            show="headings",
            height=6,
        )
        tk_listbox.heading("plugins", text="Plugin-Daten")
        tk_listbox.column("plugins", width=260)
        tk_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            body, orient="vertical", command=tk_listbox.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        tk_listbox.configure(yscrollcommand=scrollbar.set)

        controls = ttk.Frame(body, padding=(0, 12, 0, 0))
        controls.grid(row=1, column=0, columnspan=2, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Neues Projekt:").grid(row=0, column=0, padx=(0, 8))
        self._project_name_var = ttk.Entry(controls)
        self._project_name_var.grid(row=0, column=1, sticky="ew")
        ttk.Button(
            controls, text="Anlegen", command=self._create_project
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Button(
            controls,
            text="Als aktiv markieren",
            command=self._set_current,
        ).grid(row=1, column=2, pady=(8, 0))

    def refresh(self) -> None:
        for row in self._projects_list.get_children():
            self._projects_list.delete(row)
        for project in self._manager.list_projects():
            plugin_count = len(project.data.get("plugins", {}))
            label = "1 Plugin" if plugin_count == 1 else f"{plugin_count} Plugins"
            self._projects_list.insert("", "end", iid=project.name, values=(label,))
        current = self._manager.get_current().name
        if current in self._projects_list.get_children():
            self._projects_list.selection_set(current)

    def _create_project(self) -> None:
        name = self._project_name_var.get().strip() or "Neues Projekt"
        try:
            self._manager.create_project(name)
        except ValueError as exc:
            messagebox.showerror("Projekt", str(exc), parent=self.frame)
        self._project_name_var.delete(0, "end")

    def _set_current(self) -> None:
        selection = self._projects_list.selection()
        if not selection:
            messagebox.showwarning(
                "Projekt", "Bitte zuerst ein Projekt auswählen.", parent=self.frame
            )
            return
        self._manager.set_current(selection[0])


class IsolationTab:
    """Stellt die globale Isolierungsdatenbank dar."""

    def __init__(self, notebook: ttk.Notebook, library: IsolationLibrary) -> None:
        self._library = library
        self.frame = ttk.Frame(notebook, padding=(16, 12))
        notebook.add(self.frame, text="Isolierungen")
        self._build()
        library.add_listener(self.refresh)
        self.refresh()

    def _build(self) -> None:
        ttk.Label(
            self.frame,
            text="Gemeinsame Isolierungsdatenbank",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        table = ttk.Treeview(
            self.frame,
            columns=("material", "thickness"),
            show="headings",
            height=8,
        )
        table.heading("material", text="Material")
        table.heading("thickness", text="Dicke [mm]")
        table.column("material", width=220)
        table.column("thickness", width=120, anchor="center")
        table.grid(row=1, column=0, sticky="nsew", pady=12)
        self._table = table

        form = ttk.Frame(self.frame)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Bezeichnung").grid(row=0, column=0, sticky="w")
        self._name_entry = ttk.Entry(form)
        self._name_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(form, text="Material").grid(row=1, column=0, sticky="w")
        self._material_entry = ttk.Entry(form)
        self._material_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(form, text="Dicke [mm]").grid(row=2, column=0, sticky="w")
        self._thickness_entry = ttk.Entry(form)
        self._thickness_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0))

        ttk.Button(form, text="Speichern", command=self._save_record).grid(
            row=3, column=1, sticky="e", pady=(8, 0)
        )

    def _save_record(self) -> None:
        try:
            thickness = float(self._thickness_entry.get().replace(",", "."))
        except ValueError:
            messagebox.showerror(
                "Isolierungen",
                "Bitte eine gültige Dicke in Millimetern angeben.",
                parent=self.frame,
            )
            return
        record = IsolationRecord(
            name=self._name_entry.get().strip() or "Unbenannte Isolierung",
            material=self._material_entry.get().strip() or "Unbekannt",
            thickness_mm=thickness,
        )
        self._library.upsert(record)
        self._name_entry.delete(0, "end")
        self._material_entry.delete(0, "end")
        self._thickness_entry.delete(0, "end")

    def refresh(self) -> None:
        for row in self._table.get_children():
            self._table.delete(row)
        for record in self._library.list_records():
            self._table.insert(
                "", "end", iid=record.name, values=(record.material, record.thickness_mm)
            )


class ReportTab:
    """Führt alle Berichtsinhalte aus den Plugins zusammen."""

    def __init__(self, notebook: ttk.Notebook, manager: ReportManager) -> None:
        self._manager = manager
        self.frame = ttk.Frame(notebook, padding=(16, 12))
        notebook.add(self.frame, text="Bericht")
        self._build()
        manager.add_listener(self.refresh)
        self.refresh()

    def _build(self) -> None:
        ttk.Label(
            self.frame,
            text="Berichtskonfigurator",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self._contrib_table = ttk.Treeview(
            self.frame,
            columns=("plugin", "include"),
            show="headings",
            height=8,
        )
        self._contrib_table.heading("plugin", text="Plugin")
        self._contrib_table.heading("include", text="Im Bericht?")
        self._contrib_table.column("plugin", width=220)
        self._contrib_table.column("include", width=120, anchor="center")
        self._contrib_table.grid(row=1, column=0, sticky="nsew", pady=12)

        controls = ttk.Frame(self.frame)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="Inkludieren", command=self._include).pack(
            side="left"
        )
        ttk.Button(controls, text="Ausschließen", command=self._exclude).pack(
            side="left", padx=8
        )
        ttk.Button(controls, text="Bericht generieren", command=self._generate).pack(
            side="right"
        )

        self._report_preview = ttk.Frame(self.frame)
        self._report_preview.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        self.frame.rowconfigure(3, weight=1)
        ttk.Label(self._report_preview, text="Vorschau").pack(anchor="w")
        self._preview_text = tk.Text(self._report_preview, height=8, wrap="word")
        self._preview_text.pack(fill="both", expand=True)

    def refresh(self) -> None:
        for row in self._contrib_table.get_children():
            self._contrib_table.delete(row)
        for contribution in self._manager.list_contributions():
            self._contrib_table.insert(
                "",
                "end",
                iid=self._row_id(contribution),
                values=(contribution.plugin_name, "Ja" if contribution.include_in_report else "Nein"),
            )

    def _row_id(self, contribution: ReportContribution) -> str:
        return f"{contribution.plugin_name}:{contribution.section_id}"

    def _include(self) -> None:
        for item in self._contrib_table.selection():
            plugin, section = item.split(":", 1)
            self._manager.toggle_inclusion(plugin, section, True)

    def _exclude(self) -> None:
        for item in self._contrib_table.selection():
            plugin, section = item.split(":", 1)
            self._manager.toggle_inclusion(plugin, section, False)

    def _generate(self) -> None:
        report = self._manager.compile_report()
        self._preview_text.delete("1.0", "end")
        self._preview_text.insert("1.0", report or "Keine Inhalte ausgewählt.")


__all__ = ["ProjectsTab", "IsolationTab", "ReportTab"]
