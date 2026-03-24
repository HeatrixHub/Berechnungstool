"""Report-Builder für das Isolierungs-Plugin.

Der Builder transformiert exportierten Plugin-State in ein renderer-neutrales
ReportDocument ohne PDF-/HTML-Logik.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from app.core.reporting.report_document import (
    ImageBlock,
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


def build_isolierung_report(
    plugin_state: Mapping[str, Any] | None,
    *,
    title: str = "Technischer Bericht – Isolierung",
    project_name: str = "Unbenanntes Projekt",
    author: str = "Unbekannt",
    additional_info: Mapping[str, str] | None = None,
) -> ReportDocument:
    """Erzeuge ein vollständiges ReportDocument aus exportiertem Plugin-State."""

    state = _as_mapping(plugin_state)
    metadata = ReportMetadata(
        title=title,
        project_name=project_name,
        author=author,
        created_at=datetime.now(timezone.utc),
        additional_info=dict(additional_info or {}),
    )

    return ReportDocument(
        metadata=metadata,
        tags=["isolierung", "technik", "reporting-foundation"],
        sections=[
            _build_overview_section(state),
            _build_calculation_section(state),
            _build_layer_structure_section(state),
            _build_cut_plan_section(state),
        ],
    )


# Rückwärtskompatibles Alias für Schritt 2A.
build_isolierung_report_document = build_isolierung_report


def resolve_isolierung_report_metadata(plugin_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Leite robuste Berichtsmetadaten aus dem exportierten Isolierung-State ab."""

    state = _as_mapping(plugin_state)
    ui_state = _nested(state, "ui")
    return {
        "title": _first_non_empty(ui_state.get("report_title"), "Technischer Bericht – Isolierung"),
        "project_name": _first_non_empty(ui_state.get("project_name"), "Unbenanntes Projekt"),
        "author": _first_non_empty(ui_state.get("author"), "Unbekannt"),
        "additional_info": {
            "Quelle": "Qt-Berichte-Tab",
            "Plugin": "isolierung",
        },
    }


def _build_overview_section(state: Mapping[str, Any]) -> ReportSection:
    inputs = _nested(state, "inputs")
    results = _nested(state, "results")

    calc_status = _as_text(_nested(results, "berechnung").get("status"), "idle")
    build_status = _as_text(_nested(results, "schichtaufbau").get("status"), "idle")
    cut_status = _as_text(_nested(results, "zuschnitt").get("status"), "idle")

    return ReportSection(
        id="overview",
        title="Projektübersicht",
        description="Zusammenfassung der verfügbaren Isolierungsdaten.",
        blocks=[
            MetricsBlock(
                title="Berechnungsstatus",
                metrics=[
                    MetricItem("calc_status", "Isolierungsberechnung", calc_status, format_hint="status"),
                    MetricItem("build_status", "Schichtaufbau", build_status, format_hint="status"),
                    MetricItem("cut_status", "Zuschnittsplan", cut_status, format_hint="status"),
                    MetricItem(
                        "input_layer_count",
                        "Anzahl Eingabeschichten",
                        len(_records_from(_nested(inputs, "berechnung"), "layers")),
                        format_hint="integer",
                    ),
                ],
            )
        ],
    )


