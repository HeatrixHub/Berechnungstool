"""Global Qt tab for PDF report previews and export."""
from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QFileDialog, QFormLayout, QLineEdit, QLabel, QPushButton, QTabWidget, QWidget

from app.core.reporting import ReportDocument
from app.core.reporting.builders import build_isolierung_report, resolve_isolierung_report_metadata
from app.core.reporting.renderers import render_report_pdf
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.ui_helpers import create_button_row, create_page_layout


class ReportTab:
    """Global report tab with renderer-neutral preview orchestration."""

    def __init__(
        self,
        tab_widget: object,
        plugin_manager: QtPluginManager,
        *,
        title: str = "Bericht",
    ) -> None:
        self._tab_widget = tab_widget
        self._plugin_manager = plugin_manager

        self.widget = QWidget()
        self._project_name_input: QLineEdit | None = None
        self._author_input: QLineEdit | None = None
        self._preview_pdf_view: QPdfView | None = None
        self._preview_pdf_document: QPdfDocument | None = None
        self._preview_pdf_path: Path | None = None
        self._stale_preview_pdf_paths: list[Path] = []
        self._status_label: QLabel | None = None

        self._build_ui()
        self._insert_tab(title)

    def _insert_tab(self, title: str) -> None:
        if isinstance(self._tab_widget, QTabWidget):
            self._tab_widget.insertTab(1, self.widget, title)
        else:
            self._tab_widget.addTab(self.widget, title)

    def _build_ui(self) -> None:
        layout = create_page_layout(self.widget, "Bericht", show_logo=True)

        description = QLabel(
            "PDF-Vorschau und PDF-Export aus derselben ReportDocument-Quelle. "
            "Datenfluss: Plugin-States → Metadaten-Auflösung (inkl. Eingaben) "
            "→ Isolierung-Builder → ReportDocument → PDF-Renderer."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        metadata_form = QFormLayout()
        self._project_name_input = QLineEdit()
        self._project_name_input.setPlaceholderText("Projektname für den Bericht")
        self._author_input = QLineEdit()
        self._author_input.setPlaceholderText("Autor für den Bericht")
        metadata_form.addRow("Projektname", self._project_name_input)
        metadata_form.addRow("Autor", self._author_input)
        layout.addLayout(metadata_form)

        refresh_button = QPushButton("Vorschau aktualisieren")
        refresh_button.clicked.connect(self.refresh_preview)

        export_pdf_button = QPushButton("PDF exportieren")
        export_pdf_button.clicked.connect(self.export_pdf)
        layout.addLayout(create_button_row([refresh_button, export_pdf_button]))

        self._status_label = QLabel("Status: Vorschau noch nicht aktualisiert.")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._preview_pdf_document = QPdfDocument(self.widget)
        self._preview_pdf_view = QPdfView()
        self._preview_pdf_view.setDocument(self._preview_pdf_document)
        self._preview_pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._preview_pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(self._preview_pdf_view, stretch=1)

    def refresh_preview(self) -> None:
        if self._preview_pdf_document is None:
            return

        self._cleanup_stale_preview_paths()

        report_document = self._build_report_document()
        if report_document is None:
            return

        previous_preview_path = self._preview_pdf_path
        self._release_preview_document()

        try:
            preview_path = self._render_preview_pdf(report_document)
        except Exception as exc:
            self._set_status(f"Status: Fehler bei der Berichtsvorschau ({exc}).")
            self._preview_pdf_path = previous_preview_path
            return

        load_result = self._preview_pdf_document.load(str(preview_path))
        if load_result != QPdfDocument.Error.None_:
            self._set_status("Status: PDF-Vorschau konnte nicht geladen werden.")
            self._queue_stale_preview_path(preview_path)
            self._preview_pdf_path = previous_preview_path
            self._cleanup_stale_preview_paths()
            return

        self._preview_pdf_path = preview_path
        self._queue_stale_preview_path(previous_preview_path)
        self._cleanup_stale_preview_paths()
        self._set_status("Status: Vorschau erfolgreich aktualisiert.")

    def export_pdf(self) -> None:
        report_document = self._build_report_document()
        if report_document is None:
            return

        default_file_name = _sanitize_file_name(f"{report_document.metadata.project_name or 'bericht'}_bericht.pdf")
        selected_path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "PDF-Bericht speichern",
            default_file_name,
            "PDF-Dateien (*.pdf)",
        )
        if not selected_path:
            self._set_status("Status: PDF-Export abgebrochen.")
            return

        if not selected_path.lower().endswith(".pdf"):
            selected_path = f"{selected_path}.pdf"

        try:
            saved_path = render_report_pdf(report_document, selected_path)
        except Exception as exc:
            self._set_status(f"Status: PDF-Export fehlgeschlagen ({exc}).")
            return

        self._set_status(f"Status: PDF erfolgreich exportiert nach: {saved_path}")

    def _build_report_document(self) -> ReportDocument | None:
        try:
            states = self._plugin_manager.export_all_states()
        except Exception as exc:
            self._set_status(f"Status: Fehler beim Export der Plugin-States ({exc}).")
            return None

        if not states:
            self._set_status("Status: Keine Plugin-States verfügbar.")
            return None

        isolierung_state = states.get("isolierung")
        if not isinstance(isolierung_state, Mapping):
            self._set_status("Status: Isolierung-State fehlt oder hat ein ungültiges Format.")
            return None

        if not isolierung_state:
            self._set_status("Status: Isolierung-State ist leer.")
            return None

        metadata = self._resolve_report_metadata(isolierung_state)

        try:
            return build_isolierung_report(
                isolierung_state,
                title=metadata["title"],
                project_name=metadata["project_name"],
                author=metadata["author"],
                additional_info=metadata["additional_info"],
            )
        except Exception as exc:
            self._set_status(f"Status: Fehler beim Aufbau des Berichtsdokuments ({exc}).")
            return None

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(text)

    def _resolve_report_metadata(self, plugin_state: Mapping[str, object]) -> dict[str, object]:
        resolved_metadata = resolve_isolierung_report_metadata(plugin_state)
        manual_project_name = self._manual_input_value(self._project_name_input)
        manual_author = self._manual_input_value(self._author_input)

        return {
            "title": resolved_metadata.get("title"),
            "project_name": manual_project_name or resolved_metadata.get("project_name"),
            "author": manual_author or resolved_metadata.get("author"),
            "additional_info": resolved_metadata.get("additional_info", {}),
        }

    def _render_preview_pdf(self, report_document: ReportDocument) -> Path:
        with tempfile.NamedTemporaryFile(prefix="heatrix_report_preview_", suffix=".pdf", delete=False) as handle:
            preview_path = Path(handle.name)
        return render_report_pdf(report_document, preview_path)

    def _release_preview_document(self) -> None:
        if self._preview_pdf_document is not None:
            self._preview_pdf_document.close()

    def _queue_stale_preview_path(self, preview_path: Path | None) -> None:
        if preview_path is None:
            return
        if preview_path == self._preview_pdf_path:
            return
        if preview_path not in self._stale_preview_pdf_paths:
            self._stale_preview_pdf_paths.append(preview_path)

    def _cleanup_stale_preview_paths(self) -> None:
        if not self._stale_preview_pdf_paths:
            return

        remaining_paths: list[Path] = []
        for stale_path in self._stale_preview_pdf_paths:
            if stale_path == self._preview_pdf_path:
                remaining_paths.append(stale_path)
                continue
            try:
                stale_path.unlink(missing_ok=True)
            except OSError:
                remaining_paths.append(stale_path)
        self._stale_preview_pdf_paths = remaining_paths

    @staticmethod
    def _manual_input_value(line_edit: QLineEdit | None) -> str | None:
        if line_edit is None:
            return None
        value = line_edit.text().strip()
        return value or None


def _sanitize_file_name(name: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in forbidden else ch for ch in (name or "bericht.pdf"))
    return cleaned.strip() or "bericht.pdf"
