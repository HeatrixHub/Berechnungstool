from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.plugins.base import AppContext, Plugin
from app.projects.store import ProjectRecord
from app.reporting import ReportBuilder, ReportContext, ReportTemplateMetadata


@dataclass(slots=True)
class _TemplateEntry:
    plugin: Plugin
    template: ReportTemplateMetadata


class ReportTab:
    """Stellt plugin-spezifische PDF-Berichte auf Basis von Preppy-Templates bereit."""

    def __init__(self, notebook: ttk.Notebook, context: AppContext, tab_name: str = "Bericht"):
        self.context = context
        self.plugins: Sequence[Plugin] = context.plugins
        self.template_lookup: Dict[str, _TemplateEntry] = {}
        self._project_display_to_id: Dict[str, str] = {}
        self.output_path = tk.StringVar(
            value=str(Path.home() / "berichte" / "bericht.pdf")
        )
        self.source_var = tk.StringVar(value="current")
        self.project_var = tk.StringVar()

        container = ttk.Frame(notebook, padding=(14, 12, 14, 12))
        notebook.add(container, text=tab_name)

        ttk.Label(container, text="Berichtsexport", style="Title.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        main = ttk.Frame(container)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_template_tree(main)
        self._build_details_panel(main)

        self._refresh_templates()
        self._refresh_projects()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_template_tree(self, parent: ttk.Frame) -> None:
        wrapper = ttk.Frame(parent)
        wrapper.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(1, weight=1)

        header = ttk.Frame(wrapper)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Verfügbare Vorlagen", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(header, text="Aktualisieren", command=self._refresh_templates).grid(
            row=0, column=1, padx=(8, 0)
        )

        columns = ("title", "filename")
        self.tree = ttk.Treeview(
            wrapper,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            height=16,
        )
        self.tree.heading("title", text="Vorlage")
        self.tree.heading("filename", text="Vorschlag")
        self.tree.column("title", width=240, anchor="w")
        self.tree.column("filename", width=180, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._on_template_select())

        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        wrapper = ttk.Frame(parent)
        wrapper.grid(row=0, column=1, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(1, weight=1)

        self.selected_label = tk.StringVar(value="Keine Vorlage ausgewählt")
        ttk.Label(wrapper, textvariable=self.selected_label, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        self.description = tk.Text(wrapper, wrap="word", height=8)
        self.description.grid(row=1, column=0, sticky="nsew")
        self.description.configure(state="disabled")

        controls = ttk.LabelFrame(wrapper, text="Ausgabe", padding=10, style="Section.TLabelframe")
        controls.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Zielpfad:").grid(row=0, column=0, sticky="w")
        path_entry = ttk.Entry(controls, textvariable=self.output_path)
        path_entry.grid(row=0, column=1, sticky="ew", padx=(8, 6))
        ttk.Button(controls, text="…", width=3, command=self._choose_target).grid(
            row=0, column=2, sticky="w"
        )

        source_frame = ttk.LabelFrame(wrapper, text="Datengrundlage", padding=10, style="Section.TLabelframe")
        source_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        source_frame.columnconfigure(1, weight=1)

        ttk.Radiobutton(
            source_frame,
            text="Aktueller Plugin-Zustand",
            value="current",
            variable=self.source_var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            source_frame,
            text="Gespeichertes Projekt",
            value="project",
            variable=self.source_var,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Label(source_frame, text="Projekt:").grid(row=1, column=1, sticky="e", padx=(8, 4))
        self.project_combo = ttk.Combobox(source_frame, state="readonly", textvariable=self.project_var)
        self.project_combo.grid(row=1, column=2, sticky="ew")
        ttk.Button(source_frame, text="Projekte aktualisieren", command=self._refresh_projects).grid(
            row=2, column=2, sticky="e", pady=(6, 0)
        )

        action_row = ttk.Frame(wrapper, padding=(0, 12, 0, 0))
        action_row.grid(row=4, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        ttk.Button(
            action_row,
            text="PDF erzeugen",
            style="Accent.TButton",
            command=self._export_pdf,
        ).grid(row=0, column=1, sticky="e")

    # ------------------------------------------------------------------
    # Datenbeschaffung
    # ------------------------------------------------------------------
    def _collect_templates(self) -> List[_TemplateEntry]:
        entries: List[_TemplateEntry] = []
        for plugin in self.plugins:
            templates_func = getattr(plugin, "list_report_templates", None)
            if templates_func is None:
                continue
            try:
                templates = list(templates_func())
            except Exception as exc:  # pragma: no cover - Laufzeitdiagnose
                messagebox.showwarning(
                    "Bericht",
                    f"{plugin.name}: Vorlagen konnten nicht geladen werden\n{exc}",
                )
                continue
            for template in templates:
                entries.append(_TemplateEntry(plugin=plugin, template=template))
        return entries

    def _refresh_templates(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.template_lookup.clear()

        entries = self._collect_templates()
        if not entries:
            root_id = self.tree.insert("", "end", text="Keine Berichte verfügbar")
            self.tree.item(root_id, open=True)
            return

        grouped: Dict[str, List[_TemplateEntry]] = {}
        for entry in entries:
            key = entry.plugin.name
            grouped.setdefault(key, []).append(entry)

        for plugin_name, plugin_entries in grouped.items():
            plugin_id = self.tree.insert("", "end", text=plugin_name, open=True)
            for entry in plugin_entries:
                item_id = f"{entry.plugin.identifier or entry.plugin.name}:{entry.template.template_id}"
                self.template_lookup[item_id] = entry
                self.tree.insert(
                    plugin_id,
                    "end",
                    iid=item_id,
                    text=entry.template.title,
                    values=(entry.template.title, entry.template.suggested_filename or ""),
                )
        self._on_template_select()

    def _refresh_projects(self) -> None:
        records = self.context.project_store.list_projects()
        display_map: Dict[str, str] = {}
        values: List[str] = []
        for record in records:
            label = f"{record.name} ({record.updated_at})"
            display_map[label] = record.id
            values.append(label)
        self._project_display_to_id = display_map
        self.project_combo.configure(values=values)
        if values and not self.project_var.get():
            self.project_var.set(values[0])
        if not values:
            self.project_var.set("")

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------
    def _choose_target(self) -> None:
        initial = Path(self.output_path.get())
        initial_dir = initial.parent if initial.parent.exists() else Path.home()
        selected = filedialog.asksaveasfilename(
            parent=self.context.root,
            title="PDF speichern",
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf"), ("Alle Dateien", "*.*")],
            initialdir=initial_dir,
            initialfile=initial.name,
        )
        if selected:
            self.output_path.set(str(Path(selected)))

    def _on_template_select(self) -> None:
        selection = self.tree.selection()
        if not selection:
            self.selected_label.set("Keine Vorlage ausgewählt")
            self._set_description("")
            return
        item_id = selection[0]
        entry = self.template_lookup.get(item_id)
        if entry is None:
            self.selected_label.set(self.tree.item(item_id, "text"))
            self._set_description("")
            return
        self.selected_label.set(f"{entry.plugin.name} – {entry.template.title}")
        self._set_description(entry.template.description or "")
        default_filename = entry.template.suggested_filename or f"{entry.template.template_id}.pdf"
        default_path = Path.home() / "berichte" / default_filename
        self.output_path.set(str(default_path))

    def _set_description(self, text: str) -> None:
        self.description.configure(state="normal")
        self.description.delete("1.0", "end")
        if text:
            self.description.insert("1.0", text)
        self.description.configure(state="disabled")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_pdf(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Bericht", "Bitte eine Vorlage auswählen.")
            return
        entry = self.template_lookup.get(selection[0])
        if entry is None:
            messagebox.showinfo("Bericht", "Bitte eine konkrete Vorlage auswählen.")
            return

        target = Path(self.output_path.get()).expanduser()
        builder = ReportBuilder(target, title=entry.template.title)
        try:
            context = self._build_context(entry.plugin)
        except ValueError as exc:
            messagebox.showerror("Bericht", str(exc))
            return

        try:
            entry.plugin.render_report(entry.template.template_id, builder, context)
            builder.build()
        except Exception as exc:  # pragma: no cover - Laufzeitdiagnose
            messagebox.showerror(
                "Bericht",
                f"PDF konnte nicht erstellt werden:\n{exc}",
            )
            return

        messagebox.showinfo("Bericht", f"PDF gespeichert: {target}")

    def _build_context(self, plugin: Plugin) -> ReportContext:
        source = self.source_var.get()
        plugin_state: Dict[str, object] | None = None
        project_id: str | None = None
        if source == "current":
            plugin_state = plugin.export_state()
        else:
            display_value = self.project_var.get()
            project_id = self._project_display_to_id.get(display_value)
            if not project_id:
                raise ValueError("Bitte ein gespeichertes Projekt auswählen.")
            record = self.context.project_store.load_project(project_id)
            if record is None:
                raise ValueError("Projekt konnte nicht geladen werden.")
            plugin_state = self._extract_plugin_state(record, plugin)
            if plugin_state is None:
                raise ValueError(
                    "Im ausgewählten Projekt sind keine Daten für dieses Plugin gespeichert."
                )
        return ReportContext(plugin_state=plugin_state, source=source, project_id=project_id)

    def _extract_plugin_state(self, record: ProjectRecord, plugin: Plugin) -> Dict[str, object] | None:
        identifier = getattr(plugin, "identifier", None) or plugin.name
        return record.plugin_states.get(identifier)
