"""Datenstrukturen für die templating-basierte Berichtserzeugung."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Sequence, Union


@dataclass(slots=True)
class ReportTemplateMetadata:
    """Beschreibt eine auswählbare Berichtsvorlage eines Plugins."""

    template_id: str
    title: str
    description: str | None = None
    suggested_filename: str | None = None


@dataclass(slots=True)
class ReportContext:
    """Kontext für die Berichtsgenerierung eines Plugins."""

    plugin_state: Dict[str, Any] | None
    source: Literal["current", "project"]
    project_id: str | None = None


@dataclass(slots=True)
class ReportHeading:
    text: str
    level: int = 1


@dataclass(slots=True)
class ReportParagraph:
    text: str


@dataclass(slots=True)
class ReportBulletList:
    items: Sequence[str]


@dataclass(slots=True)
class ReportTable:
    rows: Sequence[Sequence[Any]]
    headers: Sequence[str] | None = None
    column_widths: Sequence[int | float] | None = None


@dataclass(slots=True)
class ReportImage:
    path: Path
    width: float | None = None
    height: float | None = None


@dataclass(slots=True)
class ReportSpacer:
    size: float = 12.0


@dataclass(slots=True)
class ReportPageBreak:
    pass


ReportElement = Union[
    ReportHeading,
    ReportParagraph,
    ReportBulletList,
    ReportTable,
    ReportImage,
    ReportSpacer,
    ReportPageBreak,
]


@dataclass(slots=True)
class StructuredReport:
    """Strukturierte Beschreibung eines PDF-Berichts.

    Preppy-Templates können dieses Format direkt zurückgeben. Alternativ reicht
    auch eine Liste von rohen Element-Dictionaries mit einem ``type``-Schlüssel.
    """

    elements: List[ReportElement]
    title: str | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> "StructuredReport":
        if isinstance(raw, StructuredReport):
            return raw
        if isinstance(raw, dict):
            elements_raw = raw.get("elements", [])
            title = raw.get("title")
        else:
            elements_raw = raw
            title = None
        parsed_elements = parse_report_elements(elements_raw)
        return cls(elements=list(parsed_elements), title=title)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def _parse_report_element(raw: Any) -> ReportElement:
    if isinstance(
        raw,
        (ReportHeading, ReportParagraph, ReportBulletList, ReportTable, ReportImage, ReportSpacer, ReportPageBreak),
    ):
        return raw
    if not isinstance(raw, dict) or "type" not in raw:
        raise ValueError(
            "Report-Elemente müssen eine 'type'-Schlüssel enthalten oder bereits dataklassen sein"
        )
    kind = str(raw.get("type")).lower()
    if kind == "heading":
        return ReportHeading(text=_as_text(raw.get("text", "")), level=int(raw.get("level", 1)))
    if kind == "paragraph":
        return ReportParagraph(text=_as_text(raw.get("text", "")))
    if kind == "bullet_list":
        items_raw = raw.get("items", [])
        if not isinstance(items_raw, Iterable):
            raise ValueError("bullet_list.items muss eine Sequenz sein")
        return ReportBulletList(items=[_as_text(item) for item in items_raw])
    if kind == "table":
        rows = raw.get("rows", [])
        headers = raw.get("headers")
        widths = raw.get("column_widths")
        if rows is None:
            rows = []
        if not isinstance(rows, Iterable):
            raise ValueError("table.rows muss eine Sequenz sein")
        parsed_rows = [list(row) for row in rows]
        parsed_headers = [
            _as_text(item) for item in headers
        ] if headers is not None else None
        parsed_widths = list(widths) if widths is not None else None
        return ReportTable(rows=parsed_rows, headers=parsed_headers, column_widths=parsed_widths)
    if kind == "image":
        path_value = raw.get("path")
        return ReportImage(path=Path(str(path_value)), width=raw.get("width"), height=raw.get("height"))
    if kind == "spacer":
        return ReportSpacer(size=float(raw.get("size", 12.0)))
    if kind == "page_break":
        return ReportPageBreak()
    raise ValueError(f"Unbekannter Report-Element-Typ: {kind}")


def parse_report_elements(raw_elements: Any) -> List[ReportElement]:
    if raw_elements is None:
        return []
    if isinstance(raw_elements, dict):
        raw_elements = [raw_elements]
    if not isinstance(raw_elements, Iterable):
        raise ValueError("Report-Elemente müssen iterierbar sein")
    return [_parse_report_element(raw) for raw in raw_elements]
