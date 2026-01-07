"""Qt-Plugin für elektrische Leistungsberechnungen."""
from __future__ import annotations

import importlib.util
from typing import Any, Callable, Tuple, Type

from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from Elektrik.core.calculations import (
    calculate_single_phase,
    calculate_three_phase,
    parse_float,
)


class _StubWidget:
    def __init__(self) -> None:
        self.layout: object | None = None

    def setLayout(self, layout: object) -> None:
        self.layout = layout


class _StubLayout:
    def __init__(self) -> None:
        self.items: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.items.append(widget)

    def addLayout(self, layout: object) -> None:
        self.items.append(layout)


class _StubGridLayout(_StubLayout):
    def addWidget(self, widget: object, *_args: object, **_kwargs: object) -> None:
        self.items.append(widget)


class _StubLabel:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _StubLineEdit:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _StubSignal:
    def __init__(self) -> None:
        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def emit(self) -> None:
        if self._callback is not None:
            self._callback()


class _StubButton:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.clicked = _StubSignal()

    def setText(self, text: str) -> None:
        self._text = text


class _StubTabWidget(_StubWidget):
    def __init__(self) -> None:
        super().__init__()
        self._tabs: list[object] = []
        self._current_index = 0

    def addTab(self, widget: object, _title: str) -> None:
        self._tabs.append(widget)

    def setCurrentIndex(self, index: int) -> None:
        self._current_index = index

    def currentIndex(self) -> int:
        return self._current_index


class _StubGroupBox(_StubWidget):
    def __init__(self, _title: str = "") -> None:
        super().__init__()


class _StubFont:
    def __init__(self) -> None:
        self._bold = False
        self._point_size = 10

    def setBold(self, bold: bool) -> None:
        self._bold = bold

    def setPointSize(self, size: int) -> None:
        self._point_size = size


