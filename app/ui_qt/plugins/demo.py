"""Demo Qt plugins for the host shell."""
from __future__ import annotations

import importlib.util
from typing import Tuple, Type

from app.ui_qt.plugins.base import QtAppContext, QtPlugin


class _StubWidget:
    def __init__(self) -> None:
        self.layout: object | None = None

    def setLayout(self, layout: object) -> None:
        self.layout = layout


class _StubLayout:
    def __init__(self) -> None:
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.widgets.append(widget)


class _StubLabel:
    def __init__(self, text: str) -> None:
        self.text = text

    def setText(self, text: str) -> None:
        self.text = text


def _resolve_qt_widgets() -> Tuple[Type[object], Type[object], Type[object]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

        return QWidget, QVBoxLayout, QLabel
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        return QWidget, QVBoxLayout, QLabel
    return _StubWidget, _StubLayout, _StubLabel


class DemoOverviewPlugin(QtPlugin):
    def __init__(self) -> None:
        self._identifier = ""
        self.widget: object | None = None
        self.label: object | None = None
        self._label_text = "Demo-Inhalt für Übersicht"

    @property
    def name(self) -> str:
        return "Übersicht"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        QWidget, QVBoxLayout, QLabel = _resolve_qt_widgets()
        widget = QWidget()
        layout = QVBoxLayout()
        label = QLabel(self._label_text)
        if hasattr(layout, "addWidget"):
            layout.addWidget(label)
        if hasattr(widget, "setLayout"):
            widget.setLayout(layout)
        self.label = label
        self.widget = widget

    def export_state(self) -> dict[str, object]:
        state = {
            "inputs": {},
            "results": {},
            "ui": {"label_text": self._label_text},
        }
        return self.validate_state(state)

    def import_state(self, state: dict[str, object]) -> None:
        super().import_state(state)

    def apply_state(self, state: dict[str, object]) -> None:
        ui_state = state.get("ui", {})
        if isinstance(ui_state, dict):
            label_text = ui_state.get("label_text")
            if isinstance(label_text, str):
                self._label_text = label_text

    def refresh_view(self) -> None:
        if self.label is not None and hasattr(self.label, "setText"):
            self.label.setText(self._label_text)


class DemoSettingsPlugin(QtPlugin):
    def __init__(self) -> None:
        self._identifier = ""
        self.widget: object | None = None
        self.label: object | None = None
        self._label_text = "Platzhalter für Einstellungen"

    @property
    def name(self) -> str:
        return "Einstellungen"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        QWidget, QVBoxLayout, QLabel = _resolve_qt_widgets()
        widget = QWidget()
        layout = QVBoxLayout()
        label = QLabel(self._label_text)
        if hasattr(layout, "addWidget"):
            layout.addWidget(label)
        if hasattr(widget, "setLayout"):
            widget.setLayout(layout)
        self.label = label
        self.widget = widget

    def export_state(self) -> dict[str, object]:
        state = {
            "inputs": {},
            "results": {},
            "ui": {"label_text": self._label_text},
        }
        return self.validate_state(state)

    def import_state(self, state: dict[str, object]) -> None:
        super().import_state(state)

    def apply_state(self, state: dict[str, object]) -> None:
        ui_state = state.get("ui", {})
        if isinstance(ui_state, dict):
            label_text = ui_state.get("label_text")
            if isinstance(label_text, str):
                self._label_text = label_text

    def refresh_view(self) -> None:
        if self.label is not None and hasattr(self.label, "setText"):
            self.label.setText(self._label_text)
