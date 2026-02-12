"""Qt UI tab for robust management of insulation families and variants."""
from __future__ import annotations

from typing import Sequence

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.core.isolierungen_db.logic import (
    create_family,
    create_variant,
    delete_family_by_id,
    delete_variant_by_id,
    get_family_by_id,
    interpolate_k,
    list_families,
    register_material_change_listener,
    unregister_material_change_listener,
    update_family,
    update_variant,
)
from app.core.isolierungen_db.services import parse_optional_float, parse_required_float
from app.ui_qt.ui_helpers import apply_form_layout_defaults, create_page_header, make_grid, make_hbox, make_root_vbox, make_vbox


class DictTableModel(QAbstractTableModel):
    def __init__(self, columns: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        key = self._columns[index.column()][0]
        value = self._rows[index.row()].get(key)
        return "" if value is None else str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section][1]
        return str(section + 1)

    def get_row(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


class IsolierungenDbTab:
    def __init__(self, tab_widget: QTabWidget, title: str = "Isolierungen DB") -> None:
        self._tab_widget = tab_widget
        self._selected_family_id: int | None = None
        self._selected_variant_id: int | None = None
        self._listener_registered = False
        self._material_change_handler = self.refresh_table

        self.widget = QWidget()
        root_layout = make_root_vbox(self.widget)
        root_layout.addWidget(create_page_header("Isolierungen DB", show_logo=True, parent=self.widget))

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self._content_layout = make_vbox(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, 1)

        tables_row = make_hbox()
        self._family_section = self._build_family_section()
        self._variant_section = self._build_variant_section()
        tables_row.addWidget(self._family_section, 1)
        tables_row.addWidget(self._variant_section, 1)
        self._content_layout.addLayout(tables_row, 4)

        forms_row = make_hbox()
        forms_row.addWidget(self._build_family_form(), 1)
        forms_row.addWidget(self._build_variant_form(), 1)
        self._content_layout.addLayout(forms_row, 0)

        self._content_layout.addWidget(self._build_plot_section(), 0)

        self.refresh_table(preserve_selection=False)
        register_material_change_listener(self._material_change_handler)
        self._listener_registered = True
        self.widget.destroyed.connect(self._on_widget_destroyed)
        self._tab_widget.addTab(self.widget, title)

    def _build_family_section(self) -> QGroupBox:
        section = QGroupBox("Materialfamilien")
        layout = make_vbox()
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Suche:"))
        self._family_search = QLineEdit()
        self._family_search.setPlaceholderText("Familienname filtern …")
        search_row.addWidget(self._family_search)

        button_row = QHBoxLayout()
        self._new_family_button = QPushButton("Neu")
        self._delete_family_button = QPushButton("Familie löschen")
        button_row.addWidget(self._new_family_button)
        button_row.addWidget(self._delete_family_button)
        button_row.addStretch(1)

        self._family_model = DictTableModel(
            [
                ("name", "Familie"),
                ("classification_temp", "Klass.-Temp [°C]"),
                ("density", "Dichte [kg/m³]"),
                ("variant_count", "Varianten"),
            ]
        )
        self._family_proxy = QSortFilterProxyModel(self.widget)
        self._family_proxy.setSourceModel(self._family_model)
        self._family_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._family_proxy.setFilterKeyColumn(0)
        self._family_proxy.setDynamicSortFilter(True)

        self._family_table = QTableView()
        self._family_table.setModel(self._family_proxy)
        self._family_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._family_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._family_table.setSortingEnabled(True)
        self._family_table.verticalHeader().setVisible(False)
        self._family_table.setMinimumHeight(260)
        self._family_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addLayout(search_row)
        layout.addLayout(button_row)
        layout.addWidget(self._family_table, 1)
        section.setLayout(layout)
        section.setMinimumHeight(340)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._family_search.textChanged.connect(self._family_proxy.setFilterFixedString)
        self._family_table.selectionModel().selectionChanged.connect(self.on_family_select)
        self._new_family_button.clicked.connect(self.new_family)
        self._delete_family_button.clicked.connect(self.delete_family)
        return section

    def _build_variant_section(self) -> QGroupBox:
        section = QGroupBox("Varianten")
        layout = make_vbox()
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Suche:"))
        self._variant_search = QLineEdit()
        self._variant_search.setPlaceholderText("Variantenname filtern …")
        search_row.addWidget(self._variant_search)

        button_row = QHBoxLayout()
        self._new_variant_button = QPushButton("Neue Variante")
        self._delete_variant_button = QPushButton("Variante löschen")
        button_row.addWidget(self._new_variant_button)
        button_row.addWidget(self._delete_variant_button)
        button_row.addStretch(1)

        self._variant_model = DictTableModel(
            [
                ("name", "Variante"),
                ("thickness", "Dicke [mm]"),
                ("length", "Länge [mm]"),
                ("width", "Breite [mm]"),
                ("price", "Preis [€]"),
            ]
        )
        self._variant_proxy = QSortFilterProxyModel(self.widget)
        self._variant_proxy.setSourceModel(self._variant_model)
        self._variant_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._variant_proxy.setFilterKeyColumn(0)
        self._variant_proxy.setDynamicSortFilter(True)

        self._variant_table = QTableView()
        self._variant_table.setModel(self._variant_proxy)
        self._variant_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._variant_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._variant_table.setSortingEnabled(True)
        self._variant_table.verticalHeader().setVisible(False)
        self._variant_table.setMinimumHeight(260)
        self._variant_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addLayout(search_row)
        layout.addLayout(button_row)
        layout.addWidget(self._variant_table, 1)
        section.setLayout(layout)
        section.setMinimumHeight(340)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._variant_search.textChanged.connect(self._variant_proxy.setFilterFixedString)
        self._variant_table.selectionModel().selectionChanged.connect(self.on_variant_select)
        self._new_variant_button.clicked.connect(self.new_variant)
        self._delete_variant_button.clicked.connect(self.delete_variant)
        return section

    def _build_family_form(self) -> QGroupBox:
        section = QGroupBox("Familienstammdaten")
        grid = make_grid()
        self._family_name_input = QLineEdit()
        self._family_class_temp_input = QLineEdit()
        self._family_density_input = QLineEdit()
        self._family_temps_input = QLineEdit()
        self._family_ks_input = QLineEdit()
        self._family_save_button = QPushButton("Stammdaten speichern")

        grid.addWidget(QLabel("Familienname:"), 0, 0)
        grid.addWidget(self._family_name_input, 0, 1)
        grid.addWidget(QLabel("Klass.-Temp [°C]:"), 1, 0)
        grid.addWidget(self._family_class_temp_input, 1, 1)
        grid.addWidget(QLabel("Dichte [kg/m³]:"), 2, 0)
        grid.addWidget(self._family_density_input, 2, 1)
        grid.addWidget(QLabel("Temperaturen [°C]:"), 3, 0)
        grid.addWidget(self._family_temps_input, 3, 1)
        grid.addWidget(QLabel("Wärmeleitfähigkeiten [W/mK]:"), 4, 0)
        grid.addWidget(self._family_ks_input, 4, 1)
        grid.addWidget(self._family_save_button, 5, 0, 1, 2, alignment=Qt.AlignRight)
        apply_form_layout_defaults(grid)
        section.setLayout(grid)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._family_save_button.clicked.connect(self.save_family)
        return section

    def _build_variant_form(self) -> QGroupBox:
        section = QGroupBox("Varianten-Editor")
        grid = make_grid()
        self._variant_name_input = QLineEdit()
        self._variant_thickness_input = QLineEdit()
        self._variant_length_input = QLineEdit()
        self._variant_width_input = QLineEdit()
        self._variant_price_input = QLineEdit()
        self._variant_save_button = QPushButton("Variante speichern")

        grid.addWidget(QLabel("Variante:"), 0, 0)
        grid.addWidget(self._variant_name_input, 0, 1)
        grid.addWidget(QLabel("Dicke [mm]:"), 1, 0)
        grid.addWidget(self._variant_thickness_input, 1, 1)
        grid.addWidget(QLabel("Länge [mm]:"), 0, 2)
        grid.addWidget(self._variant_length_input, 0, 3)
        grid.addWidget(QLabel("Breite [mm]:"), 1, 2)
        grid.addWidget(self._variant_width_input, 1, 3)
        grid.addWidget(QLabel("Preis [€/Platte]:"), 2, 0)
        grid.addWidget(self._variant_price_input, 2, 1)
        grid.addWidget(self._variant_save_button, 3, 0, 1, 4, alignment=Qt.AlignRight)
        apply_form_layout_defaults(grid, label_columns=(0, 2), field_columns=(1, 3))
        section.setLayout(grid)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._variant_save_button.clicked.connect(self.save_variant)
        return section

    def _build_plot_section(self) -> QGroupBox:
        self._plot_section = QGroupBox("Interpolierte Wärmeleitfähigkeit")
        self._plot_layout = QVBoxLayout(self._plot_section)
        self._plot_section.setMinimumHeight(280)
        self._plot_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return self._plot_section

    def refresh_table(self, preserve_selection: bool = True) -> None:
        selected_family_id = self._selected_family_id if preserve_selection else None
        selected_variant_id = self._selected_variant_id if preserve_selection else None
        family_scroll = self._family_table.verticalScrollBar().value()
        variant_scroll = self._variant_table.verticalScrollBar().value()

        families = list_families()
        self._family_model.set_rows(families)

        if selected_family_id:
            self._select_family_id(selected_family_id)
        elif families:
            self._select_family_id(int(families[0]["id"]))
        else:
            self.new_family()

        self._family_table.verticalScrollBar().setValue(family_scroll)
        self._variant_table.verticalScrollBar().setValue(variant_scroll)
        if selected_variant_id:
            self._select_variant_id(selected_variant_id)

    def _select_family_id(self, family_id: int) -> None:
        for row in range(self._family_model.rowCount()):
            source = self._family_model.get_row(row)
            if source and int(source["id"]) == family_id:
                source_index = self._family_model.index(row, 0)
                proxy_index = self._family_proxy.mapFromSource(source_index)
                if proxy_index.isValid():
                    self._family_table.selectRow(proxy_index.row())
                self._selected_family_id = family_id
                self._load_family(family_id)
                return

    def _select_variant_id(self, variant_id: int) -> None:
        for row in range(self._variant_model.rowCount()):
            source = self._variant_model.get_row(row)
            if source and int(source["id"]) == variant_id:
                source_index = self._variant_model.index(row, 0)
                proxy_index = self._variant_proxy.mapFromSource(source_index)
                if proxy_index.isValid():
                    self._variant_table.selectRow(proxy_index.row())
                return

    def _load_family(self, family_id: int) -> None:
        data = get_family_by_id(family_id)
        self._family_name_input.setText(data["name"])
        self._family_class_temp_input.setText(str(data["classification_temp"]))
        self._family_density_input.setText(str(data["density"]))
        self._family_temps_input.setText(", ".join(map(str, data.get("temps", []))))
        self._family_ks_input.setText(", ".join(map(str, data.get("ks", []))))
        self._variant_model.set_rows(data.get("variants", []))
        self._selected_variant_id = None
        self._clear_variant_form()
        self.update_plot(data.get("temps", []), data.get("ks", []), data.get("classification_temp"))

    def on_family_select(self) -> None:
        index = self._family_table.currentIndex()
        if not index.isValid():
            return
        source_index = self._family_proxy.mapToSource(index)
        row = self._family_model.get_row(source_index.row())
        if not row:
            return
        self._selected_family_id = int(row["id"])
        self._load_family(self._selected_family_id)

    def on_variant_select(self) -> None:
        index = self._variant_table.currentIndex()
        if not index.isValid():
            return
        source_index = self._variant_proxy.mapToSource(index)
        row = self._variant_model.get_row(source_index.row())
        if not row:
            return
        self._selected_variant_id = int(row["id"])
        self._variant_name_input.setText(row.get("name", ""))
        self._variant_thickness_input.setText(str(row.get("thickness", "")))
        self._variant_length_input.setText("" if row.get("length") is None else str(row.get("length")))
        self._variant_width_input.setText("" if row.get("width") is None else str(row.get("width")))
        self._variant_price_input.setText("" if row.get("price") is None else str(row.get("price")))

    def save_family(self) -> None:
        try:
            name = self._family_name_input.text().strip()
            class_temp = parse_required_float(self._family_class_temp_input.text(), "Klass.-Temp")
            density = parse_required_float(self._family_density_input.text(), "Dichte")
            temps = self._parse_float_list(self._family_temps_input.text())
            ks = self._parse_float_list(self._family_ks_input.text())
            if self._selected_family_id is None:
                self._selected_family_id = create_family(name, class_temp, density, temps, ks)
            else:
                update_family(self._selected_family_id, name, class_temp, density, temps, ks)
            self.refresh_table()
            QMessageBox.information(self.widget, "Gespeichert", "Familie wurde gespeichert.")
        except Exception as exc:
            QMessageBox.critical(self.widget, "Fehler", str(exc))

    def save_variant(self) -> None:
        if self._selected_family_id is None:
            QMessageBox.warning(self.widget, "Fehler", "Bitte zuerst eine Familie auswählen.")
            return
        try:
            name = self._variant_name_input.text().strip()
            thickness = parse_required_float(self._variant_thickness_input.text(), "Dicke")
            length = parse_optional_float(self._variant_length_input.text())
            width = parse_optional_float(self._variant_width_input.text())
            price = parse_optional_float(self._variant_price_input.text())
            if self._selected_variant_id is None:
                self._selected_variant_id = create_variant(
                    self._selected_family_id, name, thickness, length, width, price
                )
            else:
                update_variant(self._selected_variant_id, name, thickness, length, width, price)
            self.refresh_table()
            QMessageBox.information(self.widget, "Gespeichert", "Variante wurde gespeichert.")
        except Exception as exc:
            QMessageBox.critical(self.widget, "Fehler", str(exc))

    def delete_family(self) -> None:
        if self._selected_family_id is None:
            return
        if delete_family_by_id(self._selected_family_id):
            self._selected_family_id = None
            self.refresh_table()

    def delete_variant(self) -> None:
        if self._selected_variant_id is None:
            return
        if delete_variant_by_id(self._selected_variant_id):
            self._selected_variant_id = None
            self.refresh_table()

    def new_family(self) -> None:
        self._selected_family_id = None
        self._selected_variant_id = None
        self._family_table.clearSelection()
        self._variant_model.set_rows([])
        self._clear_family_form()
        self._clear_variant_form()
        self.update_plot([], [], None)

    def new_variant(self) -> None:
        self._selected_variant_id = None
        self._variant_table.clearSelection()
        self._clear_variant_form()

    def update_plot(self, temps: Sequence[float], ks: Sequence[float], class_temp: float | None) -> None:
        self._clear_layout(self._plot_layout)
        if not temps or not ks:
            return
        max_temp = class_temp if class_temp is not None else max(temps)
        x_values = [float(value) for value in range(20, max(20, int(max_temp)) + 1)]
        k_values = interpolate_k(list(temps), list(ks), x_range=np.array(x_values))

        figure = Figure(figsize=(7, 3.2), dpi=100)
        axis = figure.add_subplot(111)
        axis.plot(x_values, k_values, linewidth=2, label="Interpoliert")
        axis.scatter(temps, ks, color="red", zorder=5, label="Messpunkte")
        axis.set_xlabel("Temperatur [°C]")
        axis.set_ylabel("Wärmeleitfähigkeit [W/mK]")
        axis.set_title("Wärmeleitfähigkeit über Temperatur")
        axis.legend()
        axis.grid(True, linestyle="--", alpha=0.6)
        figure.tight_layout()

        self._plot_layout.addWidget(FigureCanvasQTAgg(figure))

    def _clear_family_form(self) -> None:
        self._family_name_input.clear()
        self._family_class_temp_input.clear()
        self._family_density_input.clear()
        self._family_temps_input.clear()
        self._family_ks_input.clear()

    def _clear_variant_form(self) -> None:
        self._variant_name_input.clear()
        self._variant_thickness_input.clear()
        self._variant_length_input.clear()
        self._variant_width_input.clear()
        self._variant_price_input.clear()

    @staticmethod
    def _parse_float_list(value: str) -> list[float]:
        cleaned = value.strip()
        if not cleaned:
            return []
        separator = ";" if ";" in cleaned else ","
        return [float(part.strip().replace(",", ".")) for part in cleaned.split(separator) if part.strip()]

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

    def _on_widget_destroyed(self, _obj: object | None = None) -> None:
        if self._listener_registered:
            unregister_material_change_listener(self._material_change_handler)
            self._listener_registered = False
