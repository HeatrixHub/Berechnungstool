"""Fachlogik für UI-unabhängige Hilfsfunktionen der Isolierungen-DB."""
from __future__ import annotations

from pathlib import Path

from .logic import FileImportResult


def parse_required_float(value: str, label: str) -> float:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        raise ValueError(f"{label} darf nicht leer sein.")
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"{label} muss eine Zahl sein.")


def parse_optional_float(value: str) -> float | None:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError("Numerischer Wert erwartet (optional).")


def build_import_summary(imported: int, results: list[FileImportResult]) -> str:
    lines = [f"{imported} Isolierung(en) importiert."]
    skipped = [r for r in results if r.skipped_reason]
    per_file_errors = [r for r in results if r.errors]

    if skipped:
        lines.append("Übersprungene Dateien:")
        for result in skipped:
            lines.append(f"- {Path(result.file_path).name}: {result.skipped_reason}")

    if per_file_errors:
        lines.append("Fehlerhafte Zeilen:")
        for result in per_file_errors:
            lines.append(f"- {Path(result.file_path).name}:")
            lines.extend([f"    * {err}" for err in result.errors])

    return "\n".join(lines)
