"""Qt-Plugin für Isolierungsberechnungen (PySide6-only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
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
from Isolierung.services.tab1_berechnung import perform_calculation, validate_inputs


@dataclass
class _LayerWidgets:
    label: QLabel
    thickness_input: QLineEdit
    family_combo: QComboBox
    variant_combo: QComboBox
    variant_lookup: dict[str, tuple[str, float]]


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

        self._materials = []
        self._material_names: list[str] = []
        self._material_change_handler = self._on_materials_changed
        self._listener_registered = False
        self._missing_materials_warning: str | None = None

        self._state: dict[str, Any] = {
            "inputs": {
                "T_left": "",
                "T_inf": "",
                "h": "",
                "layers": [{"thickness": "", "family": "", "variant": ""}],
            },
            "results": {
                "status": "idle",
                "message": "",
                "data": {},
            },
            "ui": {"active_tab": 0, "layers": []},
        }

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
        state = {
            "inputs": {
                "T_left": self._state["inputs"].get("T_left", ""),
                "T_inf": self._state["inputs"].get("T_inf", ""),
                "h": self._state["inputs"].get("h", ""),
                "layers": [dict(layer) for layer in self._state["inputs"].get("layers", [])],
            },
            "results": dict(self._state["results"]),
            "ui": dict(self._state["ui"]),
        }
        return self.validate_state(state)

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
            self._state["inputs"]["T_left"] = self._coerce_str(inputs.get("T_left", ""))
            self._state["inputs"]["T_inf"] = self._coerce_str(inputs.get("T_inf", ""))
            self._state["inputs"]["h"] = self._coerce_str(inputs.get("h", ""))
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
                    self._state["inputs"]["layers"] = normalized_layers

        if isinstance(results, dict):
            self._state["results"] = {
                "status": self._coerce_str(results.get("status", "idle")),
                "message": self._coerce_str(results.get("message", "")),
                "data": results.get("data", {}),
            }

        if isinstance(ui_state, dict):
            active_tab = ui_state.get("active_tab")
            if isinstance(active_tab, int):
                self._state["ui"]["active_tab"] = active_tab
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
                self._state["ui"]["layers"] = normalized_ui_layers

    def refresh_view(self) -> None:
        self._set_input_text(self._T_left_input, self._state["inputs"].get("T_left", ""))
        self._set_input_text(self._T_inf_input, self._state["inputs"].get("T_inf", ""))
        self._set_input_text(self._h_input, self._state["inputs"].get("h", ""))

        layers = self._state["inputs"].get("layers", [])
        if not isinstance(layers, list) or not layers:
            layers = [{"thickness": "", "family": "", "variant": ""}]
            self._state["inputs"]["layers"] = layers
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

        if self._tab_widget is not None:
            self._tab_widget.setCurrentIndex(self._state["ui"].get("active_tab", 0))

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
            layers = self._state["inputs"].get("layers", [])
            if isinstance(layers, list) and index < len(layers):
                selected_variant = self._coerce_str(layers[index].get("variant", ""))
            variant_found = self._populate_variant_combo(
                widgets, current_family, selected_variant
            )
            if not variant_found and isinstance(layers, list) and index < len(layers):
                layers[index]["variant"] = ""
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
        layers = self._state["inputs"].get("layers", [])
        if not isinstance(layers, list):
            layers = []
        if value > len(layers):
            for _ in range(value - len(layers)):
                layers.append({"thickness": "", "family": "", "variant": ""})
        elif value < len(layers):
            layers = layers[:value]
        if not layers:
            layers = [{"thickness": "", "family": "", "variant": ""}]
        self._state["inputs"]["layers"] = layers
        self.refresh_view()

    def _on_family_changed(self, index: int, text: str) -> None:
        if index >= len(self._state["inputs"].get("layers", [])):
            return
        family = "" if text == self._FAMILY_PLACEHOLDER else text
        self._state["inputs"]["layers"][index]["family"] = family
        self._state["inputs"]["layers"][index]["variant"] = ""
        self._ensure_ui_layer_state(index)
        self._state["ui"]["layers"][index]["family_index"] = self._layer_widgets[index].family_combo.currentIndex()
        self._state["ui"]["layers"][index]["variant_index"] = 0
        if index < len(self._layer_widgets):
            self._populate_variant_combo(self._layer_widgets[index], family, "")

    def _on_variant_changed(self, index: int) -> None:
        if index >= len(self._state["inputs"].get("layers", [])):
            return
        widgets = self._layer_widgets[index]
        display = widgets.variant_combo.currentText()
        if display == self._VARIANT_PLACEHOLDER:
            self._state["inputs"]["layers"][index]["variant"] = ""
            self._ensure_ui_layer_state(index)
            self._state["ui"]["layers"][index]["variant_index"] = widgets.variant_combo.currentIndex()
            return
        variant_name, thickness = widgets.variant_lookup.get(display, ("", 0.0))
        self._state["inputs"]["layers"][index]["variant"] = variant_name
        self._ensure_ui_layer_state(index)
        self._state["ui"]["layers"][index]["variant_index"] = widgets.variant_combo.currentIndex()
        if variant_name and not widgets.thickness_input.text():
            widgets.thickness_input.setText(self._format_number(thickness))

    def _on_calculate(self) -> None:
        self._sync_internal_state_from_widgets()
        try:
            parsed = self._parse_inputs()
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
            self._state["results"] = {
                "status": "ok",
                "message": "",
                "data": result,
            }
        except Exception as exc:
            self._state["results"] = {
                "status": "error",
                "message": str(exc),
                "data": {},
            }
        self.refresh_view()

    def _parse_inputs(self) -> dict[str, Any]:
        T_left = self._parse_float(self._state["inputs"].get("T_left", ""))
        T_inf = self._parse_float(self._state["inputs"].get("T_inf", ""))
        h = self._parse_float(self._state["inputs"].get("h", ""))
        if T_left is None or T_inf is None or h is None:
            raise ValueError("Bitte gültige Zahlen für T_left, T_inf und h eingeben.")

        layers = self._state["inputs"].get("layers", [])
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

    def _sync_internal_state_from_widgets(self) -> None:
        if self._T_left_input is not None:
            self._state["inputs"]["T_left"] = self._T_left_input.text()
        if self._T_inf_input is not None:
            self._state["inputs"]["T_inf"] = self._T_inf_input.text()
        if self._h_input is not None:
            self._state["inputs"]["h"] = self._h_input.text()

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
            self._state["inputs"]["layers"] = layers
            self._state["ui"]["layers"] = ui_layers

    def _format_result_text(self) -> str:
        status = self._state["results"].get("status")
        if status != "ok":
            message = self._coerce_str(self._state["results"].get("message", ""))
            base = f"Status: Fehler\n{message}" if message else "Status: Bereit"
            if self._missing_materials_warning:
                return f"{base}\n{self._missing_materials_warning}"
            return base
        result = self._state["results"].get("data", {})
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

    def _on_tab_changed(self, index: int) -> None:
        self._state["ui"]["active_tab"] = index

    def _on_text_input_changed(self, text: str) -> None:
        if self._T_left_input is not None:
            self._state["inputs"]["T_left"] = self._T_left_input.text()
        if self._T_inf_input is not None:
            self._state["inputs"]["T_inf"] = self._T_inf_input.text()
        if self._h_input is not None:
            self._state["inputs"]["h"] = self._h_input.text()

    def _on_thickness_changed(self, index: int, text: str) -> None:
        if index >= len(self._state["inputs"].get("layers", [])):
            return
        self._state["inputs"]["layers"][index]["thickness"] = text

    def _ensure_ui_layer_state(self, index: int) -> None:
        ui_layers = self._state["ui"].get("layers", [])
        if not isinstance(ui_layers, list):
            ui_layers = []
        while len(ui_layers) <= index:
            ui_layers.append({"family_index": 0, "variant_index": 0})
        self._state["ui"]["layers"] = ui_layers

    def _on_widget_destroyed(self, _obj: object | None = None) -> None:
        if self._listener_registered:
            unregister_material_change_listener(self._material_change_handler)
            self._listener_registered = False


__all__ = ["IsolierungQtPlugin"]
