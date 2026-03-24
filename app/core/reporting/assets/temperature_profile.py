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
    axis.plot(x_positions, temperatures_c, color="#1e40af", linewidth=2.0, marker="o", markersize=3.2)
    axis.set_xlabel("Abstand durch Isolierung [mm]")
    axis.set_ylabel("Temperatur [°C]")
    axis.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
    axis.set_title("Temperaturverlauf", fontsize=11)

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
