"""PDF renderer for renderer-neutral report documents."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.reporting.assets import build_temperature_profile_chart
from app.core.reporting.report_document import (
    ImageBlock,
    MetricFormatHint,
    MetricItem,
    MetricsBlock,
    ReportDocument,
    TableBlock,
    TableColumn,
    TableRow,
    TextBlock,
)


def render_report_pdf(document: ReportDocument, output_path: str | Path) -> Path:
    """Render the standard report to a PDF file."""

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles(ParagraphStyle, getSampleStyleSheet, colors)
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=document.metadata.title,
        author=document.metadata.author,
    )

    story: list[Any] = []
    _append_title(story, document, styles, Paragraph, Spacer, mm)
    _append_project_metadata(story, document, styles, Paragraph, Spacer, Table, TableStyle, colors, mm)
    _append_general_metrics(story, document, styles, Paragraph, Spacer, Table, TableStyle, colors, mm)
    _append_layer_table(story, document, styles, Paragraph, Spacer, Table, TableStyle, colors, mm)
    _append_temperature_profile(story, document, styles, Paragraph, Spacer, Image, mm)

    doc.build(story)
    return target


def _append_title(story: list[Any], document: ReportDocument, styles: dict[str, Any], Paragraph: Any, Spacer: Any, mm: Any) -> None:
    title = (document.metadata.title or "Technischer Bericht").strip() or "Technischer Bericht"
    story.append(Paragraph(title, styles["title"]))
    story.append(Spacer(1, 4 * mm))


def _append_project_metadata(
    story: list[Any],
    document: ReportDocument,
    styles: dict[str, Any],
    Paragraph: Any,
    Spacer: Any,
    Table: Any,
    TableStyle: Any,
    colors: Any,
    mm: Any,
) -> None:
    created_at = _format_datetime(document.metadata.created_at)
    metadata_rows = [
        [Paragraph("<b>Projekt</b>", styles["label"]), Paragraph(_safe_text(document.metadata.project_name, "Unbenanntes Projekt"), styles["value"])],
        [Paragraph("<b>Autor</b>", styles["label"]), Paragraph(_safe_text(document.metadata.author, "Unbekannt"), styles["value"])],
        [Paragraph("<b>Erstellt</b>", styles["label"]), Paragraph(created_at, styles["value"])],
    ]

    for key, value in sorted(document.metadata.additional_info.items()):
        metadata_rows.append([
            Paragraph(f"<b>{_safe_text(key, 'Info')}</b>", styles["label"]),
            Paragraph(_safe_text(value, "–"), styles["value"]),
        ])

    table = Table(metadata_rows, colWidths=[45 * mm, 125 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.gainsboro),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(table)
    story.append(Spacer(1, 6 * mm))


def _append_general_metrics(
    story: list[Any],
    document: ReportDocument,
    styles: dict[str, Any],
    Paragraph: Any,
    Spacer: Any,
    Table: Any,
    TableStyle: Any,
    colors: Any,
    mm: Any,
) -> None:
    story.append(Paragraph("Allgemeine Daten", styles["heading"]))
    metrics_block = _find_metrics_block(document)

    if metrics_block is None or not metrics_block.metrics:
        story.append(Paragraph("Keine Kennzahlen verfügbar.", styles["body"]))
        story.append(Spacer(1, 5 * mm))
        return

    metric_rows: list[list[Any]] = []
    for metric in metrics_block.metrics:
        label = metric.label or metric.key
        if metric.unit:
            label = f"{label} [{metric.unit}]"
        metric_rows.append([
            Paragraph(_safe_text(label, metric.key), styles["label"]),
            Paragraph(_format_metric_value(metric), styles["value"]),
        ])

    metrics_table = Table(metric_rows, colWidths=[95 * mm, 75 * mm], hAlign="LEFT")
    metrics_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.gainsboro),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(metrics_table)

    note = _find_general_text(document)
    if note:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(note, styles["hint"]))

    story.append(Spacer(1, 6 * mm))


def _append_layer_table(
    story: list[Any],
    document: ReportDocument,
    styles: dict[str, Any],
    Paragraph: Any,
    Spacer: Any,
    Table: Any,
    TableStyle: Any,
    colors: Any,
    mm: Any,
) -> None:
    story.append(Paragraph("Schichtübersicht", styles["heading"]))
    table_block = _find_layer_table_block(document)
    if table_block is None or not table_block.columns:
        story.append(Paragraph("Keine Schichtdaten verfügbar.", styles["body"]))
        story.append(Spacer(1, 5 * mm))
        return

    header = [Paragraph(_column_label(column).replace("\n", "<br/>"), styles["value"]) for column in table_block.columns]
    rows = [header]

    if table_block.rows:
        for row in table_block.rows:
            rows.append([_format_table_cell(row, column) for column in table_block.columns])
    else:
        rows.append(["Keine Tabellenzeilen verfügbar."] + [""] * (len(table_block.columns) - 1))

    col_widths = _layer_table_col_widths(table_block.columns, mm)
    grid = Table(rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(grid)
    story.append(Spacer(1, 6 * mm))


def _append_temperature_profile(
    story: list[Any],
    document: ReportDocument,
    styles: dict[str, Any],
    Paragraph: Any,
    Spacer: Any,
    Image: Any,
    mm: Any,
) -> None:
    story.append(Paragraph("Temperaturverlauf", styles["heading"]))
    chart_bytes = build_temperature_profile_chart(document)

    if chart_bytes:
        image = Image(BytesIO(chart_bytes))
        image.drawWidth = 160 * mm
        image.drawHeight = 72 * mm
        story.append(image)
        caption = _find_temperature_caption(document)
        if caption:
            story.append(Spacer(1, 1.5 * mm))
            story.append(Paragraph(caption, styles["hint"]))
    else:
        story.append(Paragraph("Kein Diagramm verfügbar (unzureichende Temperaturdaten).", styles["body"]))


def _find_metrics_block(document: ReportDocument) -> MetricsBlock | None:
    for section in document.sections:
        if section.id != "allgemeine-daten":
            continue
        for block in section.blocks:
            if isinstance(block, MetricsBlock):
                return block
    return None


def _find_general_text(document: ReportDocument) -> str | None:
    for section in document.sections:
        if section.id != "allgemeine-daten":
            continue
        for block in section.blocks:
            if isinstance(block, TextBlock) and block.text.strip():
                return block.text.strip()
    return None


def _find_layer_table_block(document: ReportDocument) -> TableBlock | None:
    for section in document.sections:
        if section.id != "schichttabelle":
            continue
        for block in section.blocks:
            if isinstance(block, TableBlock):
                return block
    return None


def _find_temperature_caption(document: ReportDocument) -> str | None:
    for section in document.sections:
        if section.id != "temperaturverlauf":
            continue
        for block in section.blocks:
            if isinstance(block, ImageBlock) and block.caption and block.caption.strip():
                return block.caption.strip()
    return None


def _column_label(column: TableColumn) -> str:
    if column.unit:
        return f"{column.label} [{column.unit}]"
    return column.label


def _format_metric_value(metric: MetricItem) -> str:
    value = metric.value
    if value is None:
        return "–"

    hint: MetricFormatHint = metric.format_hint
    if hint == "number":
        return _format_number(value)
    if hint == "integer":
        return _format_integer(value)
    if hint == "percentage":
        if isinstance(value, (int, float)):
            percentage = value * 100 if abs(float(value)) <= 1 else float(value)
            return f"{_format_number(percentage)} %"
        return f"{value} %"
    if hint == "list" and isinstance(value, list):
        return ", ".join(_format_number(item) if isinstance(item, (int, float)) else str(item) for item in value)
    if hint == "status":
        return str(value).capitalize()

    return str(value)


def _format_table_cell(row: TableRow, column: TableColumn) -> str:
    value = row.cells.get(column.key)
    if value is None:
        return "–"

    if column.value_type == "number":
        return _format_number(value)
    if column.value_type == "integer":
        return _format_integer(value)
    if column.value_type == "status":
        return str(value).capitalize()
    return str(value)


def _format_number(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return _format_number_german(float(value), decimal_places=0)
    if isinstance(value, float):
        return _format_number_german(value, decimal_places=3)
    return str(value)


def _format_integer(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(int(round(float(value))))
    return str(value)


def _build_styles(ParagraphStyle: Any, getSampleStyleSheet: Any, colors: Any) -> dict[str, Any]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "ReportHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=2,
            spaceAfter=3,
        ),
        "label": ParagraphStyle("Label", parent=sample["BodyText"], fontName="Helvetica", fontSize=9, leading=11),
        "value": ParagraphStyle("Value", parent=sample["BodyText"], fontName="Helvetica", fontSize=9, leading=11),
        "body": ParagraphStyle("Body", parent=sample["BodyText"], fontName="Helvetica", fontSize=9, leading=11),
        "hint": ParagraphStyle("Hint", parent=sample["BodyText"], fontName="Helvetica-Oblique", fontSize=8, textColor=colors.grey),
    }


def _safe_text(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _format_datetime(value: datetime | object) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%d.%m.%Y %H:%M")
    return "Unbekannt"


def _format_number_german(value: float, *, decimal_places: int) -> str:
    text = f"{value:,.{decimal_places}f}"
    if decimal_places > 0:
        text = text.rstrip("0").rstrip(".")
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _layer_table_col_widths(columns: list[TableColumn], mm: Any) -> list[float]:
    if not columns:
        return []
    if len(columns) == 6:
        return [37 * mm, 18 * mm, 30 * mm, 30 * mm, 27 * mm, 28 * mm]
    col_width = 170 * mm / len(columns)
    return [col_width] * len(columns)
