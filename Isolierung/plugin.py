"""Plugin-Integration für das Isolierungstool."""

from tkinter import ttk

try:
    import sv_ttk
except Exception:  # pragma: no cover - Theme-Bibliothek optional
    sv_ttk = None  # type: ignore[assignment]

from app.plugins.base import AppContext, Plugin
from .tabs.tab1_berechnung_ui import BerechnungTab
from .tabs.tab4_schichtaufbau_ui import SchichtaufbauTab
from .tabs.tab5_zuschnitt_ui import ZuschnittTab


class IsolierungPlugin(Plugin):
    """Stellt die bisherigen Tabs des Isolierungstools als Plugin bereit."""

    name = "Isolierung"
    version = "v1.0"

    def __init__(self) -> None:
        super().__init__()
        self.berechnung_tab: BerechnungTab | None = None
        self.schichtaufbau_tab: SchichtaufbauTab | None = None
        self.zuschnitt_tab: ZuschnittTab | None = None

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
            if self.berechnung_tab is not None and self.schichtaufbau_tab is not None:
                self.berechnung_tab.register_layer_importer(
                    self.schichtaufbau_tab.export_layer_data
                )
                self.schichtaufbau_tab.register_layer_importer(
                    self.berechnung_tab.export_layer_data
                )

            self.zuschnitt_tab = ZuschnittTab(notebook)
            if self.zuschnitt_tab is not None and self.schichtaufbau_tab is not None:
                self.zuschnitt_tab.register_plate_importer(
                    self.schichtaufbau_tab.export_plate_list
                )
        except Exception:
            import traceback

            print("Fehler beim Erstellen der Isolierungstabs:")
            traceback.print_exc()

        footer = ttk.Frame(container, padding=(10, 5))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="© 2025 Heatrix GmbH",
            font=("Segoe UI", 9),
        ).pack(side="left")

    def on_theme_changed(self, theme: str) -> None:  # pragma: no cover - GUI Callback
        if theme not in {"light", "dark"} or not sv_ttk:
            return
        if self.berechnung_tab is not None:
            self.berechnung_tab.update_theme_colors()
        if self.schichtaufbau_tab is not None:
            self.schichtaufbau_tab.update_theme_colors()
        if self.zuschnitt_tab is not None:
            self.zuschnitt_tab.update_theme_colors()

    def export_state(self) -> dict:
        state: dict = {}
        if self.berechnung_tab is not None:
            state["berechnung"] = self.berechnung_tab.export_state()
        if self.schichtaufbau_tab is not None:
            state["schichtaufbau"] = self.schichtaufbau_tab.export_state()
        if self.zuschnitt_tab is not None:
            state["zuschnitt"] = self.zuschnitt_tab.export_state()
        return state

    def import_state(self, state: dict) -> None:
        # Altes Format: Projektzustand kam ausschließlich aus dem Berechnungstab.
        if "berechnung" not in state and "schichtaufbau" not in state:
            state = {"berechnung": state}

        if self.berechnung_tab is not None and "berechnung" in state:
            self.berechnung_tab.load_project_into_ui(state.get("berechnung", {}))
        if self.schichtaufbau_tab is not None and "schichtaufbau" in state:
            self.schichtaufbau_tab.import_state(state.get("schichtaufbau", {}))
        if self.zuschnitt_tab is not None and "zuschnitt" in state:
            self.zuschnitt_tab.import_state(state.get("zuschnitt", {}))
