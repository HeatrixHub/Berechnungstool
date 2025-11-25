"""GUI-Tab zur Verwaltung von Projekten und Plugin-Zuständen."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Iterable, List, Sequence

from app.plugins.base import Plugin
from .store import ProjectRecord, ProjectStore
from app.plugins.registry import PluginSpec


class ProjectsTab:
    """Stellt einen permanenten Tab zur Verwaltung aller Projekte bereit."""

    def __init__(
        self,
        notebook: ttk.Notebook,
        store: ProjectStore,
        plugins: Iterable[Plugin],
        specs: Sequence[PluginSpec],
    ) -> None:
        self.store = store
        self.plugins: List[Plugin] = list(plugins)
        self.plugin_lookup: Dict[str, Plugin] = {
            plugin.identifier: plugin
            for plugin in self.plugins
            if getattr(plugin, "identifier", None)
        }
        self.spec_lookup: Dict[str, str] = {
            spec.identifier: spec.name for spec in specs
        }
        self.selected_project_id: str | None = None
        self.project_cache: Dict[str, ProjectRecord] = {}
        self.status_var = tk.StringVar(
            value=(
                "Wähle ein vorhandenes Projekt oder lege ein neues an, "
                "um Plugin-Eingaben und Ergebnisse zu sichern."
            )
        )

        self.frame = ttk.Frame(notebook, padding=(12, 12, 12, 12))
        notebook.add(self.frame, text="Projekte")

        self._build_ui()
        self.refresh_projects()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.frame.columnconfigure(0, weight=2)
        self.frame.columnconfigure(1, weight=3)
        self.frame.rowconfigure(3, weight=1)

        intro = ttk.Label(
            self.frame,
            wraplength=620,
            justify="left",
            text=(
                "Speichere den aktuellen Zustand aller Plugins – inklusive "
                "Eingaben und Berechnungsergebnissen – direkt in einem Projekt. "
                "Wähle links ein Projekt, lade es oder lege über \"Neu\" einen "
                "frischen Eintrag an."
            ),
        )
        intro.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        meta_frame = ttk.LabelFrame(self.frame, text="Projekt-Metadaten")
        meta_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 8))
        meta_frame.columnconfigure(1, weight=1)

        ttk.Label(meta_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )

        ttk.Label(meta_frame, text="Autor:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.author_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.author_var).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4
        )

        button_frame = ttk.Frame(self.frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for i in range(5):
            button_frame.columnconfigure(i, weight=1)

        ttk.Button(button_frame, text="Neu", command=self.reset_form).grid(
            row=0, column=0, padx=4, pady=(0, 2), sticky="ew"
        )
        ttk.Button(
            button_frame,
            text="Projekt speichern",
            command=self.save_project,
        ).grid(row=0, column=1, padx=4, pady=(0, 2), sticky="ew")
        ttk.Button(
            button_frame,
            text="Projekt laden",
            command=self.load_selected_project,
        ).grid(row=0, column=2, padx=4, pady=(0, 2), sticky="ew")
        ttk.Button(
            button_frame,
            text="Löschen",
            command=self.delete_selected_project,
        ).grid(row=0, column=3, padx=4, pady=(0, 2), sticky="ew")
        ttk.Button(
            button_frame,
            text="Aktualisieren",
            command=self.refresh_projects,
        ).grid(row=0, column=4, padx=4, pady=(0, 2), sticky="ew")

        ttk.Label(
            button_frame,
            textvariable=self.status_var,
            foreground="#6b7280",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=6, pady=(4, 0))

        tree_frame = ttk.Frame(self.frame)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=(0, 8))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("name", "author", "updated")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("name", text="Projekt")
        self.tree.heading("author", text="Autor")
        self.tree.heading("updated", text="Zuletzt geändert")
        self.tree.column("name", anchor="w", width=220)
        self.tree.column("author", anchor="center", width=120)
        self.tree.column("updated", anchor="center", width=160)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.on_project_select())

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        details_frame = ttk.LabelFrame(self.frame, text="Details & Vorschau")
        details_frame.grid(row=3, column=1, sticky="nsew")
        details_frame.rowconfigure(0, weight=1)
        details_frame.columnconfigure(0, weight=1)

        self.details = tk.Text(details_frame, wrap="word", height=18)
        self.details.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.details.configure(state="disabled")

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------
    def reset_form(self) -> None:
        self.name_var.set("")
        self.author_var.set("")
        self.selected_project_id = None
        self.tree.selection_remove(self.tree.selection())
        self._show_details(None)
        self._set_status("Neues Projekt vorbereitet. Gib Name und Autor ein.")

    def refresh_projects(self) -> None:
        self.project_cache.clear()
        self.tree.delete(*self.tree.get_children())
        for record in self.store.list_projects():
            self.project_cache[record.id] = record
            self.tree.insert(
                "",
                "end",
                iid=record.id,
                values=(record.name, record.author, record.updated_at),
            )
        if self.selected_project_id and self.selected_project_id in self.project_cache:
            self.tree.selection_set(self.selected_project_id)
            self.on_project_select()
        else:
            self.reset_form()
        self._set_status("Liste aktualisiert. Wähle ein Projekt oder speichere ein neues.")

    def on_project_select(self) -> None:
        selection = self.tree.selection()
        if not selection:
            self.selected_project_id = None
            self._show_details(None)
            return
        project_id = selection[0]
        record = self.project_cache.get(project_id)
        if not record:
            return
        self.selected_project_id = project_id
        self.name_var.set(record.name)
        self.author_var.set(record.author)
        self._show_details(record)
        self._set_status(f"Projekt '{record.name}' ausgewählt.")

    # ------------------------------------------------------------------
    # Aktionen
    # ------------------------------------------------------------------
    def save_project(self) -> None:
        name = self.name_var.get().strip()
        author = self.author_var.get().strip()
        if not name:
            messagebox.showerror("Fehler", "Bitte einen Projektnamen angeben.")
            self._set_status("Speichern abgebrochen: Projektname fehlt.")
            return

        plugin_states: Dict[str, Dict] = {}
        errors: List[str] = []
        for plugin in self.plugins:
            identifier = getattr(plugin, "identifier", None)
            if not identifier:
                continue
            try:
                state = plugin.export_state()
            except Exception as exc:  # pragma: no cover - GUI Feedback
                errors.append(f"{plugin.name}: {exc}")
                continue
            plugin_states[identifier] = state

        if errors:
            messagebox.showerror(
                "Plugin-Fehler",
                "\n".join(["Folgende Plugins konnten nicht exportiert werden:"] + errors),
            )
            return

        try:
            record = self.store.save_project(
                name=name,
                author=author,
                plugin_states=plugin_states,
                project_id=self.selected_project_id,
            )
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        self.project_cache[record.id] = record
        self.selected_project_id = record.id
        self.refresh_projects()
        messagebox.showinfo("Gespeichert", f"Projekt '{record.name}' wurde gespeichert.")
        self._set_status(
            "Aktueller Plugin-Stand wurde erfolgreich im Projekt abgelegt."
        )

    def load_selected_project(self) -> None:
        if not self.selected_project_id:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Projekt auswählen.")
            self._set_status("Kein Projekt ausgewählt zum Laden.")
            return
        record = self.store.load_project(self.selected_project_id)
        if not record:
            messagebox.showerror("Fehler", "Projekt konnte nicht geladen werden.")
            self._set_status("Projekt konnte nicht geladen werden.")
            return

        missing_plugins: List[str] = []
        for identifier, state in record.plugin_states.items():
            plugin = self.plugin_lookup.get(identifier)
            if not plugin:
                missing_plugins.append(self.spec_lookup.get(identifier, identifier))
                continue
            try:
                plugin.import_state(state)
            except Exception as exc:  # pragma: no cover - GUI Feedback
                messagebox.showerror(
                    "Fehler beim Laden",
                    f"Plugin '{plugin.name}' konnte nicht geladen werden:\n{exc}",
                )
                return

        if missing_plugins:
            messagebox.showwarning(
                "Unvollständig",
                "\n".join(
                    [
                        "Einige Plugins sind nicht installiert und wurden übersprungen:",
                        ", ".join(missing_plugins),
                    ]
                ),
            )
            self._set_status(
                "Projekt geladen, aber einige Plugins fehlen in dieser Installation."
            )

        messagebox.showinfo("Geladen", f"Projekt '{record.name}' wurde geladen.")
        self._set_status("Projektzustand auf alle Plugins angewendet.")

    def delete_selected_project(self) -> None:
        if not self.selected_project_id:
            messagebox.showinfo("Hinweis", "Bitte ein Projekt auswählen.")
            return
        record = self.project_cache.get(self.selected_project_id)
        if not record:
            return
        if not messagebox.askyesno(
            "Löschen bestätigen",
            f"Soll das Projekt '{record.name}' wirklich gelöscht werden?",
        ):
            return
        if self.store.delete_project(record.id):
            messagebox.showinfo("Gelöscht", f"Projekt '{record.name}' wurde entfernt.")
            self.selected_project_id = None
            self.refresh_projects()
            self._set_status("Projekt gelöscht. Wähle einen anderen Eintrag oder speichere neu.")
        else:
            messagebox.showerror("Fehler", "Projekt konnte nicht gelöscht werden.")
            self._set_status("Löschen fehlgeschlagen.")

    # ------------------------------------------------------------------
    # Darstellung
    # ------------------------------------------------------------------
    def _show_details(self, record: ProjectRecord | None) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        if record is None:
            self.details.insert(tk.END, "Kein Projekt ausgewählt.")
            self.details.configure(state="disabled")
            return

        lines = [
            f"Name: {record.name}",
            f"Autor: {record.author or '–'}",
            f"Erstellt: {record.created_at or '–'}",
            f"Aktualisiert: {record.updated_at or '–'}",
            "",
            "Plugin-Zustände:",
        ]
        if not record.plugin_states:
            lines.append("  (keine Zustände gespeichert)")
        else:
            for identifier, state in record.plugin_states.items():
                name = self.spec_lookup.get(identifier) or identifier
                pretty_state = json.dumps(state, indent=2, ensure_ascii=False)
                lines.append(f"• {name}")
                lines.append(pretty_state)
                lines.append("")
        self.details.insert(tk.END, "\n".join(lines))
        self.details.configure(state="disabled")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