def _build_calculation_section(state: Mapping[str, Any]) -> ReportSection:
    calc_inputs = _nested(_nested(state, "inputs"), "berechnung")
    calc_results = _nested(_nested(state, "results"), "berechnung")
    result_data = _nested(calc_results, "data")

    input_table = _table(
        title="Eingangsparameter",
        columns=[
            TableColumn("parameter", "Parameter"),
            TableColumn("value", "Wert", value_type="text"),
        ],
        rows=[
            {"parameter": "T_left", "value": _as_text(calc_inputs.get("T_left"), "–")},
            {"parameter": "T_inf", "value": _as_text(calc_inputs.get("T_inf"), "–")},
            {"parameter": "h", "value": _as_text(calc_inputs.get("h"), "–")},
        ],
    )

    layer_rows: list[dict[str, Any]] = []
    for index, layer in enumerate(_records_from(calc_inputs, "layers"), start=1):
        layer_rows.append(
            {
                "layer": index,
                "thickness_mm": _to_number_or_none(layer.get("thickness")),
                "family": _as_text(layer.get("family"), "–"),
                "variant": _as_text(layer.get("variant"), "–"),
            }
        )

    metrics = MetricsBlock(
        title="Berechnete Kennzahlen",
        metrics=[
            MetricItem("q", "Wärmestrom q", _to_number_or_none(result_data.get("q")), format_hint="number"),
            MetricItem(
                "r_total",
                "Gesamtwärmewiderstand R_total",
                _to_number_or_none(result_data.get("R_total")),
                format_hint="number",
            ),
            MetricItem(
                "iterations",
                "Iterationen",
                _to_int_or_none(result_data.get("iterations")),
                format_hint="integer",
            ),
            MetricItem(
                "interface_temperatures",
                "Grenzflächentemperaturen",
                _numbers_from_sequence(result_data.get("interface_temperatures")),
                unit="°C",
                format_hint="list",
            ),
            MetricItem(
                "t_avg",
                "Mittlere Schichttemperaturen",
                _numbers_from_sequence(result_data.get("T_avg")),
                unit="°C",
                format_hint="list",
            ),
            MetricItem(
                "k_final",
                "k_final",
                _numbers_from_sequence(result_data.get("k_final")),
                unit="W/mK",
                format_hint="list",
            ),
        ],
    )

    return ReportSection(
        id="isolierungsberechnung",
        title="Isolierungsberechnung",
        description="Normierte Übernahme der Eingabe- und Ergebnisdaten aus dem Plugin-State.",
        blocks=[
            input_table,
            _table(
                title="Schichtdaten",
                columns=[
                    TableColumn("layer", "Schicht", value_type="integer"),
                    TableColumn("thickness_mm", "Dicke", unit="mm", value_type="number"),
                    TableColumn("family", "Materialfamilie"),
                    TableColumn("variant", "Variante"),
                ],
                rows=layer_rows,
            ),
            metrics,
            TextBlock(text=_as_text(calc_results.get("message"), "")),
        ],
    )


