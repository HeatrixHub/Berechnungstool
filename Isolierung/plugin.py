"""Plugin-Integration für das Isolierungstool in der neuen Architektur."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.core.resources import IsolationRecord
from app.plugins.base import AppContext, Plugin


class IsolierungPlugin(Plugin):
    """Stellt eine berechnungszentrierte Oberfläche bereit."""

    name = "Isolierung"
    version = "v2.0"

    def __init__(self) -> None:
        super().__init__()
        self._result_var = tk.StringVar(value="Keine Berechnung durchgeführt")
        self._context: AppContext | None = None

    def attach(self, context: AppContext) -> None:
        self._context = context
        container = ttk.Frame(context.notebook, padding=(16, 12))
        context.notebook.add(container, text=self.name)

        ttk.Label(
            container, text="Isolierungsberechnung", font=("Segoe UI", 16, "bold")
        ).grid(row=0, column=0, sticky="w")

        form = ttk.Frame(container)
        form.grid(row=1, column=0, sticky="nsew", pady=(16, 8))
        container.columnconfigure(0, weight=1)

        labels = [
            "Fläche [m²]",
            "Temperaturdifferenz [K]",
            "Leitfähigkeit λ [W/mK]",
            "Dicke [mm]",
        ]
        self._entries: list[ttk.Entry] = []
        default_values = ["10", "35", "0.035", "80"]
        for row, (label, default) in enumerate(zip(labels, default_values)):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(form)
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
            self._entries.append(entry)
        form.columnconfigure(1, weight=1)

        ttk.Button(
            container, text="Berechnung starten", command=self._calculate
        ).grid(row=2, column=0, sticky="w")

        ttk.Label(container, textvariable=self._result_var, font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )

        buttons = ttk.Frame(container, padding=(0, 16, 0, 0))
        buttons.grid(row=4, column=0, sticky="w")
        ttk.Button(
            buttons, text="Im Projekt speichern", command=self._store_in_project
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="In Isolierungsdatenbank übernehmen",
            command=self._store_in_library,
        ).pack(side="left", padx=8)
        ttk.Button(
            buttons, text="Zum Bericht hinzufügen", command=self._add_to_report
        ).pack(side="left")

    def _calculate(self) -> None:
        try:
            area = float(self._entries[0].get())
            delta_t = float(self._entries[1].get())
            conductivity = float(self._entries[2].get())
            thickness_mm = float(self._entries[3].get())
        except ValueError:
            self._result_var.set("Ungültige Eingabe – bitte Zahlen verwenden.")
            return
        thickness_m = thickness_mm / 1000.0
        heat_loss = conductivity / thickness_m * area * delta_t
        self._result_var.set(
            f"Wärmeverlust: {heat_loss:,.0f} W (Dicke {thickness_mm:.1f} mm)"
        )

    def _store_in_project(self) -> None:
        if not self._context:
            return
        project_state = {
            "area": self._entries[0].get(),
            "delta_t": self._entries[1].get(),
            "conductivity": self._entries[2].get(),
            "thickness_mm": self._entries[3].get(),
            "result": self._result_var.get(),
        }
        self._context.project_manager.update_plugin_state(self.name, project_state)

    def _store_in_library(self) -> None:
        if not self._context:
            return
        try:
            thickness = float(self._entries[3].get())
        except ValueError:
            self._result_var.set("Bitte gültige Werte eingeben, bevor gespeichert wird.")
            return
        record = IsolationRecord(
            name=f"Isolierung {self._entries[0].get()} m²",
            material="Projektmaterial",
            thickness_mm=thickness,
            metadata={"delta_t": self._entries[1].get()},
        )
        self._context.isolation_library.upsert(record)

    def _add_to_report(self) -> None:
        if not self._context:
            return
        self._context.report_manager.submit_contribution(
            plugin_name=self.name,
            section_id="isolierung-ergebnis",
            title="Isolierungsberechnung",
            content=self._result_var.get() or "Keine Daten",
        )

    def on_theme_changed(self, theme: str) -> None:  # pragma: no cover - GUI Callback
        del theme
