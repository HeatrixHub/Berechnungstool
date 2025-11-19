"""Plugin-Integration für das Tool Stoffeigenschaften Luft."""

from __future__ import annotations

from tkinter import ttk

from app.plugins.base import AppContext, Plugin
from . import tab1_GUI as tab1
from . import tab2_GUI as tab2
from . import tab3_GUI as tab3


class StoffeigenschaftenLuftPlugin(Plugin):
    """Stellt die drei Tabs des Tools als Plugin für die Host-App bereit."""

    name = "Stoffeigenschaften Luft"
    version = "v2.0"

    def __init__(self) -> None:
        super().__init__()
        self._inner_notebook: ttk.Notebook | None = None

    def attach(self, context: AppContext) -> None:
        self._configure_styles(context.root)

        container = ttk.Frame(context.notebook)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        context.notebook.add(container, text=self.name)

        header = ttk.Frame(container, padding=(10, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="Stoffeigenschaften Luft",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        if self.version:
            ttk.Label(header, text=self.version, font=("Segoe UI", 9)).pack(
                side="right"
            )

        notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self._inner_notebook = notebook

        tab1.create_tab1(notebook)
        tab2.create_tab2(notebook)
        tab3.create_tab3(notebook, self._get_thermal_power_from_tab1)

        footer = ttk.Frame(container, padding=(10, 6))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="© 2025 Heatrix GmbH",
            font=("Segoe UI", 9),
        ).pack(side="left")

    def _configure_styles(self, root) -> None:
        """Richtet Schrifteinstellungen analog zur Stand-alone-App ein."""

        style = ttk.Style()
        style.configure("Standard.TEntry", foreground="black")
        style.configure("Fehler.TEntry", foreground="red")
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12))
        style.configure("TEntry", font=("Arial", 12))
        style.configure("TCheckbutton", font=("Arial", 12))
        style.configure("TCombobox", font=("Arial", 12))
        style.configure("TNotebook.Tab", font=("Arial", 12))

        root.option_add("*TCombobox*Font", "Arial 12")
        root.option_add("*TEntry*Font", "Arial 12")
        root.option_add("*TCheckbutton*Font", "Arial 12")

    def _get_thermal_power_from_tab1(self) -> float | None:
        entries = tab1.get_entries()
        try:
            return float(entries["Wärmeleistung (kW):"].get())
        except (ValueError, KeyError):
            return None
