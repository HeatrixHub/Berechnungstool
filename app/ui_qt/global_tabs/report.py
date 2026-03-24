"""Global Qt tab for HTML report previews."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QTabWidget, QTextBrowser, QWidget

from app.core.reporting.builders import build_isolierung_report
from app.core.reporting.renderers import render_report_html
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
            "HTML-Vorschau des neuen Berichtssystems. "
            "Datenfluss: Plugin-States → Isolierung-Builder → ReportDocument → HTML-Renderer."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        refresh_button = QPushButton("Vorschau aktualisieren")
        refresh_button.clicked.connect(self.refresh_preview)
        layout.addLayout(create_button_row([refresh_button]))

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

        try:
            states = self._plugin_manager.export_all_states()
        except Exception as exc:
            self._set_status(f"Status: Fehler beim Export der Plugin-States ({exc}).")
            self._preview_browser.setHtml(_message_html("Plugin-Export fehlgeschlagen", str(exc)))
            return

        if not states:
            self._set_status("Status: Keine Plugin-States verfügbar.")
            self._preview_browser.setHtml(
                _message_html(
                    "Keine Daten vorhanden",
                    "Es wurden keine Plugin-States exportiert. Die Berichtsvorschau bleibt leer.",
                )
            )
            return

        isolierung_state = states.get("isolierung")
        if not isinstance(isolierung_state, Mapping):
            self._set_status("Status: Isolierung-State fehlt oder hat ein ungültiges Format.")
            self._preview_browser.setHtml(
                _message_html(
                    "Isolierungsdaten fehlen",
                    "Der State des Isolierung-Plugins ist nicht verfügbar.",
                )
            )
            return

        if not isolierung_state:
            self._set_status("Status: Isolierung-State ist leer.")
            self._preview_browser.setHtml(
                _message_html(
                    "Leerer Isolierung-State",
                    "Es liegen aktuell keine verwertbaren Isolierungsdaten vor.",
                )
            )
            return

        metadata = _resolve_report_metadata(isolierung_state)

        try:
            report_document = build_isolierung_report(
                isolierung_state,
                title=metadata["title"],
                project_name=metadata["project_name"],
                author=metadata["author"],
                additional_info=metadata["additional_info"],
            )
            preview_html = render_report_html(report_document)
        except Exception as exc:
            self._set_status(f"Status: Fehler bei der Berichtsvorschau ({exc}).")
            self._preview_browser.setHtml(
                _message_html(
                    "Berichtsvorschau fehlgeschlagen",
                    "Beim Aufbau oder Rendern der Vorschau ist ein Fehler aufgetreten.",
                )
            )
            return

        self._preview_browser.setHtml(preview_html)
        self._set_status("Status: Vorschau erfolgreich aktualisiert.")

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(text)


def _resolve_report_metadata(plugin_state: Mapping[str, Any]) -> dict[str, Any]:
    ui_state = plugin_state.get("ui") if isinstance(plugin_state.get("ui"), Mapping) else {}

    return {
        "title": _first_non_empty(
            ui_state.get("report_title") if isinstance(ui_state, Mapping) else None,
            "Technischer Bericht – Isolierung",
        ),
        "project_name": _first_non_empty(
            ui_state.get("project_name") if isinstance(ui_state, Mapping) else None,
            "Unbenanntes Projekt",
        ),
        "author": _first_non_empty(
            ui_state.get("author") if isinstance(ui_state, Mapping) else None,
            "Unbekannt",
        ),
        "additional_info": {
            "Quelle": "Qt-Berichte-Tab",
            "Plugin": "isolierung",
        },
    }


def _first_non_empty(*candidates: object) -> str:
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return ""


def _message_html(title: str, text: str) -> str:
    return (
        "<html><body style='font-family:Segoe UI,Arial,sans-serif;padding:18px;'>"
        f"<h2 style='margin-top:0;'>{title}</h2>"
        f"<p>{text}</p>"
        "</body></html>"
    )