def _build_layer_structure_section(state: Mapping[str, Any]) -> ReportSection:
    build_inputs = _nested(_nested(state, "inputs"), "schichtaufbau")
    build_results = _nested(_nested(state, "results"), "schichtaufbau")
    result_data = _nested(build_results, "data")

    dimensions = _nested(build_inputs, "dimensions")
    layers_input = _records_from(build_inputs, "layers")

    layer_input_rows: list[dict[str, Any]] = []
    for index, layer in enumerate(layers_input, start=1):
        layer_input_rows.append(
            {
                "layer": index,
                "thickness_mm": _to_number_or_none(layer.get("thickness")),
                "family": _as_text(layer.get("family"), "–"),
                "variant": _as_text(layer.get("variant"), "–"),
            }
        )

    plate_rows: list[dict[str, Any]] = []
    for layer in _records_from(result_data, "layers"):
        layer_index = _to_int_or_none(layer.get("layer_index"))
        thickness = _to_number_or_none(layer.get("thickness"))
        for plate in _records_from(layer, "plates"):
            plate_rows.append(
                {
                    "layer": layer_index,
                    "plate": _as_text(plate.get("name"), "–"),
                    "length_mm": _to_number_or_none(plate.get("L")),
                    "width_mm": _to_number_or_none(plate.get("B")),
                    "height_mm": _to_number_or_none(plate.get("H")) or thickness,
                }
            )

    return ReportSection(
        id="schichtaufbau",
        title="Schichtaufbau",
        description="Geometrie- und Schichtdaten für den Aufbau der Isolierung.",
        blocks=[
            MetricsBlock(
                title="Geometrische Basisdaten",
                metrics=[
                    MetricItem(
                        "measure_type",
                        "Maßvorgabe",
                        _as_text(build_inputs.get("measure_type"), "outer"),
                        format_hint="plain",
                    ),
                    MetricItem("dim_l", "L", _to_number_or_none(dimensions.get("L")), unit="mm", format_hint="number"),
                    MetricItem("dim_b", "B", _to_number_or_none(dimensions.get("B")), unit="mm", format_hint="number"),
                    MetricItem("dim_h", "H", _to_number_or_none(dimensions.get("H")), unit="mm", format_hint="number"),
                    MetricItem("la_l", "la_l", _to_number_or_none(result_data.get("la_l")), unit="mm", format_hint="number"),
                    MetricItem("la_b", "la_b", _to_number_or_none(result_data.get("la_b")), unit="mm", format_hint="number"),
                    MetricItem("la_h", "la_h", _to_number_or_none(result_data.get("la_h")), unit="mm", format_hint="number"),
                    MetricItem("li_l", "li_l", _to_number_or_none(result_data.get("li_l")), unit="mm", format_hint="number"),
                    MetricItem("li_b", "li_b", _to_number_or_none(result_data.get("li_b")), unit="mm", format_hint="number"),
                    MetricItem("li_h", "li_h", _to_number_or_none(result_data.get("li_h")), unit="mm", format_hint="number"),
                ],
            ),
            _table(
                title="Eingabeschichten",
                columns=[
                    TableColumn("layer", "Schicht", value_type="integer"),
                    TableColumn("thickness_mm", "Dicke", unit="mm", value_type="number"),
                    TableColumn("family", "Materialfamilie"),
                    TableColumn("variant", "Variante"),
                ],
                rows=layer_input_rows,
            ),
            _table(
                title="Platten pro Schicht",
                columns=[
                    TableColumn("layer", "Schicht", value_type="integer"),
                    TableColumn("plate", "Platte"),
                    TableColumn("length_mm", "L", unit="mm", value_type="number"),
                    TableColumn("width_mm", "B", unit="mm", value_type="number"),
                    TableColumn("height_mm", "H", unit="mm", value_type="number"),
                ],
                rows=plate_rows,
            ),
            TextBlock(text=_as_text(build_results.get("message"), "")),
        ],
    )


