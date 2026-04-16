"""Dedizierter Report-Builder für Schichtaufbau und Zuschnitt des Isolierungs-Plugins."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from app.core.reporting.report_document import (
    MetricItem,
    MetricsBlock,
    ReportDocument,
    ReportMetadata,
    ReportSection,
    TableBlock,
    TableColumn,
    TableRow,
    TextBlock,
)

SCHICHTAUFBAU_ZUSCHNITT_REPORT_TITLE = "Schichtaufbau und Zuschnittplanung der Isolierung"


def build_isolierung_schichtaufbau_zuschnitt_report(
    plugin_state: Mapping[str, Any] | None,
    *,
    title: str = SCHICHTAUFBAU_ZUSCHNITT_REPORT_TITLE,
    project_name: str = "Unbenanntes Projekt",
    author: str = "Unbekannt",
    additional_info: Mapping[str, str] | None = None,
) -> ReportDocument:
    """Erzeuge ein ReportDocument für Schichtaufbau- und Zuschnittsergebnisse."""

    state = _as_mapping(plugin_state)
    metadata = ReportMetadata(
        title=_first_non_empty(title, SCHICHTAUFBAU_ZUSCHNITT_REPORT_TITLE),
        project_name=_first_non_empty(project_name, "Unbenanntes Projekt"),
        author=_first_non_empty(author, "Unbekannt"),
        created_at=datetime.now(timezone.utc),
        additional_info=dict(additional_info or {}),
    )

    return ReportDocument(
        metadata=metadata,
        tags=["isolierung", "schichtaufbau", "zuschnitt"],
        sections=[
            _build_layer_construction_section(state),
            _build_cutting_section(state),
        ],
    )


def _build_layer_construction_section(state: Mapping[str, Any]) -> ReportSection:
    build_inputs = _nested(_nested(state, "inputs"), "schichtaufbau")
    build_results = _nested(_nested(state, "results"), "schichtaufbau")
    build_data = _nested(build_results, "data")

    measure_type = _as_text(build_inputs.get("measure_type"), "outer")
    dimension_metrics = _dimension_metrics(measure_type, build_inputs, build_data)
    plate_rows = _layer_plate_rows(build_data)

    blocks: list[MetricsBlock | TableBlock | TextBlock] = [
        MetricsBlock(title="Maßübersicht", metrics=dimension_metrics),
        _table(
            title="Schichtaufbau-Platten",
            columns=[
                TableColumn("layer", "Schicht", value_type="integer"),
                TableColumn("material", "Material"),
                TableColumn("plate", "Platte"),
                TableColumn("length", "Länge", unit="mm", value_type="number"),
                TableColumn("width", "Breite", unit="mm", value_type="number"),
                TableColumn("height", "Höhe", unit="mm", value_type="number"),
            ],
            rows=plate_rows,
        ),
    ]

    if not plate_rows:
        blocks.append(TextBlock(text="Für den Schichtaufbau liegen derzeit keine Plattenpositionen vor."))

    return ReportSection(
        id="schichtaufbau-ergebnisse",
        title="Schichtaufbau",
        description="Maß- und Schichtübersicht basierend auf den Daten aus dem Bereich Schichtaufbau.",
        blocks=blocks,
    )


def _build_cutting_section(state: Mapping[str, Any]) -> ReportSection:
    cut_results = _nested(_nested(state, "results"), "zuschnitt")

    summary_rows: list[dict[str, Any]] = []
    for entry in _as_sequence(cut_results.get("summary"))[:512]:
        if not isinstance(entry, Mapping):
            continue
        summary_rows.append(
            {
                "material": _as_text(entry.get("material"), "–"),
                "count": _to_int_or_none(entry.get("count")),
                "cost": _cost_value(entry),
            }
        )

    blocks: list[TableBlock | TextBlock] = []
    if summary_rows:
        blocks.append(
            _table(
                title="Rohlingsübersicht",
                columns=[
                    TableColumn("material", "Material"),
                    TableColumn("count", "Rohlinge", value_type="integer"),
                    TableColumn("cost", "Gesamtkosten", unit="€", value_type="number"),
                ],
                rows=summary_rows,
            )
        )
    else:
        blocks.append(
            TextBlock(
                text=(
                    "Für den Zuschnitt liegen derzeit keine berechneten Rohlinge vor. "
                    "Die Rohlingsübersicht wird nach erfolgter Berechnung automatisch ergänzt."
                )
            )
        )

    return ReportSection(
        id="zuschnitt-ergebnisse",
        title="Zuschnitt",
        description="Zusammenfassung der berechneten Rohlinge und Kosten für den Zuschnitt.",
        blocks=blocks,
    )


def _dimension_metrics(
    measure_type: str,
    build_inputs: Mapping[str, Any],
    build_data: Mapping[str, Any],
) -> list[MetricItem]:
    dimensions = _nested(build_inputs, "dimensions")

    if measure_type == "inner":
        given_prefix = "given_inner"
        calc_prefix = "calculated_outer"
        given_label = "Gegebenes Innenmaß"
        calc_label = "Berechnetes Außenmaß"
    else:
        given_prefix = "given_outer"
        calc_prefix = "calculated_inner"
        given_label = "Gegebenes Außenmaß"
        calc_label = "Berechnetes Innenmaß"

    metrics: list[MetricItem] = []
    for axis in ("L", "B", "H"):
        axis_lower = axis.lower()
        metrics.append(
            MetricItem(
                key=f"{given_prefix}_{axis_lower}",
                label=f"{given_label} {axis}",
                value=_to_number_or_none(dimensions.get(axis)),
                unit="mm",
                format_hint="number",
            )
        )

    calculated_map = {
        "L": _to_number_or_none(build_data.get("li_l" if measure_type != "inner" else "la_l")),
        "B": _to_number_or_none(build_data.get("li_b" if measure_type != "inner" else "la_b")),
        "H": _to_number_or_none(build_data.get("li_h" if measure_type != "inner" else "la_h")),
    }
    for axis in ("L", "B", "H"):
        axis_lower = axis.lower()
        metrics.append(
            MetricItem(
                key=f"{calc_prefix}_{axis_lower}",
                label=f"{calc_label} {axis}",
                value=calculated_map[axis],
                unit="mm",
                format_hint="number",
            )
        )
    return metrics


def _layer_plate_rows(build_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    materials = [
        _as_text(item, "")
        for item in _as_sequence(build_data.get("isolierungen"))[:512]
    ]

    rows: list[dict[str, Any]] = []
    for layer in _as_sequence(build_data.get("layers"))[:512]:
        if not isinstance(layer, Mapping):
            continue
        layer_index = _to_int_or_none(layer.get("layer_index"))
        material = "–"
        if isinstance(layer_index, int) and layer_index > 0 and layer_index - 1 < len(materials):
            material = _first_non_empty(materials[layer_index - 1], "–")
        for plate in _as_sequence(layer.get("plates"))[:128]:
            if not isinstance(plate, Mapping):
                continue
            rows.append(
                {
                    "layer": layer_index,
                    "material": material,
                    "plate": _first_non_empty(_as_text(plate.get("name"), ""), "–"),
                    "length": _to_number_or_none(plate.get("L")),
                    "width": _to_number_or_none(plate.get("B")),
                    "height": _to_number_or_none(plate.get("H")),
                }
            )
    return rows


def _cost_value(entry: Mapping[str, Any]) -> float | None:
    display = _as_text(entry.get("cost_display"), "")
    if display and display != "–":
        return _to_number_or_none(entry.get("cost"))
    return _to_number_or_none(entry.get("cost"))


def _table(*, title: str, columns: list[TableColumn], rows: list[dict[str, Any]]) -> TableBlock:
    normalized_rows = [TableRow(cells={column.key: row.get(column.key) for column in columns}) for row in rows]
    return TableBlock(title=title, columns=columns, rows=normalized_rows)


def _nested(mapping: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _first_non_empty(*candidates: object) -> str:
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return ""


def _to_number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
