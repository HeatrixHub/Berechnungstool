"""Abstraktion für ReportLab-basierte PDF-Berichte."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import (
    ReportBulletList,
    ReportElement,
    ReportHeading,
    ReportImage,
    ReportPageBreak,
    ReportParagraph,
    ReportSpacer,
    ReportTable,
    StructuredReport,
)


class ReportBuilder:
    """Kapselt die PDF-Erstellung mit ReportLab.

    Plugins interagieren ausschließlich mit dieser Klasse, nicht direkt mit
    ReportLab-Canvas-Objekten.
    """

    def __init__(self, target: Path, *, title: str | None = None) -> None:
        self.target = Path(target)
        self.pagesize = A4
        self.title = title
        self._styles = getSampleStyleSheet()
        self._styles.add(
            ParagraphStyle(
                name="ListItem",
                parent=self._styles["BodyText"],
                leftIndent=16,
                bulletIndent=6,
                spaceBefore=2,
                spaceAfter=2,
            )
        )
        self._story: list = []

    # ------------------------------------------------------------------
    # Elementare Bausteine
    # ------------------------------------------------------------------
    def add_heading(self, text: str, level: int = 1) -> None:
        style_name = f"Heading{min(max(level, 1), 3)}"
        style = self._styles.get(style_name, self._styles["Heading3"])
        self._story.append(Paragraph(text, style))
        self.add_spacer(6)

    def add_paragraph(self, text: str) -> None:
        self._story.append(Paragraph(text, self._styles["BodyText"]))
        self.add_spacer(6)

    def add_bullet_list(self, items: Sequence[str]) -> None:
        list_items = [
            ListItem(Paragraph(str(item), self._styles["ListItem"]), value="bullet")
            for item in items
        ]
        flowable = ListFlowable(
            list_items,
            bulletType="bullet",
            start="bullet",
            leftIndent=0,
            bulletFontName=self._styles["BodyText"].fontName,
        )
        self._story.append(flowable)
        self.add_spacer(6)

    def add_table(
        self,
        rows: Sequence[Sequence[str]],
        *,
        headers: Sequence[str] | None = None,
        column_widths: Sequence[int | float] | None = None,
    ) -> None:
        data = []
        if headers:
            data.append([str(item) for item in headers])
        data.extend([[str(cell) for cell in row] for row in rows])
        table = Table(data, colWidths=column_widths, repeatRows=1 if headers else 0)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey if headers else colors.white),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        self._story.append(table)
        self.add_spacer(8)

    def add_image(self, path: Path, *, width: float | None = None, height: float | None = None) -> None:
        image = Image(str(path), width=width, height=height)
        image.hAlign = "LEFT"
        self._story.append(image)
        self.add_spacer(6)

    def add_spacer(self, size: float = 12) -> None:
        self._story.append(Spacer(1, size))

    def add_page_break(self) -> None:
        self._story.append(PageBreak())

    # ------------------------------------------------------------------
    # Komposition & Speicherung
    # ------------------------------------------------------------------
    def add_elements(self, elements: Sequence[ReportElement]) -> None:
        for element in elements:
            if isinstance(element, ReportHeading):
                self.add_heading(element.text, level=element.level)
            elif isinstance(element, ReportParagraph):
                self.add_paragraph(element.text)
            elif isinstance(element, ReportBulletList):
                self.add_bullet_list(element.items)
            elif isinstance(element, ReportTable):
                self.add_table(
                    element.rows,
                    headers=element.headers,
                    column_widths=element.column_widths,
                )
            elif isinstance(element, ReportImage):
                self.add_image(element.path, width=element.width, height=element.height)
            elif isinstance(element, ReportSpacer):
                self.add_spacer(element.size)
            elif isinstance(element, ReportPageBreak):
                self.add_page_break()
            else:  # pragma: no cover - defensive
                raise TypeError(f"Unbekanntes Report-Element: {element!r}")

    def render_structured_report(self, report: StructuredReport) -> None:
        if report.title:
            self.add_heading(report.title, level=1)
        self.add_elements(report.elements)

    def build(self) -> None:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(self.target), pagesize=self.pagesize, title=self.title)
        doc.build(self._story)
