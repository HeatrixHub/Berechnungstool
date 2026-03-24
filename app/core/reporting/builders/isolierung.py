"""Report-Builder für den ersten Standardbericht des Isolierungs-Plugins.

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

STANDARD_REPORT_TITLE = "Stationäre Wärmedurchgangsrechnung durch Isolierung"


def build_isolierung_report(
    plugin_state: Mapping[str, Any] | None,
    *,
    title: str = STANDARD_REPORT_TITLE,
    project_name: str = "Unbenanntes Projekt",
    author: str = "Unbekannt",
    additional_info: Mapping[str, str] | None = None,
) -> ReportDocument:
    """Erzeuge den fachlich definierten Standardbericht aus exportiertem Plugin-State."""

    state = _as_mapping(plugin_state)
    metadata = ReportMetadata(
        title=_first_non_empty(title, STANDARD_REPORT_TITLE),
        project_name=_first_non_empty(project_name, "Unbenanntes Projekt"),
        author=_first_non_empty(author, "Unbekannt"),
        created_at=datetime.now(timezone.utc),
        additional_info=dict(additional_info or {}),
    )

    return ReportDocument(
        metadata=metadata,
        tags=["isolierung", "standardbericht", "waermedurchgang"],
        sections=[
            _build_general_data_section(state),
            _build_layer_table_section(state),
            _build_temperature_profile_section(state),
        ],
    )


# Rückwärtskompatibles Alias für bestehende Aufrufer.
build_isolierung_report_document = build_isolierung_report


def resolve_isolierung_report_metadata(plugin_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Leite robuste Berichtsmetadaten aus dem exportierten Isolierung-State ab."""

    state = _as_mapping(plugin_state)
    ui_state = _nested(state, "ui")
    return {
        "title": _first_non_empty(ui_state.get("report_title"), STANDARD_REPORT_TITLE),
        "project_name": _first_non_empty(ui_state.get("project_name"), "Unbenanntes Projekt"),
        "author": _first_non_empty(ui_state.get("author"), "Unbekannt"),
        "additional_info": {
            "Quelle": "Qt-Berichte-Tab",
            "Plugin": "isolierung",
            "Berichtstyp": "Standardbericht 01",
        },
    }


def _build_general_data_section(state: Mapping[str, Any]) -> ReportSection:
    calc_inputs = _nested(_nested(state, "inputs"), "berechnung")
    calc_results = _nested(_nested(state, "results"), "berechnung")
    result_data = _nested(calc_results, "data")

    return ReportSection(
        id="allgemeine-daten",
        title="Allgemeine Daten",
        description="Zentrale Kennwerte der stationären Wärmedurchgangsrechnung.",
        blocks=[
            MetricsBlock(
                title="Berichtskennwerte",
                metrics=[
                    MetricItem(
                        "temperature_inside",
                        "Temperatur innen",
                        _to_number_or_none(calc_inputs.get("T_left")),
                        unit="°C",
                        format_hint="number",
                        note="Quelle: Eingabeparameter T_left.",
                    ),
                    MetricItem(
                        "ambient_temperature",
                        "Umgebungstemperatur",
                        _to_number_or_none(calc_inputs.get("T_inf")),
                        unit="°C",
                        format_hint="number",
                        note="Quelle: Eingabeparameter T_inf.",
                    ),
                    MetricItem(
                        "total_heat_flux_density",
                        "Gesamtwärmestromdichte",
                        _to_number_or_none(result_data.get("q")),
                        unit="W/m²",
                        format_hint="number",
                        note="Aus Berechnungsergebnis q.",
                    ),
                    MetricItem(
                        "total_thermal_resistance",
                        "Gesamtwärmewiderstand",
                        _to_number_or_none(result_data.get("R_total")),
                        unit="m²K/W",
                        format_hint="number",
                        note="Aus Berechnungsergebnis R_total.",
                    ),
                ],
            ),
            TextBlock(text=_as_text(calc_results.get("message"), "")),
        ],
    )