def _resolve_qt_widgets() -> Tuple[
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
    Type[object],
]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtWidgets import (
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
        from PyQt6.QtGui import QFont

        return (
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QGridLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTabWidget,
            QGroupBox,
            QFont,
        )
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtWidgets import (
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
        from PySide6.QtGui import QFont

        return (
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QGridLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTabWidget,
            QGroupBox,
            QFont,
        )
    return (
        _StubWidget,
        _StubLayout,
        _StubLayout,
        _StubGridLayout,
        _StubLabel,
        _StubLineEdit,
        _StubButton,
        _StubTabWidget,
        _StubGroupBox,
        _StubFont,
    )


class ElektrikQtPlugin(QtPlugin):
    """Qt-Plugin für elektrische Leistungsberechnungen."""

    _DEFAULT_RESULT = "Leistung: –"

    def __init__(self) -> None:
        self._identifier = "elektrik"
        self.widget: object | None = None
        self._tab_widget: object | None = None
        self._single_voltage_input: object | None = None
        self._single_current_input: object | None = None
        self._three_voltage_input: object | None = None
        self._three_current_input: object | None = None
        self._single_result_label: object | None = None
        self._three_result_label: object | None = None
        self._single_voltage_value = ""
        self._single_current_value = ""
        self._three_voltage_value = ""
        self._three_current_value = ""
        self._single_result_text = self._DEFAULT_RESULT
        self._three_result_text = self._DEFAULT_RESULT
        self._active_tab_index = 0

    @property
    def name(self) -> str:
        return "Elektrik"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        (
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QGridLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTabWidget,
            QGroupBox,
            QFont,
        ) = _resolve_qt_widgets()

        container = QWidget()
        layout = QVBoxLayout()

        header = QWidget()
        header_layout = QVBoxLayout()
        title = QLabel("Elektrische Leistung")
        title_font = QFont()
        if hasattr(title_font, "setPointSize"):
            title_font.setPointSize(14)
        if hasattr(title_font, "setBold"):
            title_font.setBold(True)
        if hasattr(title, "setFont"):
            title.setFont(title_font)
        subtitle = QLabel("Berechnung für ein- und dreiphasige Systeme")
        if hasattr(header_layout, "addWidget"):
            header_layout.addWidget(title)
            header_layout.addWidget(subtitle)
        if hasattr(header, "setLayout"):
            header.setLayout(header_layout)
        if hasattr(layout, "addWidget"):
            layout.addWidget(header)

        tab_widget = QTabWidget()
        self._tab_widget = tab_widget

        calculator_tab = QWidget()
        calculator_layout = QHBoxLayout()
        if hasattr(calculator_tab, "setLayout"):
            calculator_tab.setLayout(calculator_layout)
        if hasattr(tab_widget, "addTab"):
            tab_widget.addTab(calculator_tab, "Leistungsrechner")
        if hasattr(layout, "addWidget"):
            layout.addWidget(tab_widget)

        single_group = QGroupBox("Einphasig")
        single_layout = QGridLayout()
        if hasattr(single_group, "setLayout"):
            single_group.setLayout(single_layout)
        if hasattr(calculator_layout, "addWidget"):
            calculator_layout.addWidget(single_group)

        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(QLabel("Formel: P = U × I"), 0, 0, 1, 2)
            single_layout.addWidget(QLabel("Spannung U [V]"), 1, 0)
        single_voltage_input = QLineEdit()
        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(single_voltage_input, 1, 1)
        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(QLabel("Strom I [A]"), 2, 0)
        single_current_input = QLineEdit()
        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(single_current_input, 2, 1)
        single_button = QPushButton("Berechnen")
        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(single_button, 3, 0, 1, 2)
        single_result_label = QLabel(self._single_result_text)
        if hasattr(single_layout, "addWidget"):
            single_layout.addWidget(single_result_label, 4, 0, 1, 2)

        three_group = QGroupBox("Dreiphasig")
        three_layout = QGridLayout()
        if hasattr(three_group, "setLayout"):
            three_group.setLayout(three_layout)
        if hasattr(calculator_layout, "addWidget"):
            calculator_layout.addWidget(three_group)

        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(QLabel("Formel: P = U × I × √3"), 0, 0, 1, 2)
            three_layout.addWidget(QLabel("Außenleiterspannung U [V]"), 1, 0)
        three_voltage_input = QLineEdit()
        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(three_voltage_input, 1, 1)
        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(QLabel("Strom I [A]"), 2, 0)
        three_current_input = QLineEdit()
        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(three_current_input, 2, 1)
        three_button = QPushButton("Berechnen")
        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(three_button, 3, 0, 1, 2)
        three_result_label = QLabel(self._three_result_text)
        if hasattr(three_layout, "addWidget"):
            three_layout.addWidget(three_result_label, 4, 0, 1, 2)

        if hasattr(single_button, "clicked"):
            single_button.clicked.connect(self._calculate_single_phase)
        if hasattr(three_button, "clicked"):
            three_button.clicked.connect(self._calculate_three_phase)

        if hasattr(container, "setLayout"):
            container.setLayout(layout)

        self.widget = container
        self._single_voltage_input = single_voltage_input
        self._single_current_input = single_current_input
        self._three_voltage_input = three_voltage_input
        self._three_current_input = three_current_input
        self._single_result_label = single_result_label
        self._three_result_label = three_result_label

        self.refresh_view()

    def _calculate_single_phase(self) -> None:
        voltage_text = self._get_input_text(self._single_voltage_input)
        current_text = self._get_input_text(self._single_current_input)
        self._single_voltage_value = voltage_text
        self._single_current_value = current_text
        voltage = parse_float(voltage_text)
        current = parse_float(current_text)
        if voltage is None or current is None:
            self._single_result_text = "Leistung: Bitte gültige Zahlen angeben."
        else:
            power = calculate_single_phase(voltage, current)
            self._single_result_text = f"Leistung: {power:,.2f} W"
        self._set_label_text(self._single_result_label, self._single_result_text)

    def _calculate_three_phase(self) -> None:
        voltage_text = self._get_input_text(self._three_voltage_input)
        current_text = self._get_input_text(self._three_current_input)
        self._three_voltage_value = voltage_text
        self._three_current_value = current_text
        voltage = parse_float(voltage_text)
        current = parse_float(current_text)
        if voltage is None or current is None:
            self._three_result_text = "Leistung: Bitte gültige Zahlen angeben."
        else:
            power = calculate_three_phase(voltage, current)
            self._three_result_text = f"Leistung: {power:,.2f} W"
        self._set_label_text(self._three_result_label, self._three_result_text)

    def export_state(self) -> dict[str, Any]:
        state = {
            "inputs": {
                "single_voltage": self._resolve_input_value(
                    self._single_voltage_input, self._single_voltage_value
                ),
                "single_current": self._resolve_input_value(
                    self._single_current_input, self._single_current_value
                ),
                "three_voltage": self._resolve_input_value(
                    self._three_voltage_input, self._three_voltage_value
                ),
                "three_current": self._resolve_input_value(
                    self._three_current_input, self._three_current_value
                ),
            },
            "results": {
                "single_result": self._resolve_label_value(
                    self._single_result_label, self._single_result_text
                ),
                "three_result": self._resolve_label_value(
                    self._three_result_label, self._three_result_text
                ),
            },
            "ui": {
                "active_tab": self._get_active_tab_index(),
            },
        }
        return self.validate_state(state)

    def import_state(self, state: dict[str, Any]) -> None:
        super().import_state(state)

    def apply_state(self, state: dict[str, Any]) -> None:
        inputs = state.get("inputs", {})
        results = state.get("results", {})
        ui_state = state.get("ui", {})

        if isinstance(inputs, dict):
            self._single_voltage_value = self._coerce_str(inputs.get("single_voltage", ""))
            self._single_current_value = self._coerce_str(inputs.get("single_current", ""))
            self._three_voltage_value = self._coerce_str(inputs.get("three_voltage", ""))
            self._three_current_value = self._coerce_str(inputs.get("three_current", ""))
        if isinstance(results, dict):
            self._single_result_text = self._coerce_str(
                results.get("single_result", self._DEFAULT_RESULT),
                default=self._DEFAULT_RESULT,
            )
            self._three_result_text = self._coerce_str(
                results.get("three_result", self._DEFAULT_RESULT),
                default=self._DEFAULT_RESULT,
            )
        if isinstance(ui_state, dict):
            active_tab = ui_state.get("active_tab")
            if isinstance(active_tab, int):
                self._active_tab_index = active_tab

    def refresh_view(self) -> None:
        self._set_input_text(self._single_voltage_input, self._single_voltage_value)
        self._set_input_text(self._single_current_input, self._single_current_value)
        self._set_input_text(self._three_voltage_input, self._three_voltage_value)
        self._set_input_text(self._three_current_input, self._three_current_value)
        self._set_label_text(self._single_result_label, self._single_result_text)
        self._set_label_text(self._three_result_label, self._three_result_text)
        if self._tab_widget is not None and hasattr(self._tab_widget, "setCurrentIndex"):
            self._tab_widget.setCurrentIndex(self._active_tab_index)

    @staticmethod
    def _get_input_text(widget: object | None) -> str:
        if widget is None:
            return ""
        if hasattr(widget, "text"):
            try:
                text = widget.text()
            except TypeError:
                return ""
            if isinstance(text, str):
                return text
        return ""

    @staticmethod
    def _set_input_text(widget: object | None, value: str) -> None:
        if widget is None:
            return
        if hasattr(widget, "setText"):
            widget.setText(value)

    @staticmethod
    def _get_label_text(widget: object | None) -> str:
        if widget is None:
            return ""
        if hasattr(widget, "text"):
            text = widget.text()
            if isinstance(text, str):
                return text
        return ""

    @staticmethod
    def _set_label_text(widget: object | None, value: str) -> None:
        if widget is None:
            return
        if hasattr(widget, "setText"):
            widget.setText(value)

    @staticmethod
    def _resolve_input_value(widget: object | None, fallback: str) -> str:
        if widget is None:
            return fallback
        return ElektrikQtPlugin._get_input_text(widget)

    @staticmethod
    def _resolve_label_value(widget: object | None, fallback: str) -> str:
        if widget is None:
            return fallback
        return ElektrikQtPlugin._get_label_text(widget)

    @staticmethod
    def _coerce_str(value: object, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    def _get_active_tab_index(self) -> int:
        if self._tab_widget is None:
            return self._active_tab_index
        if hasattr(self._tab_widget, "currentIndex"):
            index = self._tab_widget.currentIndex()
            if isinstance(index, int):
                return index
        return self._active_tab_index


__all__ = ["ElektrikQtPlugin"]
