"""Qt-Plugin für Isolierungsberechnungen (PySide6-only)."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import importlib
import logging
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSignalBlocker, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QWidget,
    QGraphicsScene,
    QGraphicsView,
)
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from app.ui_qt.ui_helpers import make_grid, make_hbox, make_vbox
from app.core.isolierungen_db.logic import (
    register_material_change_listener,
    unregister_material_change_listener,
)
from Isolierung.core.database import list_materials, load_material
from Isolierung.services.schichtaufbau import BuildResult, LayerResult, Plate, compute_plate_dimensions
from Isolierung.services.tab1_berechnung import perform_calculation, validate_inputs
from Isolierung.services.zuschnitt import Placement, color_for, pack_plates


@dataclass
class _LayerWidgets:
    label: QLabel
    thickness_input: QLineEdit
    family_combo: QComboBox
    variant_combo: QComboBox
    variant_lookup: dict[str, tuple[str, float]]


@dataclass
class _BuildLayerWidgets:
    label: QLabel
    thickness_input: QLineEdit
    family_combo: QComboBox
    remove_button: QPushButton


@dataclass(frozen=True)
class _TableColumn:
    key: str
    label: str
    alignment: Qt.AlignmentFlag = Qt.AlignCenter
    formatter: Callable[[dict[str, Any], Any], str] | None = None


@dataclass(frozen=True)
class _ReportTemplateSpec:
    name: str
    path: Path


class _DictTableModel(QAbstractTableModel):
    def __init__(
        self,
        columns: list[_TableColumn],
        rows: list[dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows = rows or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802 - Qt API
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self._columns[index.column()]
        if role == Qt.DisplayRole:
            value = row.get(column.key)
            if column.formatter is not None:
                return column.formatter(row, value)
            if value is None:
                return "–"
            return str(value)
        if role == Qt.TextAlignmentRole:
            return column.alignment
        return None

    def headerData(  # noqa: N802 - Qt API
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self._columns):
            return self._columns[section].label
        return None

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> list[dict[str, Any]]:
        return self._rows


class _PreviewView(QGraphicsView):
    def __init__(self, on_resize: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_resize = on_resize

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._on_resize is not None:
            self._on_resize()


class IsolierungQtPlugin(QtPlugin):
    """Qt-Plugin für Isolierungsberechnungen."""

    _FAMILY_PLACEHOLDER = "Materialfamilie auswählen"
    _VARIANT_PLACEHOLDER = "Variante auswählen"

    def __init__(self) -> None:
        self._identifier = "isolierung"
        self.widget: QWidget | None = None
        self._tab_widget: QTabWidget | None = None

        self._T_left_input: QLineEdit | None = None
        self._T_inf_input: QLineEdit | None = None
        self._h_input: QLineEdit | None = None
        self._layer_count_input: QSpinBox | None = None
        self._layers_layout: QGridLayout | None = None
        self._layer_widgets: list[_LayerWidgets] = []
        self._result_label: QLabel | None = None

        self._build_measure_outer: QRadioButton | None = None
        self._build_measure_inner: QRadioButton | None = None
        self._build_measure_group: QButtonGroup | None = None
        self._build_L_input: QLineEdit | None = None
        self._build_B_input: QLineEdit | None = None
        self._build_H_input: QLineEdit | None = None
        self._build_layers_layout: QGridLayout | None = None
        self._build_layer_widgets: list[_BuildLayerWidgets] = []
        self._build_given_group: QGroupBox | None = None
        self._build_calc_group: QGroupBox | None = None
        self._build_given_labels: dict[str, QLabel] = {}
        self._build_calc_labels: dict[str, QLabel] = {}
        self._build_layer_count_label: QLabel | None = None
        self._build_results_table: QTableWidget | None = None
        self._build_status_label: QLabel | None = None

        self._zuschnitt_kerf_input: QLineEdit | None = None
        self._zuschnitt_status_label: QLabel | None = None
        self._zuschnitt_overview_view: QTableView | None = None
        self._zuschnitt_overview_model: _DictTableModel | None = None
        self._zuschnitt_results_view: QTableView | None = None
        self._zuschnitt_results_model: _DictTableModel | None = None
        self._zuschnitt_preview_scene: QGraphicsScene | None = None
        self._zuschnitt_preview_view: QGraphicsView | None = None

        self._report_tab: QWidget | None = None
        self._report_template_combo: QComboBox | None = None
        self._report_preview: QTextBrowser | None = None
        self._report_status_label: QLabel | None = None
        self._report_templates: list[_ReportTemplateSpec] = []
        self._report_current_text: str = ""
        self._report_logger = logging.getLogger(__name__)

        self._materials = []
        self._material_names: list[str] = []
        self._material_change_handler = self._on_materials_changed
        self._listener_registered = False
        self._missing_materials_warning: str | None = None
        self._build_missing_materials_warning: str | None = None

        self._calc_inputs: dict[str, Any] = {
            "T_left": "",
            "T_inf": "",
            "h": "",
            "layers": [{"thickness": "", "family": "", "variant": ""}],
        }
        self._calc_results: dict[str, Any] = {
            "status": "idle",
            "message": "",
            "data": {},
        }
        self._calc_ui: dict[str, Any] = {"layers": []}
        self._build_inputs: dict[str, Any] = {
            "measure_type": "outer",
            "dimensions": {"L": "", "B": "", "H": ""},
            "layers": [{"thickness": "", "family": ""}],
        }
        self._build_results: dict[str, Any] = {
            "status": "idle",
            "message": "",
            "data": {},
        }
        self._build_ui: dict[str, Any] = {"selected_row": -1}
        self._zuschnitt_inputs: dict[str, Any] = {"kerf": "", "cached_plates": []}
        self._zuschnitt_results: dict[str, Any] = {
            "status": "idle",
            "message": "",
            "placements": [],
            "summary": [],
            "total_cost": None,
            "total_bin_count": None,
        }
        self._zuschnitt_ui: dict[str, Any] = {
            "selected_placement_row": -1,
            "selected_summary_row": -1,
        }
        self._ui_state: dict[str, Any] = {"active_tab": 0}

    @property
    def name(self) -> str:
        return "Isolierung"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        container = QWidget()
        layout = make_vbox()

        header = QWidget()
        header_layout = make_hbox()
        title = QLabel("Isolierungsberechnung")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header.setLayout(header_layout)
        layout.addWidget(header)

        tab_widget = QTabWidget()
        self._tab_widget = tab_widget
        tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(tab_widget)

        tab_widget.addTab(self._build_calculation_tab(), "Berechnung")
        tab_widget.addTab(self._build_schichtaufbau_tab(), "Schichtaufbau")
        tab_widget.addTab(self._build_zuschnitt_tab(), "Zuschnitt")

        container.setLayout(layout)
        self.widget = container

        self._load_materials()
        if not self._listener_registered:
            register_material_change_listener(self._material_change_handler)
            self._listener_registered = True
        if self.widget is not None and hasattr(self.widget, "destroyed"):
            self.widget.destroyed.connect(self._on_widget_destroyed)
        self.refresh_view()

    def export_state(self) -> dict[str, Any]:
        self._sync_internal_state_from_widgets()
        inputs = {
            "berechnung": {
                "T_left": self._calc_inputs.get("T_left", ""),
                "T_inf": self._calc_inputs.get("T_inf", ""),
                "h": self._calc_inputs.get("h", ""),
                "layers": [dict(layer) for layer in self._calc_inputs.get("layers", [])],
            },
            "schichtaufbau": {
                "measure_type": self._build_inputs.get("measure_type", "outer"),
                "dimensions": dict(self._build_inputs.get("dimensions", {})),
                "layers": [dict(layer) for layer in self._build_inputs.get("layers", [])],
            },
            "zuschnitt": {
                "kerf": self._zuschnitt_inputs.get("kerf", ""),
                "cached_plates": list(self._zuschnitt_inputs.get("cached_plates", [])),
            },
        }
        results = {
            "berechnung": dict(self._calc_results),
            "schichtaufbau": dict(self._build_results),
            "zuschnitt": dict(self._zuschnitt_results),
        }
        ui = {
            "active_tab": self._ui_state.get("active_tab", 0),
            "berechnung": dict(self._calc_ui),
            "schichtaufbau": dict(self._build_ui),
            "zuschnitt": dict(self._zuschnitt_ui),
        }
        return self.validate_state({"inputs": inputs, "results": results, "ui": ui})

    def import_state(self, state: dict[str, Any]) -> None:
        normalized = QtPlugin.validate_state(self, state)
        self._apply_state(normalized)
        self.refresh_view()

    def apply_state(self, state: dict[str, Any]) -> None:
        self._apply_state(state)

    def _apply_state(self, state: dict[str, Any]) -> None:
        inputs = state.get("inputs", {})
        results = state.get("results", {})
        ui_state = state.get("ui", {})

        if isinstance(inputs, dict):
            if "berechnung" in inputs or "schichtaufbau" in inputs or "zuschnitt" in inputs:
                self._apply_calc_inputs(inputs.get("berechnung", {}))
                self._apply_build_inputs(inputs.get("schichtaufbau", {}))
                self._apply_zuschnitt_inputs(inputs.get("zuschnitt", {}))
            else:
                self._apply_calc_inputs(inputs)

        if isinstance(results, dict):
            if "berechnung" in results or "schichtaufbau" in results or "zuschnitt" in results:
                self._apply_calc_results(results.get("berechnung", {}))
                self._apply_build_results(results.get("schichtaufbau", {}))
                self._apply_zuschnitt_results(results.get("zuschnitt", {}))
            else:
                self._apply_calc_results(results)

        if isinstance(ui_state, dict):
            active_tab = ui_state.get("active_tab")
            if isinstance(active_tab, int):
                self._ui_state["active_tab"] = active_tab
            if "berechnung" in ui_state or "schichtaufbau" in ui_state or "zuschnitt" in ui_state:
                self._apply_calc_ui(ui_state.get("berechnung", {}))
                self._apply_build_ui(ui_state.get("schichtaufbau", {}))
                self._apply_zuschnitt_ui(ui_state.get("zuschnitt", {}))
            else:
                self._apply_calc_ui(ui_state)

    def refresh_view(self) -> None:
        self._sync_calculation_view()
        self._sync_schichtaufbau_view()
        self._sync_zuschnitt_view()
        if (
            self._tab_widget is not None
            and self._report_tab is not None
            and self._tab_widget.currentWidget() is self._report_tab
        ):
            self._update_report_preview()
        if self._tab_widget is not None:
            self._tab_widget.setCurrentIndex(self._ui_state.get("active_tab", 0))

    def _apply_calc_inputs(self, inputs: dict[str, Any]) -> None:
        if not isinstance(inputs, dict):
            return
        self._calc_inputs["T_left"] = self._coerce_str(inputs.get("T_left", ""))
        self._calc_inputs["T_inf"] = self._coerce_str(inputs.get("T_inf", ""))
        self._calc_inputs["h"] = self._coerce_str(inputs.get("h", ""))
        layers = inputs.get("layers", [])
        if isinstance(layers, list) and layers:
            normalized_layers = []
            for layer in layers:
                if not isinstance(layer, dict):
                    continue
                normalized_layers.append(
                    {
                        "thickness": self._coerce_str(layer.get("thickness", "")),
                        "family": self._coerce_str(layer.get("family", "")),
                        "variant": self._coerce_str(layer.get("variant", "")),
                    }
                )
            if normalized_layers:
                self._calc_inputs["layers"] = normalized_layers

    def _apply_build_inputs(self, inputs: dict[str, Any]) -> None:
        if not isinstance(inputs, dict):
            return
        measure_type = self._coerce_str(inputs.get("measure_type", "outer"))
        if measure_type not in {"outer", "inner"}:
            measure_type = "outer"
        self._build_inputs["measure_type"] = measure_type
        dimensions = inputs.get("dimensions", {})
        if isinstance(dimensions, dict):
            self._build_inputs["dimensions"] = {
                "L": self._coerce_str(dimensions.get("L", "")),
                "B": self._coerce_str(dimensions.get("B", "")),
                "H": self._coerce_str(dimensions.get("H", "")),
            }
        layers = inputs.get("layers", [])
        if isinstance(layers, list) and layers:
            normalized_layers = []
            for layer in layers:
                if not isinstance(layer, dict):
                    continue
                normalized_layers.append(
                    {
                        "thickness": self._coerce_str(layer.get("thickness", "")),
                        "family": self._coerce_str(layer.get("family", "")),
                    }
                )
            if normalized_layers:
                self._build_inputs["layers"] = normalized_layers

    def _apply_calc_results(self, results: dict[str, Any]) -> None:
        if not isinstance(results, dict):
            return
        self._calc_results = {
            "status": self._coerce_str(results.get("status", "idle")),
            "message": self._coerce_str(results.get("message", "")),
            "data": results.get("data", {}),
        }

    def _apply_build_results(self, results: dict[str, Any]) -> None:
        if not isinstance(results, dict):
            return
        self._build_results = {
            "status": self._coerce_str(results.get("status", "idle")),
            "message": self._coerce_str(results.get("message", "")),
            "data": results.get("data", {}),
        }

    def _apply_calc_ui(self, ui_state: dict[str, Any]) -> None:
        if not isinstance(ui_state, dict):
            return
        ui_layers = ui_state.get("layers")
        if isinstance(ui_layers, list):
            normalized_ui_layers = []
            for layer in ui_layers:
                if not isinstance(layer, dict):
                    continue
                family_index = layer.get("family_index", 0)
                variant_index = layer.get("variant_index", 0)
                normalized_ui_layers.append(
                    {
                        "family_index": family_index if isinstance(family_index, int) else 0,
                        "variant_index": variant_index if isinstance(variant_index, int) else 0,
                    }
                )
            self._calc_ui["layers"] = normalized_ui_layers

    def _apply_build_ui(self, ui_state: dict[str, Any]) -> None:
        if not isinstance(ui_state, dict):
            return
        selected_row = ui_state.get("selected_row", -1)
        if isinstance(selected_row, int):
            self._build_ui["selected_row"] = selected_row

    def _apply_zuschnitt_inputs(self, inputs: dict[str, Any]) -> None:
        if not isinstance(inputs, dict):
            return
        self._zuschnitt_inputs["kerf"] = self._coerce_str(inputs.get("kerf", ""))
        cached = inputs.get("cached_plates", [])
        self._zuschnitt_inputs["cached_plates"] = cached if isinstance(cached, list) else []

    def _apply_zuschnitt_results(self, results: dict[str, Any]) -> None:
        if not isinstance(results, dict):
            return
        placements = results.get("placements", [])
        summary = results.get("summary", [])
        self._zuschnitt_results = {
            "status": self._coerce_str(results.get("status", "idle")) or "idle",
            "message": self._coerce_str(results.get("message", "")),
            "placements": placements if isinstance(placements, list) else [],
            "summary": summary if isinstance(summary, list) else [],
            "total_cost": results.get("total_cost"),
            "total_bin_count": results.get("total_bin_count"),
        }

    def _apply_zuschnitt_ui(self, ui_state: dict[str, Any]) -> None:
        if not isinstance(ui_state, dict):
            return
        selected_placement_row = ui_state.get("selected_placement_row", -1)
        if isinstance(selected_placement_row, int):
            self._zuschnitt_ui["selected_placement_row"] = selected_placement_row
        selected_summary_row = ui_state.get("selected_summary_row", -1)
        if isinstance(selected_summary_row, int):
            self._zuschnitt_ui["selected_summary_row"] = selected_summary_row

    def _sync_calculation_state_from_widgets(self) -> None:
        if self._T_left_input is not None:
            self._calc_inputs["T_left"] = self._T_left_input.text()
        if self._T_inf_input is not None:
            self._calc_inputs["T_inf"] = self._T_inf_input.text()
        if self._h_input is not None:
            self._calc_inputs["h"] = self._h_input.text()

        layers: list[dict[str, str]] = []
        ui_layers: list[dict[str, int]] = []
        for widgets in self._layer_widgets:
            family_text = widgets.family_combo.currentText()
            if family_text == self._FAMILY_PLACEHOLDER:
                family_text = ""
            variant_display = widgets.variant_combo.currentText()
            variant_text = ""
            if variant_display != self._VARIANT_PLACEHOLDER:
                variant_text = widgets.variant_lookup.get(variant_display, (variant_display, 0.0))[0]
            layers.append(
                {
                    "thickness": widgets.thickness_input.text(),
                    "family": family_text,
                    "variant": variant_text,
                }
            )
            ui_layers.append(
                {
                    "family_index": widgets.family_combo.currentIndex(),
                    "variant_index": widgets.variant_combo.currentIndex(),
                }
            )
        if layers:
            self._calc_inputs["layers"] = layers
            self._calc_ui["layers"] = ui_layers

    def _sync_build_state_from_widgets(self) -> None:
        if self._build_measure_outer is not None and self._build_measure_outer.isChecked():
            self._build_inputs["measure_type"] = "outer"
        elif self._build_measure_inner is not None and self._build_measure_inner.isChecked():
            self._build_inputs["measure_type"] = "inner"
        if self._build_L_input is not None:
            self._build_inputs.setdefault("dimensions", {})["L"] = self._build_L_input.text()
        if self._build_B_input is not None:
            self._build_inputs.setdefault("dimensions", {})["B"] = self._build_B_input.text()
        if self._build_H_input is not None:
            self._build_inputs.setdefault("dimensions", {})["H"] = self._build_H_input.text()
        layers: list[dict[str, str]] = []
        for widgets in self._build_layer_widgets:
            family_text = widgets.family_combo.currentText()
            if family_text == self._FAMILY_PLACEHOLDER:
                family_text = ""
            layers.append(
                {
                    "thickness": widgets.thickness_input.text(),
                    "family": family_text,
                }
            )
        if layers:
            self._build_inputs["layers"] = layers

    def _sync_zuschnitt_state_from_widgets(self) -> None:
        if self._zuschnitt_kerf_input is not None:
            self._zuschnitt_inputs["kerf"] = self._zuschnitt_kerf_input.text()

    def _sync_calculation_view(self) -> None:
        self._set_input_text(self._T_left_input, self._calc_inputs.get("T_left", ""))
        self._set_input_text(self._T_inf_input, self._calc_inputs.get("T_inf", ""))
        self._set_input_text(self._h_input, self._calc_inputs.get("h", ""))

        layers = self._calc_inputs.get("layers", [])
        if not isinstance(layers, list) or not layers:
            layers = [{"thickness": "", "family": "", "variant": ""}]
            self._calc_inputs["layers"] = layers
        self._set_layer_count(len(layers))

        missing_families: list[str] = []
        for layer, widgets in zip(layers, self._layer_widgets, strict=False):
            thickness = self._coerce_str(layer.get("thickness", ""))
            family = self._coerce_str(layer.get("family", ""))
            variant = self._coerce_str(layer.get("variant", ""))
            if family and family not in self._material_names:
                missing_families.append(family)
                family = ""
                variant = ""
                layer["family"] = ""
                layer["variant"] = ""
            with QSignalBlocker(widgets.thickness_input):
                widgets.thickness_input.setText(thickness)
            with QSignalBlocker(widgets.family_combo):
                self._select_combo_value(widgets.family_combo, family, self._FAMILY_PLACEHOLDER)
            variant_found = self._populate_variant_combo(widgets, family, variant)
            if variant and not variant_found:
                layer["variant"] = ""

        if missing_families:
            unique_missing = sorted(set(missing_families))
            self._missing_materials_warning = (
                "Fehlende Materialfamilien: " + ", ".join(unique_missing)
            )
        else:
            self._missing_materials_warning = None

        result_text = self._format_result_text()
        self._set_label_text(self._result_label, result_text)

        if self._layer_count_input is not None:
            with QSignalBlocker(self._layer_count_input):
                self._layer_count_input.setValue(len(layers))

    def _sync_schichtaufbau_view(self) -> None:
        measure_type = self._build_inputs.get("measure_type", "outer")
        if self._build_measure_outer is not None:
            with QSignalBlocker(self._build_measure_outer):
                self._build_measure_outer.setChecked(measure_type == "outer")
        if self._build_measure_inner is not None:
            with QSignalBlocker(self._build_measure_inner):
                self._build_measure_inner.setChecked(measure_type == "inner")

        dimensions = self._build_inputs.get("dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        self._set_input_text(self._build_L_input, self._coerce_str(dimensions.get("L", "")))
        self._set_input_text(self._build_B_input, self._coerce_str(dimensions.get("B", "")))
        self._set_input_text(self._build_H_input, self._coerce_str(dimensions.get("H", "")))

        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list) or not layers:
            layers = [{"thickness": "", "family": ""}]
            self._build_inputs["layers"] = layers
        self._set_build_layer_count(len(layers))
        self._refresh_build_layer_labels()

        missing_families: list[str] = []
        for layer, widgets in zip(layers, self._build_layer_widgets, strict=False):
            thickness = self._coerce_str(layer.get("thickness", ""))
            family = self._coerce_str(layer.get("family", ""))
            if family and family not in self._material_names:
                missing_families.append(family)
                family = ""
                layer["family"] = ""
            with QSignalBlocker(widgets.thickness_input):
                widgets.thickness_input.setText(thickness)
            with QSignalBlocker(widgets.family_combo):
                self._select_combo_value(widgets.family_combo, family, self._FAMILY_PLACEHOLDER)

        if missing_families:
            unique_missing = sorted(set(missing_families))
            self._build_missing_materials_warning = (
                "Fehlende Materialfamilien: " + ", ".join(unique_missing)
            )
        else:
            self._build_missing_materials_warning = None

        self._refresh_build_results_view()

    def _sync_zuschnitt_view(self) -> None:
        self._set_input_text(self._zuschnitt_kerf_input, self._coerce_str(self._zuschnitt_inputs.get("kerf", "")))
        self._refresh_zuschnitt_results_view()

    def _build_calculation_tab(self) -> QWidget:
        tab = QWidget()
        layout = make_vbox()

        inputs_group = QGroupBox("Randbedingungen")
        inputs_layout = make_grid()
        inputs_layout.addWidget(QLabel("Temperatur links T_left [°C]"), 0, 0)
        self._T_left_input = QLineEdit()
        self._T_left_input.textChanged.connect(self._on_text_input_changed)
        inputs_layout.addWidget(self._T_left_input, 0, 1)
        inputs_layout.addWidget(QLabel("Umgebungstemperatur T_inf [°C]"), 1, 0)
        self._T_inf_input = QLineEdit()
        self._T_inf_input.textChanged.connect(self._on_text_input_changed)
        inputs_layout.addWidget(self._T_inf_input, 1, 1)
        inputs_layout.addWidget(QLabel("Wärmeübergangskoeffizient h [W/m²K]"), 2, 0)
        self._h_input = QLineEdit()
        self._h_input.textChanged.connect(self._on_text_input_changed)
        inputs_layout.addWidget(self._h_input, 2, 1)
        inputs_group.setLayout(inputs_layout)
        layout.addWidget(inputs_group)

        layers_group = QGroupBox("Schichten")
        layers_layout = make_vbox()
        layer_controls = make_hbox()
        layer_controls.addWidget(QLabel("Anzahl der Schichten"))
        self._layer_count_input = QSpinBox()
        self._layer_count_input.setMinimum(1)
        self._layer_count_input.setMaximum(12)
        self._layer_count_input.valueChanged.connect(self._on_layer_count_changed)
        layer_controls.addWidget(self._layer_count_input)
        layer_controls.addStretch()
        layers_layout.addLayout(layer_controls)

        grid = make_grid()
        grid.addWidget(QLabel("Schicht"), 0, 0)
        grid.addWidget(QLabel("Dicke [mm]"), 0, 1)
        grid.addWidget(QLabel("Materialfamilie"), 0, 2)
        grid.addWidget(QLabel("Variante"), 0, 3)
        self._layers_layout = grid
        layers_layout.addLayout(grid)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        action_layout = make_hbox()
        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._on_calculate)
        action_layout.addStretch()
        action_layout.addWidget(calculate_button)
        layout.addLayout(action_layout)

        result_group = QGroupBox("Ergebnisse")
        result_layout = make_vbox()
        self._result_label = QLabel()
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _build_schichtaufbau_tab(self) -> QWidget:
        tab = QWidget()
        layout = make_vbox()

        measure_group = QGroupBox("Maßvorgabe")
        measure_layout = make_hbox()
        self._build_measure_outer = QRadioButton("Außenmaße gegeben")
        self._build_measure_inner = QRadioButton("Innenmaße gegeben")
        self._build_measure_group = QButtonGroup()
        self._build_measure_group.addButton(self._build_measure_outer)
        self._build_measure_group.addButton(self._build_measure_inner)
        self._build_measure_outer.toggled.connect(self._on_build_measure_changed)
        self._build_measure_inner.toggled.connect(self._on_build_measure_changed)
        measure_layout.addWidget(self._build_measure_outer)
        measure_layout.addWidget(self._build_measure_inner)
        measure_layout.addStretch()
        measure_group.setLayout(measure_layout)
        layout.addWidget(measure_group)

        dims_group = QGroupBox("Abmessungen")
        dims_layout = make_grid()
        dims_layout.addWidget(QLabel("Länge [mm]"), 0, 0)
        self._build_L_input = QLineEdit()
        self._build_L_input.textChanged.connect(self._on_build_dimension_changed)
        dims_layout.addWidget(self._build_L_input, 0, 1)
        dims_layout.addWidget(QLabel("Breite [mm]"), 0, 2)
        self._build_B_input = QLineEdit()
        self._build_B_input.textChanged.connect(self._on_build_dimension_changed)
        dims_layout.addWidget(self._build_B_input, 0, 3)
        dims_layout.addWidget(QLabel("Höhe [mm]"), 0, 4)
        self._build_H_input = QLineEdit()
        self._build_H_input.textChanged.connect(self._on_build_dimension_changed)
        dims_layout.addWidget(self._build_H_input, 0, 5)
        dims_group.setLayout(dims_layout)
        layout.addWidget(dims_group)

        layers_group = QGroupBox("Schichtdicken [mm]")
        layers_layout = make_vbox()
        layer_controls = make_hbox()
        add_button = QPushButton("+ Schicht")
        add_button.clicked.connect(self._on_build_add_layer)
        import_button = QPushButton("Aus Berechnung übernehmen")
        import_button.clicked.connect(self._on_build_import_layers)
        layer_controls.addWidget(add_button)
        layer_controls.addWidget(import_button)
        layer_controls.addStretch()
        layers_layout.addLayout(layer_controls)

        grid = make_grid()
        grid.addWidget(QLabel("#"), 0, 0)
        grid.addWidget(QLabel("Dicke [mm]"), 0, 1)
        grid.addWidget(QLabel("Materialfamilie"), 0, 2)
        grid.addWidget(QLabel("Aktionen"), 0, 3)
        self._build_layers_layout = grid
        layers_layout.addLayout(grid)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        action_layout = make_hbox()
        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._on_build_calculate)
        reset_button = QPushButton("Felder leeren")
        reset_button.clicked.connect(self._on_build_reset)
        action_layout.addStretch()
        action_layout.addWidget(calculate_button)
        action_layout.addWidget(reset_button)
        layout.addLayout(action_layout)

        results_group = QGroupBox("Ergebnis")
        results_layout = make_vbox()
        self._build_status_label = QLabel()
        self._build_status_label.setWordWrap(True)
        results_layout.addWidget(self._build_status_label)

        summary_layout = make_hbox()
        self._build_given_group = QGroupBox("Gegebene Maße")
        given_layout = make_grid()
        self._build_given_labels = self._build_dimension_summary(given_layout)
        self._build_given_group.setLayout(given_layout)
        summary_layout.addWidget(self._build_given_group)

        self._build_calc_group = QGroupBox("Berechnete Maße")
        calc_layout = make_grid()
        self._build_calc_labels = self._build_dimension_summary(calc_layout)
        self._build_calc_group.setLayout(calc_layout)
        summary_layout.addWidget(self._build_calc_group)

        layer_info_group = QGroupBox("Schichten")
        layer_info_layout = make_vbox()
        self._build_layer_count_label = QLabel("–")
        layer_info_layout.addWidget(self._build_layer_count_label)
        layer_info_group.setLayout(layer_info_layout)
        summary_layout.addWidget(layer_info_group)
        results_layout.addLayout(summary_layout)

        self._build_results_table = QTableWidget(0, 6)
        self._build_results_table.setHorizontalHeaderLabels(
            ["Schicht", "Material", "Platte", "L [mm]", "B [mm]", "H [mm]"]
        )
        self._build_results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._build_results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._build_results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._build_results_table.itemSelectionChanged.connect(
            self._on_build_result_selection_changed
        )
        self._build_results_table.horizontalHeader().setStretchLastSection(True)
        self._build_results_table.verticalHeader().setVisible(False)
        results_layout.addWidget(self._build_results_table)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _build_zuschnitt_tab(self) -> QWidget:
        tab = QWidget()
        layout = make_vbox()

        header = QLabel("Zuschnittoptimierung")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        settings_group = QGroupBox("Einstellungen")
        settings_layout = make_grid()
        settings_layout.addWidget(QLabel("Schnittfuge [mm]"), 0, 0)
        self._zuschnitt_kerf_input = QLineEdit()
        self._zuschnitt_kerf_input.textChanged.connect(self._on_zuschnitt_kerf_changed)
        settings_layout.addWidget(self._zuschnitt_kerf_input, 0, 1)

        button_layout = make_hbox()
        import_button = QPushButton("Platten übernehmen")
        import_button.clicked.connect(self._on_zuschnitt_import_plates)
        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._on_zuschnitt_calculate)
        button_layout.addWidget(import_button)
        button_layout.addWidget(calculate_button)
        button_layout.addStretch()
        settings_layout.addLayout(button_layout, 0, 2)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        self._zuschnitt_status_label = QLabel()
        self._zuschnitt_status_label.setWordWrap(True)
        layout.addWidget(self._zuschnitt_status_label)

        overview_group = QGroupBox("Rohlingübersicht")
        overview_layout = make_vbox()
        overview_columns = [
            _TableColumn("material", "Material", alignment=Qt.AlignLeft | Qt.AlignVCenter),
            _TableColumn("count", "Rohlinge (min)", alignment=Qt.AlignCenter),
            _TableColumn("price", "Preis/Stk [€]", alignment=Qt.AlignCenter, formatter=self._format_price),
            _TableColumn("cost", "Kosten [€]", alignment=Qt.AlignCenter, formatter=self._format_cost),
        ]
        self._zuschnitt_overview_model = _DictTableModel(overview_columns, parent=tab)
        self._zuschnitt_overview_view = QTableView()
        self._zuschnitt_overview_view.setModel(self._zuschnitt_overview_model)
        self._zuschnitt_overview_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._zuschnitt_overview_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._zuschnitt_overview_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._zuschnitt_overview_view.horizontalHeader().setStretchLastSection(True)
        self._zuschnitt_overview_view.verticalHeader().setVisible(False)
        self._zuschnitt_overview_view.selectionModel().selectionChanged.connect(
            self._on_zuschnitt_summary_selection_changed
        )
        overview_layout.addWidget(self._zuschnitt_overview_view)
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        results_group = QGroupBox("Platzierungen")
        results_layout = make_vbox()
        placements_columns = [
            _TableColumn("material", "Material", alignment=Qt.AlignLeft | Qt.AlignVCenter),
            _TableColumn("bin", "Rohling", alignment=Qt.AlignCenter),
            _TableColumn("teil", "Teil", alignment=Qt.AlignLeft | Qt.AlignVCenter),
            _TableColumn("breite", "Eff. Breite [mm]", alignment=Qt.AlignCenter, formatter=self._format_mm_one),
            _TableColumn("hoehe", "Eff. Höhe [mm]", alignment=Qt.AlignCenter, formatter=self._format_mm_one),
            _TableColumn("x", "X [mm]", alignment=Qt.AlignCenter, formatter=self._format_mm_one),
            _TableColumn("y", "Y [mm]", alignment=Qt.AlignCenter, formatter=self._format_mm_one),
            _TableColumn("rotation", "Drehung", alignment=Qt.AlignCenter, formatter=self._format_rotation),
        ]
        self._zuschnitt_results_model = _DictTableModel(placements_columns, parent=tab)
        self._zuschnitt_results_view = QTableView()
        self._zuschnitt_results_view.setModel(self._zuschnitt_results_model)
        self._zuschnitt_results_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._zuschnitt_results_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._zuschnitt_results_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._zuschnitt_results_view.horizontalHeader().setStretchLastSection(True)
        self._zuschnitt_results_view.verticalHeader().setVisible(False)
        self._zuschnitt_results_view.selectionModel().selectionChanged.connect(
            self._on_zuschnitt_placement_selection_changed
        )
        results_layout.addWidget(self._zuschnitt_results_view)

        export_layout = make_hbox()
        export_layout.addStretch()
        export_csv_button = QPushButton("CSV exportieren")
        export_csv_button.clicked.connect(self._on_zuschnitt_export_csv)
        export_excel_button = QPushButton("Excel exportieren")
        export_excel_button.clicked.connect(self._on_zuschnitt_export_excel)
        export_layout.addWidget(export_csv_button)
        export_layout.addWidget(export_excel_button)
        results_layout.addLayout(export_layout)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        preview_group = QGroupBox("Graphische Übersicht")
        preview_layout = make_vbox()
        self._zuschnitt_preview_scene = QGraphicsScene()
        self._zuschnitt_preview_view = _PreviewView(self._refresh_zuschnitt_preview)
        self._zuschnitt_preview_view.setScene(self._zuschnitt_preview_scene)
        preview_layout.addWidget(self._zuschnitt_preview_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _build_report_tab(self) -> QWidget:
        tab = QWidget()
        layout = make_vbox()

        header = QLabel("Bericht")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        template_layout = make_hbox()
        template_layout.addWidget(QLabel("Template"))
        self._report_template_combo = QComboBox()
        self._report_template_combo.currentIndexChanged.connect(self._update_report_preview)
        template_layout.addWidget(self._report_template_combo)
        refresh_button = QPushButton("Templates aktualisieren")
        refresh_button.clicked.connect(self._discover_report_templates)
        template_layout.addWidget(refresh_button)
        template_layout.addStretch()
        layout.addLayout(template_layout)

        action_layout = make_hbox()
        preview_button = QPushButton("Vorschau aktualisieren")
        preview_button.clicked.connect(self._update_report_preview)
        export_button = QPushButton("PDF exportieren")
        export_button.clicked.connect(self._on_report_export_pdf)
        action_layout.addWidget(preview_button)
        action_layout.addStretch()
        action_layout.addWidget(export_button)
        layout.addLayout(action_layout)

        self._report_preview = QTextBrowser()
        self._report_preview.setOpenExternalLinks(False)
        preview_font = QFont("Courier New")
        preview_font.setStyleHint(QFont.Monospace)
        self._report_preview.setFont(preview_font)
        layout.addWidget(self._report_preview)

        self._report_status_label = QLabel()
        self._report_status_label.setWordWrap(True)
        layout.addWidget(self._report_status_label)

        tab.setLayout(layout)
        self._discover_report_templates()
        self._update_report_preview()
        return tab

    @staticmethod
    def _build_dimension_summary(layout: QGridLayout) -> dict[str, QLabel]:
        labels = {}
        for row_index, (title, key) in enumerate(
            (("Länge [mm]", "L"), ("Breite [mm]", "B"), ("Höhe [mm]", "H"))
        ):
            layout.addWidget(QLabel(title), row_index, 0)
            value_label = QLabel("–")
            layout.addWidget(value_label, row_index, 1)
            labels[key] = value_label
        return labels

    def _on_zuschnitt_kerf_changed(self, text: str) -> None:
        self._zuschnitt_inputs["kerf"] = text

    def _on_zuschnitt_import_plates(self) -> None:
        try:
            plates = self._collect_build_plates()
            if not plates:
                raise ValueError("Keine Platten im Schichtaufbau gefunden.")
            self._zuschnitt_inputs["cached_plates"] = plates
            self._invalidate_zuschnitt_results("Platten übernommen. Bitte neu berechnen.")
        except Exception as exc:
            self._zuschnitt_results["status"] = "error"
            self._zuschnitt_results["message"] = str(exc)
            self._refresh_zuschnitt_results_view()

    def _on_zuschnitt_calculate(self) -> None:
        self._sync_internal_state_from_widgets()
        try:
            kerf_value = self._parse_float(self._zuschnitt_inputs.get("kerf", "")) or 0.0
            if kerf_value < 0:
                raise ValueError("Schnittfuge muss >= 0 sein.")
            plates = self._zuschnitt_inputs.get("cached_plates", [])
            if not plates:
                plates = self._collect_build_plates()
                self._zuschnitt_inputs["cached_plates"] = plates
            if not plates:
                raise ValueError("Keine Platten vorhanden. Bitte zuerst übernehmen.")
            placements, summary, total_cost, total_bins = pack_plates(plates, kerf_value)
            placement_rows = self._build_placement_rows(placements)
            summary_rows = self._build_summary_rows(summary, total_cost, total_bins)
            self._zuschnitt_results = {
                "status": "ok",
                "message": "",
                "placements": placement_rows,
                "summary": summary_rows,
                "total_cost": total_cost,
                "total_bin_count": total_bins,
            }
        except Exception as exc:
            self._zuschnitt_results = {
                "status": "error",
                "message": str(exc),
                "placements": [],
                "summary": [],
                "total_cost": None,
                "total_bin_count": None,
            }
        self._refresh_zuschnitt_results_view()

    def _collect_build_plates(self) -> list[dict[str, Any]]:
        status = self._build_results.get("status", "idle")
        if status != "ok":
            raise ValueError("Bitte den Schichtaufbau berechnen, bevor Platten übernommen werden.")
        data = self._build_results.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Keine gültigen Plattendaten vorhanden.")
        result = self._deserialize_build_result(data)
        isolierungen = data.get("isolierungen", [])
        if not isinstance(isolierungen, list):
            isolierungen = []
        plates: list[dict[str, Any]] = []
        for layer in result.layers:
            material = ""
            if 0 <= layer.layer_index - 1 < len(isolierungen):
                material = str(isolierungen[layer.layer_index - 1]).strip()
            for plate in layer.plates:
                plates.append(
                    {
                        "material": material,
                        "thickness": layer.thickness,
                        "length": plate.L,
                        "width": plate.B,
                        "name": plate.name,
                        "layer": layer.layer_index,
                    }
                )
        return plates

    def _build_placement_rows(self, placements: Iterable[Placement]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for placement in placements:
            rows.append(
                {
                    "material": placement.material,
                    "bin": placement.bin_index,
                    "teil": placement.part_label,
                    "breite": placement.width,
                    "hoehe": placement.height,
                    "x": placement.x,
                    "y": placement.y,
                    "rotation": placement.rotated,
                    "bin_width": placement.bin_width,
                    "bin_height": placement.bin_height,
                    "original_width": placement.original_width,
                    "original_height": placement.original_height,
                }
            )
        return rows

    def _build_summary_rows(
        self, material_summary: list[dict[str, Any]], total_cost: float | None, total_bins: int | None
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for entry in material_summary:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "material": entry.get("material", "–"),
                    "count": entry.get("count"),
                    "price": entry.get("price"),
                    "cost": entry.get("cost"),
                }
            )
        if rows:
            missing_prices = any(entry.get("price") is None for entry in material_summary)
            if missing_prices and total_cost is not None:
                cost_text = f"{total_cost:.2f} (ohne fehlende Preise)"
            elif missing_prices:
                cost_text = "– (fehlende Preise)"
            elif total_cost is None:
                cost_text = "–"
            else:
                cost_text = f"{total_cost:.2f}"
            rows.append(
                {
                    "material": "Summe",
                    "count": total_bins,
                    "price": None,
                    "cost": total_cost,
                    "cost_display": cost_text,
                    "is_total": True,
                }
            )
        return rows

    def _discover_report_templates(self) -> None:
        self._report_templates = []
        report_dir = self._resolve_report_directory()
        if report_dir is not None and report_dir.exists():
            for template_path in sorted(report_dir.glob("*.j2")):
                self._report_templates.append(
                    _ReportTemplateSpec(name=template_path.stem, path=template_path)
                )
        if self._report_template_combo is not None:
            current_name = self._report_template_combo.currentText()
            with QSignalBlocker(self._report_template_combo):
                self._report_template_combo.clear()
                for spec in self._report_templates:
                    self._report_template_combo.addItem(spec.name)
            if current_name:
                index = self._report_template_combo.findText(current_name)
                if index >= 0:
                    self._report_template_combo.setCurrentIndex(index)
        if not self._report_templates:
            self._set_report_status(
                "Keine Templates gefunden. Lege .j2-Dateien in Isolierung/reports ab."
            )
        else:
            self._set_report_status("Templates geladen. Vorschau aktualisieren, um den Bericht zu sehen.")

    def _resolve_report_directory(self) -> Path | None:
        module = importlib.import_module("Isolierung")
        module_file = getattr(module, "__file__", None)
        if not module_file:
            return None
        return Path(module_file).resolve().parent / "reports"

    def _current_report_template(self) -> _ReportTemplateSpec | None:
        if not self._report_templates:
            return None
        if self._report_template_combo is None:
            return self._report_templates[0]
        name = self._report_template_combo.currentText()
        for spec in self._report_templates:
            if spec.name == name:
                return spec
        return self._report_templates[0]

    def _update_report_preview(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            self._set_report_preview_text("Keine Report-Templates gefunden.")
            self._set_report_status("Keine Templates verfügbar.")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="isolierung-report-preview-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
        except Exception as exc:
            self._set_report_preview_text(f"Bericht konnte nicht erstellt werden:\n{exc}")
            self._set_report_status("Bericht konnte nicht aktualisiert werden.")
            return
        self._report_current_text = rendered
        self._set_report_preview_text(rendered)
        self._set_report_status("Bericht aktualisiert.")

    def _set_report_preview_text(self, text: str) -> None:
        if self._report_preview is None:
            return
        self._report_preview.setPlainText(text)

    def _set_report_status(self, message: str) -> None:
        if self._report_status_label is None:
            return
        self._report_status_label.setText(message)

    def _on_report_export_pdf(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            QMessageBox.warning(self.widget, "Hinweis", "Keine Report-Templates gefunden.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "PDF speichern",
            "",
            "PDF (*.pdf);;Alle Dateien (*.*)",
        )
        if not path:
            return
        try:
            with tempfile.TemporaryDirectory(prefix="isolierung-report-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
                self._report_current_text = rendered
                self._set_report_preview_text(rendered)
                self._write_report_pdf(Path(path), [(f"Isolierung – {spec.name}", rendered)])
        except Exception as exc:
            QMessageBox.critical(
                self.widget,
                "Fehler",
                f"Der Bericht konnte nicht erstellt werden:\n{exc}",
            )
            return
        self._set_report_status(f"Bericht gespeichert unter {path}.")
        QMessageBox.information(self.widget, "Fertig", "Der Bericht wurde erstellt.")

    def _render_report_template(self, spec: _ReportTemplateSpec, resource_dir: Path) -> str:
        project, plugin_states = self._build_report_context()
        env = Environment(
            loader=FileSystemLoader(spec.path.parent),
            autoescape=False,
            undefined=StrictUndefined,
        )
        template = env.get_template(spec.path.name)
        context = {"project": project, "plugin_states": plugin_states}
        context |= self._augment_report_context(plugin_states, resource_dir)
        rendered = template.render(context)
        return rendered

    def _build_report_context(self) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        self._sync_internal_state_from_widgets()
        project = {
            "name": "Aktuelle Eingaben",
            "author": "",
            "created_at": "",
            "updated_at": "",
        }
        calc_layers = self._calc_inputs.get("layers", [])
        thicknesses: list[float] = []
        families: list[str] = []
        variants: list[str] = []
        if isinstance(calc_layers, list):
            for layer in calc_layers:
                if not isinstance(layer, dict):
                    continue
                thicknesses.append(self._float_or_zero(layer.get("thickness")))
                families.append(self._coerce_str(layer.get("family", "")))
                variants.append(self._coerce_str(layer.get("variant", "")))
        berechnung: dict[str, Any] = {
            "name": "",
            "layer_count": len(thicknesses),
            "thicknesses": thicknesses,
            "isolierungen": families,
            "varianten": variants,
            "T_left": self._float_or_zero(self._calc_inputs.get("T_left")),
            "T_inf": self._float_or_zero(self._calc_inputs.get("T_inf")),
            "h": self._float_or_zero(self._calc_inputs.get("h")),
        }
        if self._calc_results.get("status") == "ok" and isinstance(
            self._calc_results.get("data"), dict
        ):
            berechnung["result"] = dict(self._calc_results.get("data", {}))

        build_layers = self._build_inputs.get("layers", [])
        build_thicknesses: list[float] = []
        build_families: list[str] = []
        if isinstance(build_layers, list):
            for layer in build_layers:
                if not isinstance(layer, dict):
                    continue
                build_thicknesses.append(self._float_or_zero(layer.get("thickness")))
                build_families.append(self._coerce_str(layer.get("family", "")))
        dimensions = self._build_inputs.get("dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        schichtaufbau: dict[str, Any] = {
            "measure_type": self._coerce_str(self._build_inputs.get("measure_type", "")),
            "dimensions": {
                "L": self._float_or_zero(dimensions.get("L")),
                "B": self._float_or_zero(dimensions.get("B")),
                "H": self._float_or_zero(dimensions.get("H")),
            },
            "layers": {
                "thicknesses": build_thicknesses,
                "isolierungen": build_families,
            },
        }
        if self._build_results.get("status") == "ok" and isinstance(
            self._build_results.get("data"), dict
        ):
            schichtaufbau["result"] = dict(self._build_results.get("data", {}))

        zuschnitt_status = self._coerce_str(self._zuschnitt_results.get("status", "idle"))
        zuschnitt_summary = self._zuschnitt_results.get("summary", [])
        material_summary: list[dict[str, Any]] = []
        if isinstance(zuschnitt_summary, list):
            for entry in zuschnitt_summary:
                if not isinstance(entry, dict):
                    continue
                if entry.get("is_total"):
                    continue
                material_summary.append(
                    {
                        "material": entry.get("material", "–"),
                        "count": entry.get("count"),
                        "price": entry.get("price"),
                        "cost": entry.get("cost"),
                    }
                )
        zuschnitt: dict[str, Any] = {
            "status": zuschnitt_status,
            "message": self._coerce_str(self._zuschnitt_results.get("message", "")),
            "kerf": self._float_or_zero(self._zuschnitt_inputs.get("kerf")),
            "cached_plates": list(self._zuschnitt_inputs.get("cached_plates", [])),
            "placements": list(self._zuschnitt_results.get("placements", []))
            if zuschnitt_status == "ok"
            else [],
            "material_summary": material_summary,
            "total_cost": self._zuschnitt_results.get("total_cost"),
            "total_bin_count": self._zuschnitt_results.get("total_bin_count"),
        }
        return project, {
            "isolierung": {
                "berechnung": berechnung,
                "schichtaufbau": schichtaufbau,
                "zuschnitt": zuschnitt,
            }
        }

    def _write_report_pdf(self, target: Path, sections: list[tuple[str, str]]) -> None:
        doc = SimpleDocTemplate(str(target), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for title, content in sections:
            story.append(Paragraph(title, styles["Heading1"]))
            story.append(Spacer(1, 12))
            for block in self._to_flowables(content, styles):
                story.append(block)
        doc.build(story)

    def _to_flowables(self, content: str, styles) -> list[Any]:
        sanitized = content.strip()
        if not sanitized:
            return [Paragraph("(keine Daten)", styles["Normal"])]
        elements: list[Any] = []
        blocks = sanitized.split("\n\n")
        for index, raw_block in enumerate(blocks):
            block = raw_block.strip()
            image = self._parse_image_block(block)
            if image is not None:
                elements.append(image)
            else:
                try:
                    clean_block = self._sanitize_block(block)
                    elements.append(Paragraph(clean_block.replace("\n", "<br/>"), styles["Normal"]))
                except Exception as exc:
                    self._report_logger.warning(
                        "Ungültiger Absatz im Bericht: %s", block, exc_info=exc
                    )
                    elements.append(Paragraph("(keine Daten)", styles["Normal"]))
            if index < len(blocks) - 1:
                elements.append(Spacer(1, 8))
        return elements

    def _parse_image_block(self, block: str) -> Image | None:
        align = None
        para_match = re.fullmatch(r"<para([^>]*)>(.*)</para>", block, flags=re.IGNORECASE | re.DOTALL)
        if para_match:
            attr_text = para_match.group(1)
            align_match = re.search(r"align=\"?([a-zA-Z]+)\"?", attr_text or "")
            if align_match:
                align = align_match.group(1).upper()
            block = para_match.group(2).strip()

        img_match = re.fullmatch(r"<img\s+[^>]*src=\"([^\"]+)\"[^>]*>", block, flags=re.IGNORECASE)
        if not img_match:
            return None
        src = img_match.group(1)
        width = self._extract_dimension(block, "width")
        height = self._extract_dimension(block, "height")
        try:
            image = Image(src, width=width, height=height)
        except Exception as exc:
            self._report_logger.warning("Bild konnte nicht geladen werden: %s", src, exc_info=exc)
            return None
        if align in {"LEFT", "CENTER", "RIGHT"}:
            image.hAlign = align
        return image

    @staticmethod
    def _sanitize_block(block: str) -> str:
        without_font = re.sub(r"</?font[^>]*>", "", block, flags=re.IGNORECASE)
        without_para = re.sub(r"</?para[^>]*>", "", without_font, flags=re.IGNORECASE)
        cleaned = without_para.strip()
        return cleaned or "(keine Daten)"

    @staticmethod
    def _extract_dimension(block: str, name: str) -> float | None:
        match = re.search(rf"{name}=\"?([0-9.]+)\"?", block, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _augment_report_context(
        self, plugin_states: dict[str, dict[str, Any]], resource_dir: Path
    ) -> dict[str, dict[str, Any]]:
        iso_state = plugin_states.get("isolierung", {})
        berechnung = iso_state.get("berechnung", {})
        result = berechnung.get("result")
        if not berechnung or not result:
            return {}
        thicknesses = berechnung.get("thicknesses") or []
        temperatures = result.get("interface_temperatures") or []
        if not thicknesses or len(temperatures) != len(thicknesses) + 1:
            return {}
        plot_path = resource_dir / "isolierung_temperature_plot.png"
        try:
            self._make_temperature_plot(thicknesses, temperatures, plot_path)
        except Exception:
            return {}
        enriched_berechnung = dict(berechnung)
        enriched_berechnung["temperature_plot"] = str(plot_path)
        updated_plugin_states = dict(plugin_states)
        updated_iso_state = dict(iso_state)
        updated_iso_state["berechnung"] = enriched_berechnung
        updated_plugin_states["isolierung"] = updated_iso_state
        return {"plugin_states": updated_plugin_states}

    def _make_temperature_plot(
        self, thicknesses: Iterable[float], temperatures: Iterable[float], target: Path
    ) -> None:
        plt.switch_backend("Agg")
        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        total_x = [0.0]
        for thickness in thicknesses:
            total_x.append(total_x[-1] + float(thickness))

        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("report_cmap", colors, N=256)
        ax.plot(total_x, list(temperatures), linewidth=2, marker="o", color="#111827")

        x_pos = 0.0
        thickness_list = list(thicknesses)
        for index, thickness in enumerate(thickness_list):
            color_value = index / max(len(thickness_list) - 1, 1)
            ax.axvspan(x_pos, x_pos + thickness, color=cmap(color_value), alpha=0.35)
            x_pos += thickness

        for x, temp in zip(total_x, temperatures):
            ax.text(
                x,
                temp + 5,
                f"{float(temp):.0f}°C",
                ha="center",
                fontsize=8,
                bbox=dict(facecolor="#ffffff", alpha=0.8, edgecolor="none"),
                color="#111827",
            )

        ax.set_xlabel("Dicke [mm]", color="#111827")
        ax.set_ylabel("Temperatur [°C]", color="#111827")
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=11, color="#111827")
        ax.grid(True, linestyle="--", alpha=0.5, color="#9ca3af")
        ax.tick_params(axis="x", colors="#111827", labelsize=8)
        ax.tick_params(axis="y", colors="#111827", labelsize=8)
        fig.tight_layout()
        fig.savefig(target, bbox_inches="tight")
        plt.close(fig)

    def _refresh_zuschnitt_results_view(self) -> None:
        if self._zuschnitt_status_label is None:
            return
        status = self._zuschnitt_results.get("status", "idle")
        message = self._coerce_str(self._zuschnitt_results.get("message", ""))
        lines = []
        if status == "ok":
            lines.append("Status: Berechnung abgeschlossen")
        elif status == "error":
            lines.append("Status: Fehler")
            if message:
                lines.append(message)
        else:
            lines.append("Status: Bereit")
            if message:
                lines.append(message)
        self._zuschnitt_status_label.setText("\n".join(lines))

        placements = self._zuschnitt_results.get("placements", [])
        summary = self._zuschnitt_results.get("summary", [])
        if self._zuschnitt_results_model is not None:
            self._zuschnitt_results_model.set_rows(
                placements if isinstance(placements, list) else []
            )
        if self._zuschnitt_overview_model is not None:
            self._zuschnitt_overview_model.set_rows(summary if isinstance(summary, list) else [])
        self._restore_zuschnitt_selection()
        self._refresh_zuschnitt_preview()

    def _restore_zuschnitt_selection(self) -> None:
        if self._zuschnitt_results_view is not None:
            selected_row = self._zuschnitt_ui.get("selected_placement_row", -1)
            if isinstance(selected_row, int) and 0 <= selected_row < self._zuschnitt_results_view.model().rowCount():
                self._zuschnitt_results_view.selectRow(selected_row)
            else:
                self._zuschnitt_results_view.clearSelection()
        if self._zuschnitt_overview_view is not None:
            selected_row = self._zuschnitt_ui.get("selected_summary_row", -1)
            if isinstance(selected_row, int) and 0 <= selected_row < self._zuschnitt_overview_view.model().rowCount():
                self._zuschnitt_overview_view.selectRow(selected_row)
            else:
                self._zuschnitt_overview_view.clearSelection()

    def _refresh_zuschnitt_preview(self) -> None:
        if self._zuschnitt_preview_scene is None or self._zuschnitt_preview_view is None:
            return
        self._zuschnitt_preview_scene.clear()
        placements = self._zuschnitt_results.get("placements", [])
        if not isinstance(placements, list) or not placements:
            self._zuschnitt_preview_scene.setSceneRect(0, 0, 0, 0)
            return

        grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for placement in placements:
            if not isinstance(placement, dict):
                continue
            key = (str(placement.get("material", "")), int(placement.get("bin", 0)))
            grouped.setdefault(key, []).append(placement)

        bins = list(grouped.items())
        columns = max(1, math.ceil(math.sqrt(len(bins))))
        rows = math.ceil(len(bins) / columns)

        col_widths = [0.0 for _ in range(columns)]
        row_heights = [0.0 for _ in range(rows)]
        for idx, (_, entries) in enumerate(bins):
            col = idx % columns
            row = idx // columns
            if not entries:
                continue
            col_widths[col] = max(col_widths[col], float(entries[0].get("bin_width", 0)))
            row_heights[row] = max(row_heights[row], float(entries[0].get("bin_height", 0)))

        gap = 30.0
        padding = 16.0
        total_width = sum(col_widths) + gap * (columns - 1)
        total_height = sum(row_heights) + gap * (rows - 1)

        view_width = max(self._zuschnitt_preview_view.viewport().width(), 200)
        view_height = max(self._zuschnitt_preview_view.viewport().height(), 200)
        scale_x = (view_width - 2 * padding) / total_width if total_width else 1.0
        scale_y = (view_height - 2 * padding) / total_height if total_height else 1.0
        scale = min(scale_x, scale_y, 2.0)

        col_offsets = [padding]
        for width in col_widths[:-1]:
            col_offsets.append(col_offsets[-1] + width * scale + gap * scale)
        row_offsets = [padding]
        for height in row_heights[:-1]:
            row_offsets.append(row_offsets[-1] + height * scale + gap * scale)

        label_offset = 6
        for idx, ((material, bin_idx), entries) in enumerate(bins):
            col = idx % columns
            row = idx // columns
            x_cursor = col_offsets[col]
            y_cursor = row_offsets[row]
            if not entries:
                continue
            bin_w = float(entries[0].get("bin_width", 0))
            bin_h = float(entries[0].get("bin_height", 0))

            outline_pen = QPen(QColor("#444"))
            outline_pen.setWidth(2)
            self._zuschnitt_preview_scene.addRect(
                x_cursor,
                y_cursor + label_offset,
                bin_w * scale,
                bin_h * scale,
                outline_pen,
            )

            label_item = self._zuschnitt_preview_scene.addText(
                f"{material} – Rohling {bin_idx}",
                QFont("Segoe UI", 9, QFont.Bold),
            )
            label_item.setPos(x_cursor + 6, y_cursor + 4)
            label_item.setTextWidth(max(bin_w * scale - 12, 50))

            for placement in entries:
                color = QColor(color_for(str(material)))
                fill_brush = QBrush(color)
                rect_pen = QPen(QColor("#222"))
                px = x_cursor + float(placement.get("x", 0)) * scale
                py = y_cursor + label_offset + float(placement.get("y", 0)) * scale
                pw = float(placement.get("breite", 0)) * scale
                ph = float(placement.get("hoehe", 0)) * scale
                self._zuschnitt_preview_scene.addRect(px, py, pw, ph, rect_pen, fill_brush)
                text_item = self._zuschnitt_preview_scene.addText(
                    str(placement.get("teil", "")),
                    QFont("Segoe UI", 8),
                )
                text_item.setTextWidth(max(pw - 12, 20))
                text_item.setPos(px + max((pw - text_item.textWidth()) / 2, 2), py + max((ph - 14) / 2, 2))

        layout_width = padding * 2 + total_width * scale + max(gap * scale, 0)
        layout_height = padding * 2 + total_height * scale + label_offset + max(gap * scale, 0)
        self._zuschnitt_preview_scene.setSceneRect(0, 0, layout_width, layout_height)

    def _on_zuschnitt_summary_selection_changed(self) -> None:
        if self._zuschnitt_overview_view is None:
            return
        selected = self._zuschnitt_overview_view.selectionModel().selectedRows()
        if not selected:
            self._zuschnitt_ui["selected_summary_row"] = -1
        else:
            self._zuschnitt_ui["selected_summary_row"] = selected[0].row()

    def _on_zuschnitt_placement_selection_changed(self) -> None:
        if self._zuschnitt_results_view is None:
            return
        selected = self._zuschnitt_results_view.selectionModel().selectedRows()
        if not selected:
            self._zuschnitt_ui["selected_placement_row"] = -1
        else:
            self._zuschnitt_ui["selected_placement_row"] = selected[0].row()

    def _invalidate_zuschnitt_results(self, message: str = "", clear_cached: bool = False) -> None:
        self._zuschnitt_results = {
            "status": "idle",
            "message": message,
            "placements": [],
            "summary": [],
            "total_cost": None,
            "total_bin_count": None,
        }
        if clear_cached:
            self._zuschnitt_inputs["cached_plates"] = []
        self._zuschnitt_ui["selected_placement_row"] = -1
        self._zuschnitt_ui["selected_summary_row"] = -1
        self._refresh_zuschnitt_results_view()

    def _ensure_zuschnitt_results(self) -> None:
        placements = self._zuschnitt_results.get("placements", [])
        if not isinstance(placements, list) or not placements:
            raise ValueError("Keine Ergebnisse zum Export vorhanden.")

    def _on_zuschnitt_export_csv(self) -> None:
        try:
            self._ensure_zuschnitt_results()
            path, _ = QFileDialog.getSaveFileName(
                self.widget,
                "CSV speichern",
                "",
                "CSV (*.csv);;Alle Dateien (*.*)",
            )
            if not path:
                return
            placements = self._zuschnitt_results.get("placements", [])
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(
                    [
                        "Material",
                        "Rohling",
                        "Teil",
                        "Breite_eff_mm",
                        "Hoehe_eff_mm",
                        "X_mm",
                        "Y_mm",
                        "Rotation",
                        "Breite_original_mm",
                        "Hoehe_original_mm",
                    ]
                )
                for row in placements:
                    writer.writerow(
                        [
                            row.get("material", ""),
                            row.get("bin", ""),
                            row.get("teil", ""),
                            row.get("breite", ""),
                            row.get("hoehe", ""),
                            row.get("x", ""),
                            row.get("y", ""),
                            "90" if row.get("rotation") else "0",
                            row.get("original_width", ""),
                            row.get("original_height", ""),
                        ]
                    )
        except Exception as exc:
            self._zuschnitt_results["status"] = "error"
            self._zuschnitt_results["message"] = str(exc)
            self._refresh_zuschnitt_results_view()

    def _on_zuschnitt_export_excel(self) -> None:
        try:
            self._ensure_zuschnitt_results()
            path, _ = QFileDialog.getSaveFileName(
                self.widget,
                "Excel speichern",
                "",
                "Excel (*.xlsx);;Alle Dateien (*.*)",
            )
            if not path:
                return
            wb = Workbook()
            ws = wb.active
            ws.title = "Zuschnitt"
            ws.append(
                [
                    "Material",
                    "Rohling",
                    "Teil",
                    "Breite_eff_mm",
                    "Hoehe_eff_mm",
                    "X_mm",
                    "Y_mm",
                    "Rotation",
                    "Breite_original_mm",
                    "Hoehe_original_mm",
                ]
            )
            placements = self._zuschnitt_results.get("placements", [])
            for row in placements:
                ws.append(
                    [
                        row.get("material"),
                        row.get("bin"),
                        row.get("teil"),
                        row.get("breite"),
                        row.get("hoehe"),
                        row.get("x"),
                        row.get("y"),
                        90 if row.get("rotation") else 0,
                        row.get("original_width"),
                        row.get("original_height"),
                    ]
                )
            wb.save(path)
        except Exception as exc:
            self._zuschnitt_results["status"] = "error"
            self._zuschnitt_results["message"] = str(exc)
            self._refresh_zuschnitt_results_view()

    def _load_materials(self) -> None:
        self._materials = list_materials()
        self._material_names = [material.name for material in self._materials]

    def _on_materials_changed(self) -> None:
        if self.widget is None:
            return
        self._load_materials()
        for index, widgets in enumerate(self._layer_widgets):
            current_family = widgets.family_combo.currentText()
            current_family = (
                current_family if current_family in self._material_names else ""
            )
            self._populate_family_combo(widgets.family_combo)
            self._select_combo_value(
                widgets.family_combo, current_family, self._FAMILY_PLACEHOLDER
            )
            selected_variant = ""
            layers = self._calc_inputs.get("layers", [])
            if isinstance(layers, list) and index < len(layers):
                selected_variant = self._coerce_str(layers[index].get("variant", ""))
            variant_found = self._populate_variant_combo(
                widgets, current_family, selected_variant
            )
            if not variant_found and isinstance(layers, list) and index < len(layers):
                layers[index]["variant"] = ""
        for index, widgets in enumerate(self._build_layer_widgets):
            current_family = widgets.family_combo.currentText()
            current_family = (
                current_family if current_family in self._material_names else ""
            )
            self._populate_build_family_combo(widgets.family_combo)
            self._select_combo_value(
                widgets.family_combo, current_family, self._FAMILY_PLACEHOLDER
            )
            build_layers = self._build_inputs.get("layers", [])
            if isinstance(build_layers, list) and index < len(build_layers):
                if current_family != build_layers[index].get("family", ""):
                    build_layers[index]["family"] = current_family
        self._sync_internal_state_from_widgets()
        self._invalidate_zuschnitt_results(
            "Isolierung DB wurde aktualisiert. Bitte Zuschnitt neu berechnen."
        )

    def _set_layer_count(self, count: int) -> None:
        if self._layers_layout is None:
            return
        if count == len(self._layer_widgets):
            return
        self._clear_layer_rows()
        self._layer_widgets = []
        for index in range(count):
            widgets = self._create_layer_row(index)
            self._layer_widgets.append(widgets)

    def _clear_layer_rows(self) -> None:
        if self._layers_layout is None:
            return
        while self._layers_layout.count() > 4:
            item = self._layers_layout.takeAt(4)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _create_layer_row(self, index: int) -> _LayerWidgets:
        assert self._layers_layout is not None
        row = index + 1
        label = QLabel(f"{row}")
        thickness_input = QLineEdit()
        thickness_input.textChanged.connect(lambda text, idx=index: self._on_thickness_changed(idx, text))
        family_combo = QComboBox()
        variant_combo = QComboBox()
        family_combo.currentTextChanged.connect(
            lambda text, idx=index: self._on_family_changed(idx, text)
        )
        variant_combo.currentIndexChanged.connect(
            lambda _value, idx=index: self._on_variant_changed(idx)
        )

        self._populate_family_combo(family_combo)
        widgets = _LayerWidgets(label, thickness_input, family_combo, variant_combo, {})
        self._populate_variant_combo(widgets, "", "")

        self._layers_layout.addWidget(label, row, 0)
        self._layers_layout.addWidget(thickness_input, row, 1)
        self._layers_layout.addWidget(family_combo, row, 2)
        self._layers_layout.addWidget(variant_combo, row, 3)
        return widgets

    def _populate_family_combo(self, combo: QComboBox) -> None:
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem(self._FAMILY_PLACEHOLDER)
            for name in self._material_names:
                combo.addItem(name)

    def _populate_variant_combo(
        self, widgets: _LayerWidgets, family_name: str, selected_variant: str
    ) -> bool:
        variant_lookup: dict[str, tuple[str, float]] = {}
        found = False
        with QSignalBlocker(widgets.variant_combo):
            widgets.variant_combo.clear()
            widgets.variant_combo.addItem(self._VARIANT_PLACEHOLDER)
            if family_name and family_name != self._FAMILY_PLACEHOLDER:
                material = load_material(family_name)
                if material:
                    for variant in material.variants:
                        display = f"{variant.name} ({variant.thickness} mm)"
                        widgets.variant_combo.addItem(display)
                        variant_lookup[display] = (variant.name, variant.thickness)
            display_value = selected_variant
            if selected_variant:
                for display, (name, _thickness) in variant_lookup.items():
                    if name == selected_variant:
                        display_value = display
                        found = True
                        break
            self._select_combo_value(
                widgets.variant_combo, display_value, self._VARIANT_PLACEHOLDER
            )
        widgets.variant_lookup = variant_lookup
        if not selected_variant:
            return True
        return found

    def _on_layer_count_changed(self, value: int) -> None:
        layers = self._calc_inputs.get("layers", [])
        if not isinstance(layers, list):
            layers = []
        if value > len(layers):
            for _ in range(value - len(layers)):
                layers.append({"thickness": "", "family": "", "variant": ""})
        elif value < len(layers):
            layers = layers[:value]
        if not layers:
            layers = [{"thickness": "", "family": "", "variant": ""}]
        self._calc_inputs["layers"] = layers
        self.refresh_view()

    def _on_family_changed(self, index: int, text: str) -> None:
        if index >= len(self._calc_inputs.get("layers", [])):
            return
        family = "" if text == self._FAMILY_PLACEHOLDER else text
        self._calc_inputs["layers"][index]["family"] = family
        self._calc_inputs["layers"][index]["variant"] = ""
        self._ensure_calc_ui_layer_state(index)
        self._calc_ui["layers"][index]["family_index"] = (
            self._layer_widgets[index].family_combo.currentIndex()
        )
        self._calc_ui["layers"][index]["variant_index"] = 0
        if index < len(self._layer_widgets):
            self._populate_variant_combo(self._layer_widgets[index], family, "")

    def _on_variant_changed(self, index: int) -> None:
        if index >= len(self._calc_inputs.get("layers", [])):
            return
        widgets = self._layer_widgets[index]
        display = widgets.variant_combo.currentText()
        if display == self._VARIANT_PLACEHOLDER:
            self._calc_inputs["layers"][index]["variant"] = ""
            self._ensure_calc_ui_layer_state(index)
            self._calc_ui["layers"][index]["variant_index"] = widgets.variant_combo.currentIndex()
            return
        variant_name, thickness = widgets.variant_lookup.get(display, ("", 0.0))
        self._calc_inputs["layers"][index]["variant"] = variant_name
        self._ensure_calc_ui_layer_state(index)
        self._calc_ui["layers"][index]["variant_index"] = widgets.variant_combo.currentIndex()
        if variant_name and not widgets.thickness_input.text():
            widgets.thickness_input.setText(self._format_number(thickness))

    def _on_calculate(self) -> None:
        self._sync_internal_state_from_widgets()
        try:
            parsed = self._parse_calculation_inputs()
            validate_inputs(
                parsed["n"],
                parsed["thicknesses"],
                parsed["isolierungen"],
                parsed["T_left"],
                parsed["T_inf"],
                parsed["h"],
            )
            result = perform_calculation(
                parsed["thicknesses"],
                parsed["isolierungen"],
                parsed["T_left"],
                parsed["T_inf"],
                parsed["h"],
            )
            self._calc_results = {
                "status": "ok",
                "message": "",
                "data": result,
            }
        except Exception as exc:
            self._calc_results = {
                "status": "error",
                "message": str(exc),
                "data": {},
            }
        self.refresh_view()

    def _parse_calculation_inputs(self) -> dict[str, Any]:
        T_left = self._parse_float(self._calc_inputs.get("T_left", ""))
        T_inf = self._parse_float(self._calc_inputs.get("T_inf", ""))
        h = self._parse_float(self._calc_inputs.get("h", ""))
        if T_left is None or T_inf is None or h is None:
            raise ValueError("Bitte gültige Zahlen für T_left, T_inf und h eingeben.")

        layers = self._calc_inputs.get("layers", [])
        thicknesses = []
        isolierungen = []
        for layer in layers:
            thickness_value = self._parse_float(layer.get("thickness", ""))
            if thickness_value is None:
                raise ValueError("Bitte gültige Schichtdicken (mm) eingeben.")
            thicknesses.append(thickness_value)
            family = self._coerce_str(layer.get("family", ""))
            if not family:
                raise ValueError("Bitte für jede Schicht eine Materialfamilie auswählen.")
            isolierungen.append(family)
        return {
            "n": len(layers),
            "thicknesses": thicknesses,
            "isolierungen": isolierungen,
            "T_left": T_left,
            "T_inf": T_inf,
            "h": h,
        }

    def _populate_build_family_combo(self, combo: QComboBox) -> None:
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem(self._FAMILY_PLACEHOLDER)
            for name in self._material_names:
                combo.addItem(name)

    def _set_build_layer_count(self, count: int) -> None:
        if self._build_layers_layout is None:
            return
        if count == len(self._build_layer_widgets):
            return
        self._clear_build_layer_rows()
        self._build_layer_widgets = []
        for index in range(count):
            widgets = self._create_build_layer_row(index)
            self._build_layer_widgets.append(widgets)

    def _clear_build_layer_rows(self) -> None:
        if self._build_layers_layout is None:
            return
        while self._build_layers_layout.count() > 4:
            item = self._build_layers_layout.takeAt(4)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _create_build_layer_row(self, index: int) -> _BuildLayerWidgets:
        assert self._build_layers_layout is not None
        row = index + 1
        label = QLabel(f"{row}")
        thickness_input = QLineEdit()
        thickness_input.textChanged.connect(
            lambda text, idx=index: self._on_build_thickness_changed(idx, text)
        )
        family_combo = QComboBox()
        family_combo.currentTextChanged.connect(
            lambda text, idx=index: self._on_build_family_changed(idx, text)
        )
        remove_button = QPushButton("Entfernen")
        remove_button.clicked.connect(lambda _checked=False, idx=index: self._on_build_remove_layer(idx))

        self._populate_build_family_combo(family_combo)

        self._build_layers_layout.addWidget(label, row, 0)
        self._build_layers_layout.addWidget(thickness_input, row, 1)
        self._build_layers_layout.addWidget(family_combo, row, 2)
        self._build_layers_layout.addWidget(remove_button, row, 3)
        return _BuildLayerWidgets(label, thickness_input, family_combo, remove_button)

    def _refresh_build_layer_labels(self) -> None:
        single = len(self._build_layer_widgets) <= 1
        for index, widgets in enumerate(self._build_layer_widgets, start=1):
            widgets.label.setText(str(index))
            widgets.remove_button.setEnabled(not single)

    def _on_build_add_layer(self) -> None:
        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list):
            layers = []
        layers.append({"thickness": "", "family": ""})
        self._build_inputs["layers"] = layers
        self.refresh_view()

    def _on_build_remove_layer(self, index: int) -> None:
        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list):
            layers = []
        if len(layers) <= 1:
            return
        if 0 <= index < len(layers):
            layers.pop(index)
        if not layers:
            layers = [{"thickness": "", "family": ""}]
        self._build_inputs["layers"] = layers
        self.refresh_view()

    def _on_build_measure_changed(self) -> None:
        if self._build_measure_outer is not None and self._build_measure_outer.isChecked():
            self._build_inputs["measure_type"] = "outer"
        elif self._build_measure_inner is not None and self._build_measure_inner.isChecked():
            self._build_inputs["measure_type"] = "inner"

    def _on_build_dimension_changed(self, _text: str) -> None:
        if self._build_L_input is not None:
            self._build_inputs.setdefault("dimensions", {})["L"] = self._build_L_input.text()
        if self._build_B_input is not None:
            self._build_inputs.setdefault("dimensions", {})["B"] = self._build_B_input.text()
        if self._build_H_input is not None:
            self._build_inputs.setdefault("dimensions", {})["H"] = self._build_H_input.text()

    def _on_build_thickness_changed(self, index: int, text: str) -> None:
        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list) or index >= len(layers):
            return
        layers[index]["thickness"] = text

    def _on_build_family_changed(self, index: int, text: str) -> None:
        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list) or index >= len(layers):
            return
        family = "" if text == self._FAMILY_PLACEHOLDER else text
        layers[index]["family"] = family

    def _on_build_import_layers(self) -> None:
        self._sync_calculation_state_from_widgets()
        layers = self._calc_inputs.get("layers", [])
        if not isinstance(layers, list) or not layers:
            return
        imported = []
        for layer in layers:
            imported.append(
                {
                    "thickness": self._coerce_str(layer.get("thickness", "")),
                    "family": self._coerce_str(layer.get("family", "")),
                }
            )
        if imported:
            self._build_inputs["layers"] = imported
        self.refresh_view()

    def _on_build_calculate(self) -> None:
        self._sync_internal_state_from_widgets()
        try:
            parsed = self._parse_build_inputs()
            result = compute_plate_dimensions(
                parsed["thicknesses"],
                parsed["measure_type"],
                parsed["L"],
                parsed["B"],
                parsed["H"],
            )
            self._build_results = {
                "status": "ok",
                "message": "",
                "data": self._serialize_build_result(result, parsed["materials"]),
            }
            self._invalidate_zuschnitt_results(
                "Schichtaufbau aktualisiert. Bitte Platten neu übernehmen.", clear_cached=True
            )
        except Exception as exc:
            self._build_results = {
                "status": "error",
                "message": str(exc),
                "data": {},
            }
            self._invalidate_zuschnitt_results(
                "Schichtaufbau fehlgeschlagen. Zuschnitt-Ergebnisse wurden zurückgesetzt.",
                clear_cached=True,
            )
        self.refresh_view()

    def _on_build_reset(self) -> None:
        self._build_inputs["measure_type"] = "outer"
        self._build_inputs["dimensions"] = {"L": "", "B": "", "H": ""}
        self._build_inputs["layers"] = [{"thickness": "", "family": ""}]
        self._build_results = {"status": "idle", "message": "", "data": {}}
        self._build_ui["selected_row"] = -1
        self._invalidate_zuschnitt_results(
            "Schichtaufbau zurückgesetzt. Bitte Platten neu übernehmen.", clear_cached=True
        )
        self.refresh_view()

    def _parse_build_inputs(self) -> dict[str, Any]:
        measure_type = self._coerce_str(self._build_inputs.get("measure_type", "outer"))
        if measure_type not in {"outer", "inner"}:
            raise ValueError("Bitte eine gültige Maßvorgabe wählen.")
        dimensions = self._build_inputs.get("dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        L = self._parse_float(dimensions.get("L"))
        B = self._parse_float(dimensions.get("B"))
        H = self._parse_float(dimensions.get("H"))
        if L is None or B is None or H is None:
            raise ValueError("Bitte gültige Maße (L, B, H) angeben.")

        layers = self._build_inputs.get("layers", [])
        if not isinstance(layers, list):
            layers = []
        thicknesses: list[float] = []
        materials: list[str] = []
        for layer in layers:
            thickness_text = self._coerce_str(layer.get("thickness", "")).strip()
            if not thickness_text:
                continue
            thickness_value = self._parse_float(thickness_text)
            if thickness_value is None:
                raise ValueError("Bitte gültige Schichtdicken (mm) eingeben.")
            thicknesses.append(thickness_value)
            materials.append(self._coerce_str(layer.get("family", "")))
        if not thicknesses:
            raise ValueError("Bitte mindestens eine Schichtdicke angeben.")
        return {
            "measure_type": measure_type,
            "L": L,
            "B": B,
            "H": H,
            "thicknesses": thicknesses,
            "materials": materials,
        }

    def _serialize_build_result(self, result: BuildResult, isolierungen: Iterable[str]) -> dict[str, Any]:
        data = asdict(result)
        data["isolierungen"] = list(isolierungen)
        return data

    def _deserialize_build_result(self, data: dict[str, Any]) -> BuildResult:
        layers: list[LayerResult] = []
        for layer in data.get("layers", []):
            plates = [Plate(**plate) for plate in layer.get("plates", [])]
            layers.append(
                LayerResult(
                    layer_index=int(layer.get("layer_index", 0)),
                    thickness=float(layer.get("thickness", 0.0)),
                    plates=plates,
                )
            )
        return BuildResult(
            float(data.get("la_l", 0.0)),
            float(data.get("la_b", 0.0)),
            float(data.get("la_h", 0.0)),
            float(data.get("li_l", 0.0)),
            float(data.get("li_b", 0.0)),
            float(data.get("li_h", 0.0)),
            layers,
        )

    def _refresh_build_results_view(self) -> None:
        if self._build_status_label is None:
            return
        status = self._build_results.get("status", "idle")
        message = self._coerce_str(self._build_results.get("message", ""))
        lines = []
        if status == "ok":
            lines.append("Status: Berechnung abgeschlossen")
        elif status == "error":
            lines.append("Status: Fehler")
            if message:
                lines.append(message)
        else:
            lines.append("Status: Bereit")
        if self._build_missing_materials_warning:
            lines.append(self._build_missing_materials_warning)
        self._build_status_label.setText("\n".join(lines))

        result_data = self._build_results.get("data", {})
        if status != "ok" or not isinstance(result_data, dict):
            self._clear_build_results()
            return
        try:
            result = self._deserialize_build_result(result_data)
            isolierungen = result_data.get("isolierungen", [])
            if not isinstance(isolierungen, list):
                isolierungen = []
            self._populate_build_results(result, isolierungen)
        except Exception:
            self._clear_build_results()

    def _clear_build_results(self) -> None:
        for label in list(self._build_given_labels.values()) + list(self._build_calc_labels.values()):
            label.setText("–")
        if self._build_layer_count_label is not None:
            self._build_layer_count_label.setText("–")
        if self._build_results_table is not None:
            with QSignalBlocker(self._build_results_table):
                self._build_results_table.setRowCount(0)
                self._build_results_table.clearSelection()
        self._build_ui["selected_row"] = -1

    def _populate_build_results(self, result: BuildResult, isolierungen: list[str]) -> None:
        measure_type = self._build_inputs.get("measure_type", "outer")
        if self._build_given_group is not None and self._build_calc_group is not None:
            if measure_type == "outer":
                self._build_given_group.setTitle("Gegebene Außenmaße")
                self._build_calc_group.setTitle("Berechnete Innenmaße")
                values_given = (result.la_l, result.la_b, result.la_h)
                values_calc = (result.li_l, result.li_b, result.li_h)
            else:
                self._build_given_group.setTitle("Gegebene Innenmaße")
                self._build_calc_group.setTitle("Berechnete Außenmaße")
                values_given = (result.li_l, result.li_b, result.li_h)
                values_calc = (result.la_l, result.la_b, result.la_h)
            for key, value in zip(("L", "B", "H"), values_given):
                if key in self._build_given_labels:
                    self._build_given_labels[key].setText(f"{value:.3f} mm")
            for key, value in zip(("L", "B", "H"), values_calc):
                if key in self._build_calc_labels:
                    self._build_calc_labels[key].setText(f"{value:.3f} mm")
        if self._build_layer_count_label is not None:
            self._build_layer_count_label.setText(str(len(result.layers)))

        if self._build_results_table is None:
            return
        with QSignalBlocker(self._build_results_table):
            self._build_results_table.setRowCount(0)
            row_index = 0
            for layer in result.layers:
                material = "-"
                if layer.layer_index - 1 < len(isolierungen):
                    material_candidate = str(isolierungen[layer.layer_index - 1]).strip()
                    material = material_candidate if material_candidate else "-"
                for plate in layer.plates:
                    self._build_results_table.insertRow(row_index)
                    values = [
                        str(layer.layer_index),
                        material,
                        plate.name,
                        f"{plate.L:.3f}",
                        f"{plate.B:.3f}",
                        f"{plate.H:.3f}",
                    ]
                    for col_index, value in enumerate(values):
                        item = QTableWidgetItem(value)
                        self._build_results_table.setItem(row_index, col_index, item)
                    row_index += 1
        self._restore_build_selection()

    def _on_build_result_selection_changed(self) -> None:
        if self._build_results_table is None:
            return
        selected = self._build_results_table.selectionModel().selectedRows()
        if not selected:
            self._build_ui["selected_row"] = -1
        else:
            self._build_ui["selected_row"] = selected[0].row()

    def _restore_build_selection(self) -> None:
        if self._build_results_table is None:
            return
        selected_row = self._build_ui.get("selected_row", -1)
        if not isinstance(selected_row, int):
            return
        if 0 <= selected_row < self._build_results_table.rowCount():
            self._build_results_table.selectRow(selected_row)
        else:
            self._build_results_table.clearSelection()

    def _sync_internal_state_from_widgets(self) -> None:
        self._sync_calculation_state_from_widgets()
        self._sync_build_state_from_widgets()
        self._sync_zuschnitt_state_from_widgets()
        self._ui_state["active_tab"] = self._get_active_tab_index()

    def _format_result_text(self) -> str:
        status = self._calc_results.get("status")
        if status != "ok":
            message = self._coerce_str(self._calc_results.get("message", ""))
            base = f"Status: Fehler\n{message}" if message else "Status: Bereit"
            if self._missing_materials_warning:
                return f"{base}\n{self._missing_materials_warning}"
            return base
        result = self._calc_results.get("data", {})
        if not isinstance(result, dict):
            return "Status: Berechnung abgeschlossen"
        q = result.get("q")
        r_total = result.get("R_total")
        iterations = result.get("iterations")
        interfaces = result.get("interface_temperatures")
        t_avg = result.get("T_avg")
        k_final = result.get("k_final")
        lines = ["Status: Berechnung abgeschlossen"]
        if q is not None:
            lines.append(f"Wärmestromdichte q: {float(q):.3f} W/m²")
        if r_total is not None:
            lines.append(f"Gesamtwiderstand R_total: {float(r_total):.4f} m²K/W")
        if iterations is not None:
            lines.append(f"Iterationen: {iterations}")
        if interfaces:
            temps = ", ".join(f"{value:.1f}" for value in interfaces)
            lines.append(f"Grenzflächentemperaturen [°C]: {temps}")
        if t_avg:
            temps = ", ".join(f"{value:.1f}" for value in t_avg)
            lines.append(f"Schichtmitteltemperaturen [°C]: {temps}")
        if k_final:
            values = ", ".join(f"{value:.3f}" for value in k_final)
            lines.append(f"Endleitfähigkeiten k [W/mK]: {values}")
        if self._missing_materials_warning:
            lines.append(self._missing_materials_warning)
        return "\n".join(lines)

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_mm_one(row: dict[str, Any], value: Any) -> str:
        try:
            return f"{float(value):.1f}"
        except (TypeError, ValueError):
            return "–"

    @staticmethod
    def _format_rotation(row: dict[str, Any], value: Any) -> str:
        if value is None:
            return "–"
        rotation_value = 90 if bool(value) else 0
        return f"{rotation_value}°"

    @staticmethod
    def _format_price(row: dict[str, Any], value: Any) -> str:
        if value is None:
            return "–"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "–"

    @staticmethod
    def _format_cost(row: dict[str, Any], value: Any) -> str:
        override = row.get("cost_display")
        if isinstance(override, str) and override:
            return override
        if value is None:
            return "–"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "–"

    @staticmethod
    def _parse_float(value: str | float | int | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, (float, int)):
            return float(value)
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _float_or_zero(value: str | float | int | None) -> float:
        parsed = IsolierungQtPlugin._parse_float(value)
        return parsed if parsed is not None else 0.0

    @staticmethod
    def _coerce_str(value: object, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _set_input_text(widget: QLineEdit | None, value: str) -> None:
        if widget is None:
            return
        widget.setText(value)

    @staticmethod
    def _set_label_text(widget: QLabel | None, value: str) -> None:
        if widget is None:
            return
        widget.setText(value)

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str, placeholder: str) -> None:
        if not value:
            combo.setCurrentIndex(0)
            return
        index = combo.findText(value)
        if index == -1:
            combo.setCurrentIndex(0)
        else:
            combo.setCurrentIndex(index)

    def _get_active_tab_index(self) -> int:
        if self._tab_widget is None:
            return 0
        return self._tab_widget.currentIndex()

    def _on_tab_changed(self, index: int) -> None:
        self._ui_state["active_tab"] = index
        if self._tab_widget is None or self._report_tab is None:
            return
        if self._tab_widget.indexOf(self._report_tab) == index:
            self._update_report_preview()

    def _on_text_input_changed(self, text: str) -> None:
        if self._T_left_input is not None:
            self._calc_inputs["T_left"] = self._T_left_input.text()
        if self._T_inf_input is not None:
            self._calc_inputs["T_inf"] = self._T_inf_input.text()
        if self._h_input is not None:
            self._calc_inputs["h"] = self._h_input.text()

    def _on_thickness_changed(self, index: int, text: str) -> None:
        if index >= len(self._calc_inputs.get("layers", [])):
            return
        self._calc_inputs["layers"][index]["thickness"] = text

    def _ensure_calc_ui_layer_state(self, index: int) -> None:
        ui_layers = self._calc_ui.get("layers", [])
        if not isinstance(ui_layers, list):
            ui_layers = []
        while len(ui_layers) <= index:
            ui_layers.append({"family_index": 0, "variant_index": 0})
        self._calc_ui["layers"] = ui_layers

    def _on_widget_destroyed(self, _obj: object | None = None) -> None:
        if self._listener_registered:
            unregister_material_change_listener(self._material_change_handler)
            self._listener_registered = False


__all__ = ["IsolierungQtPlugin"]
