"""Hilfsfunktionen zum Rendern von Preppy-Templates in PDFs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import preppy

from .builder import ReportBuilder
from .models import StructuredReport


class PreppyTemplateRenderer:
    """Kompiliert eine Preppy-Template-Datei und schreibt sie in einen ReportBuilder."""

    def __init__(self, template_path: Path) -> None:
        self.template_path = Path(template_path)

    def render(self, builder: ReportBuilder, context: Mapping[str, Any]) -> None:
        module = preppy.getModule(str(self.template_path))
        structured = module.getOutput(context)
        report = StructuredReport.from_raw(structured)
        builder.render_structured_report(report)