def _build_cut_plan_section(state: Mapping[str, Any]) -> ReportSection:
    cut_inputs = _nested(_nested(state, "inputs"), "zuschnitt")
    cut_results = _nested(_nested(state, "results"), "zuschnitt")
    cut_data = _nested(cut_results, "data")

    placements = _records_from_any(cut_results, cut_data, key="placements")
    summaries = _records_from_any(cut_results, cut_data, key="summary")
    bins = _records_from_any(cut_results, cut_data, key="bins")
    manual_cut_candidates = _records_from_any(cut_results, cut_data, key="manual_cut_candidates")

    placement_rows = [
        {
            "material": _as_text(row.get("material"), "–"),
            "bin": _as_text(row.get("bin"), "–"),
            "part": _as_text(row.get("teil"), "–"),
            "width_mm": _to_number_or_none(row.get("breite")),
            "height_mm": _to_number_or_none(row.get("hoehe")),
            "x_mm": _to_number_or_none(row.get("x")),
            "y_mm": _to_number_or_none(row.get("y")),
            "status": _as_text(row.get("status"), "–"),
        }
        for row in placements
    ]

    summary_rows = [
        {
            "material": _as_text(row.get("material"), "–"),
            "bin_count": _to_int_or_none(row.get("count")),
            "price": _to_number_or_none(row.get("price")),
            "cost": _to_number_or_none(row.get("cost")),
        }
        for row in summaries
    ]

    bins_rows = [
        {
            "material": _as_text(row.get("material"), "–"),
            "bin": _to_int_or_none(row.get("bin")),
            "bin_width_mm": _to_number_or_none(row.get("bin_width")),
            "bin_height_mm": _to_number_or_none(row.get("bin_height")),
            "parts": len(_records_from(row, "parts")),
        }
        for row in bins
    ]

    return ReportSection(
        id="zuschnittsplan",
        title="Zuschnittsplan",
        description="Material-, Rohling-, Platzierungs- und Kostendaten aus dem Zuschnittzustand.",
        blocks=[
            MetricsBlock(
                title="Zuschnitt-Kennzahlen",
                metrics=[
                    MetricItem("kerf", "Schnittfuge (Kerf)", _to_number_or_none(cut_inputs.get("kerf")), unit="mm", format_hint="number"),
                    MetricItem("cached_plates", "Anzahl Cache-Platten", len(_records_from(cut_inputs, "cached_plates")), format_hint="integer"),
                    MetricItem("total_cost", "Gesamtkosten", _to_number_or_none(_coalesce(cut_results.get("total_cost"), cut_data.get("total_cost"))), format_hint="number"),
                    MetricItem("total_bin_count", "Anzahl Rohlinge gesamt", _to_int_or_none(_coalesce(cut_results.get("total_bin_count"), cut_data.get("total_bin_count"))), format_hint="integer"),
                    MetricItem("manual_cut_candidates", "Manuelle Zuschnitte", len(manual_cut_candidates), format_hint="integer"),
                ],
            ),
            _table(
                title="Platzierungen",
                columns=[
                    TableColumn("material", "Material"),
                    TableColumn("bin", "Rohling"),
                    TableColumn("part", "Teil"),
                    TableColumn("width_mm", "Breite", unit="mm", value_type="number"),
                    TableColumn("height_mm", "Höhe", unit="mm", value_type="number"),
                    TableColumn("x_mm", "X", unit="mm", value_type="number"),
                    TableColumn("y_mm", "Y", unit="mm", value_type="number"),
                    TableColumn("status", "Status", value_type="status"),
                ],
                rows=placement_rows,
            ),
            _table(
                title="Materialübersicht",
                columns=[
                    TableColumn("material", "Material"),
                    TableColumn("bin_count", "Anzahl Rohlinge", value_type="integer"),
                    TableColumn("price", "Preis", value_type="number"),
                    TableColumn("cost", "Kosten", value_type="number"),
                ],
                rows=summary_rows,
            ),
            _table(
                title="Rohlinggruppen",
                columns=[
                    TableColumn("material", "Material"),
                    TableColumn("bin", "Rohling", value_type="integer"),
                    TableColumn("bin_width_mm", "Rohlingbreite", unit="mm", value_type="number"),
                    TableColumn("bin_height_mm", "Rohlinghöhe", unit="mm", value_type="number"),
                    TableColumn("parts", "Teile", value_type="integer"),
                ],
                rows=bins_rows,
            ),
            ImageBlock(
                title="Zuschnitt-Visualisierung (Slot)",
                image_role="diagram",
                alt_text="Platzhalter für Zuschnittdiagramm",
                caption="Diagramm-Slot; die Asset-Generierung ist im aktuellen Stand noch nicht enthalten.",
                metadata={
                    "source_domain": "zuschnitt",
                    "placement_count": len(placements),
                    "bin_group_count": len(bins),
                },
            ),
            TextBlock(text=_as_text(cut_results.get("message"), "")),
        ],
    )


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


def _records_from(mapping: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _as_sequence(mapping.get(key)):
        if isinstance(entry, Mapping):
            rows.append(dict(entry))
    return rows


def _records_from_any(*mappings: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    for mapping in mappings:
        rows = _records_from(mapping, key)
        if rows:
            return rows
    return []


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


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
    number = _to_number_or_none(value)
    if number is None:
        return None
    return int(number)


def _numbers_from_sequence(value: Any, *, max_items: int = 24) -> list[float]:
    numbers: list[float] = []
    for item in _as_sequence(value)[:max_items]:
        number = _to_number_or_none(item)
        if number is not None:
            numbers.append(number)
    return numbers
