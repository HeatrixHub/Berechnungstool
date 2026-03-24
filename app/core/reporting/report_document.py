"""Renderer-unabhängiges Berichtsdatenmodell."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, TypeAlias

ReportScalar: TypeAlias = str | int | float | bool | None
ReportSequence: TypeAlias = list[ReportScalar]
ReportValue: TypeAlias = ReportScalar | ReportSequence


@dataclass(slots=True)
class ReportMetadata:
    """Metadaten eines Berichts mit defensiven Defaults."""

    title: str = "Technischer Bericht"
    project_name: str = "Unbenanntes Projekt"
    author: str = "Unbekannt"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    additional_info: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TextBlock:
    """Freitextblock innerhalb eines Abschnitts."""

    kind: Literal["text"] = "text"
    heading: str | None = None
    text: str = ""


@dataclass(slots=True)
class TableColumn:
    """Stabile Spaltendefinition für renderer-neutrale Tabellen."""

    key: str
    label: str
    unit: str | None = None
    value_type: Literal["text", "number", "integer", "status"] = "text"


@dataclass(slots=True)
class TableRow:
    """Zeile mit klarer Zuordnung über Spalten-Keys."""

    cells: dict[str, ReportScalar] = field(default_factory=dict)


@dataclass(slots=True)
class TableBlock:
    """Tabellarischer Block mit expliziter Spalten- und Zeilenstruktur."""

    kind: Literal["table"] = "table"
    title: str | None = None
    columns: list[TableColumn] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    caption: str | None = None


@dataclass(slots=True)
class MetricItem:
    """Einzelne Kennzahl als typisierter Rohwert mit optionalem Format-Hinweis."""

    key: str
    label: str
    value: ReportValue = None
    unit: str | None = None
    format_hint: Literal["plain", "number", "percentage", "status", "list"] = "plain"
    note: str | None = None


@dataclass(slots=True)
class MetricsBlock:
    """Block für eine Gruppe fachlicher Kennzahlen."""

    kind: Literal["metrics"] = "metrics"
    title: str | None = None
    metrics: list[MetricItem] = field(default_factory=list)


@dataclass(slots=True)
class ImageBlock:
    """Renderer-neutrale Beschreibung eines Bild- oder Diagramm-Slots."""

    kind: Literal["image"] = "image"
    title: str | None = None
    image_role: Literal["chart", "diagram", "photo", "preview", "placeholder"] = "placeholder"
    asset_ref: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    metadata: dict[str, ReportValue] = field(default_factory=dict)


ReportBlock = TextBlock | TableBlock | MetricsBlock | ImageBlock


@dataclass(slots=True)
class ReportSection:
    """Fachlicher Abschnitt eines technischen Berichts."""

    id: str
    title: str
    description: str | None = None
    blocks: list[ReportBlock] = field(default_factory=list)


@dataclass(slots=True)
class ReportDocument:
    """Vollständiges Berichtsdokument als renderer-neutrale Struktur."""

    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    sections: list[ReportSection] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
