from __future__ import annotations

from datetime import datetime, timezone

from app.core.reporting.builders import (
    ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG,
    build_isolierung_report_by_type,
)
from app.core.reporting.renderers.pdf import _column_header_markup, _compact_dimension_rows, _format_datetime
from app.core.reporting.report_document import MetricItem, TableColumn
from app.core.reporting.renderers import render_report_pdf


def _plugin_state() -> dict[str, object]:
    return {
        "inputs": {
            "berechnung": {
                "T_left": 120,
                "T_inf": 20,
                "layers": [
                    {"name": "Steinwolle", "thickness": 40, "classification_temperature": 200},
                ],
            },
            "schichtaufbau": {
                "measure_type": "outer",
                "dimensions": {"L": "1000", "B": "500", "H": "300"},
            },
        },
        "results": {
            "berechnung": {
                "status": "ok",
                "data": {
                    "q": 42.0,
                    "R_total": 2.5,
                    "interface_temperatures": [120, 70, 20],
                    "T_avg": [95],
                    "k_final": [0.035],
                },
            },
            "schichtaufbau": {
                "status": "ok",
                "data": {
                    "la_l": 1000,
                    "la_b": 500,
                    "la_h": 300,
                    "li_l": 920,
                    "li_b": 420,
                    "li_h": 220,
                    "isolierungen": ["Steinwolle"],
                    "layers": [
                        {
                            "layer_index": 1,
                            "plates": [
                                {"name": "Oben", "L": 1000, "B": 500, "H": 40},
                            ],
                        }
                    ],
                },
            },
            "zuschnitt": {
                "summary": [
                    {"material": "Steinwolle (40 mm)", "count": 2, "cost": 123.45},
                ]
            },
        },
    }


def test_render_standard_report_pdf_still_exports(tmp_path) -> None:
    document = build_isolierung_report_by_type(
        _plugin_state(),
        report_type=ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG,
    )

    output = tmp_path / "standardbericht.pdf"
    render_report_pdf(document, output)

    assert output.exists()
    assert output.stat().st_size > 0


def test_render_schichtaufbau_zuschnitt_report_pdf_exports(tmp_path) -> None:
    document = build_isolierung_report_by_type(
        _plugin_state(),
        report_type=ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    )

    output = tmp_path / "schichtaufbau_zuschnitt.pdf"
    render_report_pdf(document, output)

    assert output.exists()
    assert output.stat().st_size > 0


def test_compact_dimension_rows_groups_axes_into_one_row_per_measure_type() -> None:
    rows = _compact_dimension_rows(
        [
            MetricItem(key="given_outer_l", label="Gegebenes Außenmaß L", value=1000, unit="mm", format_hint="number"),
            MetricItem(key="given_outer_b", label="Gegebenes Außenmaß B", value=500, unit="mm", format_hint="number"),
            MetricItem(key="given_outer_h", label="Gegebenes Außenmaß H", value=300, unit="mm", format_hint="number"),
            MetricItem(key="calculated_inner_l", label="Berechnetes Innenmaß L", value=920, unit="mm", format_hint="number"),
            MetricItem(key="calculated_inner_b", label="Berechnetes Innenmaß B", value=420, unit="mm", format_hint="number"),
            MetricItem(key="calculated_inner_h", label="Berechnetes Innenmaß H", value=220, unit="mm", format_hint="number"),
        ]
    )

    assert rows == [
        ("Gegebenes Außenmaß (L×B×H)", "1.000 × 500 × 300 mm"),
        ("Berechnetes Innenmaß (L×B×H)", "920 × 420 × 220 mm"),
    ]


def test_format_datetime_returns_date_without_time() -> None:
    created = datetime(2026, 4, 16, 14, 30, tzinfo=timezone.utc)

    assert _format_datetime(created) == "16.04.2026"


def test_column_header_markup_renders_label_and_optional_unit() -> None:
    with_unit = TableColumn(key="q", label="Wärmestrom", unit="W/m²", value_type="number")
    without_unit = TableColumn(key="material", label="Material", unit=None, value_type="text")

    assert _column_header_markup(with_unit, include_unit=True) == "<b>Wärmestrom</b><br/>W/m²"
    assert _column_header_markup(without_unit, include_unit=True) == "<b>Material</b>"
