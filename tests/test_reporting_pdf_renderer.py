from __future__ import annotations

from app.core.reporting.builders import (
    ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG,
    build_isolierung_report_by_type,
)
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