def _build_layer_table_section(state: Mapping[str, Any]) -> ReportSection:
    calc_inputs = _nested(_nested(state, "inputs"), "berechnung")
    calc_results = _nested(_nested(state, "results"), "berechnung")
    result_data = _nested(calc_results, "data")

    interfaces = _numbers_from_sequence(result_data.get("interface_temperatures"), max_items=128)
    mean_temperatures = _numbers_from_sequence(result_data.get("T_avg"), max_items=128)
    thermal_conductivities = _numbers_from_sequence(result_data.get("k_final"), max_items=128)

    rows: list[dict[str, Any]] = []
    for index, layer in enumerate(_records_from(calc_inputs, "layers"), start=1):
        rows.append(
            {
                "layer_name": _layer_name(layer, index),
                "thickness_mm": _to_number_or_none(layer.get("thickness")),
                "classification_temperature_c": _to_number_or_none(layer.get("classification_temperature")),
                "interface_temperature_c": _sequence_item_or_none(interfaces, index),
                "mean_temperature_c": _sequence_item_or_none(mean_temperatures, index - 1),
                "thermal_conductivity": _sequence_item_or_none(thermal_conductivities, index - 1),
            }
        )

    return ReportSection(
        id="schichttabelle",
        title="Schichtübersicht Isolierungen",
        description="Tabellarische Übersicht der Schichten aus dem Tab „Isolierungen“.",
        blocks=[
            _table(
                title="Schichten",
                columns=[
                    TableColumn("layer_name", "Name der Isolierung"),
                    TableColumn("thickness_mm", "Dicke", unit="mm", value_type="number"),
                    TableColumn(
                        "classification_temperature_c",
                        "Klassifizierungstemperatur",
                        unit="°C",
                        value_type="number",
                    ),
                    TableColumn(
                        "interface_temperature_c",
                        "Grenzflächentemperatur der Schicht",
                        unit="°C",
                        value_type="number",
                    ),
                    TableColumn(
                        "mean_temperature_c",
                        "Mittlere Temperatur der Schicht",
                        unit="°C",
                        value_type="number",
                    ),
                    TableColumn(
                        "thermal_conductivity",
                        "Wärmeleitfähigkeit der Schicht",
                        unit="W/mK",
                        value_type="number",
                    ),
                ],
                rows=rows,
            )
        ],
    )


def _build_temperature_profile_section(state: Mapping[str, Any]) -> ReportSection:
    calc_inputs = _nested(_nested(state, "inputs"), "berechnung")
    calc_results = _nested(_nested(state, "results"), "berechnung")
    result_data = _nested(calc_results, "data")

    thickness_values = [
        _to_number_or_none(layer.get("thickness"))
        for layer in _records_from(calc_inputs, "layers")
    ]
    thicknesses_mm = [value for value in thickness_values if value is not None]
    interface_temperatures = _numbers_from_sequence(result_data.get("interface_temperatures"), max_items=256)

    return ReportSection(
        id="temperaturverlauf",
        title="Temperaturverlauf durch die Isolierung",
        description=(
            "Fachlicher Slot für den Temperaturplot aus dem Berechnungs-Tab "
            "des Plugins „Isolierung“ oder für ein später erzeugtes Diagramm-Asset."
        ),
        blocks=[
            ImageBlock(
                title="Temperaturprofil (Diagramm-Slot)",
                image_role="chart",
                asset_ref=None,
                alt_text="Temperaturverlauf über den Isolierungsaufbau",
                caption=(
                    "Der Plot ist noch nicht gerendert. Die Struktur enthält bereits "
                    "alle relevanten Referenzdaten für eine spätere Diagramm-Generierung."
                ),
                metadata={
                    "source_plugin": "isolierung",
                    "source_tab": "Berechnung",
                    "source_plot": "Temperaturverlauf",
                    "preferred_asset_key": "isolierung.temperature_profile",
                    "thickness_profile_mm": thicknesses_mm,
                    "interface_temperatures_c": interface_temperatures,
                    "layer_count": len(thicknesses_mm),
                },
            ),
            TextBlock(
                text=(
                    "Referenz: vorhandener Temperaturplot im Berechnungs-Tab. "
                    "Falls dieser nicht direkt wiederverwendet werden kann, soll das Diagramm "
                    "aus thickness_profile_mm und interface_temperatures_c erzeugt werden."
                )
            ),
        ],
    )


def _table(*, title: str, columns: list[TableColumn], rows: list[dict[str, Any]]) -> TableBlock:
    normalized_rows = [TableRow(cells={column.key: row.get(column.key) for column in columns}) for row in rows]
    return TableBlock(title=title, columns=columns, rows=normalized_rows)


def _layer_name(layer: Mapping[str, Any], index: int) -> str:
    variant = _as_text(layer.get("variant"), "")
    family = _as_text(layer.get("family"), "")
    if variant and family:
        return f"{family} – {variant}"
    if variant:
        return variant
    if family:
        return family
    return f"Schicht {index}"


def _sequence_item_or_none(values: Sequence[float], index: int) -> float | None:
    if 0 <= index < len(values):
        return values[index]
    return None


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


def _numbers_from_sequence(value: Any, *, max_items: int = 24) -> list[float]:
    numbers: list[float] = []
    for item in _as_sequence(value)[:max_items]:
        number = _to_number_or_none(item)
        if number is not None:
            numbers.append(number)
    return numbers
