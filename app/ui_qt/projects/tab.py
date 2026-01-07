"""Qt tab for managing projects and plugin states."""
from __future__ import annotations

import getpass
import importlib.util
import json
from typing import Any, Iterable, Sequence

from app.core.projects.store import ProjectRecord, ProjectStore
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.plugins.registry import QtPluginSpec, get_plugins


class _StubWidget:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.clicked = _StubSignal()
        return None

    def __getattr__(self, _name: str) -> Any:
        if _name == "itemSelectionChanged" or _name.endswith("Changed"):
            return _StubSignal()

        def _noop(*_args: object, **_kwargs: object) -> Any:
            return None

        return _noop


class _StubSignal:
    def connect(self, *_args: object, **_kwargs: object) -> None:
        return None


class _StubQt:
    AlignLeft = 0
    AlignVCenter = 0
    UserRole = 0


class _StubMessageBox:
    Yes = 0
    No = 1

    @staticmethod
    def information(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def warning(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def critical(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def question(*_args: object, **_kwargs: object) -> int:
        return _StubMessageBox.No


def _resolve_qt_widgets() -> tuple[bool, dict[str, Any]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QAbstractItemView,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMessageBox,
            QPushButton,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        return True, {
            "Qt": Qt,
            "QAbstractItemView": QAbstractItemView,
            "QGridLayout": QGridLayout,
            "QHBoxLayout": QHBoxLayout,
            "QLabel": QLabel,
            "QLineEdit": QLineEdit,
            "QMessageBox": QMessageBox,
            "QPushButton": QPushButton,
            "QSplitter": QSplitter,
            "QTableWidget": QTableWidget,
            "QTableWidgetItem": QTableWidgetItem,
            "QTextEdit": QTextEdit,
            "QVBoxLayout": QVBoxLayout,
            "QWidget": QWidget,
        }
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMessageBox,
            QPushButton,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        return True, {
            "Qt": Qt,
            "QAbstractItemView": QAbstractItemView,
            "QGridLayout": QGridLayout,
            "QHBoxLayout": QHBoxLayout,
            "QLabel": QLabel,
            "QLineEdit": QLineEdit,
            "QMessageBox": QMessageBox,
            "QPushButton": QPushButton,
            "QSplitter": QSplitter,
            "QTableWidget": QTableWidget,
            "QTableWidgetItem": QTableWidgetItem,
            "QTextEdit": QTextEdit,
            "QVBoxLayout": QVBoxLayout,
            "QWidget": QWidget,
        }
    return False, {
        "Qt": _StubQt,
        "QAbstractItemView": _StubWidget,
        "QGridLayout": _StubWidget,
        "QHBoxLayout": _StubWidget,
        "QLabel": _StubWidget,
        "QLineEdit": _StubWidget,
        "QMessageBox": _StubMessageBox,
        "QPushButton": _StubWidget,
        "QSplitter": _StubWidget,
        "QTableWidget": _StubWidget,
        "QTableWidgetItem": _StubWidget,
        "QTextEdit": _StubWidget,
        "QVBoxLayout": _StubWidget,
        "QWidget": _StubWidget,
    }


class ProjectsTab:
    """Stellt einen permanenten Tab zur Verwaltung aller Projekte bereit."""

    def __init__(
        self,
        tab_widget: object,
        plugin_manager: QtPluginManager,
        *,
        store: ProjectStore | None = None,
        plugin_specs: Sequence[QtPluginSpec] | None = None,
        author: str | None = None,
    ) -> None:
        self._qt_available, widgets = _resolve_qt_widgets()
        self._Qt = widgets["Qt"]
        self._QAbstractItemView = widgets["QAbstractItemView"]
        self._QGridLayout = widgets["QGridLayout"]
        self._QHBoxLayout = widgets["QHBoxLayout"]
        self._QLabel = widgets["QLabel"]
        self._QLineEdit = widgets["QLineEdit"]
        self._QMessageBox = widgets["QMessageBox"]
        self._QPushButton = widgets["QPushButton"]
        self._QSplitter = widgets["QSplitter"]
        self._QTableWidget = widgets["QTableWidget"]
        self._QTableWidgetItem = widgets["QTableWidgetItem"]
        self._QTextEdit = widgets["QTextEdit"]
        self._QVBoxLayout = widgets["QVBoxLayout"]
        self._QWidget = widgets["QWidget"]

        self._tab_widget = tab_widget
        self._plugin_manager = plugin_manager
        self._store = store or ProjectStore()
        self._author = author or getpass.getuser()
        self._plugin_specs = plugin_specs or get_plugins()
        self._spec_lookup = {spec.identifier: spec.name for spec in self._plugin_specs}
        self._selected_project_id: str | None = None
        self._project_cache: dict[str, ProjectRecord] = {}
        self._is_new_mode = False

        self.widget = self._QWidget()
        self._build_ui()
        self._insert_tab()
        self.refresh_projects()

    def _insert_tab(self) -> None:
        if hasattr(self._tab_widget, "insertTab"):
            self._tab_widget.insertTab(0, self.widget, "Projekte")
            return
        if hasattr(self._tab_widget, "addTab"):
            self._tab_widget.addTab(self.widget, "Projekte")

    def _build_ui(self) -> None:
        layout = self._QVBoxLayout()
        if hasattr(self.widget, "setLayout"):
            self.widget.setLayout(layout)

        title = self._QLabel("Projektverwaltung")
        if hasattr(layout, "addWidget"):
            layout.addWidget(title)

        meta_container = self._QWidget()
        meta_layout = self._QGridLayout()
        if hasattr(meta_container, "setLayout"):
            meta_container.setLayout(meta_layout)
        if hasattr(layout, "addWidget"):
            layout.addWidget(meta_container)

        self._name_input = self._QLineEdit()
        self._author_input = self._QLineEdit()
        if hasattr(self._author_input, "setText"):
            self._author_input.setText(self._author)

        meta_layout.addWidget(self._QLabel("Name:"), 0, 0)
        meta_layout.addWidget(self._name_input, 0, 1)
        meta_layout.addWidget(self._QLabel("Autor:"), 0, 2)
        meta_layout.addWidget(self._author_input, 0, 3)

        actions_container = self._QWidget()
        actions_layout = self._QHBoxLayout()
        if hasattr(actions_container, "setLayout"):
            actions_container.setLayout(actions_layout)
        if hasattr(layout, "addWidget"):
            layout.addWidget(actions_container)

        self._new_button = self._QPushButton("Neu")
        self._save_button = self._QPushButton("Projekt speichern")
        self._load_button = self._QPushButton("Projekt laden")
        self._delete_button = self._QPushButton("Löschen")

        actions_layout.addWidget(self._new_button)
        actions_layout.addWidget(self._save_button)
        actions_layout.addWidget(self._load_button)
        actions_layout.addWidget(self._delete_button)

        if hasattr(self._new_button, "clicked"):
            self._new_button.clicked.connect(self._enter_new_mode)
        if hasattr(self._save_button, "clicked"):
            self._save_button.clicked.connect(self.save_project)
        if hasattr(self._load_button, "clicked"):
            self._load_button.clicked.connect(self.load_selected_project)
        if hasattr(self._delete_button, "clicked"):
            self._delete_button.clicked.connect(self.delete_selected_project)

        self._status_label = self._QLabel(
            "Wähle ein vorhandenes Projekt oder lege ein neues an, "
            "um Plugin-Eingaben und Ergebnisse zu sichern."
        )
        if hasattr(layout, "addWidget"):
            layout.addWidget(self._status_label)

        splitter = self._QSplitter()
        if hasattr(layout, "addWidget"):
            layout.addWidget(splitter)

        list_container = self._QWidget()
        list_layout = self._QVBoxLayout()
        if hasattr(list_container, "setLayout"):
            list_container.setLayout(list_layout)
        list_layout.addWidget(self._QLabel("Projektliste"))
        list_layout.addWidget(self._QLabel("Alle gespeicherten Projekte"))

        self._table = self._QTableWidget(0, 3)
        if hasattr(self._table, "setHorizontalHeaderLabels"):
            self._table.setHorizontalHeaderLabels(
                ["Projekt", "Autor", "Zuletzt geändert"]
            )
        if self._qt_available and hasattr(self._table, "setSelectionBehavior"):
            self._table.setSelectionBehavior(
                self._QAbstractItemView.SelectionBehavior.SelectRows
            )
        if self._qt_available and hasattr(self._table, "setSelectionMode"):
            self._table.setSelectionMode(
                self._QAbstractItemView.SelectionMode.SingleSelection
            )
        if hasattr(self._table, "itemSelectionChanged"):
            self._table.itemSelectionChanged.connect(self.on_project_select)
        if hasattr(self._table, "itemClicked"):
            self._table.itemClicked.connect(self.on_project_select)
        if hasattr(self._table, "horizontalHeader"):
            header = self._table.horizontalHeader()
            if hasattr(header, "setStretchLastSection"):
                header.setStretchLastSection(True)
        list_layout.addWidget(self._table)

        details_container = self._QWidget()
        details_layout = self._QVBoxLayout()
        if hasattr(details_container, "setLayout"):
            details_container.setLayout(details_layout)
        details_layout.addWidget(self._QLabel("Details & Vorschau"))
        self._details = self._QTextEdit()
        if hasattr(self._details, "setReadOnly"):
            self._details.setReadOnly(True)
        details_layout.addWidget(self._details)

        if hasattr(splitter, "addWidget"):
            splitter.addWidget(list_container)
            splitter.addWidget(details_container)

    def reset_form(self, *, new_mode: bool = True) -> None:
        if hasattr(self._name_input, "setText"):
            self._name_input.setText("")
        if hasattr(self._author_input, "setText"):
            self._author_input.setText(self._author)
        self._selected_project_id = None
        self._is_new_mode = new_mode
        if hasattr(self._table, "clearSelection"):
            self._table.clearSelection()
        self._show_details(None)
        if new_mode:
            self._set_action_buttons(can_save=True, can_load=False, can_delete=False)
            self._set_status("Neues Projekt vorbereitet. Gib Name und Autor ein.")
        else:
            self._set_action_buttons(can_save=False, can_load=False, can_delete=False)
            self._set_status("Kein Projekt ausgewählt.")

    def _enter_new_mode(self) -> None:
        self.reset_form(new_mode=True)

    def refresh_projects(self) -> None:
        previous_selection = self._selected_project_id
        was_new_mode = self._is_new_mode
        self._project_cache.clear()
        if hasattr(self._table, "setRowCount"):
            self._table.setRowCount(0)
        for record in self._store.list_projects():
            self._project_cache[record.id] = record
            row = self._table.rowCount() if hasattr(self._table, "rowCount") else 0
            if row is None:
                row = 0
            if hasattr(self._table, "insertRow"):
                self._table.insertRow(row)
            name_item = self._QTableWidgetItem(record.name)
            author_item = self._QTableWidgetItem(record.author)
            updated_item = self._QTableWidgetItem(record.updated_at)
            if hasattr(name_item, "setData"):
                name_item.setData(self._Qt.UserRole, record.id)
            if hasattr(self._table, "setItem"):
                self._table.setItem(row, 0, name_item)
                self._table.setItem(row, 1, author_item)
                self._table.setItem(row, 2, updated_item)
        if was_new_mode:
            self._set_action_buttons(can_save=True, can_load=False, can_delete=False)
        elif previous_selection and previous_selection in self._project_cache:
            self._select_project_row(previous_selection)
            self.on_project_select()
        elif self._project_cache:
            first_id = next(iter(self._project_cache))
            self._select_project_row(first_id)
            self.on_project_select()
        else:
            self.reset_form(new_mode=False)
        self._set_status("Liste aktualisiert. Wähle ein Projekt oder speichere ein neues.")

    def on_project_select(self, *_args: object) -> None:
        project_id = self._current_selection_id()
        if not project_id:
            if not self._is_new_mode:
                self._selected_project_id = None
                self._show_details(None)
                self._set_action_buttons(
                    can_save=False, can_load=False, can_delete=False
                )
            return
        record = self._project_cache.get(project_id)
        if not record:
            return
        self._is_new_mode = False
        self._selected_project_id = project_id
        if hasattr(self._name_input, "setText"):
            self._name_input.setText(record.name)
        if hasattr(self._author_input, "setText"):
            self._author_input.setText(record.author)
        self._show_details(record)
        self._set_action_buttons(can_save=True, can_load=True, can_delete=True)
        self._set_status(f"Projekt '{record.name}' ausgewählt.")

    def save_project(self) -> bool:
        name = self._text(self._name_input).strip()
        author = self._text(self._author_input).strip()
        if not name:
            self._show_error("Fehler", "Bitte einen Projektnamen angeben.")
            self._set_status("Speichern abgebrochen: Projektname fehlt.")
            return False
        states = self._plugin_manager.export_all_states()
        ui_state = self._capture_ui_state()
        project_id = None if self._is_new_mode else self._selected_project_id
        try:
            record = self._store.save_project(
                name=name,
                author=author,
                plugin_states=states,
                ui_state=ui_state,
                project_id=project_id,
            )
        except ValueError as exc:
            self._show_error("Fehler", str(exc))
            return False
        self._project_cache[record.id] = record
        self._selected_project_id = record.id
        self._is_new_mode = False
        self.refresh_projects()
        self._show_info("Gespeichert", f"Projekt '{record.name}' wurde gespeichert.")
        self._set_status("Aktueller Plugin-Stand wurde erfolgreich im Projekt abgelegt.")
        return True

    def load_selected_project(self) -> None:
        if not self._selected_project_id:
            self._show_info("Hinweis", "Bitte zuerst ein Projekt auswählen.")
            self._set_status("Kein Projekt ausgewählt zum Laden.")
            return
        record = self._store.load_project(self._selected_project_id)
        if not record:
            self._show_error("Fehler", "Projekt konnte nicht geladen werden.")
            self._set_status("Projekt konnte nicht geladen werden.")
            return
        self._plugin_manager.import_all_states(record.plugin_states)
        self._apply_ui_state(record.ui_state)
        missing_plugins = [
            self._spec_lookup.get(plugin_id, plugin_id)
            for plugin_id in record.plugin_states
            if plugin_id not in self._plugin_manager.plugins
        ]
        if missing_plugins:
            self._show_warning(
                "Unvollständig",
                "\n".join(
                    [
                        "Einige Plugins sind nicht installiert und wurden übersprungen:",
                        ", ".join(missing_plugins),
                    ]
                ),
            )
            self._set_status(
                "Projekt geladen, aber einige Plugins fehlen in dieser Installation."
            )
        self._show_info("Geladen", f"Projekt '{record.name}' wurde geladen.")
        self._set_status("Projektzustand auf alle Plugins angewendet.")

    def delete_selected_project(self) -> None:
        if not self._selected_project_id:
            self._show_info("Hinweis", "Bitte ein Projekt auswählen.")
            return
        record = self._project_cache.get(self._selected_project_id)
        if not record:
            return
        result = self._QMessageBox.question(
            self.widget,
            "Löschen bestätigen",
            f"Soll das Projekt '{record.name}' wirklich gelöscht werden?",
        )
        if result != self._QMessageBox.Yes:
            return
        if self._store.delete_project(record.id):
            self._show_info("Gelöscht", f"Projekt '{record.name}' wurde entfernt.")
            self._selected_project_id = None
            self._is_new_mode = False
            self.refresh_projects()
            self._set_status("Projekt gelöscht. Wähle einen anderen Eintrag oder speichere neu.")
        else:
            self._show_error("Fehler", "Projekt konnte nicht gelöscht werden.")
            self._set_status("Löschen fehlgeschlagen.")

    def _capture_ui_state(self) -> dict[str, Any]:
        if not self._tab_widget or not hasattr(self._tab_widget, "currentIndex"):
            return {}
        current = self._tab_widget.currentIndex()
        return {"active_tab": int(current)}

    def _apply_ui_state(self, state: dict[str, Any]) -> None:
        if not self._tab_widget or not isinstance(state, dict):
            return
        active_tab = state.get("active_tab")
        if not isinstance(active_tab, int):
            return
        if hasattr(self._tab_widget, "count"):
            count = self._tab_widget.count()
            if count:
                active_tab = max(0, min(active_tab, count - 1))
        if hasattr(self._tab_widget, "setCurrentIndex"):
            self._tab_widget.setCurrentIndex(active_tab)

    def _select_project_row(self, project_id: str) -> None:
        if not self._qt_available or not hasattr(self._table, "rowCount"):
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if not item or not hasattr(item, "data"):
                continue
            if item.data(self._Qt.UserRole) == project_id:
                if hasattr(self._table, "selectRow"):
                    self._table.selectRow(row)
                return

    def _current_selection_id(self) -> str | None:
        if hasattr(self._table, "currentRow") and hasattr(self._table, "item"):
            row = self._table.currentRow()
            if row is not None and row >= 0:
                item = self._table.item(row, 0)
                if item and hasattr(item, "data"):
                    return item.data(self._Qt.UserRole)
        if hasattr(self._table, "selectedItems"):
            selected = self._table.selectedItems()
            if not selected:
                return None
            item = selected[0]
            if hasattr(item, "data"):
                return item.data(self._Qt.UserRole)
        return None

    def _set_action_buttons(
        self, *, can_save: bool, can_load: bool, can_delete: bool
    ) -> None:
        if hasattr(self._save_button, "setEnabled"):
            self._save_button.setEnabled(can_save)
        if hasattr(self._load_button, "setEnabled"):
            self._load_button.setEnabled(can_load)
        if hasattr(self._delete_button, "setEnabled"):
            self._delete_button.setEnabled(can_delete)

    def _show_details(self, record: ProjectRecord | None) -> None:
        if record is None:
            text = "Kein Projekt ausgewählt."
        else:
            lines = [
                f"Name: {record.name}",
                f"Autor: {record.author or '–'}",
                f"Erstellt: {record.created_at or '–'}",
                f"Aktualisiert: {record.updated_at or '–'}",
                "",
                "Plugin-Zustände:",
            ]
            if not record.plugin_states:
                lines.append("  (keine Zustände gespeichert)")
            else:
                for identifier, state in record.plugin_states.items():
                    name = self._spec_lookup.get(identifier) or identifier
                    pretty_state = json.dumps(state, indent=2, ensure_ascii=False)
                    lines.append(f"• {name}")
                    lines.append(pretty_state)
                    lines.append("")
            text = "\n".join(lines)
        if hasattr(self._details, "setPlainText"):
            self._details.setPlainText(text)

    def _set_status(self, message: str) -> None:
        if hasattr(self._status_label, "setText"):
            self._status_label.setText(message)

    def _text(self, widget: object) -> str:
        if hasattr(widget, "text"):
            return str(widget.text())
        return ""

    def _show_info(self, title: str, message: str) -> None:
        self._QMessageBox.information(self.widget, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        self._QMessageBox.warning(self.widget, title, message)

    def _show_error(self, title: str, message: str) -> None:
        self._QMessageBox.critical(self.widget, title, message)
