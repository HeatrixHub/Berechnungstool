"""Einfache GUI zur Verwaltung der installierten Plugins."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Dict, List

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
except Exception as exc:  # pragma: no cover - tkinter ist optional
    raise RuntimeError("tkinter wird für die Host-Anwendung benötigt") from exc

from app.core import plugin_registry as registry


@dataclass
class _EntryWidgets:
    container: ttk.Frame
    checkbox: ttk.Checkbutton
    enabled_var: tk.BooleanVar


class PluginManagerDialog(tk.Toplevel):
    """Dialog zum Aktivieren, Deaktivieren und Registrieren von Plugins."""

    def __init__(self, parent: tk.Misc, on_save: Callable[[], None] | None = None):
        super().__init__(parent)
        self.title("Pluginverwaltung")
        self.resizable(False, False)
        self.transient(parent)

        self._on_save = on_save
        self._specs: List[registry.PluginSpec] = registry.load_registry()
        self._rows: Dict[str, _EntryWidgets] = {}

        self.columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text=(
                "Aktiviere oder deaktiviere Plugins. Neue Einträge können durch "
                "Angabe von Modul- und Klassenname hinzugefügt werden."
            ),
            wraplength=420,
            padding=(12, 12),
        ).grid(row=0, column=0, sticky="ew")

        self._list_frame = ttk.Frame(self, padding=(12, 6))
        self._list_frame.grid(row=1, column=0, sticky="nsew")
        self._list_frame.columnconfigure(0, weight=1)

        self._build_rows()

        ttk.Separator(self).grid(row=2, column=0, sticky="ew", pady=(6, 6))

        button_row = ttk.Frame(self, padding=(12, 6))
        button_row.grid(row=3, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)

        ttk.Button(
            button_row, text="Plugin hinzufügen", command=self._show_add_dialog
        ).grid(row=0, column=0, sticky="w")

        ttk.Button(button_row, text="Speichern", command=self._save).grid(
            row=0, column=1, padx=(12, 0)
        )
        ttk.Button(button_row, text="Schließen", command=self.destroy).grid(
            row=0, column=2, padx=(6, 0)
        )

    def _build_rows(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._rows.clear()

        for idx, spec in enumerate(self._specs):
            frame = ttk.Frame(self._list_frame)
            frame.grid(row=idx, column=0, sticky="ew", pady=2)
            frame.columnconfigure(0, weight=1)

            enabled_var = tk.BooleanVar(value=spec.enabled)
            checkbox = ttk.Checkbutton(
                frame,
                text=f"{spec.name} ({spec.module}:{spec.class_name})",
                variable=enabled_var,
            )
            checkbox.grid(row=0, column=0, sticky="w")
            self._rows[spec.identifier] = _EntryWidgets(
                container=frame, checkbox=checkbox, enabled_var=enabled_var
            )

    def _save(self) -> None:
        for spec in self._specs:
            widgets = self._rows.get(spec.identifier)
            if widgets is None:
                continue
            spec.enabled = bool(widgets.enabled_var.get())
        registry.save_registry(self._specs)
        if self._on_save is not None:
            self._on_save()

    def _show_add_dialog(self) -> None:
        dialog = _AddPluginDialog(self, existing_ids={spec.identifier for spec in self._specs})
        self.wait_window(dialog)
        if dialog.result is None:
            return
        self._specs.append(dialog.result)
        self._build_rows()


class _AddPluginDialog(tk.Toplevel):
    """Dialog zum Registrieren eines neuen Plugins."""

    def __init__(self, parent: tk.Misc, existing_ids: set[str]):
        super().__init__(parent)
        self.title("Plugin hinzufügen")
        self.resizable(False, False)
        self.transient(parent)
        self.result: registry.PluginSpec | None = None
        self._existing_ids = existing_ids

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Name").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        self._name_entry = ttk.Entry(self)
        self._name_entry.grid(row=0, column=1, padx=12, pady=(12, 4), sticky="ew")

        ttk.Label(self, text="Modulpfad").grid(row=1, column=0, padx=12, pady=4, sticky="w")
        self._module_entry = ttk.Entry(self)
        self._module_entry.grid(row=1, column=1, padx=12, pady=4, sticky="ew")

        ttk.Label(self, text="Klassenname").grid(row=2, column=0, padx=12, pady=4, sticky="w")
        self._class_entry = ttk.Entry(self)
        self._class_entry.grid(row=2, column=1, padx=12, pady=4, sticky="ew")

        button_row = ttk.Frame(self, padding=(12, 12))
        button_row.grid(row=3, column=0, columnspan=2, sticky="ew")
        button_row.columnconfigure(0, weight=1)

        ttk.Button(button_row, text="Abbrechen", command=self.destroy).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(button_row, text="Hinzufügen", command=self._submit).grid(
            row=0, column=1, sticky="e"
        )

        self._name_entry.focus()

    def _submit(self) -> None:
        name = self._name_entry.get().strip()
        module = self._module_entry.get().strip()
        class_name = self._class_entry.get().strip()

        if not name or not module or not class_name:
            messagebox.showerror("Eingabe fehlt", "Bitte alle Felder ausfüllen.")
            return

        identifier = self._slugify(name)
        if identifier in self._existing_ids:
            messagebox.showerror(
                "Plugin existiert bereits",
                "Der angegebene Name ist schon vorhanden. Bitte wähle einen anderen.",
            )
            return

        self.result = registry.PluginSpec(
            identifier=identifier,
            name=name,
            module=module,
            class_name=class_name,
            enabled=True,
        )
        self.destroy()

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value or "plugin"
