"""HTML renderer for renderer-neutral report documents."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from html import escape

from app.core.reporting.report_document import (
    ImageBlock,
    MetricItem,
    MetricsBlock,
    ReportDocument,
    ReportSection,
    TableBlock,
    TableColumn,
    TableRow,
    TextBlock,
)


def render_report_html(document: ReportDocument) -> str:
    """Render a complete :class:`ReportDocument` into preview-friendly HTML."""

    metadata = document.metadata
    created_at = _format_datetime(metadata.created_at)

    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html lang='de'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<style>",
        _STYLE,
        "</style>",
        "</head>",
        "<body>",
        "<article class='report'>",
        "<header class='report-header'>",
        f"<h1>{_safe_text(metadata.title, fallback='Technischer Bericht')}</h1>",
        "<div class='metadata-grid'>",
        _metadata_item("Projekt", metadata.project_name, "Unbenanntes Projekt"),
        _metadata_item("Autor", metadata.author, "Unbekannt"),
        _metadata_item("Erstellt", created_at, "Unbekannt"),
        "</div>",
    ]

    for key, value in sorted(metadata.additional_info.items()):
        parts.append(_metadata_item(key, value, "–"))

    parts.extend(["</header>"])

    if not document.sections:
        parts.append("<p class='empty'>Keine Berichtsinhalte vorhanden.</p>")
    else:
        for section in document.sections:
            parts.extend(_render_section(section))

    parts.extend(["</article>", "</body>", "</html>"])
    return "\n".join(parts)


def _render_section(section: ReportSection) -> list[str]:
    section_parts = [
        f"<section class='report-section' id='section-{escape(section.id)}'>",
        f"<h2>{_safe_text(section.title, fallback='Abschnitt')}</h2>",
    ]

    if section.description and section.description.strip():
        section_parts.append(f"<p class='section-description'>{escape(section.description.strip())}</p>")

    if not section.blocks:
        section_parts.append("<p class='empty'>Keine Inhalte in diesem Abschnitt.</p>")
    else:
        for block in section.blocks:
            if isinstance(block, TextBlock):
                section_parts.extend(_render_text_block(block))
            elif isinstance(block, MetricsBlock):
                section_parts.extend(_render_metrics_block(block))
            elif isinstance(block, TableBlock):
                section_parts.extend(_render_table_block(block))
            elif isinstance(block, ImageBlock):
                section_parts.extend(_render_image_block(block))

    section_parts.append("</section>")
    return section_parts


def _render_text_block(block: TextBlock) -> list[str]:
    text = (block.text or "").strip()
    if not text and not block.heading:
        return []

    parts = ["<div class='block block-text'>"]
    if block.heading:
        parts.append(f"<h3>{escape(block.heading)}</h3>")

    if text:
        parts.append(f"<p>{escape(text)}</p>")
    else:
        parts.append("<p class='empty'>Kein Textinhalt vorhanden.</p>")

    parts.append("</div>")
    return parts


def _render_metrics_block(block: MetricsBlock) -> list[str]:
    parts = ["<div class='block block-metrics'>"]
    if block.title:
        parts.append(f"<h3>{escape(block.title)}</h3>")

    if not block.metrics:
        parts.append("<p class='empty'>Keine Kennzahlen verfügbar.</p>")
    else:
        parts.append("<dl class='metrics-grid'>")
        for metric in block.metrics:
            label = metric.label.strip() if metric.label else metric.key
            formatted = _format_metric_value(metric)
            unit = f" <span class='metric-unit'>{escape(metric.unit)}</span>" if metric.unit else ""
            note = f"<div class='metric-note'>{escape(metric.note)}</div>" if metric.note else ""
            parts.append("<div class='metric-item'>")
            parts.append(f"<dt>{escape(label)}</dt>")
            parts.append(f"<dd>{formatted}{unit}</dd>")
            if note:
                parts.append(note)
            parts.append("</div>")
        parts.append("</dl>")

    parts.append("</div>")
    return parts


def _render_table_block(block: TableBlock) -> list[str]:
    parts = ["<div class='block block-table'>"]
    if block.title:
        parts.append(f"<h3>{escape(block.title)}</h3>")

    if not block.columns:
        parts.append("<p class='empty'>Keine Tabellenspalten definiert.</p>")
        parts.append("</div>")
        return parts

    parts.append("<table>")
    parts.append("<thead><tr>")
    for column in block.columns:
        header = escape(column.label)
        if column.unit:
            header = f"{header} [{escape(column.unit)}]"
        parts.append(f"<th>{header}</th>")
    parts.append("</tr></thead>")

    parts.append("<tbody>")
    if block.rows:
        for row in block.rows:
            parts.append("<tr>")
            for column in block.columns:
                parts.append(f"<td>{_format_table_cell(row, column)}</td>")
            parts.append("</tr>")
    else:
        parts.append(
            f"<tr><td class='empty' colspan='{len(block.columns)}'>Keine Tabellenzeilen verfügbar.</td></tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")

    if block.caption:
        parts.append(f"<p class='caption'>{escape(block.caption)}</p>")

    parts.append("</div>")
    return parts


def _render_image_block(block: ImageBlock) -> list[str]:
    parts = ["<div class='block block-image'>"]
    if block.title:
        parts.append(f"<h3>{escape(block.title)}</h3>")

    has_asset = bool(block.asset_ref)
    if has_asset:
        parts.append("<p><strong>Bildslot:</strong> Asset referenziert.</p>")
        parts.append(f"<p class='image-ref'>Referenz: <code>{escape(block.asset_ref or '')}</code></p>")
    else:
        parts.append(
            "<div class='image-placeholder'>"
            "<p><strong>Bildslot reserviert.</strong>"
            " Für diese Vorschau ist noch kein Asset hinterlegt.</p>"
            "</div>"
        )

    details: list[str] = [f"Rolle: {escape(block.image_role)}"]
    if block.alt_text:
        details.append(f"Alt-Text: {escape(block.alt_text)}")
    if block.metadata:
        details.append(f"Metadaten: {escape(_format_metadata_summary(block.metadata))}")

    if details:
        parts.append(f"<p class='image-meta'>{' | '.join(details)}</p>")
    if block.caption:
        parts.append(f"<p class='caption'>{escape(block.caption)}</p>")

    parts.append("</div>")
    return parts


def _metadata_item(label: str, value: str | None, fallback: str) -> str:
    return (
        "<div class='metadata-item'>"
        f"<span class='metadata-label'>{escape(label)}</span>"
        f"<span class='metadata-value'>{_safe_text(value, fallback=fallback)}</span>"
        "</div>"
    )


def _safe_text(value: str | None, *, fallback: str = "–") -> str:
    if value is None:
        return escape(fallback)
    text = str(value).strip()
    return escape(text) if text else escape(fallback)


def _format_metric_value(metric: MetricItem) -> str:
    value = metric.value
    hint = metric.format_hint

    if value is None:
        return "–"

    if hint == "list":
        values = _as_sequence(value)
        if not values:
            return "–"
        return ", ".join(_format_number(item) if isinstance(item, (float, int)) else escape(str(item)) for item in values)

    if hint == "number":
        return _format_number(value)

    if hint == "percentage":
        if isinstance(value, (float, int)):
            pct_value = float(value) * 100 if abs(float(value)) <= 1 else float(value)
            return f"{_format_number(pct_value)} %"
        return f"{escape(str(value))} %"

    if hint == "status":
        return escape(str(value)).capitalize()

    if hint == "integer":
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (float, int)):
            return str(int(value))

    return escape(str(value))


def _format_table_cell(row: TableRow, column: TableColumn) -> str:
    value = row.cells.get(column.key)
    if value is None:
        return "–"

    if column.value_type == "number":
        return _format_number(value)
    if column.value_type == "integer":
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            return str(int(value))
    if column.value_type == "status":
        return escape(str(value)).capitalize()

    return escape(str(value))


def _format_number(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:,.3f}"
        text = text.rstrip("0").rstrip(".")
        return text.replace(",", " ")
    return escape(str(value))


def _format_datetime(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    return _safe_text(str(value) if value is not None else None, fallback="Unbekannt")


def _format_metadata_summary(metadata: dict[str, object]) -> str:
    chunks: list[str] = []
    for key, value in metadata.items():
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        chunks.append(f"{key}={rendered}")
    return "; ".join(chunks)


def _as_sequence(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


_STYLE = """
body {
    font-family: "Segoe UI", Arial, sans-serif;
    background: #ffffff;
    color: #1f2937;
    margin: 0;
    padding: 20px;
}
.report {
    max-width: 980px;
    margin: 0 auto;
    line-height: 1.45;
}
.report-header {
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 22px;
    padding-bottom: 14px;
}
h1 {
    margin: 0 0 12px;
    font-size: 28px;
}
h2 {
    margin: 18px 0 8px;
    font-size: 20px;
}
h3 {
    margin: 0 0 8px;
    font-size: 16px;
}
.metadata-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 8px;
}
.metadata-item {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 8px;
}
.metadata-label {
    display: block;
    color: #6b7280;
    font-size: 12px;
    margin-bottom: 2px;
}
.metadata-value {
    font-weight: 600;
}
.report-section {
    margin-bottom: 20px;
}
.section-description {
    color: #4b5563;
    margin-top: 0;
}
.block {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
    margin: 10px 0;
    background: #ffffff;
}
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
    margin: 0;
}
.metric-item dt {
    font-size: 12px;
    color: #6b7280;
    margin-bottom: 2px;
}
.metric-item dd {
    margin: 0;
    font-weight: 600;
}
.metric-note {
    font-size: 12px;
    color: #4b5563;
}
.metric-unit {
    color: #4b5563;
    font-weight: 500;
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    border: 1px solid #e5e7eb;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
}
th {
    background: #f3f4f6;
    font-weight: 600;
}
.caption {
    color: #4b5563;
    font-size: 12px;
    margin-bottom: 0;
}
.image-placeholder {
    border: 1px dashed #9ca3af;
    border-radius: 6px;
    padding: 8px;
    background: #f9fafb;
}
.image-meta {
    color: #4b5563;
    font-size: 12px;
}
.image-ref code {
    background: #f3f4f6;
    border-radius: 4px;
    padding: 2px 4px;
}
.empty {
    color: #6b7280;
    font-style: italic;
}
"""
