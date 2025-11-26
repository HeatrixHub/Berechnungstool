"""Plugin-Integration für elektrische Leistungsberechnungen."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from app.plugins.base import AppContext, Plugin


class LeistungsrechnerTab(ttk.Frame):
    """Tab für Leistungsberechnungen von ein- und dreiphasigen Systemen."""

    def __init__(self, notebook: ttk.Notebook) -> None:
        super().__init__(notebook, padding=(10, 8))
        self.columnconfigure(0, weight=1)
        notebook.add(self, text="Leistungsrechner")

        header = ttk.Frame(self, padding=(4, 0, 4, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="Elektrische Leistung", 
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Berechnung für ein- und dreiphasige Systeme",
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        content = ttk.Frame(self)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        self._build_single_phase(content)
        self._build_three_phase(content)

    def _build_single_phase(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Einphasig", padding=(10, 8))
        frame.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Formel: P = U × I (Wirklast)").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )

        ttk.Label(frame, text="Spannung U [V]").grid(row=1, column=0, sticky="w", pady=2)
        self._single_voltage = tk.StringVar()
        ttk.Entry(frame, textvariable=self._single_voltage).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        ttk.Label(frame, text="Strom I [A]").grid(row=2, column=0, sticky="w", pady=2)
        self._single_current = tk.StringVar()
        ttk.Entry(frame, textvariable=self._single_current).grid(
            row=2, column=1, sticky="ew", pady=2
        )

        ttk.Button(frame, text="Berechnen", command=self._calculate_single_phase).grid(
            row=3, column=0, columnspan=2, pady=(6, 4)
        )

        self._single_result = tk.StringVar(value="Leistung: –")
        ttk.Label(frame, textvariable=self._single_result, font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(2, 0)
        )

    def _build_three_phase(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Dreiphasig", padding=(10, 8))
        frame.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Formel: P = U × I × √3 (symmetrische Last)").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )

        ttk.Label(frame, text="Außenleiterspannung U [V]").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self._three_voltage = tk.StringVar()
        ttk.Entry(frame, textvariable=self._three_voltage).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        ttk.Label(frame, text="Strom I [A]").grid(row=2, column=0, sticky="w", pady=2)
        self._three_current = tk.StringVar()
        ttk.Entry(frame, textvariable=self._three_current).grid(
            row=2, column=1, sticky="ew", pady=2
        )

        ttk.Button(frame, text="Berechnen", command=self._calculate_three_phase).grid(
            row=3, column=0, columnspan=2, pady=(6, 4)
        )

        self._three_result = tk.StringVar(value="Leistung: –")
        ttk.Label(frame, textvariable=self._three_result, font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(2, 0)
        )

    def _calculate_single_phase(self) -> None:
        voltage = self._parse_value(self._single_voltage)
        current = self._parse_value(self._single_current)
        if voltage is None or current is None:
            self._single_result.set("Leistung: Bitte gültige Zahlen angeben.")
            return
        power = voltage * current
        self._single_result.set(f"Leistung: {power:,.2f} W")

    def _calculate_three_phase(self) -> None:
        voltage = self._parse_value(self._three_voltage)
        current = self._parse_value(self._three_current)
        if voltage is None or current is None:
            self._three_result.set("Leistung: Bitte gültige Zahlen angeben.")
            return
        power = voltage * current * math.sqrt(3)
        self._three_result.set(f"Leistung: {power:,.2f} W")

    @staticmethod
    def _parse_value(value: tk.StringVar) -> float | None:
        try:
            return float(value.get())
        except (ValueError, TypeError):
            return None


class ElektrikPlugin(Plugin):
    """Plugin für grundlegende elektrische Berechnungen."""

    name = "Elektrik"
    version = "v1.0"

    def __init__(self) -> None:
        super().__init__()
        self._inner_notebook: ttk.Notebook | None = None

    def attach(self, context: AppContext) -> None:
        container = ttk.Frame(context.notebook)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        context.notebook.add(container, text=self.name)

        header = ttk.Frame(container, padding=(10, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="Elektrik", 
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=5)
        if self.version:
            ttk.Label(header, text=self.version, font=("Segoe UI", 9)).pack(side="right")

        notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self._inner_notebook = notebook

        LeistungsrechnerTab(notebook)

        footer = ttk.Frame(container, padding=(10, 5))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="© 2025 Heatrix GmbH", 
            font=("Segoe UI", 9),
        ).pack(side="left")
