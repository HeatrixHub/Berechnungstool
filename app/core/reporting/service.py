"""Shared report rendering and PDF export services."""
from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


class ReportingService:
    """Service for template-based report preview rendering and PDF export."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def build_plugin_states(
        self, plugin_states: dict[str, dict[str, Any]], resource_dir: Path | None = None
    ) -> dict[str, dict[str, Any]]:
        report_states: dict[str, dict[str, Any]] = {}
        report_states.update(self._build_isolierung_report_state(plugin_states.get("isolierung", {})))
        for plugin_id, state in plugin_states.items():
            if plugin_id == "isolierung":
                continue
            if isinstance(state, dict):
                report_states[plugin_id] = dict(state)

        if resource_dir is None:
            return report_states

        return self._augment_with_temperature_plot(report_states, resource_dir)

    def render_preview(self, context: dict[str, Any], template: Path) -> str:
        """Render a report preview from template and context."""
        env = Environment(
            loader=FileSystemLoader(template.parent),
            autoescape=False,
            undefined=StrictUndefined,
        )
        jinja_template = env.get_template(template.name)
        return jinja_template.render(context)

    def export_pdf(self, sections: list[tuple[str, str]], path: Path) -> None:
        """Export report sections to a PDF file."""
        doc = SimpleDocTemplate(str(path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for title, content in sections:
            story.append(Paragraph(title, styles["Heading1"]))
            story.append(Spacer(1, 12))
            for block in self._to_flowables(content, styles):
                story.append(block)
        doc.build(story)

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
            "placements": list(zuschnitt_results.get("placements", [])) if zuschnitt_status == "ok" else [],
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
                    self._logger.warning("Ungültiger Absatz im Bericht: %s", block, exc_info=exc)
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
            self._logger.warning("Bild konnte nicht geladen werden: %s", src, exc_info=exc)
            return None
        if align in {"LEFT", "CENTER", "RIGHT"}:
            image.hAlign = align
        return image

    def _augment_with_temperature_plot(
        self, plugin_states: dict[str, dict[str, Any]], resource_dir: Path
    ) -> dict[str, dict[str, Any]]:
        iso_state = plugin_states.get("isolierung", {})
        berechnung = iso_state.get("berechnung", {})
        result = berechnung.get("result")
        if not berechnung or not result:
            return plugin_states
        thicknesses = berechnung.get("thicknesses") or []
        temperatures = result.get("interface_temperatures") or []
        if not thicknesses or len(temperatures) != len(thicknesses) + 1:
            return plugin_states
        plot_path = resource_dir / "isolierung_temperature_plot.png"
        try:
            self._make_temperature_plot(thicknesses, temperatures, plot_path)
        except Exception:
            return plugin_states
        enriched_berechnung = dict(berechnung)
        enriched_berechnung["temperature_plot"] = str(plot_path)
        updated_plugin_states = dict(plugin_states)
        updated_iso_state = dict(iso_state)
        updated_iso_state["berechnung"] = enriched_berechnung
        updated_plugin_states["isolierung"] = updated_iso_state
        return updated_plugin_states

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
