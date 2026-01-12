"""Qt-Plugin für Stoffeigenschaften Luft (PySide6-only)."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
)

from app.ui_qt.plugins.base import QtAppContext, QtPlugin
from app.ui_qt.ui_helpers import (
    apply_form_layout_defaults,
    create_button_row,
    create_page_layout,
    make_grid,
)
from SoffeigenschaftenLuft.core.flow_calculations import compute_flow_properties
from SoffeigenschaftenLuft.core.heater_calculations import compute_heater_power
from SoffeigenschaftenLuft.core.state_calculations import calculate_state


class StoffeigenschaftenLuftQtPlugin(QtPlugin):
    """Qt-Plugin für Stoffeigenschaften Luft."""

    _DEFAULT_VERSION = "v2.0"

    _TAB1_FIELDS = [
        ("Normkubikmeter (m³/h):", "", 3, 2),
        ("Temperatur 1 (°C):", "20", 4, 0),
        ("Volumenstrom 1 (m³/h):", "", 5, 0),
        ("Druck 1 (Pa):", "101325", 6, 0),
        ("Dichte 1 (kg/m³):", "1.20412", 7, 0),
        ("Temperatur 2 (°C):", "", 4, 2),
        ("Volumenstrom 2 (m³/h):", "", 5, 2),
        ("Druck 2 (Pa):", "", 6, 2),
        ("Dichte 2 (kg/m³):", "", 7, 2),
        ("Dynamische Viskosität 1 (Pa·s):", "", 8, 0),
        ("Dynamische Viskosität 2 (Pa·s):", "", 8, 2),
        ("Schallgeschwindigkeit 1 (m/s):", "", 9, 0),
        ("Schallgeschwindigkeit 2 (m/s):", "", 9, 2),
        ("Spezifische Wärmekapazität Cp 1 (J/kg*K):", "", 10, 0),
        ("Spezifische Wärmekapazität Cp 2 (J/kg*K):", "", 10, 2),
        ("Massenstrom 1 (kg/s):", "", 11, 0),
        ("Massenstrom 2 (kg/s):", "", 11, 2),
        ("Wärmeleistung (kW):", "", 12, 0),
    ]

    _TAB1_OUTPUT_FIELDS = {
        "Volumenstrom 2 (m³/h):",
        "Druck 2 (Pa):",
        "Dichte 2 (kg/m³):",
        "Dynamische Viskosität 1 (Pa·s):",
        "Dynamische Viskosität 2 (Pa·s):",
        "Schallgeschwindigkeit 1 (m/s):",
        "Schallgeschwindigkeit 2 (m/s):",
        "Spezifische Wärmekapazität Cp 1 (J/kg*K):",
        "Spezifische Wärmekapazität Cp 2 (J/kg*K):",
        "Massenstrom 1 (kg/s):",
        "Massenstrom 2 (kg/s):",
    }

    _TAB2_RESULT_FIELDS = {
        "Strömungsgeschwindigkeit (m/s):",
        "Reynolds-Zahl:",
        "Strömungsart:",
    }

    _TAB3_FIELDS = [
        ("Elektrische Leistung (kW):", ""),
        ("Wärmeleistung (kW):", ""),
        ("Effizienz (%):", "90"),
    ]

    def __init__(self) -> None:
        self._identifier = "stoffeigenschaften_luft"
        self.widget: QWidget | None = None
        self._tab_widget: QTabWidget | None = None

        self._tab1_entries: dict[str, QLineEdit] = {}
        self._tab1_zustand_combo: QComboBox | None = None
        self._tab1_normkubik_check: QCheckBox | None = None
        self._tab1_heatrix_check: QCheckBox | None = None
        self._tab1_normkubikmenge_check: QCheckBox | None = None
        self._tab1_heat_priority_check: QCheckBox | None = None
        self._tab1_normkubik_label: QLabel | None = None
        self._tab1_cp1_label: QLabel | None = None
        self._tab1_cp2_label: QLabel | None = None

        self._tab2_entries: dict[str, QLineEdit] = {}
        self._tab2_shape_combo: QComboBox | None = None
        self._tab2_flow_unit_combo: QComboBox | None = None
        self._tab2_normkubik_check: QCheckBox | None = None
        self._tab2_diameter_label: QLabel | None = None
        self._tab2_diameter_entry: QLineEdit | None = None
        self._tab2_side_a_label: QLabel | None = None
        self._tab2_side_a_entry: QLineEdit | None = None
        self._tab2_side_b_label: QLabel | None = None
        self._tab2_side_b_entry: QLineEdit | None = None

        self._tab3_entries: dict[str, QLineEdit] = {}
        self._tab3_use_tab1_power_check: QCheckBox | None = None

        self._tab1_inputs: dict[str, Any] = {
            "zustand": "Isobar",
            "normkubik": False,
            "heatrix": False,
            "normkubikmenge": False,
            "heat_priority": False,
            "entries": {},
        }
        self._tab2_inputs: dict[str, Any] = {
            "shape": "Rund",
            "flow_unit": "m³/h",
            "normkubik": False,
            "entries": {},
        }
        self._tab3_inputs: dict[str, Any] = {
            "use_tab1_power": False,
            "entries": {},
        }
        self._tab1_results: dict[str, Any] = {"status": "idle", "message": "", "values": {}}
        self._tab2_results: dict[str, Any] = {"status": "idle", "message": "", "values": {}}
        self._tab3_results: dict[str, Any] = {"status": "idle", "message": "", "values": {}}
        self._ui_state: dict[str, Any] = {"active_tab": 0, "tab1": {}, "tab2": {}, "tab3": {}}

    @property
    def name(self) -> str:
        return "Stoffeigenschaften Luft"

    @property
    def identifier(self) -> str:
        return self._identifier

    def attach(self, context: QtAppContext) -> None:
        container = QWidget()
        version = QLabel(self._DEFAULT_VERSION)
        version_font = QFont()
        version_font.setPointSize(10)
        version.setFont(version_font)
        layout = create_page_layout(
            container,
            "Stoffeigenschaften Luft",
            actions=version,
        )

        tab_widget = QTabWidget()
        self._tab_widget = tab_widget
        tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(tab_widget)

        tab_widget.addTab(self._build_tab1(), "Zustandsgrößen")
        tab_widget.addTab(self._build_tab2(), "Geschwindigkeitsberechnung & Reynolds-Zahl")
        tab_widget.addTab(self._build_tab3(), "Heizer Leistung")

        footer = QLabel("© 2025 Heatrix GmbH")
        footer_font = QFont()
        footer_font.setPointSize(9)
        footer.setFont(footer_font)
        layout.addWidget(footer)

        self.widget = container

        self.refresh_view()

    def export_state(self) -> dict[str, Any]:
        self._sync_internal_state_from_widgets()
        inputs = {
            "tab1": {
                "zustand": self._tab1_inputs.get("zustand", "Isobar"),
                "normkubik": self._tab1_inputs.get("normkubik", False),
                "heatrix": self._tab1_inputs.get("heatrix", False),
                "normkubikmenge": self._tab1_inputs.get("normkubikmenge", False),
                "heat_priority": self._tab1_inputs.get("heat_priority", False),
                "entries": dict(self._tab1_inputs.get("entries", {})),
            },
            "tab2": {
                "shape": self._tab2_inputs.get("shape", "Rund"),
                "flow_unit": self._tab2_inputs.get("flow_unit", "m³/h"),
                "normkubik": self._tab2_inputs.get("normkubik", False),
                "entries": dict(self._tab2_inputs.get("entries", {})),
            },
            "tab3": {
                "use_tab1_power": self._tab3_inputs.get("use_tab1_power", False),
                "entries": dict(self._tab3_inputs.get("entries", {})),
            },
        }
        results = {
            "tab1": dict(self._tab1_results),
            "tab2": dict(self._tab2_results),
            "tab3": dict(self._tab3_results),
        }
        return self.validate_state({"inputs": inputs, "results": results, "ui": dict(self._ui_state)})

    def import_state(self, state: dict[str, Any]) -> None:
        normalized = self.validate_state(state)
        self.apply_state(normalized)
        self._apply_ui_state()
        self.refresh_view()

    def apply_state(self, state: dict[str, Any]) -> None:
        inputs = state.get("inputs", {})
        results = state.get("results", {})
        ui_state = state.get("ui", {})

        if isinstance(inputs, dict):
            self._tab1_inputs = self._coerce_tab_inputs(inputs.get("tab1"), self._tab1_inputs)
            self._tab2_inputs = self._coerce_tab_inputs(inputs.get("tab2"), self._tab2_inputs)
            self._tab3_inputs = self._coerce_tab_inputs(inputs.get("tab3"), self._tab3_inputs)
        if isinstance(results, dict):
            self._tab1_results = self._coerce_results(results.get("tab1"), self._tab1_results)
            self._tab2_results = self._coerce_results(results.get("tab2"), self._tab2_results)
            self._tab3_results = self._coerce_results(results.get("tab3"), self._tab3_results)
        if isinstance(ui_state, dict):
            self._ui_state = ui_state

    def _sync_internal_state_from_widgets(self) -> None:
        self._store_tab1_inputs()
        self._store_tab2_inputs()
        self._store_tab3_inputs()
        self._ui_state["active_tab"] = self._get_active_tab_index()
        self._ui_state["tab1"] = {
            "entry_states": self._collect_entry_states(self._tab1_entries),
        }
        self._ui_state["tab2"] = {
            "entry_states": self._collect_entry_states(self._tab2_entries),
        }
        self._ui_state["tab3"] = {
            "entry_states": self._collect_entry_states(self._tab3_entries),
        }

    def refresh_view(self) -> None:
        self._sync_tab1_view()
        self._sync_tab2_view()
        self._sync_tab3_view()
        if self._tab_widget is not None:
            self._tab_widget.setCurrentIndex(self._ui_state.get("active_tab", 0))

    def _build_tab1(self) -> QWidget:
        tab = QWidget()
        layout = create_page_layout(tab, "Zustandsgrößen")
        grid = make_grid()
        layout.addLayout(grid)

        zustand_combo = QComboBox()
        zustand_combo.addItems(["Isobar", "Isochor"])
        zustand_combo.currentTextChanged.connect(self._on_tab1_zustand_changed)
        self._tab1_zustand_combo = zustand_combo
        grid.addWidget(zustand_combo, 0, 1, 1, 2)

        normkubik_check = QCheckBox("Normbedingungen DIN 1343")
        normkubik_check.toggled.connect(self._on_tab1_toggle_din)
        grid.addWidget(normkubik_check, 1, 0, 1, 2)
        self._tab1_normkubik_check = normkubik_check

        heatrix_check = QCheckBox("Heatrix Normalbedingungen")
        heatrix_check.toggled.connect(self._on_tab1_toggle_heatrix)
        grid.addWidget(heatrix_check, 2, 0, 1, 2)
        self._tab1_heatrix_check = heatrix_check

        normkubikmenge_check = QCheckBox("Normkubikmeter verwenden")
        normkubikmenge_check.toggled.connect(self._on_tab1_toggle_normkubikmenge)
        grid.addWidget(normkubikmenge_check, 1, 2, 1, 2)
        self._tab1_normkubikmenge_check = normkubikmenge_check

        for text, default, row, col in self._TAB1_FIELDS:
            label = QLabel(text)
            grid.addWidget(label, row, col)
            entry = QLineEdit()
            entry.setText(default)
            grid.addWidget(entry, row, col + 1)
            self._tab1_entries[text] = entry
            entry.textChanged.connect(
                lambda value, key=text: self._update_entry_value("tab1", key, value)
            )
            if text == "Normkubikmeter (m³/h):":
                entry.setEnabled(False)
                self._tab1_normkubik_label = label
            if text == "Spezifische Wärmekapazität Cp 1 (J/kg*K):":
                self._tab1_cp1_label = label
            if text == "Spezifische Wärmekapazität Cp 2 (J/kg*K):":
                self._tab1_cp2_label = label
            if text in self._TAB1_OUTPUT_FIELDS:
                entry.setReadOnly(True)
            if text in {"Druck 2 (Pa):", "Dichte 2 (kg/m³):", "Volumenstrom 2 (m³/h):"}:
                entry.setReadOnly(True)

            if text == "Wärmeleistung (kW):":
                heat_priority_check = QCheckBox("Wärmeleistung priorisieren")
                heat_priority_check.toggled.connect(self._on_tab1_toggle_heat_priority)
                grid.addWidget(heat_priority_check, row, col + 2)
                self._tab1_heat_priority_check = heat_priority_check

        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._calculate_tab1)
        grid.addLayout(create_button_row([calculate_button]), 13, 0, 1, 4)

        apply_form_layout_defaults(grid, label_columns=(0, 2), field_columns=(1, 3))
        return tab

    def _build_tab2(self) -> QWidget:
        tab = QWidget()
        layout = create_page_layout(tab, "Geschwindigkeitsberechnung")
        grid = make_grid()
        layout.addLayout(grid)

        shape_label = QLabel("Querschnittsform:")
        grid.addWidget(shape_label, 0, 0)
        shape_combo = QComboBox()
        shape_combo.addItems(["Rund", "Rechteckig"])
        shape_combo.currentTextChanged.connect(self._on_tab2_shape_changed)
        grid.addWidget(shape_combo, 0, 1, 1, 2)
        self._tab2_shape_combo = shape_combo

        diameter_label = QLabel("Durchmesser (mm):")
        diameter_entry = QLineEdit()
        grid.addWidget(diameter_label, 1, 0)
        grid.addWidget(diameter_entry, 1, 1)
        self._tab2_diameter_label = diameter_label
        self._tab2_diameter_entry = diameter_entry
        self._tab2_entries["Durchmesser (mm):"] = diameter_entry
        diameter_entry.textChanged.connect(
            lambda value, key="Durchmesser (mm):": self._update_entry_value("tab2", key, value)
        )

        side_a_label = QLabel("Seite a (mm):")
        side_a_entry = QLineEdit()
        side_b_label = QLabel("Seite b (mm):")
        side_b_entry = QLineEdit()
        grid.addWidget(side_a_label, 1, 0)
        grid.addWidget(side_a_entry, 1, 1)
        grid.addWidget(side_b_label, 2, 0)
        grid.addWidget(side_b_entry, 2, 1)
        self._tab2_side_a_label = side_a_label
        self._tab2_side_a_entry = side_a_entry
        self._tab2_side_b_label = side_b_label
        self._tab2_side_b_entry = side_b_entry
        self._tab2_entries["Seite a (mm):"] = side_a_entry
        self._tab2_entries["Seite b (mm):"] = side_b_entry
        side_a_entry.textChanged.connect(
            lambda value, key="Seite a (mm):": self._update_entry_value("tab2", key, value)
        )
        side_b_entry.textChanged.connect(
            lambda value, key="Seite b (mm):": self._update_entry_value("tab2", key, value)
        )

        grid.addWidget(QLabel("Volumenstrom:"), 3, 0)
        entry_flow = QLineEdit()
        grid.addWidget(entry_flow, 3, 1)
        self._tab2_entries["Volumenstrom"] = entry_flow
        entry_flow.textChanged.connect(
            lambda value, key="Volumenstrom": self._update_entry_value("tab2", key, value)
        )

        flow_unit_combo = QComboBox()
        flow_unit_combo.addItems(["m³/h", "m³/s"])
        flow_unit_combo.currentTextChanged.connect(self._on_tab2_flow_unit_changed)
        grid.addWidget(flow_unit_combo, 3, 2)
        self._tab2_flow_unit_combo = flow_unit_combo

        for i, label in enumerate(["Temperatur (°C):", "Dichte (kg/m³):"]):
            grid.addWidget(QLabel(label), 4 + i, 0)
            entry = QLineEdit()
            grid.addWidget(entry, 4 + i, 1)
            self._tab2_entries[label] = entry
            entry.textChanged.connect(
                lambda value, key=label: self._update_entry_value("tab2", key, value)
            )

        grid.addWidget(QLabel("Strömungsgeschwindigkeit (m/s):"), 6, 0)
        entry_velocity = QLineEdit()
        entry_velocity.setReadOnly(True)
        grid.addWidget(entry_velocity, 6, 1)
        self._tab2_entries["Strömungsgeschwindigkeit (m/s):"] = entry_velocity
        entry_velocity.textChanged.connect(
            lambda value, key="Strömungsgeschwindigkeit (m/s):": self._update_entry_value(
                "tab2", key, value
            )
        )

        grid.addWidget(QLabel("Reynolds-Zahl:"), 7, 0)
        entry_reynolds = QLineEdit()
        entry_reynolds.setReadOnly(True)
        grid.addWidget(entry_reynolds, 7, 1)
        self._tab2_entries["Reynolds-Zahl:"] = entry_reynolds
        entry_reynolds.textChanged.connect(
            lambda value, key="Reynolds-Zahl:": self._update_entry_value("tab2", key, value)
        )

        grid.addWidget(QLabel("Strömungsart:"), 7, 2)
        entry_flowtype = QLineEdit()
        entry_flowtype.setReadOnly(True)
        grid.addWidget(entry_flowtype, 7, 3)
        self._tab2_entries["Strömungsart:"] = entry_flowtype
        entry_flowtype.textChanged.connect(
            lambda value, key="Strömungsart:": self._update_entry_value("tab2", key, value)
        )

        norm_check = QCheckBox("Heatrix Normalbedingungen")
        norm_check.toggled.connect(self._on_tab2_toggle_norm)
        grid.addWidget(norm_check, 8, 0, 1, 2)
        self._tab2_normkubik_check = norm_check

        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._calculate_tab2)
        grid.addLayout(create_button_row([calculate_button]), 10, 1, 1, 2)

        apply_form_layout_defaults(grid, label_columns=(0, 2), field_columns=(1, 3))
        return tab

    def _build_tab3(self) -> QWidget:
        tab = QWidget()
        layout = create_page_layout(tab, "Heizer Leistung")
        grid = make_grid()
        layout.addLayout(grid)

        for i, (label_text, default) in enumerate(self._TAB3_FIELDS):
            label = QLabel(label_text)
            grid.addWidget(label, i, 0)
            entry = QLineEdit()
            entry.setText(default)
            grid.addWidget(entry, i, 1)
            self._tab3_entries[label_text] = entry
            entry.textChanged.connect(
                lambda value, key=label_text: self._update_entry_value("tab3", key, value)
            )

        calculate_button = QPushButton("Berechnen")
        calculate_button.clicked.connect(self._calculate_tab3)
        grid.addLayout(create_button_row([calculate_button]), 4, 1, 1, 2)

        use_tab1_check = QCheckBox("Leistung übernehmen")
        use_tab1_check.toggled.connect(self._on_tab3_toggle_use_tab1)
        grid.addWidget(use_tab1_check, 3, 0, 1, 2)
        self._tab3_use_tab1_power_check = use_tab1_check

        efficiency_entry = self._tab3_entries.get("Effizienz (%):")
        if efficiency_entry is not None:
            efficiency_entry.textChanged.connect(self._on_tab3_efficiency_changed)

        apply_form_layout_defaults(grid)
        return tab

    def _sync_tab1_view(self) -> None:
        if self._tab1_zustand_combo is None:
            return
        with QSignalBlocker(self._tab1_zustand_combo):
            self._tab1_zustand_combo.setCurrentText(self._tab1_inputs.get("zustand", "Isobar"))

        if self._tab1_normkubik_check is not None:
            with QSignalBlocker(self._tab1_normkubik_check):
                self._tab1_normkubik_check.setChecked(bool(self._tab1_inputs.get("normkubik", False)))
        if self._tab1_heatrix_check is not None:
            with QSignalBlocker(self._tab1_heatrix_check):
                self._tab1_heatrix_check.setChecked(bool(self._tab1_inputs.get("heatrix", False)))
        if self._tab1_normkubikmenge_check is not None:
            with QSignalBlocker(self._tab1_normkubikmenge_check):
                self._tab1_normkubikmenge_check.setChecked(
                    bool(self._tab1_inputs.get("normkubikmenge", False))
                )
        if self._tab1_heat_priority_check is not None:
            with QSignalBlocker(self._tab1_heat_priority_check):
                self._tab1_heat_priority_check.setChecked(
                    bool(self._tab1_inputs.get("heat_priority", False))
                )

        self._update_tab1_labels()
        self._apply_tab1_toggle_states()
        self._apply_entry_states(self._tab1_entries, self._ui_state.get("tab1", {}).get("entry_states"))

        self._apply_entry_values(self._tab1_entries, self._tab1_inputs.get("entries", {}))
        self._apply_tab1_results()

    def _sync_tab2_view(self) -> None:
        if self._tab2_shape_combo is None or self._tab2_flow_unit_combo is None:
            return
        with QSignalBlocker(self._tab2_shape_combo):
            self._tab2_shape_combo.setCurrentText(self._tab2_inputs.get("shape", "Rund"))
        with QSignalBlocker(self._tab2_flow_unit_combo):
            self._tab2_flow_unit_combo.setCurrentText(self._tab2_inputs.get("flow_unit", "m³/h"))
        if self._tab2_normkubik_check is not None:
            with QSignalBlocker(self._tab2_normkubik_check):
                self._tab2_normkubik_check.setChecked(bool(self._tab2_inputs.get("normkubik", False)))

        self._update_tab2_fields()
        self._apply_tab2_norm_state()
        self._apply_entry_states(self._tab2_entries, self._ui_state.get("tab2", {}).get("entry_states"))

        self._apply_entry_values(self._tab2_entries, self._tab2_inputs.get("entries", {}))
        self._apply_tab2_results()

    def _sync_tab3_view(self) -> None:
        if self._tab3_use_tab1_power_check is not None:
            with QSignalBlocker(self._tab3_use_tab1_power_check):
                self._tab3_use_tab1_power_check.setChecked(
                    bool(self._tab3_inputs.get("use_tab1_power", False))
                )
        self._apply_tab3_use_tab1_state()
        self._apply_entry_states(self._tab3_entries, self._ui_state.get("tab3", {}).get("entry_states"))
        self._apply_entry_values(self._tab3_entries, self._tab3_inputs.get("entries", {}))
        self._apply_tab3_results()

    def _apply_ui_state(self) -> None:
        if isinstance(self._ui_state.get("active_tab"), int):
            self._ui_state["active_tab"] = int(self._ui_state["active_tab"])

    def _update_tab1_labels(self) -> None:
        if self._tab1_zustand_combo is None:
            return
        zustand = self._tab1_zustand_combo.currentText()
        if zustand == "Isochor":
            if self._tab1_cp1_label is not None:
                self._tab1_cp1_label.setText("Spezifische Wärmekapazität Cv 1 (J/kg*K):")
            if self._tab1_cp2_label is not None:
                self._tab1_cp2_label.setText("Spezifische Wärmekapazität Cv 2 (J/kg*K):")
        else:
            if self._tab1_cp1_label is not None:
                self._tab1_cp1_label.setText("Spezifische Wärmekapazität Cp 1 (J/kg*K):")
            if self._tab1_cp2_label is not None:
                self._tab1_cp2_label.setText("Spezifische Wärmekapazität Cp 2 (J/kg*K):")
        self._update_normkubik_label()

    def _update_normkubik_label(self) -> None:
        if self._tab1_normkubik_label is None:
            return
        if self._tab1_normkubik_check is not None and self._tab1_normkubik_check.isChecked():
            self._tab1_normkubik_label.setText("Normkubikmeter (Nm³/h):")
        elif self._tab1_heatrix_check is not None and self._tab1_heatrix_check.isChecked():
            self._tab1_normkubik_label.setText("Normkubikmeter (HNm³/h):")
        else:
            self._tab1_normkubik_label.setText("Normkubikmeter (m³/h):")

    def _apply_norm_values(self, values: dict[str, str], freeze: bool = True) -> None:
        for key, value in values.items():
            entry = self._tab1_entries.get(key)
            if entry is None:
                continue
            self._write_entry_preserve_state(entry, value)
            if freeze:
                entry.setReadOnly(True)

    def _apply_tab1_toggle_states(self) -> None:
        normkubik = self._tab1_normkubik_check.isChecked() if self._tab1_normkubik_check else False
        heatrix = self._tab1_heatrix_check.isChecked() if self._tab1_heatrix_check else False
        normkubikmenge = (
            self._tab1_normkubikmenge_check.isChecked() if self._tab1_normkubikmenge_check else False
        )
        if normkubik:
            self._apply_norm_values(
                {"Druck 1 (Pa):": "101325", "Dichte 1 (kg/m³):": "1.29228", "Temperatur 1 (°C):": "0"},
                freeze=not normkubikmenge,
            )
        elif heatrix:
            self._apply_norm_values(
                {"Druck 1 (Pa):": "101325", "Dichte 1 (kg/m³):": "1.20412", "Temperatur 1 (°C):": "20"},
                freeze=not normkubikmenge,
            )

        if normkubikmenge:
            self._set_entry_state(self._tab1_entries.get("Normkubikmeter (m³/h):"), "normal")
            self._write_entry_preserve_state(self._tab1_entries.get("Volumenstrom 1 (m³/h):"), "")
            self._set_entry_state(self._tab1_entries.get("Volumenstrom 1 (m³/h):"), "readonly")
            for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):"]:
                self._write_entry_preserve_state(self._tab1_entries.get(key), "")
                self._set_entry_state(self._tab1_entries.get(key), "readonly")
            if normkubik or heatrix:
                self._set_entry_state(self._tab1_entries.get("Temperatur 1 (°C):"), "normal")
            else:
                self._set_entry_state(self._tab1_entries.get("Temperatur 1 (°C):"), "readonly")
        else:
            self._write_entry_preserve_state(self._tab1_entries.get("Normkubikmeter (m³/h):"), "")
            self._set_entry_state(self._tab1_entries.get("Normkubikmeter (m³/h):"), "disabled")
            self._set_entry_state(self._tab1_entries.get("Volumenstrom 1 (m³/h):"), "normal")
            for key in ["Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"]:
                self._set_entry_state(self._tab1_entries.get(key), "normal")
            if normkubik:
                self._apply_norm_values(
                    {"Druck 1 (Pa):": "101325", "Dichte 1 (kg/m³):": "1.29228", "Temperatur 1 (°C):": "0"},
                )
            elif heatrix:
                self._apply_norm_values(
                    {"Druck 1 (Pa):": "101325", "Dichte 1 (kg/m³):": "1.20412", "Temperatur 1 (°C):": "20"},
                )

    def _update_tab2_fields(self) -> None:
        shape = self._tab2_shape_combo.currentText() if self._tab2_shape_combo else "Rund"
        is_round = shape == "Rund"
        for widget in (self._tab2_diameter_label, self._tab2_diameter_entry):
            if widget is not None:
                widget.setVisible(is_round)
        for widget in (self._tab2_side_a_label, self._tab2_side_a_entry, self._tab2_side_b_label, self._tab2_side_b_entry):
            if widget is not None:
                widget.setVisible(not is_round)

    def _apply_tab2_norm_state(self) -> None:
        if self._tab2_normkubik_check is None:
            return
        temp_entry = self._tab2_entries.get("Temperatur (°C):")
        density_entry = self._tab2_entries.get("Dichte (kg/m³):")
        if self._tab2_normkubik_check.isChecked():
            self._write_entry_preserve_state(temp_entry, "20")
            self._set_entry_state(temp_entry, "readonly")
            self._write_entry_preserve_state(density_entry, "1.20412")
            self._set_entry_state(density_entry, "readonly")
        else:
            self._set_entry_state(temp_entry, "normal")
            self._set_entry_state(density_entry, "normal")

    def _apply_tab3_use_tab1_state(self) -> None:
        if self._tab3_use_tab1_power_check is None:
            return
        if self._tab3_use_tab1_power_check.isChecked():
            thermal = self._get_tab1_thermal_power()
            if thermal is not None:
                self._write_entry_preserve_state(
                    self._tab3_entries.get("Wärmeleistung (kW):"), f"{thermal:.2f}"
                )
            self._set_entry_state(self._tab3_entries.get("Wärmeleistung (kW):"), "readonly")
        else:
            self._set_entry_state(self._tab3_entries.get("Wärmeleistung (kW):"), "normal")

    def _calculate_tab1(self) -> None:
        self._store_tab1_inputs()
        temperature_entry = self._tab1_entries.get("Temperatur 1 (°C):")
        T1_C = self._read_required_float(temperature_entry)
        if T1_C is None:
            self._set_tab1_error("Bitte gültige Zahlen angeben.")
            return

        T2_C = None
        Q_kW = None
        heat_priority = self._tab1_heat_priority_check.isChecked() if self._tab1_heat_priority_check else False
        T2_entry = self._tab1_entries.get("Temperatur 2 (°C):")
        Q_entry = self._tab1_entries.get("Wärmeleistung (kW):")

        if heat_priority:
            Q_kW = self._read_required_float(Q_entry)
            if Q_kW is None:
                self._set_tab1_error("Bitte gültige Zahlen angeben.")
                return
        else:
            T2_C = self._optional_float(T2_entry)
            if T2_C is None:
                Q_kW = self._optional_float(Q_entry)
                if Q_kW is None:
                    self._mark_error(T2_entry)
                    self._set_tab1_error("Bitte gültige Zahlen angeben.")
                    return

        normkubikmenge = self._tab1_normkubikmenge_check.isChecked() if self._tab1_normkubikmenge_check else False
        V1 = None
        V_norm = None
        if normkubikmenge:
            V_norm = self._read_required_float(self._tab1_entries.get("Normkubikmeter (m³/h):"))
            if V_norm is None:
                self._set_tab1_error("Bitte gültige Zahlen angeben.")
                return
        else:
            V1 = self._read_required_float(self._tab1_entries.get("Volumenstrom 1 (m³/h):"))
            if V1 is None:
                self._set_tab1_error("Bitte gültige Zahlen angeben.")
                return

        p1 = self._optional_float(self._tab1_entries.get("Druck 1 (Pa):"))
        rho1 = self._optional_float(self._tab1_entries.get("Dichte 1 (kg/m³):"))
        if not normkubikmenge and p1 is None and rho1 is None:
            self._mark_error(self._tab1_entries.get("Druck 1 (Pa):"))
            self._mark_error(self._tab1_entries.get("Dichte 1 (kg/m³):"))
            self._set_tab1_error("Bitte gültige Zahlen angeben.")
            return

        zustand = self._tab1_zustand_combo.currentText() if self._tab1_zustand_combo else "Isobar"
        normart = None
        if self._tab1_normkubik_check is not None and self._tab1_normkubik_check.isChecked():
            normart = "DIN"
        elif self._tab1_heatrix_check is not None and self._tab1_heatrix_check.isChecked():
            normart = "HEATRIX"

        try:
            result = calculate_state(p1, rho1, T1_C, T2_C, V1, V_norm, Q_kW, zustand, normart)
        except Exception:
            self._set_tab1_error("Berechnung fehlgeschlagen.")
            return

        values = {
            "Druck 1 (Pa):": result["p1"],
            "Dichte 1 (kg/m³):": result["rho1"],
            "Volumenstrom 1 (m³/h):": result["V1"],
            "Druck 2 (Pa):": result["p2"],
            "Dichte 2 (kg/m³):": result["rho2"],
            "Volumenstrom 2 (m³/h):": result["V2"],
            "Dynamische Viskosität 1 (Pa·s):": result["mu1"],
            "Dynamische Viskosität 2 (Pa·s):": result["mu2"],
            "Schallgeschwindigkeit 1 (m/s):": result["c1"],
            "Schallgeschwindigkeit 2 (m/s):": result["c2"],
            "Spezifische Wärmekapazität Cp 1 (J/kg*K):": result["cp1"]
            if zustand == "Isobar"
            else result["cv1"],
            "Spezifische Wärmekapazität Cp 2 (J/kg*K):": result["cp2"]
            if zustand == "Isobar"
            else result["cv2"],
            "Massenstrom 1 (kg/s):": result["m_dot1"],
            "Massenstrom 2 (kg/s):": result["m_dot2"],
        }

        for key, val in values.items():
            if val is None:
                continue
            if key == "Volumenstrom 1 (m³/h):" and not normkubikmenge:
                self._write_entry_preserve_state(self._tab1_entries.get(key), self._format_value(val))
            elif key in {"Druck 1 (Pa):", "Dichte 1 (kg/m³):", "Temperatur 1 (°C):"}:
                if not normkubikmenge and normart is None:
                    self._write_entry_preserve_state(self._tab1_entries.get(key), self._format_value(val))
                else:
                    self._write_entry_preserve_state(self._tab1_entries.get(key), self._format_value(val))
                    self._set_entry_state(self._tab1_entries.get(key), "readonly")
            else:
                self._write_entry_preserve_state(self._tab1_entries.get(key), self._format_value(val))
                self._set_entry_state(self._tab1_entries.get(key), "readonly")

        temp2_entry = self._tab1_entries.get("Temperatur 2 (°C):")
        if result["T2_C"] is not None:
            self._write_entry_preserve_state(temp2_entry, f"{result['T2_C']:.2f}")
        power_entry = self._tab1_entries.get("Wärmeleistung (kW):")
        if result["Q"] is not None:
            self._write_entry_preserve_state(power_entry, f"{result['Q']:.2f}")

        self._tab1_results = {
            "status": "ok",
            "message": "",
            "values": {
                "Temperatur 2 (°C):": result["T2_C"],
                "Wärmeleistung (kW):": result["Q"],
                **{key: val for key, val in values.items()},
            },
        }

    def _calculate_tab2(self) -> None:
        self._store_tab2_inputs()
        flow = self._read_required_float(self._tab2_entries.get("Volumenstrom"))
        if flow is None:
            self._set_tab2_error("Bitte gültige Zahlen angeben.")
            return

        shape = self._tab2_shape_combo.currentText() if self._tab2_shape_combo else "Rund"
        diameter = None
        side_a = None
        side_b = None
        if shape == "Rund":
            diameter = self._read_required_float(self._tab2_entries.get("Durchmesser (mm):"))
            if diameter is None:
                self._set_tab2_error("Bitte gültige Zahlen angeben.")
                return
        else:
            side_a = self._read_required_float(self._tab2_entries.get("Seite a (mm):"))
            side_b = self._read_required_float(self._tab2_entries.get("Seite b (mm):"))
            if side_a is None or side_b is None:
                self._set_tab2_error("Bitte gültige Zahlen angeben.")
                return

        temperature = self._optional_float(self._tab2_entries.get("Temperatur (°C):"))
        density = self._optional_float(self._tab2_entries.get("Dichte (kg/m³):"))
        flow_unit = self._tab2_flow_unit_combo.currentText() if self._tab2_flow_unit_combo else "m³/h"

        try:
            result = compute_flow_properties(
                shape=shape,
                flow=flow,
                flow_unit=flow_unit,
                diameter_mm=diameter,
                side_a_mm=side_a,
                side_b_mm=side_b,
                temperature_c=temperature,
                density=density,
            )
        except ValueError:
            self._set_tab2_error("Berechnung fehlgeschlagen.")
            return

        velocity_entry = self._tab2_entries.get("Strömungsgeschwindigkeit (m/s):")
        reynolds_entry = self._tab2_entries.get("Reynolds-Zahl:")
        flowtype_entry = self._tab2_entries.get("Strömungsart:")
        if result["velocity"] is not None:
            self._write_entry_preserve_state(velocity_entry, self._format_value(result["velocity"]))
        if result["reynolds"] is not None:
            self._write_entry_preserve_state(reynolds_entry, self._format_value(result["reynolds"]))
            self._write_entry_preserve_state(flowtype_entry, str(result["flow_type"]))
        else:
            self._write_entry_preserve_state(reynolds_entry, "")
            self._write_entry_preserve_state(flowtype_entry, "")

        self._tab2_results = {
            "status": "ok",
            "message": "",
            "values": {
                "Strömungsgeschwindigkeit (m/s):": result["velocity"],
                "Reynolds-Zahl:": result["reynolds"],
                "Strömungsart:": result["flow_type"],
            },
        }

    def _calculate_tab3(self) -> None:
        self._store_tab3_inputs()
        if self._tab3_use_tab1_power_check is not None and self._tab3_use_tab1_power_check.isChecked():
            thermal = self._get_tab1_thermal_power()
            if thermal is not None:
                self._write_entry_preserve_state(
                    self._tab3_entries.get("Wärmeleistung (kW):"), f"{thermal:.2f}"
                )
                self._set_entry_state(self._tab3_entries.get("Wärmeleistung (kW):"), "readonly")

        electrical_kw = self._optional_float(self._tab3_entries.get("Elektrische Leistung (kW):"))
        thermal_kw = self._optional_float(self._tab3_entries.get("Wärmeleistung (kW):"))
        efficiency_entry = self._tab3_entries.get("Effizienz (%):")
        efficiency = self._read_required_float(efficiency_entry)
        if efficiency is None:
            self._set_tab3_error("Bitte gültige Zahlen angeben.")
            return

        try:
            result = compute_heater_power(
                electrical_kw=electrical_kw,
                thermal_kw=thermal_kw,
                efficiency_percent=efficiency,
            )
        except ValueError:
            self._set_tab3_error("Berechnung fehlgeschlagen.")
            return

        for key, value in result.items():
            label = "Elektrische Leistung (kW):" if key == "electrical_kw" else "Wärmeleistung (kW):"
            self._write_entry_preserve_state(self._tab3_entries.get(label), f"{value:.2f}")
            if label == "Wärmeleistung (kW):" and self._tab3_use_tab1_power_check is not None:
                if self._tab3_use_tab1_power_check.isChecked():
                    self._set_entry_state(self._tab3_entries.get(label), "readonly")

        self._tab3_results = {
            "status": "ok",
            "message": "",
            "values": {
                "Elektrische Leistung (kW):": result.get("electrical_kw"),
                "Wärmeleistung (kW):": result.get("thermal_kw"),
            },
        }

    def _apply_tab1_results(self) -> None:
        values = self._tab1_results.get("values", {})
        if not isinstance(values, dict):
            return
        for key, val in values.items():
            entry = self._tab1_entries.get(key)
            if entry is None:
                continue
            if key in {"Temperatur 2 (°C):", "Wärmeleistung (kW):"}:
                numeric = self._coerce_float(val)
                if numeric is None:
                    continue
                self._write_entry_preserve_state(entry, f"{numeric:.2f}")
            else:
                numeric = self._coerce_float(val)
                if numeric is None:
                    continue
                self._write_entry_preserve_state(entry, self._format_value(numeric))

    def _apply_tab2_results(self) -> None:
        values = self._tab2_results.get("values", {})
        if not isinstance(values, dict):
            return
        velocity = self._coerce_float(values.get("Strömungsgeschwindigkeit (m/s):"))
        reynolds = self._coerce_float(values.get("Reynolds-Zahl:"))
        flow_type = values.get("Strömungsart:")
        if velocity is not None:
            self._write_entry_preserve_state(
                self._tab2_entries.get("Strömungsgeschwindigkeit (m/s):"),
                self._format_value(velocity),
            )
        if reynolds is not None:
            self._write_entry_preserve_state(
                self._tab2_entries.get("Reynolds-Zahl:"), self._format_value(reynolds)
            )
            self._write_entry_preserve_state(
                self._tab2_entries.get("Strömungsart:"), str(flow_type or "")
            )
        else:
            self._write_entry_preserve_state(self._tab2_entries.get("Reynolds-Zahl:"), "")
            self._write_entry_preserve_state(self._tab2_entries.get("Strömungsart:"), "")

    def _apply_tab3_results(self) -> None:
        values = self._tab3_results.get("values", {})
        if not isinstance(values, dict):
            return
        for label in ["Elektrische Leistung (kW):", "Wärmeleistung (kW):"]:
            numeric = self._coerce_float(values.get(label))
            if numeric is None:
                continue
            self._write_entry_preserve_state(self._tab3_entries.get(label), f"{numeric:.2f}")

    def _on_tab1_zustand_changed(self, text: str) -> None:
        self._tab1_inputs["zustand"] = text
        self._update_tab1_labels()

    def _on_tab1_toggle_din(self, checked: bool) -> None:
        if checked and self._tab1_heatrix_check is not None:
            with QSignalBlocker(self._tab1_heatrix_check):
                self._tab1_heatrix_check.setChecked(False)
            self._tab1_inputs["heatrix"] = False
        self._tab1_inputs["normkubik"] = checked
        self._update_normkubik_label()
        self._apply_tab1_toggle_states()

    def _on_tab1_toggle_heatrix(self, checked: bool) -> None:
        if checked and self._tab1_normkubik_check is not None:
            with QSignalBlocker(self._tab1_normkubik_check):
                self._tab1_normkubik_check.setChecked(False)
            self._tab1_inputs["normkubik"] = False
        self._tab1_inputs["heatrix"] = checked
        self._update_normkubik_label()
        self._apply_tab1_toggle_states()

    def _on_tab1_toggle_normkubikmenge(self, checked: bool) -> None:
        if checked and self._tab1_normkubik_check is not None and self._tab1_heatrix_check is not None:
            if not self._tab1_normkubik_check.isChecked() and not self._tab1_heatrix_check.isChecked():
                with QSignalBlocker(self._tab1_heatrix_check):
                    self._tab1_heatrix_check.setChecked(True)
                self._tab1_inputs["heatrix"] = True
        self._tab1_inputs["normkubikmenge"] = checked
        self._update_normkubik_label()
        self._apply_tab1_toggle_states()

    def _on_tab1_toggle_heat_priority(self, checked: bool) -> None:
        self._tab1_inputs["heat_priority"] = checked

    def _on_tab2_shape_changed(self, text: str) -> None:
        self._tab2_inputs["shape"] = text
        self._update_tab2_fields()

    def _on_tab2_flow_unit_changed(self, text: str) -> None:
        self._tab2_inputs["flow_unit"] = text

    def _on_tab2_toggle_norm(self, checked: bool) -> None:
        self._tab2_inputs["normkubik"] = checked
        self._apply_tab2_norm_state()

    def _on_tab3_toggle_use_tab1(self, checked: bool) -> None:
        self._tab3_inputs["use_tab1_power"] = checked
        self._apply_tab3_use_tab1_state()

    def _on_tab3_efficiency_changed(self, _text: str) -> None:
        if self._tab3_use_tab1_power_check is not None and self._tab3_use_tab1_power_check.isChecked():
            self._calculate_tab3()

    def _on_tab_changed(self, index: int) -> None:
        self._ui_state["active_tab"] = int(index)

    def _update_entry_value(self, tab_key: str, entry_key: str, value: str) -> None:
        if tab_key == "tab1":
            self._tab1_inputs.setdefault("entries", {})[entry_key] = value
        elif tab_key == "tab2":
            self._tab2_inputs.setdefault("entries", {})[entry_key] = value
        elif tab_key == "tab3":
            self._tab3_inputs.setdefault("entries", {})[entry_key] = value

    def _store_tab1_inputs(self) -> None:
        self._tab1_inputs["zustand"] = (
            self._tab1_zustand_combo.currentText() if self._tab1_zustand_combo else "Isobar"
        )
        self._tab1_inputs["normkubik"] = (
            self._tab1_normkubik_check.isChecked() if self._tab1_normkubik_check else False
        )
        self._tab1_inputs["heatrix"] = (
            self._tab1_heatrix_check.isChecked() if self._tab1_heatrix_check else False
        )
        self._tab1_inputs["normkubikmenge"] = (
            self._tab1_normkubikmenge_check.isChecked() if self._tab1_normkubikmenge_check else False
        )
        self._tab1_inputs["heat_priority"] = (
            self._tab1_heat_priority_check.isChecked() if self._tab1_heat_priority_check else False
        )
        self._tab1_inputs["entries"] = self._collect_entry_values(self._tab1_entries, {})

    def _store_tab2_inputs(self) -> None:
        self._tab2_inputs["shape"] = (
            self._tab2_shape_combo.currentText() if self._tab2_shape_combo else "Rund"
        )
        self._tab2_inputs["flow_unit"] = (
            self._tab2_flow_unit_combo.currentText() if self._tab2_flow_unit_combo else "m³/h"
        )
        self._tab2_inputs["normkubik"] = (
            self._tab2_normkubik_check.isChecked() if self._tab2_normkubik_check else False
        )
        self._tab2_inputs["entries"] = self._collect_entry_values(self._tab2_entries, {})

    def _store_tab3_inputs(self) -> None:
        self._tab3_inputs["use_tab1_power"] = (
            self._tab3_use_tab1_power_check.isChecked()
            if self._tab3_use_tab1_power_check
            else False
        )
        self._tab3_inputs["entries"] = self._collect_entry_values(self._tab3_entries, {})

    def _get_tab1_thermal_power(self) -> float | None:
        entry = self._tab1_entries.get("Wärmeleistung (kW):")
        return self._optional_float(entry)

    @staticmethod
    def _format_value(value: float) -> str:
        return f"{value:.5e}" if abs(value) < 0.001 else f"{value:.5f}"

    @staticmethod
    def _get_entry_text(entry: QLineEdit | None) -> str:
        if entry is None:
            return ""
        return entry.text()

    @staticmethod
    def _write_entry_preserve_state(entry: QLineEdit | None, value: str | None) -> None:
        if entry is None:
            return
        was_enabled = entry.isEnabled()
        was_readonly = entry.isReadOnly()
        entry.setEnabled(True)
        entry.setReadOnly(False)
        entry.setText("" if value is None else value)
        entry.setReadOnly(was_readonly)
        entry.setEnabled(was_enabled)

    @staticmethod
    def _set_entry_state(entry: QLineEdit | None, state: str) -> None:
        if entry is None:
            return
        if state == "disabled":
            entry.setEnabled(False)
            entry.setReadOnly(True)
        elif state == "readonly":
            entry.setEnabled(True)
            entry.setReadOnly(True)
        else:
            entry.setEnabled(True)
            entry.setReadOnly(False)

    @staticmethod
    def _get_entry_state(entry: QLineEdit | None) -> str:
        if entry is None:
            return "normal"
        if not entry.isEnabled():
            return "disabled"
        if entry.isReadOnly():
            return "readonly"
        return "normal"

    def _apply_entry_states(self, entries: dict[str, QLineEdit], states: Any) -> None:
        if not isinstance(states, dict):
            return
        for key, state in states.items():
            if key in entries and isinstance(state, str):
                self._set_entry_state(entries[key], state)

    def _apply_entry_values(self, entries: dict[str, QLineEdit], values: Any) -> None:
        if not isinstance(values, dict):
            return
        for key, value in values.items():
            if key in entries:
                self._write_entry_preserve_state(entries[key], self._coerce_str(value))

    def _collect_entry_values(self, entries: dict[str, QLineEdit], fallback: dict[str, str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, entry in entries.items():
            if entry is not None:
                values[key] = entry.text()
            elif key in fallback:
                values[key] = self._coerce_str(fallback.get(key))
        return values

    def _collect_entry_states(self, entries: dict[str, QLineEdit]) -> dict[str, str]:
        return {key: self._get_entry_state(entry) for key, entry in entries.items()}

    @staticmethod
    def _coerce_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_tab_inputs(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            return fallback
        merged = dict(fallback)
        merged.update(value)
        if "entries" in merged and not isinstance(merged["entries"], dict):
            merged["entries"] = {}
        return merged

    @staticmethod
    def _coerce_results(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            return fallback
        merged = dict(fallback)
        merged.update(value)
        if "values" in merged and not isinstance(merged["values"], dict):
            merged["values"] = {}
        return merged

    def _read_required_float(self, entry: QLineEdit | None) -> float | None:
        if entry is None:
            return None
        raw = entry.text().strip()
        if not raw or raw == "Bitte eintragen!":
            self._mark_error(entry)
            return None
        try:
            entry.setStyleSheet("color: black;")
            return float(raw)
        except ValueError:
            self._mark_error(entry)
            return None

    def _optional_float(self, entry: QLineEdit | None) -> float | None:
        if entry is None:
            return None
        raw = entry.text().strip()
        if not raw or raw == "Bitte eintragen!":
            return None
        try:
            entry.setStyleSheet("color: black;")
            return float(raw)
        except ValueError:
            self._mark_error(entry)
            return None

    def _mark_error(self, entry: QLineEdit | None) -> None:
        if entry is None:
            return
        entry.setStyleSheet("color: red;")
        entry.setText("Bitte eintragen!")

    def _set_tab1_error(self, message: str) -> None:
        self._tab1_results = {"status": "error", "message": message, "values": {}}

    def _set_tab2_error(self, message: str) -> None:
        self._tab2_results = {"status": "error", "message": message, "values": {}}

    def _set_tab3_error(self, message: str) -> None:
        self._tab3_results = {"status": "error", "message": message, "values": {}}

    def _get_active_tab_index(self) -> int:
        if self._tab_widget is None:
            return int(self._ui_state.get("active_tab", 0))
        return int(self._tab_widget.currentIndex())


__all__ = ["StoffeigenschaftenLuftQtPlugin"]
