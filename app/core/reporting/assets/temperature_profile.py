"""Chart asset generation for report renderers."""
from __future__ import annotations

from io import BytesIO

from matplotlib.figure import Figure

from app.core.reporting.report_document import ImageBlock, ReportDocument


def build_temperature_profile_chart(document: ReportDocument) -> bytes | None:
    """Create a PNG chart asset from temperature profile metadata.

    The function reads only renderer-neutral ``ReportDocument`` content and never
    accesses plugin/UI state directly.
    """

    image_block = _find_temperature_image_block(document)
    if image_block is None:
        return None

    thicknesses_mm = _float_list(image_block.metadata.get("thickness_profile_mm"))
    temperatures_c = _float_list(image_block.metadata.get("interface_temperatures_c"))

    if len(temperatures_c) < 2:
        return None

    x_positions = _build_distance_axis(thicknesses_mm, len(temperatures_c))
    if len(x_positions) != len(temperatures_c):
        return None

    figure = Figure(figsize=(7.0, 3.2), dpi=160)
    axis = figure.add_subplot(1, 1, 1)

    _render_layer_background(axis, thicknesses_mm, x_positions)
    axis.plot(x_positions, temperatures_c, color="#111827", linewidth=2.0, marker="o", markersize=3.0, zorder=4)
    _render_interface_markers(axis, x_positions, temperatures_c)

    axis.set_xlabel("Dicke [mm]")
    axis.set_ylabel("Temperatur [°C]")
    axis.grid(True, linestyle="--", linewidth=0.5, alpha=0.45, color="#9ca3af")
    axis.tick_params(axis="x", labelsize=8, colors="#111827")
    axis.tick_params(axis="y", labelsize=8, colors="#111827")

    buffer = BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()


def _find_temperature_image_block(document: ReportDocument) -> ImageBlock | None:
    for section in document.sections:
        if section.id != "temperaturverlauf":
            continue
        for block in section.blocks:
            if isinstance(block, ImageBlock):
                return block
    return None


def _float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []

    items: list[float] = []
    for entry in value:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, (int, float)):
            items.append(float(entry))
            continue
        try:
            items.append(float(str(entry).strip()))
        except (TypeError, ValueError):
            continue
    return items


def _build_distance_axis(thicknesses_mm: list[float], temperature_count: int) -> list[float]:
    if len(thicknesses_mm) >= temperature_count - 1 and temperature_count >= 2:
        cumulative = [0.0]
        for thickness in thicknesses_mm[: temperature_count - 1]:
            cumulative.append(cumulative[-1] + max(thickness, 0.0))
        return cumulative

    return [float(index) for index in range(temperature_count)]


def _render_layer_background(axis: object, thicknesses_mm: list[float], x_positions: list[float]) -> None:
    palette = [
        "#2E5B9A",
        "#C25B4A",
        "#4A8F60",
        "#8D5DA7",
        "#B88731",
        "#2C8A8A",
    ]
    x_start = 0.0
    for index, thickness in enumerate(thicknesses_mm):
        x_end = x_start + max(0.0, float(thickness))
        if x_end > x_start:
            axis.axvspan(x_start, x_end, color=palette[index % len(palette)], alpha=0.28, zorder=1)
        x_start = x_end

    for boundary in x_positions:
        axis.axvline(boundary, color="#4b5563", linewidth=0.8, alpha=0.55, zorder=2)


def _render_interface_markers(axis: object, x_positions: list[float], temperatures_c: list[float]) -> None:
    if not x_positions or not temperatures_c:
        return
    t_min = min(temperatures_c)
    t_max = max(temperatures_c)
    span = max(1.0, t_max - t_min)
    label_offset = max(1.2, span * 0.05)
    y_margin = max(3.5, span * 0.16)

    for x_pos, temperature in zip(x_positions, temperatures_c, strict=False):
        axis.text(
            x_pos,
            temperature + label_offset,
            f"{temperature:.1f}".replace(".", ",") + " °C",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color="#111827",
            bbox={"facecolor": "#ffffff", "alpha": 0.86, "edgecolor": "none", "pad": 1.0},
            zorder=5,
            clip_on=False,
        )

    axis.set_xlim(0.0, x_positions[-1])
    axis.set_ylim(t_min - y_margin, t_max + y_margin + label_offset)
