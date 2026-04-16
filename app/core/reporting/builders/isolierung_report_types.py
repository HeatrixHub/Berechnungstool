"""Berichtstypen und Auflösung für das Isolierungs-Reporting."""
from __future__ import annotations

from typing import Final, Literal

IsolierungReportType = Literal["waermedurchgang", "schichtaufbau_zuschnitt"]

ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG: Final[IsolierungReportType] = "waermedurchgang"
ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT: Final[IsolierungReportType] = "schichtaufbau_zuschnitt"

ISOLIERUNG_REPORT_TYPE_OPTIONS: tuple[tuple[IsolierungReportType, str], ...] = (
    (ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG, "Stationäre Wärmedurchgangsrechnung"),
    (ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT, "Schichtaufbau und Zuschnitt"),
)


def normalize_isolierung_report_type(value: object) -> IsolierungReportType:
    text = str(value).strip() if value is not None else ""
    if text == ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT:
        return ISOLIERUNG_REPORT_TYPE_SCHICHTAUFBAU_ZUSCHNITT
    return ISOLIERUNG_REPORT_TYPE_WAERMEDURCHGANG


def report_type_label(report_type: object) -> str:
    normalized = normalize_isolierung_report_type(report_type)
    for key, label in ISOLIERUNG_REPORT_TYPE_OPTIONS:
        if key == normalized:
            return label
    return ISOLIERUNG_REPORT_TYPE_OPTIONS[0][1]
