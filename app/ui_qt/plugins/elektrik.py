"""Qt-Plugin für elektrische Leistungsberechnungen."""
from __future__ import annotations

from typing import Any

from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from Elektrik.core.calculations import (
    calculate_single_phase,
    calculate_three_phase,
    parse_float,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui_qt.ui_helpers import create_page_layout, make_grid, make_hbox



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
        self._single_result_value: float | None = None
        self._single_result_status = "error"
        self._single_result_message = ""
        self._three_result_value: float | None = None
        self._three_result_status = "error"
        self._three_result_message = ""
        self._active_tab_index = 0

    @property
    def name(self) -> str:
        return "Elektrik"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        container = QWidget()
        layout = create_page_layout(
            container,
            "Elektrische Leistung",
            subtitle="Berechnung für ein- und dreiphasige Systeme",
            show_logo=True,
        )

        tab_widget = QTabWidget()
        self._tab_widget = tab_widget

        calculator_tab = QWidget()
        calculator_layout = create_page_layout(calculator_tab, "Leistungsrechner")
        calculator_content = make_hbox()
        calculator_content.setSpacing(16)
        calculator_layout.addLayout(calculator_content)
        tab_widget.addTab(calculator_tab, "Leistungsrechner")
        layout.addWidget(tab_widget)

        single_group = QGroupBox("Einphasig")
        single_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        single_layout = make_grid()
        single_layout.setHorizontalSpacing(12)
        single_layout.setVerticalSpacing(10)
        single_layout.setColumnStretch(0, 0)
        single_layout.setColumnStretch(1, 1)
        single_group.setLayout(single_layout)
        calculator_content.addWidget(single_group, 1)

        single_formula = QLabel("Formel: P = U × I")
        single_formula.setStyleSheet("color: #5f6368;")
        single_layout.addWidget(single_formula, 0, 0, 1, 2)
        single_layout.addWidget(QLabel("Spannung U [V]"), 1, 0)
        single_voltage_input = QLineEdit()
        single_voltage_input.setPlaceholderText("z. B. 230")
        single_voltage_input.setClearButtonEnabled(True)
        single_layout.addWidget(single_voltage_input, 1, 1)
        single_layout.addWidget(QLabel("Strom I [A]"), 2, 0)
        single_current_input = QLineEdit()
        single_current_input.setPlaceholderText("z. B. 16")
        single_current_input.setClearButtonEnabled(True)
        single_layout.addWidget(single_current_input, 2, 1)
        single_button = QPushButton("Berechnen")
        single_button.setMinimumHeight(32)
        single_layout.addWidget(single_button, 3, 0, 1, 2)

        single_result_box = QFrame()
        single_result_box.setFrameShape(QFrame.StyledPanel)
        single_result_box.setStyleSheet("QFrame { border-radius: 6px; background-color: #f7f8fa; }")
        single_result_layout = QVBoxLayout(single_result_box)
        single_result_layout.setContentsMargins(10, 8, 10, 8)
        single_result_layout.setSpacing(4)
        single_result_title = QLabel("Ergebnis")
        single_result_title.setStyleSheet("color: #5f6368;")
        single_result_label = QLabel(self._single_result_text)
        single_result_font = QFont()
        single_result_font.setPointSize(11)
        single_result_font.setWeight(QFont.Weight.DemiBold)
        single_result_label.setFont(single_result_font)
        single_result_layout.addWidget(single_result_title)
        single_result_layout.addWidget(single_result_label)
        single_layout.addWidget(single_result_box, 4, 0, 1, 2)
        single_layout.setRowStretch(5, 1)

        three_group = QGroupBox("Dreiphasig")
        three_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        three_layout = make_grid()
        three_layout.setHorizontalSpacing(12)
        three_layout.setVerticalSpacing(10)
        three_layout.setColumnStretch(0, 0)
        three_layout.setColumnStretch(1, 1)
        three_group.setLayout(three_layout)
        calculator_content.addWidget(three_group, 1)

        three_formula = QLabel("Formel: P = U × I × √3")
        three_formula.setStyleSheet("color: #5f6368;")
        three_layout.addWidget(three_formula, 0, 0, 1, 2)
        three_layout.addWidget(QLabel("Außenleiterspannung U [V]"), 1, 0)
        three_voltage_input = QLineEdit()
        three_voltage_input.setPlaceholderText("z. B. 400")
        three_voltage_input.setClearButtonEnabled(True)
        three_layout.addWidget(three_voltage_input, 1, 1)
        three_layout.addWidget(QLabel("Strom I [A]"), 2, 0)
        three_current_input = QLineEdit()
        three_current_input.setPlaceholderText("z. B. 16")
        three_current_input.setClearButtonEnabled(True)
        three_layout.addWidget(three_current_input, 2, 1)
        three_button = QPushButton("Berechnen")
        three_button.setMinimumHeight(32)
        three_layout.addWidget(three_button, 3, 0, 1, 2)

        three_result_box = QFrame()
        three_result_box.setFrameShape(QFrame.StyledPanel)
        three_result_box.setStyleSheet("QFrame { border-radius: 6px; background-color: #f7f8fa; }")
        three_result_layout = QVBoxLayout(three_result_box)
        three_result_layout.setContentsMargins(10, 8, 10, 8)
        three_result_layout.setSpacing(4)
        three_result_title = QLabel("Ergebnis")
        three_result_title.setStyleSheet("color: #5f6368;")
        three_result_label = QLabel(self._three_result_text)
        three_result_font = QFont()
        three_result_font.setPointSize(11)
        three_result_font.setWeight(QFont.Weight.DemiBold)
        three_result_label.setFont(three_result_font)
        three_result_layout.addWidget(three_result_title)
        three_result_layout.addWidget(three_result_label)
        three_layout.addWidget(three_result_box, 4, 0, 1, 2)
        three_layout.setRowStretch(5, 1)

        calculator_content.setAlignment(Qt.AlignTop)

        single_button.clicked.connect(self._calculate_single_phase)
        three_button.clicked.connect(self._calculate_three_phase)

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
            self._single_result_value = None
            self._single_result_status = "error"
            self._single_result_message = "Bitte gültige Zahlen angeben."
        else:
            power = calculate_single_phase(voltage, current)
            self._single_result_value = power
            self._single_result_status = "ok"
            self._single_result_message = ""
        self._single_result_text = self._format_result_text(
            self._single_result_value,
            self._single_result_status,
            self._single_result_message,
        )
        self._set_label_text(self._single_result_label, self._single_result_text)

    def _calculate_three_phase(self) -> None:
        voltage_text = self._get_input_text(self._three_voltage_input)
        current_text = self._get_input_text(self._three_current_input)
        self._three_voltage_value = voltage_text
        self._three_current_value = current_text
        voltage = parse_float(voltage_text)
        current = parse_float(current_text)
        if voltage is None or current is None:
            self._three_result_value = None
            self._three_result_status = "error"
            self._three_result_message = "Bitte gültige Zahlen angeben."
        else:
            power = calculate_three_phase(voltage, current)
            self._three_result_value = power
            self._three_result_status = "ok"
            self._three_result_message = ""
        self._three_result_text = self._format_result_text(
            self._three_result_value,
            self._three_result_status,
            self._three_result_message,
        )
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
                "single_phase": {
                    "value": self._single_result_value,
                    "status": self._single_result_status,
                    "message": self._single_result_message,
                },
                "three_phase": {
                    "value": self._three_result_value,
                    "status": self._three_result_status,
                    "message": self._three_result_message,
                },
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
            if "single_phase" in results or "three_phase" in results:
                self._single_result_value, self._single_result_status, self._single_result_message = (
                    self._coerce_result_entry(results.get("single_phase"))
                )
                self._three_result_value, self._three_result_status, self._three_result_message = (
                    self._coerce_result_entry(results.get("three_phase"))
                )
            else:
                self._single_result_value, self._single_result_status, self._single_result_message = (
                    self._parse_legacy_result(results.get("single_result", self._DEFAULT_RESULT))
                )
                self._three_result_value, self._three_result_status, self._three_result_message = (
                    self._parse_legacy_result(results.get("three_result", self._DEFAULT_RESULT))
                )
            self._single_result_text = self._format_result_text(
                self._single_result_value,
                self._single_result_status,
                self._single_result_message,
            )
            self._three_result_text = self._format_result_text(
                self._three_result_value,
                self._three_result_status,
                self._three_result_message,
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
        self._single_result_text = self._format_result_text(
            self._single_result_value,
            self._single_result_status,
            self._single_result_message,
        )
        self._three_result_text = self._format_result_text(
            self._three_result_value,
            self._three_result_status,
            self._three_result_message,
        )
        self._set_label_text(self._single_result_label, self._single_result_text)
        self._set_label_text(self._three_result_label, self._three_result_text)
        if self._tab_widget is not None:
            self._tab_widget.setCurrentIndex(self._active_tab_index)

    @staticmethod
    def _get_input_text(widget: object | None) -> str:
        if widget is None:
            return ""
        return str(widget.text())

    @staticmethod
    def _set_input_text(widget: object | None, value: str) -> None:
        if widget is None:
            return
        widget.setText(value)

    @staticmethod
    def _get_label_text(widget: object | None) -> str:
        if widget is None:
            return ""
        return str(widget.text())

    @staticmethod
    def _set_label_text(widget: object | None, value: str) -> None:
        if widget is None:
            return
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

    @staticmethod
    def _format_result_text(value: float | None, status: str, message: str) -> str:
        if status == "ok" and value is not None:
            return f"Leistung: {value:,.2f} W"
        if message:
            if message.startswith("Leistung:"):
                return message
            return f"Leistung: {message}"
        return ElektrikQtPlugin._DEFAULT_RESULT

    @staticmethod
    def _coerce_result_entry(entry: object) -> tuple[float | None, str, str]:
        if not isinstance(entry, dict):
            return None, "error", ""
        value = entry.get("value")
        if not isinstance(value, (int, float)):
            value = None
        status = entry.get("status")
        if status not in {"ok", "error"}:
            status = "ok" if value is not None else "error"
        message_value = entry.get("message")
        message = ElektrikQtPlugin._coerce_str(message_value, default="")
        if status == "ok" and value is None:
            status = "error"
        return value, status, message

    @staticmethod
    def _parse_legacy_result(value: object) -> tuple[float | None, str, str]:
        text = ElektrikQtPlugin._coerce_str(value, default=ElektrikQtPlugin._DEFAULT_RESULT)
        if "Bitte gültige Zahlen" in text:
            return None, "error", "Bitte gültige Zahlen angeben."
        numeric_value = parse_float(text)
        if numeric_value is not None:
            return numeric_value, "ok", ""
        if text.startswith("Leistung:"):
            text = text.replace("Leistung:", "", 1).strip()
        return None, "error", text

    def _get_active_tab_index(self) -> int:
        if self._tab_widget is None:
            return self._active_tab_index
        return int(self._tab_widget.currentIndex())


__all__ = ["ElektrikQtPlugin"]
