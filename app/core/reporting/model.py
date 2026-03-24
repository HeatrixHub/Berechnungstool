"""Renderer-unabhängiges Berichtsdatenmodell.

Dieses Modul definiert das fachliche Fundament für technische Berichte.
Die Dataclasses beschreiben Inhalte strukturiert, ohne PDF-/HTML- oder UI-Abhängigkeiten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


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
class TableBlock:
    """Tabellarischer Block mit flexiblen Zeilen."""

    kind: Literal["table"] = "table"
    title: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    caption: str | None = None


@dataclass(slots=True)
class MetricItem:
    """Einzelne Kennzahl inkl. Einheit und optionalem Hinweis."""

    label: str
    value: str | float | int | None = None
    unit: str | None = None
    hint: str | None = None


@dataclass(slots=True)
class MetricsBlock:
    """Block für eine Gruppe fachlicher Kennzahlen."""

    kind: Literal["metrics"] = "metrics"
    title: str | None = None
    metrics: list[MetricItem] = field(default_factory=list)


@dataclass(slots=True)
class ImageBlock:
    """Platzhalter für visuelle Inhalte, unabhängig vom Renderer."""

    kind: Literal["image"] = "image"
    title: str | None = None
    source: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
