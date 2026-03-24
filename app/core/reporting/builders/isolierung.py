"""Report-Builder für das Isolierungs-Plugin.

Der Builder transformiert ausschließlich exportierten Plugin-State in ein
renderer-neutrales ReportDocument.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.core.reporting.model import (
    ImageBlock,
    MetricItem,
    MetricsBlock,
    ReportDocument,
    ReportMetadata,
    ReportSection,
    TableBlock,
    TextBlock,
)


def build_isolierung_report_document(
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
                    MetricItem("Isolierungsberechnung", calc_status),
                    MetricItem("Schichtaufbau", build_status),
                    MetricItem("Zuschnittsplan", cut_status),
                    MetricItem(
                        "Anzahl Eingabeschichten",
                        len(_as_list(_nested(inputs, "berechnung").get("layers"))),
                    ),
                ],
            )
        ],
    )


def _build_calculation_section(state: Mapping[str, Any]) -> ReportSection:
    calc_inputs = _nested(_nested(state, "inputs"), "berechnung")
    calc_results = _nested(_nested(state, "results"), "berechnung")
    result_data = _nested(calc_results, "data")

    input_table = TableBlock(
        title="Eingangsparameter",
        columns=["Parameter", "Wert"],
        rows=[
            {"Parameter": "T_left", "Wert": _as_text(calc_inputs.get("T_left"))},
            {"Parameter": "T_inf", "Wert": _as_text(calc_inputs.get("T_inf"))},
            {"Parameter": "h", "Wert": _as_text(calc_inputs.get("h"))},
        ],
    )

    layer_rows = []
    for index, layer in enumerate(_as_list(calc_inputs.get("layers")), start=1):
        layer_map = _as_mapping(layer)
        layer_rows.append(
            {
                "Schicht": index,
                "Dicke (mm)": _as_text(layer_map.get("thickness")),
                "Materialfamilie": _as_text(layer_map.get("family"), "–"),
                "Variante": _as_text(layer_map.get("variant"), "–"),
            }
        )

    metrics = MetricsBlock(
        title="Berechnete Kennzahlen",
        metrics=[
            MetricItem("Wärmestrom q", _format_number(result_data.get("q"))),
            MetricItem("Gesamtwärmewiderstand R_total", _format_number(result_data.get("R_total"))),
            MetricItem("Iterationen", _format_number(result_data.get("iterations"))),
            MetricItem(
                "Grenzflächentemperaturen",
                _format_sequence(result_data.get("interface_temperatures")),
                unit="°C",
            ),
            MetricItem("Mittlere Schichttemperaturen", _format_sequence(result_data.get("T_avg")), unit="°C"),
            MetricItem("k_final", _format_sequence(result_data.get("k_final")), unit="W/mK"),
        ],
    )

    return ReportSection(
        id="isolierungsberechnung",
        title="Isolierungsberechnung",
        description="Normierte Übernahme der Eingabe- und Ergebnisdaten aus dem Plugin-State.",
        blocks=[
            input_table,
            TableBlock(
                title="Schichtdaten",
                columns=["Schicht", "Dicke (mm)", "Materialfamilie", "Variante"],
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
    layers_input = _as_list(build_inputs.get("layers"))

    layer_input_rows = []
    for index, layer in enumerate(layers_input, start=1):
        layer_map = _as_mapping(layer)
        layer_input_rows.append(
            {
                "Schicht": index,
                "Dicke (mm)": _as_text(layer_map.get("thickness")),
                "Materialfamilie": _as_text(layer_map.get("family"), "–"),
                "Variante": _as_text(layer_map.get("variant"), "–"),
            }
        )

    plate_rows = []
    for layer in _as_list(result_data.get("layers")):
        layer_map = _as_mapping(layer)
        layer_index = _as_text(layer_map.get("layer_index"), "–")
        thickness = _as_text(layer_map.get("thickness"), "–")
        for plate in _as_list(layer_map.get("plates")):
            plate_map = _as_mapping(plate)
            plate_rows.append(
                {
                    "Schicht": layer_index,
                    "Platte": _as_text(plate_map.get("name"), "–"),
                    "L": _format_number(plate_map.get("L")),
                    "B": _format_number(plate_map.get("B")),
                    "H": _format_number(plate_map.get("H"), fallback=thickness),
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
                    MetricItem("Maßvorgabe", _as_text(build_inputs.get("measure_type"), "outer")),
                    MetricItem("L", _as_text(dimensions.get("L")), unit="mm"),
                    MetricItem("B", _as_text(dimensions.get("B")), unit="mm"),
                    MetricItem("H", _as_text(dimensions.get("H")), unit="mm"),
                    MetricItem("la_l", _format_number(result_data.get("la_l")), unit="mm"),
                    MetricItem("la_b", _format_number(result_data.get("la_b")), unit="mm"),
                    MetricItem("la_h", _format_number(result_data.get("la_h")), unit="mm"),
                    MetricItem("li_l", _format_number(result_data.get("li_l")), unit="mm"),
                    MetricItem("li_b", _format_number(result_data.get("li_b")), unit="mm"),
                    MetricItem("li_h", _format_number(result_data.get("li_h")), unit="mm"),
                ],
            ),
            TableBlock(
                title="Eingabeschichten",
                columns=["Schicht", "Dicke (mm)", "Materialfamilie", "Variante"],
                rows=layer_input_rows,
            ),
            TableBlock(
                title="Platten pro Schicht",
                columns=["Schicht", "Platte", "L", "B", "H"],
                rows=plate_rows,
            ),
            TextBlock(text=_as_text(build_results.get("message"), "")),
        ],
    )


def _build_cut_plan_section(state: Mapping[str, Any]) -> ReportSection:
    cut_inputs = _nested(_nested(state, "inputs"), "zuschnitt")
    cut_results = _nested(_nested(state, "results"), "zuschnitt")

    placement_rows = []
    for row in _as_list(cut_results.get("placements")):
        row_map = _as_mapping(row)
        placement_rows.append(
            {
                "Material": _as_text(row_map.get("material"), "–"),
                "Rohling": _as_text(row_map.get("bin"), "–"),
                "Teil": _as_text(row_map.get("teil"), "–"),
                "Breite": _format_number(row_map.get("breite")),
                "Höhe": _format_number(row_map.get("hoehe")),
                "X": _format_number(row_map.get("x")),
                "Y": _format_number(row_map.get("y")),
                "Status": _as_text(row_map.get("status"), "–"),
            }
        )

    summary_rows = []
    for row in _as_list(cut_results.get("summary")):
        row_map = _as_mapping(row)
        summary_rows.append(
            {
                "Material": _as_text(row_map.get("material"), "–"),
                "Anzahl Rohlinge": _format_number(row_map.get("count")),
                "Preis": _format_number(row_map.get("price")),
                "Kosten": _format_number(row_map.get("cost")),
            }
        )

    bins_rows = []
    for row in _as_list(cut_results.get("bins")):
        row_map = _as_mapping(row)
        bins_rows.append(
            {
                "Material": _as_text(row_map.get("material"), "–"),
                "Rohling": _format_number(row_map.get("bin")),
                "Rohlingbreite": _format_number(row_map.get("bin_width")),
                "Rohlinghöhe": _format_number(row_map.get("bin_height")),
                "Teile": len(_as_list(row_map.get("parts"))),
            }
        )

    return ReportSection(
        id="zuschnittsplan",
        title="Zuschnittsplan",
        description="Material-, Rohling-, Platzierungs- und Kostendaten aus dem Zuschnittzustand.",
        blocks=[
            MetricsBlock(
                title="Zuschnitt-Kennzahlen",
                metrics=[
                    MetricItem("Schnittfuge (Kerf)", _as_text(cut_inputs.get("kerf")), unit="mm"),
                    MetricItem("Anzahl Cache-Platten", len(_as_list(cut_inputs.get("cached_plates")))),
                    MetricItem("Gesamtkosten", _format_number(cut_results.get("total_cost"))),
                    MetricItem("Anzahl Rohlinge gesamt", _format_number(cut_results.get("total_bin_count"))),
                    MetricItem(
                        "Manuelle Zuschnitte",
                        len(_as_list(cut_results.get("manual_cut_candidates"))),
                    ),
                ],
            ),
            TableBlock(
                title="Platzierungen",
                columns=["Material", "Rohling", "Teil", "Breite", "Höhe", "X", "Y", "Status"],
                rows=placement_rows,
            ),
            TableBlock(
                title="Materialübersicht",
                columns=["Material", "Anzahl Rohlinge", "Preis", "Kosten"],
                rows=summary_rows,
            ),
            TableBlock(
                title="Rohlinggruppen",
                columns=["Material", "Rohling", "Rohlingbreite", "Rohlinghöhe", "Teile"],
                rows=bins_rows,
            ),
            ImageBlock(
                title="Zuschnitt-Visualisierung (Placeholder)",
                caption="In diesem Ausbauschritt wird nur die Datenstruktur vorbereitet.",
            ),
            TextBlock(text=_as_text(cut_results.get("message"), "")),
        ],
    )


def _nested(mapping: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _format_number(value: Any, fallback: str = "–") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_sequence(value: Any, *, max_items: int = 12) -> str:
    items = _as_list(value)
    if not items:
        return "–"
    formatted = [_format_number(item, fallback=_as_text(item, "–")) for item in items[:max_items]]
    if len(items) > max_items:
        formatted.append("…")
    return ", ".join(formatted)
