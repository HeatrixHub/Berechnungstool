"""Plugin-Integration für das Isolierungstool."""

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Sequence

from tkinter import ttk

try:
    import sv_ttk
except Exception:  # pragma: no cover - Theme-Bibliothek optional
    sv_ttk = None  # type: ignore[assignment]

from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from app.plugins.base import AppContext, Plugin
from app.reporting import (
    PreppyTemplateRenderer,
    ReportBuilder,
    ReportContext,
    ReportTemplateMetadata,
)
from .tabs.tab1_berechnung_logic import perform_calculation, validate_inputs
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
        self._app_context: AppContext | None = None
        self._report_template = Path(__file__).with_name("reporting") / "berechnung.prep"

    def attach(self, context: AppContext) -> None:
        self._app_context = context
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

    # ------------------------------------------------------------------
    # Reporting (Preppy)
    # ------------------------------------------------------------------
    def list_report_templates(self) -> Sequence[ReportTemplateMetadata]:
        return (
            ReportTemplateMetadata(
                template_id="berechnung-a4",
                title="Berechnung – A4",  # noqa: RUF001
                description="Stationäre Wärmedurchgansrechnung durch ebene Wand.",
                suggested_filename="waermedurchgang-berechnung.pdf",
            ),
        )

    def render_report(
        self, template_id: str, builder: "ReportBuilder", context: ReportContext
    ) -> None:
        if template_id != "berechnung-a4":
            raise ValueError(f"Unbekannte Berichtsvorlage: {template_id}")
        if context.plugin_state is None:
            raise ValueError("Keine Daten für den Bericht verfügbar.")

        payload = self._build_report_context(context)
        renderer = PreppyTemplateRenderer(self._report_template)
        renderer.render(builder, payload)

    # ------------------------------------------------------------------
    # Reporting Helfer
    # ------------------------------------------------------------------
    def _build_report_context(self, context: ReportContext) -> Dict[str, Any]:
        state = context.plugin_state or {}
        calc_state = state.get("berechnung") if "berechnung" in state else state
        if not calc_state:
            raise ValueError("Im Projekt sind keine Berechnungsdaten vorhanden.")

        thicknesses = [float(v) for v in calc_state.get("thicknesses", [])]
        materials = calc_state.get("isolierungen", [])
        if not thicknesses or not materials or len(thicknesses) != len(materials):
            raise ValueError(
                "Für die Berichtserstellung werden vollständige Schichtdaten benötigt."
            )

        T_left = float(calc_state.get("T_left", 0.0))
        T_inf = float(calc_state.get("T_inf", 0.0))
        h = float(calc_state.get("h", 0.0))

        result: Dict[str, Any] | None = calc_state.get("result")
        if not result:
            validate_inputs(len(thicknesses), thicknesses, materials, T_left, T_inf, h)
            result = perform_calculation(thicknesses, materials, T_left, T_inf, h)

        interface_temps: List[float] = result.get("interface_temperatures", []) if result else []
        if len(interface_temps) != len(thicknesses) + 1:
            raise ValueError(
                "Die berechneten Grenzflächentemperaturen sind unvollständig und können nicht ausgegeben werden."
            )

        T_avg: List[float] = result.get("T_avg", []) if result else []
        k_avg: List[float] = result.get("k_final", []) if result else []

        layers = self._compile_layers(thicknesses, materials, interface_temps, T_avg, k_avg)
        plot_path = self._render_temperature_plot(thicknesses, interface_temps)

        return {
            "author": self._resolve_author(context),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "project_name": calc_state.get("name", "Projekt ohne Namen"),
            "boundaries": {"T_left": T_left, "T_inf": T_inf, "h": h},
            "summary": {
                "q": result.get("q") if result else None,
                "R_total": result.get("R_total") if result else None,
                "iterations": result.get("iterations") if result else None,
            },
            "layers": layers,
            "plot_path": str(plot_path) if plot_path else None,
        }

    def _compile_layers(
        self,
        thicknesses: List[float],
        materials: Sequence[str],
        interface_temps: List[float],
        T_avg: List[float],
        k_avg: List[float],
    ) -> List[Dict[str, Any]]:
        layers: List[Dict[str, Any]] = []
        for idx, (thickness, name) in enumerate(zip(thicknesses, materials)):
            T_l = interface_temps[idx]
            T_r = interface_temps[idx + 1]
            T_m = T_avg[idx] if idx < len(T_avg) else 0.5 * (T_l + T_r)
            k_m = k_avg[idx] if idx < len(k_avg) else 0.0
            label = f"{idx + 1} ({name})" if name else f"Schicht {idx + 1}"
            layers.append(
                {
                    "label": label,
                    "thickness": thickness,
                    "T_left": T_l,
                    "T_right": T_r,
                    "T_mean": T_m,
                    "k_mean": k_m,
                }
            )
        return layers

    def _render_temperature_plot(
        self, thicknesses: List[float], interface_temps: List[float]
    ) -> Path | None:
        if not thicknesses or not interface_temps:
            return None
        if len(interface_temps) != len(thicknesses) + 1:
            return None

        plt.switch_backend("Agg")

        cumulative: List[float] = [0.0]
        for value in thicknesses:
            cumulative.append(cumulative[-1] + value)

        fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=180)
        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("custom_cmap", colors, N=256)

        ax.plot(cumulative, interface_temps, linewidth=2, marker="o", color="#222222")

        start = 0.0
        for idx, thickness in enumerate(thicknesses):
            fill_color = cmap(idx / max(len(thicknesses) - 1, 1))
            ax.axvspan(start, start + thickness, color=fill_color, alpha=0.35)
            start += thickness

        for x, temp in zip(cumulative, interface_temps):
            ax.text(x, temp + 3, f"{temp:.1f}°C", ha="center", fontsize=8)

        ax.set_xlabel("Dicke [mm]")
        ax.set_ylabel("Temperatur [°C]")
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6, color="gray")

        tmp = NamedTemporaryFile(suffix=".png", delete=False)
        fig.savefig(tmp.name, bbox_inches="tight")
        plt.close(fig)
        return Path(tmp.name)

    def _resolve_author(self, context: ReportContext) -> str:
        if (
            context.source == "project"
            and context.project_id
            and self._app_context is not None
        ):
            record = self._app_context.project_store.load_project(context.project_id)
            if record is not None and record.author:
                return record.author
        return "–"
