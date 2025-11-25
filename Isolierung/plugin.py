"""Plugin-Integration für das Isolierungstool."""

import tkinter as tk
from tkinter import ttk

try:
    import sv_ttk
except Exception:  # pragma: no cover - Theme-Bibliothek optional
    sv_ttk = None  # type: ignore[assignment]

from app.plugins.base import AppContext, Plugin
from .tabs.tab1_berechnung_ui import BerechnungTab
from .tabs.tab3_bericht_ui import BerichtTab
from .tabs.tab4_schichtaufbau_ui import SchichtaufbauTab


class IsolierungPlugin(Plugin):
    """Stellt die bisherigen Tabs des Isolierungstools als Plugin bereit."""

    name = "Isolierung"
    version = "v1.0"

    def __init__(self) -> None:
        super().__init__()
        self.berechnung_tab: BerechnungTab | None = None
        self.schichtaufbau_tab: SchichtaufbauTab | None = None
        self.bericht_tab: BerichtTab | None = None

    def attach(self, context: AppContext) -> None:
        container = ttk.Frame(context.notebook)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        context.notebook.add(container, text=self.name)

        header = ttk.Frame(container, padding=(10, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="Heatrix Isolierungsberechnung",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=5)
        ttk.Label(
            header,
            text=self.version or "",
            font=("Segoe UI", 9),
        ).pack(side="right")

        notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        try:
            self.berechnung_tab = BerechnungTab(notebook)
            self.schichtaufbau_tab = SchichtaufbauTab(notebook)
            self.bericht_tab = BerichtTab(notebook)
        except Exception:
            import traceback

            print("Fehler beim Erstellen der Isolierungstabs:")
            traceback.print_exc()

        notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        footer = ttk.Frame(container, padding=(10, 5))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="© 2025 Heatrix GmbH",
            font=("Segoe UI", 9),
        ).pack(side="left")

    def on_tab_changed(self, event: tk.Event) -> None:
        notebook = event.widget
        selected_tab = notebook.nametowidget(notebook.select())

        if (
            self.bericht_tab is not None
            and selected_tab == self.bericht_tab.scrollable.master
        ):
            self.bericht_tab.refresh_project_list()
            print("[Auto-Update] Tab 3 (Bericht) aktualisiert.")

    def on_theme_changed(self, theme: str) -> None:  # pragma: no cover - GUI Callback
        if theme not in {"light", "dark"} or not sv_ttk:
            return
        if self.berechnung_tab is not None:
            self.berechnung_tab.update_theme_colors()
        if self.schichtaufbau_tab is not None:
            self.schichtaufbau_tab.update_theme_colors()
        if self.bericht_tab is not None and hasattr(
            self.bericht_tab, "update_theme_colors"
        ):
            self.bericht_tab.update_theme_colors()

    def export_state(self) -> dict:
        if self.berechnung_tab is None:
            return {}
        return self.berechnung_tab.export_state()

    def import_state(self, state: dict) -> None:
        if self.berechnung_tab is None:
            return
        self.berechnung_tab.load_project_into_ui(state)
