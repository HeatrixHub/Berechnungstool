"""Qt-Plugin für Isolierungsberechnungen (PySide6-only)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from app.core.isolierungen_db.logic import (
    register_material_change_listener,
    unregister_material_change_listener,
)
from Isolierung.core.database import list_materials, load_material
from Isolierung.services.schichtaufbau import BuildResult, LayerResult, Plate, compute_plate_dimensions
from Isolierung.services.tab1_berechnung import perform_calculation, validate_inputs


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
        self._ui_state: dict[str, Any] = {"active_tab": 0}

    @property
    def name(self) -> str:
        return "Isolierung"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        container = QWidget()
        layout = QVBoxLayout()

        header = QWidget()
        header_layout = QHBoxLayout()
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
        tab_widget.addTab(self._build_placeholder_tab(), "Zuschnitt (in Vorbereitung)")

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
        }
        results = {
            "berechnung": dict(self._calc_results),
            "schichtaufbau": dict(self._build_results),
        }
        ui = {
            "active_tab": self._ui_state.get("active_tab", 0),
            "berechnung": dict(self._calc_ui),
            "schichtaufbau": dict(self._build_ui),
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
            if "berechnung" in inputs or "schichtaufbau" in inputs:
                self._apply_calc_inputs(inputs.get("berechnung", {}))
                self._apply_build_inputs(inputs.get("schichtaufbau", {}))
            else:
                self._apply_calc_inputs(inputs)

        if isinstance(results, dict):
            if "berechnung" in results or "schichtaufbau" in results:
                self._apply_calc_results(results.get("berechnung", {}))
                self._apply_build_results(results.get("schichtaufbau", {}))
            else:
                self._apply_calc_results(results)

        if isinstance(ui_state, dict):
            active_tab = ui_state.get("active_tab")
            if isinstance(active_tab, int):
                self._ui_state["active_tab"] = active_tab
            if "berechnung" in ui_state or "schichtaufbau" in ui_state:
                self._apply_calc_ui(ui_state.get("berechnung", {}))
                self._apply_build_ui(ui_state.get("schichtaufbau", {}))
            else:
                self._apply_calc_ui(ui_state)

    def refresh_view(self) -> None:
        self._sync_calculation_view()
        self._sync_schichtaufbau_view()
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

    def _build_calculation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        inputs_group = QGroupBox("Randbedingungen")
        inputs_layout = QGridLayout()
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
        layers_layout = QVBoxLayout()
        layer_controls = QHBoxLayout()
        layer_controls.addWidget(QLabel("Anzahl der Schichten"))
        self._layer_count_input = QSpinBox()
        self._layer_count_input.setMinimum(1)
        self._layer_count_input.setMaximum(12)
        self._layer_count_input.valueChanged.connect(self._on_layer_count_changed)
        layer_controls.addWidget(self._layer_count_input)
        layer_controls.addStretch()
        layers_layout.addLayout(layer_controls)

        grid = QGridLayout()
        grid.addWidget(QLabel("Schicht"), 0, 0)
        grid.addWidget(QLabel("Dicke [mm]"), 0, 1)
        grid.addWidget(QLabel("Materialfamilie"), 0, 2)
        grid.addWidget(QLabel("Variante"), 0, 3)
        self._layers_layout = grid
        layers_layout.addLayout(grid)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        action_layout = QHBoxLayout()
        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._on_calculate)
        action_layout.addStretch()
        action_layout.addWidget(calculate_button)
        layout.addLayout(action_layout)

        result_group = QGroupBox("Ergebnisse")
        result_layout = QVBoxLayout()
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
        layout = QVBoxLayout()

        measure_group = QGroupBox("Maßvorgabe")
        measure_layout = QHBoxLayout()
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
        dims_layout = QGridLayout()
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
        layers_layout = QVBoxLayout()
        layer_controls = QHBoxLayout()
        add_button = QPushButton("+ Schicht")
        add_button.clicked.connect(self._on_build_add_layer)
        import_button = QPushButton("Aus Berechnung übernehmen")
        import_button.clicked.connect(self._on_build_import_layers)
        layer_controls.addWidget(add_button)
        layer_controls.addWidget(import_button)
        layer_controls.addStretch()
        layers_layout.addLayout(layer_controls)

        grid = QGridLayout()
        grid.addWidget(QLabel("#"), 0, 0)
        grid.addWidget(QLabel("Dicke [mm]"), 0, 1)
        grid.addWidget(QLabel("Materialfamilie"), 0, 2)
        grid.addWidget(QLabel("Aktionen"), 0, 3)
        self._build_layers_layout = grid
        layers_layout.addLayout(grid)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        action_layout = QHBoxLayout()
        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._on_build_calculate)
        reset_button = QPushButton("Felder leeren")
        reset_button.clicked.connect(self._on_build_reset)
        action_layout.addStretch()
        action_layout.addWidget(calculate_button)
        action_layout.addWidget(reset_button)
        layout.addLayout(action_layout)

        results_group = QGroupBox("Ergebnis")
        results_layout = QVBoxLayout()
        self._build_status_label = QLabel()
        self._build_status_label.setWordWrap(True)
        results_layout.addWidget(self._build_status_label)

        summary_layout = QHBoxLayout()
        self._build_given_group = QGroupBox("Gegebene Maße")
        given_layout = QGridLayout()
        self._build_given_labels = self._build_dimension_summary(given_layout)
        self._build_given_group.setLayout(given_layout)
        summary_layout.addWidget(self._build_given_group)

        self._build_calc_group = QGroupBox("Berechnete Maße")
        calc_layout = QGridLayout()
        self._build_calc_labels = self._build_dimension_summary(calc_layout)
        self._build_calc_group.setLayout(calc_layout)
        summary_layout.addWidget(self._build_calc_group)

        layer_info_group = QGroupBox("Schichten")
        layer_info_layout = QVBoxLayout()
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

    @staticmethod
    def _build_placeholder_tab() -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()
        placeholder = QLabel("Der Zuschnitt-Tab wird in einem späteren Schritt ergänzt.")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
        layout.addStretch()
        tab.setLayout(layout)
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
        except Exception as exc:
            self._build_results = {
                "status": "error",
                "message": str(exc),
                "data": {},
            }
        self.refresh_view()

    def _on_build_reset(self) -> None:
        self._build_inputs["measure_type"] = "outer"
        self._build_inputs["dimensions"] = {"L": "", "B": "", "H": ""}
        self._build_inputs["layers"] = [{"thickness": "", "family": ""}]
        self._build_results = {"status": "idle", "message": "", "data": {}}
        self._build_ui["selected_row"] = -1
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
