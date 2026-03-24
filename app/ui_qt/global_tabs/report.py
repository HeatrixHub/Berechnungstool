"""Global Qt tab for HTML report previews and PDF export."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QTabWidget, QTextBrowser, QWidget

from app.core.reporting import ReportDocument
from app.core.reporting.builders import build_isolierung_report, resolve_isolierung_report_metadata
from app.core.reporting.renderers import render_report_html, render_report_pdf
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
        self._preview_browser: QTextBrowser | None = None
        self._status_label: QLabel | None = None

        self._build_ui()
        self._insert_tab(title)
        self.refresh_preview()

    def _insert_tab(self, title: str) -> None:
        if isinstance(self._tab_widget, QTabWidget):
            self._tab_widget.insertTab(1, self.widget, title)
        else:
            self._tab_widget.addTab(self.widget, title)

    def _build_ui(self) -> None:
        layout = create_page_layout(self.widget, "Bericht", show_logo=True)

        description = QLabel(
            "HTML-Vorschau und PDF-Export des Berichtssystems. "
            "Datenfluss: Plugin-States → Isolierung-Builder → ReportDocument → HTML/PDF-Renderer."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        refresh_button = QPushButton("Vorschau aktualisieren")
        refresh_button.clicked.connect(self.refresh_preview)

        export_pdf_button = QPushButton("PDF exportieren")
        export_pdf_button.clicked.connect(self.export_pdf)
        layout.addLayout(create_button_row([refresh_button, export_pdf_button]))

        self._status_label = QLabel("Status: Vorschau wird initialisiert …")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._preview_browser = QTextBrowser()
        self._preview_browser.setOpenExternalLinks(False)
        self._preview_browser.setPlaceholderText("Noch keine Berichtsvorschau vorhanden.")
        layout.addWidget(self._preview_browser, stretch=1)

    def refresh_preview(self) -> None:
        if self._preview_browser is None:
            return

        report_document = self._build_report_document()
        if report_document is None:
            return

        try:
            preview_html = render_report_html(report_document)
        except Exception as exc:
            self._set_status(f"Status: Fehler bei der Berichtsvorschau ({exc}).")
            self._preview_browser.setHtml(
                _message_html(
                    "Berichtsvorschau fehlgeschlagen",
                    "Beim Rendern der Vorschau ist ein Fehler aufgetreten.",
                )
            )
            return

        self._preview_browser.setHtml(preview_html)
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
        if self._preview_browser is None:
            return None

        try:
            states = self._plugin_manager.export_all_states()
        except Exception as exc:
            self._set_status(f"Status: Fehler beim Export der Plugin-States ({exc}).")
            self._preview_browser.setHtml(_message_html("Plugin-Export fehlgeschlagen", str(exc)))
            return None

        if not states:
            self._set_status("Status: Keine Plugin-States verfügbar.")
            self._preview_browser.setHtml(
                _message_html(
                    "Keine Daten vorhanden",
                    "Es wurden keine Plugin-States exportiert. Die Berichtsvorschau bleibt leer.",
                )
            )
            return None

        isolierung_state = states.get("isolierung")
        if not isinstance(isolierung_state, Mapping):
            self._set_status("Status: Isolierung-State fehlt oder hat ein ungültiges Format.")
            self._preview_browser.setHtml(
                _message_html(
                    "Isolierungsdaten fehlen",
                    "Der State des Isolierung-Plugins ist nicht verfügbar.",
                )
            )
            return None

        if not isolierung_state:
            self._set_status("Status: Isolierung-State ist leer.")
            self._preview_browser.setHtml(
                _message_html(
                    "Leerer Isolierung-State",
                    "Es liegen aktuell keine verwertbaren Isolierungsdaten vor.",
                )
            )
            return None

        metadata = resolve_isolierung_report_metadata(isolierung_state)

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
            self._preview_browser.setHtml(
                _message_html(
                    "Berichtsdokument fehlgeschlagen",
                    "Beim Aufbau des ReportDocument ist ein Fehler aufgetreten.",
                )
            )
            return None

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(text)


def _sanitize_file_name(name: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in forbidden else ch for ch in (name or "bericht.pdf"))
    return cleaned.strip() or "bericht.pdf"


def _message_html(title: str, text: str) -> str:
    return (
        "<html><body style='font-family:Segoe UI,Arial,sans-serif;padding:18px;'>"
        f"<h2 style='margin-top:0;'>{title}</h2>"
        f"<p>{text}</p>"
        "</body></html>"
    )
