"""Global Qt tab placeholder for the upcoming reporting rebuild.

This module intentionally contains only a minimal UI. The previous mixed
architecture (template rendering, plugin-specific data shaping, preview text
rendering, chart generation, and PDF creation) was removed to create a clean
cut for a modular redesign.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTabWidget, QWidget

from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.ui_helpers import create_page_layout, create_button_row


class ReportTab:
    """Global report tab in a reduced, stable placeholder state."""

    def __init__(
        self,
        tab_widget: object,
        plugin_manager: QtPluginManager,
        *,
        title: str = "Bericht",
    ) -> None:
        self._tab_widget = tab_widget
        # Kept for the upcoming modular rebuild integration boundary.
        self._plugin_manager = plugin_manager

        self.widget = QWidget()
        self._build_ui()
        self._insert_tab(title)

    def _insert_tab(self, title: str) -> None:
        if isinstance(self._tab_widget, QTabWidget):
            self._tab_widget.insertTab(1, self.widget, title)
        else:
            self._tab_widget.addTab(self.widget, title)

    def _build_ui(self) -> None:
        layout = create_page_layout(self.widget, "Bericht", show_logo=True)

        hint = QLabel("Berichtssystem wird neu aufgebaut.")
        hint.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(hint)

        description = QLabel(
            "Der Berichte-Tab befindet sich im reduzierten Übergangsmodus. "
            "Berichtserstellung, Vorschau und Export sind vorübergehend deaktiviert."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        disabled_actions = create_button_row(
            [
                QPushButton("Vorschau (deaktiviert)"),
                QPushButton("PDF-Export (deaktiviert)"),
            ]
        )
        for index in range(disabled_actions.count()):
            item = disabled_actions.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setEnabled(False)
        layout.addLayout(disabled_actions)

        status = QLabel("Status: Platzhalter aktiv – Neuaufbau vorbereitet.")
        status.setWordWrap(True)
        layout.addWidget(status)
