"""Global Qt tab for PDF report generation."""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QWidget,
)

from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.ui_helpers import (
    create_button_row,
    create_page_layout,
    make_hbox,
)


@dataclass(frozen=True)
class _ReportTemplateSpec:
    name: str
    path: Path


class ReportTab:
    """Global tab for building PDF reports from current plugin states."""

    def __init__(
        self,
        tab_widget: object,
        plugin_manager: QtPluginManager,
        *,
        title: str = "Bericht",
    ) -> None:
        self._tab_widget = tab_widget
        self._plugin_manager = plugin_manager
        self._report_logger = logging.getLogger(__name__)

        self._report_templates: list[_ReportTemplateSpec] = []
        self._report_current_text: str = ""
        self._report_template_combo: object | None = None
        self._report_preview: object | None = None
        self._report_status_label: object | None = None

        self.widget = QWidget()
        self._build_ui()
        self._insert_tab(title)
        self._discover_report_templates()
        self._update_report_preview()

        if hasattr(self._tab_widget, "currentChanged"):
            self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def _insert_tab(self, title: str) -> None:
        if isinstance(self._tab_widget, QTabWidget):
            self._tab_widget.insertTab(1, self.widget, title)
        else:
            self._tab_widget.addTab(self.widget, title)

    def _build_ui(self) -> None:
        layout = create_page_layout(self.widget, "Bericht", show_logo=True)

        template_layout = make_hbox()
        template_layout.addWidget(QLabel("Template"))
        self._report_template_combo = QComboBox()
        self._report_template_combo.currentIndexChanged.connect(self._update_report_preview)
        template_layout.addWidget(self._report_template_combo)
        refresh_button = QPushButton("Templates aktualisieren")
        refresh_button.clicked.connect(self._discover_report_templates)
        template_layout.addWidget(refresh_button)
        template_layout.addStretch()
        layout.addLayout(template_layout)

        preview_button = QPushButton("Vorschau aktualisieren")
        preview_button.clicked.connect(self._update_report_preview)
        export_button = QPushButton("PDF exportieren")
        export_button.clicked.connect(self._on_report_export_pdf)
        action_layout = create_button_row([preview_button, export_button])
        layout.addLayout(action_layout)

        self._report_preview = QTextBrowser()
        self._report_preview.setOpenExternalLinks(False)
        preview_font = QFont("Courier New")
        preview_font.setStyleHint(QFont.Monospace)
        self._report_preview.setFont(preview_font)
        layout.addWidget(self._report_preview)

        self._report_status_label = QLabel()
        self._report_status_label.setWordWrap(True)
        layout.addWidget(self._report_status_label)

    def _discover_report_templates(self) -> None:
        self._report_templates = []
        report_dir = self._resolve_report_directory()
        if report_dir is not None and report_dir.exists():
            for template_path in sorted(report_dir.glob("*.j2")):
                self._report_templates.append(
                    _ReportTemplateSpec(name=template_path.stem, path=template_path)
                )
        if self._report_template_combo is not None:
            current_name = self._report_template_combo.currentText()
            with QSignalBlocker(self._report_template_combo):
                self._report_template_combo.clear()
                for spec in self._report_templates:
                    self._report_template_combo.addItem(spec.name)
            if current_name:
                index = self._report_template_combo.findText(current_name)
                if index >= 0:
                    self._report_template_combo.setCurrentIndex(index)
        if not self._report_templates:
            self._set_report_status(
                "Keine Templates gefunden. Lege .j2-Dateien in Isolierung/reports ab."
            )
        else:
            self._set_report_status("Templates geladen. Vorschau aktualisieren, um den Bericht zu sehen.")

    def _resolve_report_directory(self) -> Path | None:
        module = importlib.import_module("Isolierung")
        module_file = getattr(module, "__file__", None)
        if not module_file:
            return None
        return Path(module_file).resolve().parent / "reports"

    def _current_report_template(self) -> _ReportTemplateSpec | None:
        if not self._report_templates:
            return None
        if self._report_template_combo is None:
            return self._report_templates[0]
        name = self._report_template_combo.currentText()
        for spec in self._report_templates:
            if spec.name == name:
                return spec
        return self._report_templates[0]

    def _update_report_preview(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            self._set_report_preview_text("Keine Report-Templates gefunden.")
            self._set_report_status("Keine Templates verfügbar.")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="report-preview-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
        except Exception as exc:
            self._set_report_preview_text(f"Bericht konnte nicht erstellt werden:\n{exc}")
            self._set_report_status("Bericht konnte nicht aktualisiert werden.")
            return
        self._report_current_text = rendered
        self._set_report_preview_text(rendered)
        self._set_report_status("Bericht aktualisiert.")

    def _set_report_preview_text(self, text: str) -> None:
        if self._report_preview is None:
            return
        self._report_preview.setPlainText(text)

    def _set_report_status(self, message: str) -> None:
        if self._report_status_label is None:
            return
        self._report_status_label.setText(message)

    def _on_report_export_pdf(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            QMessageBox.warning(self.widget, "Hinweis", "Keine Report-Templates gefunden.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "PDF speichern",
            "",
            "PDF (*.pdf);;Alle Dateien (*.*)",
        )
        if not path:
            return
        try:
            with tempfile.TemporaryDirectory(prefix="report-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
                self._report_current_text = rendered
                self._set_report_preview_text(rendered)
                self._write_report_pdf(Path(path), [(f"Bericht – {spec.name}", rendered)])
        except Exception as exc:
            QMessageBox.critical(
                self.widget,
                "Fehler",
                f"Der Bericht konnte nicht erstellt werden:\n{exc}",
            )
            return
        self._set_report_status(f"Bericht gespeichert unter {path}.")
        QMessageBox.information(self.widget, "Fertig", "Der Bericht wurde erstellt.")

    def _render_report_template(self, spec: _ReportTemplateSpec, resource_dir: Path) -> str:
        project, plugin_states = self._build_report_context()
        env = Environment(
            loader=FileSystemLoader(spec.path.parent),
            autoescape=False,
            undefined=StrictUndefined,
        )
        template = env.get_template(spec.path.name)
        context = {"project": project, "plugin_states": plugin_states}
        context |= self._augment_report_context(plugin_states, resource_dir)
        rendered = template.render(context)
        return rendered

    def _build_report_context(self) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        project = {
            "name": "Aktuelle Eingaben",
            "author": "",
            "created_at": "",
            "updated_at": "",
        }
        plugin_states = self._plugin_manager.export_all_states()
        report_states: dict[str, dict[str, Any]] = {}
        report_states.update(self._build_isolierung_report_state(plugin_states.get("isolierung", {})))
        for plugin_id, state in plugin_states.items():
            if plugin_id == "isolierung":
                continue
            if isinstance(state, dict):
                report_states[plugin_id] = dict(state)
        return project, report_states

    def _build_isolierung_report_state(self, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if not isinstance(state, dict):
            return {}
        inputs = state.get("inputs", {})
        results = state.get("results", {})
        calc_inputs = inputs.get("berechnung", {}) if isinstance(inputs, dict) else {}
        calc_layers = calc_inputs.get("layers", []) if isinstance(calc_inputs, dict) else []
        thicknesses: list[float] = []
        families: list[str] = []
        variants: list[str] = []
        if isinstance(calc_layers, list):
            for layer in calc_layers:
                if not isinstance(layer, dict):
                    continue
                thicknesses.append(self._float_or_zero(layer.get("thickness")))
                families.append(self._coerce_str(layer.get("family", "")))
                variants.append(self._coerce_str(layer.get("variant", "")))
        berechnung: dict[str, Any] = {
            "name": "",
            "layer_count": len(thicknesses),
            "thicknesses": thicknesses,
            "isolierungen": families,
            "varianten": variants,
            "T_left": self._float_or_zero(calc_inputs.get("T_left")),
            "T_inf": self._float_or_zero(calc_inputs.get("T_inf")),
            "h": self._float_or_zero(calc_inputs.get("h")),
        }
        calc_results = results.get("berechnung", {}) if isinstance(results, dict) else {}
        if isinstance(calc_results, dict) and calc_results.get("status") == "ok":
            data = calc_results.get("data")
            if isinstance(data, dict):
                berechnung["result"] = dict(data)

        build_inputs = inputs.get("schichtaufbau", {}) if isinstance(inputs, dict) else {}
        build_layers = build_inputs.get("layers", []) if isinstance(build_inputs, dict) else []
        build_thicknesses: list[float] = []
        build_families: list[str] = []
        if isinstance(build_layers, list):
            for layer in build_layers:
                if not isinstance(layer, dict):
                    continue
                build_thicknesses.append(self._float_or_zero(layer.get("thickness")))
                build_families.append(self._coerce_str(layer.get("family", "")))
        dimensions = build_inputs.get("dimensions", {}) if isinstance(build_inputs, dict) else {}
        if not isinstance(dimensions, dict):
            dimensions = {}
        schichtaufbau: dict[str, Any] = {
            "measure_type": self._coerce_str(build_inputs.get("measure_type", "")),
            "dimensions": {
                "L": self._float_or_zero(dimensions.get("L")),
                "B": self._float_or_zero(dimensions.get("B")),
                "H": self._float_or_zero(dimensions.get("H")),
            },
            "layers": {
                "thicknesses": build_thicknesses,
                "isolierungen": build_families,
            },
        }
        build_results = results.get("schichtaufbau", {}) if isinstance(results, dict) else {}
        if isinstance(build_results, dict) and build_results.get("status") == "ok":
            data = build_results.get("data")
            if isinstance(data, dict):
                schichtaufbau["result"] = dict(data)

        zuschnitt_inputs = inputs.get("zuschnitt", {}) if isinstance(inputs, dict) else {}
        zuschnitt_results = results.get("zuschnitt", {}) if isinstance(results, dict) else {}
        zuschnitt_status = self._coerce_str(zuschnitt_results.get("status", "idle"))
        material_summary: list[dict[str, Any]] = []
        summary = zuschnitt_results.get("summary", [])
        if isinstance(summary, list):
            for entry in summary:
                if not isinstance(entry, dict):
                    continue
                if entry.get("is_total"):
                    continue
                material_summary.append(
                    {
                        "material": entry.get("material", "–"),
                        "count": entry.get("count"),
                        "price": entry.get("price"),
                        "cost": entry.get("cost"),
                    }
                )
        zuschnitt: dict[str, Any] = {
            "status": zuschnitt_status,
            "message": self._coerce_str(zuschnitt_results.get("message", "")),
            "kerf": self._float_or_zero(zuschnitt_inputs.get("kerf")),
            "cached_plates": list(zuschnitt_inputs.get("cached_plates", []))
            if isinstance(zuschnitt_inputs, dict)
            else [],
            "placements": list(zuschnitt_results.get("placements", []))
            if zuschnitt_status == "ok"
            else [],
            "material_summary": material_summary,
            "total_cost": zuschnitt_results.get("total_cost"),
            "total_bin_count": zuschnitt_results.get("total_bin_count"),
        }
        return {
            "isolierung": {
                "berechnung": berechnung,
                "schichtaufbau": schichtaufbau,
                "zuschnitt": zuschnitt,
            }
        }

    def _write_report_pdf(self, target: Path, sections: list[tuple[str, str]]) -> None:
        doc = SimpleDocTemplate(str(target), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for title, content in sections:
            story.append(Paragraph(title, styles["Heading1"]))
            story.append(Spacer(1, 12))
            for block in self._to_flowables(content, styles):
                story.append(block)
        doc.build(story)

    def _to_flowables(self, content: str, styles) -> list[Any]:
        sanitized = content.strip()
        if not sanitized:
            return [Paragraph("(keine Daten)", styles["Normal"])]
        elements: list[Any] = []
        blocks = sanitized.split("\n\n")
        for index, raw_block in enumerate(blocks):
            block = raw_block.strip()
            image = self._parse_image_block(block)
            if image is not None:
                elements.append(image)
            else:
                try:
                    clean_block = self._sanitize_block(block)
                    elements.append(Paragraph(clean_block.replace("\n", "<br/>"), styles["Normal"]))
                except Exception as exc:
                    self._report_logger.warning(
                        "Ungültiger Absatz im Bericht: %s", block, exc_info=exc
                    )
                    elements.append(Paragraph("(keine Daten)", styles["Normal"]))
            if index < len(blocks) - 1:
                elements.append(Spacer(1, 8))
        return elements

    def _parse_image_block(self, block: str) -> Image | None:
        align = None
        para_match = re.fullmatch(r"<para([^>]*)>(.*)</para>", block, flags=re.IGNORECASE | re.DOTALL)
        if para_match:
            attr_text = para_match.group(1)
            align_match = re.search(r"align=\"?([a-zA-Z]+)\"?", attr_text or "")
            if align_match:
                align = align_match.group(1).upper()
            block = para_match.group(2).strip()

        img_match = re.fullmatch(r"<img\s+[^>]*src=\"([^\"]+)\"[^>]*>", block, flags=re.IGNORECASE)
        if not img_match:
            return None
        src = img_match.group(1)
        width = self._extract_dimension(block, "width")
        height = self._extract_dimension(block, "height")
        try:
            image = Image(src, width=width, height=height)
        except Exception as exc:
            self._report_logger.warning("Bild konnte nicht geladen werden: %s", src, exc_info=exc)
            return None
        if align in {"LEFT", "CENTER", "RIGHT"}:
            image.hAlign = align
        return image

    @staticmethod
    def _sanitize_block(block: str) -> str:
        without_font = re.sub(r"</?font[^>]*>", "", block, flags=re.IGNORECASE)
        without_para = re.sub(r"</?para[^>]*>", "", without_font, flags=re.IGNORECASE)
        cleaned = without_para.strip()
        return cleaned or "(keine Daten)"

    @staticmethod
    def _extract_dimension(block: str, name: str) -> float | None:
        match = re.search(rf"{name}=\"?([0-9.]+)\"?", block, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _augment_report_context(
        self, plugin_states: dict[str, dict[str, Any]], resource_dir: Path
    ) -> dict[str, dict[str, Any]]:
        iso_state = plugin_states.get("isolierung", {})
        berechnung = iso_state.get("berechnung", {})
        result = berechnung.get("result")
        if not berechnung or not result:
            return {}
        thicknesses = berechnung.get("thicknesses") or []
        temperatures = result.get("interface_temperatures") or []
        if not thicknesses or len(temperatures) != len(thicknesses) + 1:
            return {}
        plot_path = resource_dir / "isolierung_temperature_plot.png"
        try:
            self._make_temperature_plot(thicknesses, temperatures, plot_path)
        except Exception:
            return {}
        enriched_berechnung = dict(berechnung)
        enriched_berechnung["temperature_plot"] = str(plot_path)
        updated_plugin_states = dict(plugin_states)
        updated_iso_state = dict(iso_state)
        updated_iso_state["berechnung"] = enriched_berechnung
        updated_plugin_states["isolierung"] = updated_iso_state
        return {"plugin_states": updated_plugin_states}

    def _make_temperature_plot(
        self, thicknesses: Iterable[float], temperatures: Iterable[float], target: Path
    ) -> None:
        plt.switch_backend("Agg")
        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        total_x = [0.0]
        for thickness in thicknesses:
            total_x.append(total_x[-1] + float(thickness))

        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("report_cmap", colors, N=256)
        ax.plot(total_x, list(temperatures), linewidth=2, marker="o", color="#111827")

        x_pos = 0.0
        thickness_list = list(thicknesses)
        for index, thickness in enumerate(thickness_list):
            color_value = index / max(len(thickness_list) - 1, 1)
            ax.axvspan(x_pos, x_pos + thickness, color=cmap(color_value), alpha=0.35)
            x_pos += thickness

        for x, temp in zip(total_x, temperatures):
            ax.text(
                x,
                temp + 5,
                f"{float(temp):.0f}°C",
                ha="center",
                fontsize=8,
                bbox=dict(facecolor="#ffffff", alpha=0.8, edgecolor="none"),
                color="#111827",
            )

        ax.set_xlabel("Dicke [mm]", color="#111827")
        ax.set_ylabel("Temperatur [°C]", color="#111827")
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=11, color="#111827")
        ax.grid(True, linestyle="--", alpha=0.5, color="#9ca3af")
        ax.tick_params(axis="x", colors="#111827", labelsize=8)
        ax.tick_params(axis="y", colors="#111827", labelsize=8)
        fig.tight_layout()
        fig.savefig(target, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _coerce_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _float_or_zero(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (float, int)):
            return float(value)
        try:
            text = str(value).strip().replace(",", ".")
            return float(text)
        except ValueError:
            return 0.0

    def _on_tab_changed(self, index: int) -> None:
        if not hasattr(self._tab_widget, "indexOf"):
            return
        if self._tab_widget.indexOf(self.widget) == index:
            self._update_report_preview()
