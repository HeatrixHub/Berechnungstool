from __future__ import annotations

from app.core.reporting.builders import (
    ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG,
    build_isolierung_report_by_type,
    resolve_isolierung_report_metadata,
)


def _plugin_state() -> dict[str, object]:
    return {
        "inputs": {
            "schichtaufbau": {
                "measure_type": "outer",
                "dimensions": {"L": "1000", "B": "500", "H": "300"},
            }
        },
        "results": {
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
                            "thickness": 40,
                            "plates": [
                                {"name": "Oben", "L": 1000, "B": 500, "H": 40},
                            ],
                        }
                    ],
                },
            },
            "zuschnitt": {
                "summary": [
                    {"material": "Steinwolle (40 mm)", "count": 2, "cost": 123.0},
                ]
            },
        },
    }


def test_build_report_by_type_keeps_standard_report_intact() -> None:
    document = build_isolierung_report_by_type(
        _plugin_state(),
        report_type=ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG,
    )

    assert document.metadata.title == "Stationäre Wärmedurchgangsrechnung durch Isolierung"
    assert [section.id for section in document.sections] == [
        "allgemeine-daten",
        "schichttabelle",
        "temperaturverlauf",
    ]


def test_build_schichtaufbau_zuschnitt_report_contains_sections_and_tables() -> None:
    document = build_isolierung_report_by_type(
        _plugin_state(),
        report_type=ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    )

    assert document.metadata.title == "Schichtaufbau und Zuschnittplanung der Isolierung"
    assert [section.id for section in document.sections] == [
        "schichtaufbau-ergebnisse",
        "zuschnitt-ergebnisse",
    ]

    schicht_table = document.sections[0].blocks[1]
    assert schicht_table.kind == "table"
    assert [column.label for column in schicht_table.columns] == [
        "Schicht",
        "Material",
        "Plattenbereich",
        "Länge",
        "Breite",
        "Höhe",
    ]

    zuschnitt_table = document.sections[1].blocks[0]
    assert zuschnitt_table.kind == "table"
    assert [column.label for column in zuschnitt_table.columns] == [
        "Material",
        "Rohlinge",
        "Gesamtkosten",
    ]


def test_build_schichtaufbau_zuschnitt_report_handles_missing_cut_summary_robustly() -> None:
    state = _plugin_state()
    state["results"] = {"schichtaufbau": state["results"]["schichtaufbau"], "zuschnitt": {"message": "debug"}}

    document = build_isolierung_report_by_type(
        state,
        report_type=ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    )

    zuschnitt_blocks = document.sections[1].blocks
    assert len(zuschnitt_blocks) == 1
    assert zuschnitt_blocks[0].kind == "text"


def test_build_schichtaufbau_zuschnitt_report_handles_missing_layer_rows_robustly() -> None:
    state = _plugin_state()
    state["results"]["schichtaufbau"]["data"]["layers"] = []

    document = build_isolierung_report_by_type(
        state,
        report_type=ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    )

    section = document.sections[0]
    assert [block.kind for block in section.blocks] == ["metrics", "table", "text"]


def test_metadata_resolution_uses_report_type_specific_default_title() -> None:
    state = {"ui": {}}

    metadata = resolve_isolierung_report_metadata(
        state,
        report_type=ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT,
    )

    assert metadata["title"] == "Schichtaufbau und Zuschnittplanung der Isolierung"
