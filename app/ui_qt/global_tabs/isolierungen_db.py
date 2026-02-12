"""Qt UI tab for managing insulation material data."""
from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

from app.core.isolierungen_db.logic import (
    delete_insulation_by_id,
    delete_variant,
    export_insulations_to_csv,
    export_insulations_to_folder,
    get_all_insulations,
    import_insulations_from_csv_files,
    interpolate_k,
    load_insulation_by_id,
    register_material_change_listener,
    unregister_material_change_listener,
    rename_family,
    rename_variant,
    save_family,
    save_variant,
)
from app.core.isolierungen_db.services import (
    build_import_summary,
    parse_optional_float,
    parse_required_float,
)
from app.ui_qt.ui_helpers import (
    apply_form_layout_defaults,
    create_button_row,
    create_page_header,
    make_grid,
    make_hbox,
    make_root_vbox,
    make_vbox,
)


class IsolierungenDbTab:
    """Global Qt tab for managing insulation material master data."""

    def __init__(self, tab_widget: QTabWidget, title: str = "Isolierungen DB") -> None:
        self._tab_widget = tab_widget
        self._selected_family: int | None = None
        self._is_new_family_mode = False
        self._selected_variant: int | None = None
        self._material_change_handler = self.refresh_table
        self._listener_registered = False

        self.widget = QWidget()
        root_layout = make_root_vbox(self.widget)
        header = create_page_header("Isolierungen DB", show_logo=True, parent=self.widget)
        root_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        self._layout = make_vbox(content_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area, 1)

        tables_row = make_hbox()
        tables_row.addWidget(self._build_family_section(), 1)
        tables_row.addWidget(self._build_variant_section(), 1)
        self._layout.addLayout(tables_row, 5)

        forms_row = make_hbox()
        forms_row.addWidget(self._build_family_form(), 1)
        forms_row.addWidget(self._build_variant_form(), 1)
        self._layout.addLayout(forms_row, 0)

        self._layout.addWidget(self._build_plot_section(), 2)

        self.refresh_table(preserve_selection=False)
        if not self._listener_registered:
            register_material_change_listener(self._material_change_handler)
            self._listener_registered = True
        if hasattr(self.widget, "destroyed"):
            self.widget.destroyed.connect(self._on_widget_destroyed)

        if hasattr(self._tab_widget, "addTab"):
            self._tab_widget.addTab(self.widget, title)

    def _build_family_section(self) -> QGroupBox:
        section = QGroupBox("Materialfamilien")
        layout = make_vbox()

        self._new_family_button = QPushButton("Neu")
        self._delete_family_button = QPushButton("Familie löschen")
        self._export_button = QPushButton("Exportieren (CSV)")
        self._import_button = QPushButton("Importieren (CSV)")
        action_bar = create_button_row(
            [
                self._new_family_button,
                self._delete_family_button,
                self._export_button,
                self._import_button,
            ]
        )

        self._family_table = QTableWidget(0, 4)
        self._family_table.setHorizontalHeaderLabels(
            ["Familie", "Klass.-Temp [°C]", "Dichte [kg/m³]", "Varianten"]
        )
        self._family_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._family_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._family_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._family_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._family_table.setMinimumHeight(280)
        self._family_table.horizontalHeader().setStretchLastSection(True)
        self._family_table.verticalHeader().setVisible(False)

        layout.addLayout(action_bar)
        layout.addWidget(self._family_table, 1)
        section.setLayout(layout)
        section.setMinimumHeight(360)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._new_family_button.clicked.connect(self.new_family)
        self._delete_family_button.clicked.connect(self.delete_family)
        self._export_button.clicked.connect(self.export_selected)
        self._import_button.clicked.connect(self.import_from_csv)
        self._family_table.itemSelectionChanged.connect(self.on_family_select)
        return section

    def _build_variant_section(self) -> QGroupBox:
        section = QGroupBox("Varianten")
        layout = make_vbox()

        self._new_variant_button = QPushButton("Neue Variante")
        self._delete_variant_button = QPushButton("Variante löschen")
        action_bar = create_button_row([self._new_variant_button, self._delete_variant_button])

        self._variant_table = QTableWidget(0, 5)
        self._variant_table.setHorizontalHeaderLabels(
            ["Variante", "Dicke [mm]", "Länge [mm]", "Breite [mm]", "Preis [€]"]
        )
        self._variant_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._variant_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._variant_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._variant_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._variant_table.setMinimumHeight(280)
        self._variant_table.horizontalHeader().setStretchLastSection(True)
        self._variant_table.verticalHeader().setVisible(False)

        layout.addLayout(action_bar)
        layout.addWidget(self._variant_table, 1)
        section.setLayout(layout)
        section.setMinimumHeight(360)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._new_variant_button.clicked.connect(self.new_variant)
        self._delete_variant_button.clicked.connect(self.delete_variant)
        self._variant_table.itemSelectionChanged.connect(self.on_variant_select)
        return section

    def _build_family_form(self) -> QGroupBox:
        section = QGroupBox("Stammdaten")
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
        section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._family_save_button.clicked.connect(self.save_family)
        return section

    def _build_variant_form(self) -> QGroupBox:
        section = QGroupBox("Variante bearbeiten")
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
        section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._variant_save_button.clicked.connect(self.save_variant)
        return section

    def _build_plot_section(self) -> QGroupBox:
        self._plot_section = QGroupBox("Interpolierte Wärmeleitfähigkeit")
        self._plot_layout = make_vbox()
        self._plot_section.setMinimumHeight(260)
        self._plot_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._plot_section.setLayout(self._plot_layout)
        return self._plot_section

    def refresh_table(self, preserve_selection: bool = True) -> None:
        selected_family = self._selected_family if preserve_selection else None

        self._family_table.setRowCount(0)
        for insulation in get_all_insulations():
            row = self._family_table.rowCount()
            self._family_table.insertRow(row)
            family_item = QTableWidgetItem(str(insulation.get("name", "")))
            family_item.setData(Qt.UserRole, insulation.get("id"))
            self._family_table.setItem(row, 0, family_item)
            self._family_table.setItem(
                row, 1, QTableWidgetItem(str(insulation.get("classification_temp", "")))
            )
            self._family_table.setItem(row, 2, QTableWidgetItem(str(insulation.get("density", ""))))
            self._family_table.setItem(
                row, 3, QTableWidgetItem(str(insulation.get("variant_count", 0)))
            )

        self._family_table.resizeColumnsToContents()

        if selected_family is not None:
            self._select_family_by_id(selected_family)
        else:
            self._variant_table.setRowCount(0)
            self._clear_family_form()
            self._clear_variant_form()
            self.update_plot([], [], None)

    def _select_family_by_id(self, family_id: int) -> None:
        for row in range(self._family_table.rowCount()):
            item = self._family_table.item(row, 0)
            if item and item.data(Qt.UserRole) == family_id:
                with QSignalBlocker(self._family_table):
                    self._family_table.selectRow(row)
                self._selected_family = family_id
                self._is_new_family_mode = False
                self._load_family(family_id)
                return
        self._selected_family = None
        self._is_new_family_mode = True
        self._variant_table.setRowCount(0)
        self._clear_family_form()
        self._clear_variant_form()
        self.update_plot([], [], None)

    def new_family(self) -> None:
        self._selected_family = None
        self._is_new_family_mode = True
        with QSignalBlocker(self._family_table):
            self._family_table.clearSelection()
            self._family_table.setCurrentCell(-1, -1)
        self._clear_family_form()
        self._variant_table.setRowCount(0)
        self._clear_variant_form()
        self.update_plot([], [], None)

    def on_family_select(self) -> None:
        selection_model = self._family_table.selectionModel()
        if selection_model is None or not selection_model.hasSelection() or not self._family_table.selectedItems():
            return
        row = self._family_table.currentRow()
        if row < 0:
            row = self._family_table.selectedItems()[0].row()
        item = self._family_table.item(row, 0)
        if item is None:
            return
        family_id = item.data(Qt.UserRole)
        if family_id is None:
            return
        self._selected_family = int(family_id)
        self._is_new_family_mode = False
        self._load_family(self._selected_family)

    def _load_family(self, family_id: int) -> None:
        data = load_insulation_by_id(family_id)
        if not data:
            return
        self._fill_family_form(data)
        self._populate_variants(data.get("variants", []))
        self.update_plot(data.get("temps", []), data.get("ks", []), data.get("classification_temp"))

    def _fill_family_form(self, data: dict) -> None:
        self._family_name_input.setText(str(data.get("name", "")))
        class_temp = data.get("classification_temp")
        self._family_class_temp_input.setText("" if class_temp is None else str(class_temp))
        density = data.get("density")
        self._family_density_input.setText("" if density is None else str(density))
        temps = data.get("temps", [])
        ks = data.get("ks", [])
        self._family_temps_input.setText(", ".join(map(str, temps)) if temps else "")
        self._family_ks_input.setText(", ".join(map(str, ks)) if ks else "")

    def _populate_variants(self, variants: Sequence[dict]) -> None:
        self._variant_table.setRowCount(0)
        for variant in variants:
            row = self._variant_table.rowCount()
            self._variant_table.insertRow(row)
            variant_item = QTableWidgetItem(str(variant.get("name", "")))
            variant_item.setData(Qt.UserRole, variant.get("id"))
            self._variant_table.setItem(row, 0, variant_item)
            self._variant_table.setItem(
                row, 1, QTableWidgetItem(str(variant.get("thickness", "")))
            )
            self._variant_table.setItem(row, 2, QTableWidgetItem(str(variant.get("length", ""))))
            self._variant_table.setItem(row, 3, QTableWidgetItem(str(variant.get("width", ""))))
            self._variant_table.setItem(row, 4, QTableWidgetItem(str(variant.get("price", ""))))

        self._variant_table.resizeColumnsToContents()

    def new_variant(self) -> None:
        self._selected_variant = None
        self._variant_table.clearSelection()
        self._clear_variant_form()

    def on_variant_select(self) -> None:
        row = self._variant_table.currentRow()
        if row < 0:
            return
        name_item = self._variant_table.item(row, 0)
        if name_item is None:
            return
        values = [
            self._variant_table.item(row, col).text() if self._variant_table.item(row, col) else ""
            for col in range(self._variant_table.columnCount())
        ]
        variant_id = name_item.data(Qt.UserRole)
        if variant_id is None:
            return
        self._selected_variant = int(variant_id)
        self._variant_name_input.setText(values[0])
        self._variant_thickness_input.setText(values[1] if len(values) > 1 else "")
        self._variant_length_input.setText(values[2] if len(values) > 2 else "")
        self._variant_width_input.setText(values[3] if len(values) > 3 else "")
        self._variant_price_input.setText(values[4] if len(values) > 4 else "")

    # Regression-Testszenario (manuell):
    # 1) Vorhandene Familie auswählen.
    # 2) Auf "Neu" klicken.
    # 3) Neuen Familiennamen eintragen und speichern.
    # Erwartung: Create-Pfad (Insert, Count +1), kein Rename der zuvor gewählten Familie.
    def save_family(self) -> None:
        name = self._family_name_input.text().strip()
        if not name:
            QMessageBox.warning(self.widget, "Fehler", "Familienname darf nicht leer sein.")
            return
        try:
            class_temp = parse_required_float(self._family_class_temp_input.text(), "Klass.-Temp")
            density = parse_required_float(self._family_density_input.text(), "Dichte")
            temps = self._parse_float_list(self._family_temps_input.text())
            ks = self._parse_float_list(self._family_ks_input.text())
            if len(temps) != len(ks):
                QMessageBox.critical(
                    self.widget,
                    "Fehler",
                    "Temperatur- und k-Werte müssen gleich viele Einträge haben.",
                )
                return

            is_new_mode = self._is_new_family_mode
            if is_new_mode:
                if self._family_exists(name):
                    response = QMessageBox.question(
                        self.widget,
                        "Familie überschreiben",
                        (
                            f"Die Familie '{name}' existiert bereits. "
                            "Möchten Sie die Stammdaten überschreiben?"
                        ),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if response != QMessageBox.Yes:
                        return
            else:
                if self._selected_family is None:
                    QMessageBox.warning(
                        self.widget,
                        "Hinweis",
                        "Bitte zuerst eine Familie auswählen oder über 'Neu' eine neue Familie anlegen.",
                    )
                    return
                current = load_insulation_by_id(self._selected_family)
                current_name = current.get("name", "")
                if current_name and current_name != name:
                    if not rename_family(self._selected_family, name):
                        QMessageBox.critical(
                            self.widget,
                            "Fehler",
                            "Familie konnte nicht umbenannt werden. Bitte Namen prüfen.",
                        )
                        return

            saved = save_family(name, class_temp, density, temps, ks)
            if not saved:
                QMessageBox.critical(self.widget, "Fehler", "Familie konnte nicht gespeichert werden.")
                return
            materials = get_all_insulations()
            chosen = next((m for m in materials if m.get("name") == name), None)
            self._selected_family = int(chosen["id"]) if chosen and chosen.get("id") is not None else None
            self._is_new_family_mode = False
            QMessageBox.information(self.widget, "Gespeichert", f"Familie '{name}' wurde gespeichert.")
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self.widget, "Fehler", str(exc))

    def save_variant(self) -> None:
        family_id = self._selected_family
        family_name = self._family_name_input.text().strip()
        if family_id is None or not family_name:
            QMessageBox.warning(self.widget, "Fehler", "Bitte zuerst eine Familie auswählen.")
            return
        variant_name = self._variant_name_input.text().strip() or "Standard"
        try:
            thickness = parse_required_float(self._variant_thickness_input.text(), "Dicke")
            length = parse_optional_float(self._variant_length_input.text())
            width = parse_optional_float(self._variant_width_input.text())
            price = parse_optional_float(self._variant_price_input.text())

            variant_data = load_insulation_by_id(family_id).get("variants", [])
            existing_variants = {variant.get("name", "") for variant in variant_data}
            selected_variant = next(
                (v for v in variant_data if v.get("id") == self._selected_variant),
                None,
            )

            if selected_variant and selected_variant.get("name") != variant_name:
                if variant_name in existing_variants:
                    QMessageBox.critical(
                        self.widget,
                        "Fehler",
                        "Der Variantenname existiert bereits in dieser Familie.",
                    )
                    return
            elif not selected_variant and variant_name in existing_variants:
                response = QMessageBox.question(
                    self.widget,
                    "Variante überschreiben",
                    (
                        f"Die Variante '{variant_name}' existiert bereits. "
                        "Möchten Sie sie überschreiben?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if response != QMessageBox.Yes:
                    return

            if selected_variant and selected_variant.get("name") != variant_name:
                if not rename_variant(family_id, self._selected_variant, variant_name):
                    QMessageBox.critical(
                        self.widget,
                        "Fehler",
                        "Variante konnte nicht umbenannt werden. Bitte Namen prüfen.",
                    )
                    return

            saved = save_variant(family_id, variant_name, thickness, length, width, price)
            if not saved:
                QMessageBox.critical(
                    self.widget,
                    "Fehler",
                    "Variante konnte nicht gespeichert werden. Bitte Familie prüfen.",
                )
                return

            variants = load_insulation_by_id(family_id).get("variants", [])
            chosen_variant = next((v for v in variants if v.get("name") == variant_name), None)
            self._selected_variant = int(chosen_variant["id"]) if chosen_variant and chosen_variant.get("id") is not None else None
            QMessageBox.information(
                self.widget,
                "Gespeichert",
                f"Variante '{variant_name}' wurde für '{family_name}' gespeichert.",
            )
            self._load_family(family_id)
        except Exception as exc:
            QMessageBox.critical(self.widget, "Fehler", str(exc))

    def delete_family(self) -> None:
        family_id = self._selected_family
        name = self._family_name_input.text().strip()
        if family_id is None:
            QMessageBox.information(self.widget, "Hinweis", "Bitte eine Isolierung auswählen.")
            return
        response = QMessageBox.question(
            self.widget,
            "Löschen bestätigen",
            (
                f"Soll das Material '{name}' endgültig gelöscht werden?\n"
                "Dieser Vorgang kann nicht rückgängig gemacht werden."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.Yes:
            return
        if delete_insulation_by_id(family_id):
            self._selected_family = None
            self.refresh_table(preserve_selection=False)
            self._clear_family_form()
            self._clear_variant_form()
        else:
            QMessageBox.critical(self.widget, "Löschen fehlgeschlagen", "Das Material konnte nicht gelöscht werden.")

    def delete_variant(self) -> None:
        family_id = self._selected_family
        family_name = self._family_name_input.text().strip()
        variant_id = self._selected_variant
        if family_id is None or not family_name or variant_id is None:
            QMessageBox.information(
                self.widget, "Hinweis", "Bitte zuerst eine Familie und Variante auswählen."
            )
            return
        response = QMessageBox.question(
            self.widget,
            "Variante löschen",
            f"Soll die ausgewählte Variante aus '{family_name}' gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.Yes:
            return
        if delete_variant(family_id, variant_id):
            self._selected_variant = None
            self._load_family(family_id)
            self._clear_variant_form()
        else:
            QMessageBox.critical(self.widget, "Löschen fehlgeschlagen", "Die Variante konnte nicht gelöscht werden.")

    def export_selected(self) -> None:
        preselected = {self._family_name_input.text().strip()} if self._selected_family else set()
        names = self._choose_export_names(preselected)
        if not names:
            return
        try:
            if len(names) == 1:
                file_path, _ = QFileDialog.getSaveFileName(
                    self.widget,
                    "Isolierung exportieren",
                    f"{names[0]}.csv",
                    "CSV Dateien (*.csv);;Alle Dateien (*)",
                )
                if not file_path:
                    return
                exported, failed = export_insulations_to_csv(names, file_path)
                message = f"{exported} Isolierung exportiert nach\n{file_path}"
            else:
                target_dir = QFileDialog.getExistingDirectory(
                    self.widget, "Zielordner für Export wählen"
                )
                if not target_dir:
                    return
                exported, failed, export_dir = export_insulations_to_folder(names, target_dir)
                message = (
                    f"{exported} Isolierungen wurden exportiert.\n"
                    f"Speicherort: {export_dir}"
                )

            if failed:
                message += "\nNicht exportiert: " + ", ".join(failed)
            QMessageBox.information(self.widget, "Export abgeschlossen", message)
        except Exception as exc:
            QMessageBox.critical(self.widget, "Export fehlgeschlagen", str(exc))

    def import_from_csv(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.widget,
            "Isolierungen importieren",
            "",
            "CSV Dateien (*.csv);;Alle Dateien (*)",
        )
        if not file_paths:
            return
        try:
            imported, results = import_insulations_from_csv_files(list(file_paths))
            self.refresh_table()
            message = build_import_summary(imported, results)
            QMessageBox.information(self.widget, "Import abgeschlossen", message)
        except Exception as exc:
            QMessageBox.critical(self.widget, "Import fehlgeschlagen", str(exc))

    def update_plot(self, temps: Sequence[float], ks: Sequence[float], class_temp: float | None) -> None:
        self._clear_layout(self._plot_layout)
        if not temps or not ks:
            return
        try:
            max_temp = class_temp if class_temp is not None else (max(temps) if temps else 20)
            end_temp = max(20, int(max_temp))
            x_values = [float(value) for value in range(20, end_temp + 1)]
            k_values = interpolate_k(list(temps), list(ks), x_range=np.array(x_values))

            figure = Figure(figsize=(6, 3), dpi=100)
            axis = figure.add_subplot(111)
            axis.plot(x_values, k_values, linewidth=2, label="Interpoliert")
            axis.scatter(temps, ks, color="red", zorder=5, label="Messpunkte")
            axis.set_xlabel("Temperatur [°C]")
            axis.set_ylabel("Wärmeleitfähigkeit [W/mK]")
            axis.set_title("Wärmeleitfähigkeit über Temperatur")
            axis.legend()
            axis.grid(True, linestyle="--", alpha=0.6)

            canvas = FigureCanvasQTAgg(figure)
            self._plot_layout.addWidget(canvas)
        except Exception as exc:
            QMessageBox.critical(self.widget, "Fehler beim Plotten", str(exc))

    def _choose_export_names(self, preselected: Iterable[str]) -> list[str]:
        dialog = QDialog(self.widget)
        dialog.setWindowTitle("Isolierungen exportieren")
        layout = make_vbox()

        layout.addWidget(
            QLabel("Bitte wählen Sie ein oder mehrere Isolierungen für den Export aus:")
        )

        list_widget = QListWidget()
        for insulation in get_all_insulations():
            name = insulation.get("name", "")
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in preselected else Qt.Unchecked)
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        action_bar = make_hbox()
        select_all_btn = QPushButton("Alle auswählen")
        deselect_btn = QPushButton("Auswahl löschen")
        action_bar.addWidget(select_all_btn)
        action_bar.addWidget(deselect_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        def _set_all(state: Qt.CheckState) -> None:
            for idx in range(list_widget.count()):
                item = list_widget.item(idx)
                if item is not None:
                    item.setCheckState(state)

        def _accept() -> None:
            if not self._checked_names(list_widget):
                QMessageBox.information(
                    dialog,
                    "Hinweis",
                    "Bitte mindestens eine Isolierung zum Export auswählen.",
                )
                return
            dialog.accept()

        select_all_btn.clicked.connect(lambda: _set_all(Qt.Checked))
        deselect_btn.clicked.connect(lambda: _set_all(Qt.Unchecked))
        buttons.accepted.connect(_accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted:
            return []
        return self._checked_names(list_widget)

    @staticmethod
    def _checked_names(list_widget: QListWidget) -> list[str]:
        names: list[str] = []
        for idx in range(list_widget.count()):
            item = list_widget.item(idx)
            if item is not None and item.checkState() == Qt.Checked:
                names.append(item.text())
        return names

    def _family_exists(self, name: str) -> bool:
        return any(insulation.get("name") == name for insulation in get_all_insulations())

    def _parse_float_list(self, value: str) -> list[float]:
        cleaned = (value or "").strip()
        if not cleaned:
            return []
        try:
            separator = ";" if ";" in cleaned else ","
            parts = [item.strip() for item in cleaned.split(separator) if item.strip()]
            return [float(item.replace(",", ".")) for item in parts]
        except ValueError as exc:
            raise ValueError("Temperatur- und k-Werte müssen numerisch sein.") from exc

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
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

    def _on_widget_destroyed(self, _obj: object | None = None) -> None:
        if self._listener_registered:
            unregister_material_change_listener(self._material_change_handler)
            self._listener_registered = False
