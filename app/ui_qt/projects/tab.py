"""Qt tab for managing projects and plugin states."""
from __future__ import annotations

import getpass
import json
import logging
from typing import Any, Sequence

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QWidget,
)

from app.core.projects.store import ProjectRecord, ProjectStore
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.plugins.registry import QtPluginSpec, get_plugins
from app.ui_qt.projects.state import DirtyStateTracker, PluginStateCoordinator
from app.ui_qt.ui_helpers import (
    create_button_row,
    create_section_header,
    make_grid,
    make_hbox,
    make_vbox,
)

logger = logging.getLogger(__name__)


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
        main_window: object | None = None,
    ) -> None:
        self._tab_widget = tab_widget
        self._plugin_manager = plugin_manager
        self._store = store or ProjectStore()
        self._author = author or getpass.getuser()
        self._plugin_specs = plugin_specs or get_plugins()
        self._spec_lookup = {spec.identifier: spec.name for spec in self._plugin_specs}

        self._project_cache: dict[str, ProjectRecord] = {}
        self._selected_project_id: str | None = None
        self._active_project_id: str | None = None
        self._dirty = False
        self._is_new_mode = False
        self._suppress_project_updates = False

        self._state_coordinator = PluginStateCoordinator(
            plugin_manager=self._plugin_manager,
            plugin_specs=self._plugin_specs,
        )
        self._dirty_tracker = DirtyStateTracker(self._mark_dirty)

        self.widget = QWidget()
        self._build_ui()
        self._insert_tab()
        self.refresh_projects()
        self._install_close_handler(main_window)

    def on_plugins_loaded(self) -> None:
        for plugin in self._plugin_manager.plugins.values():
            widget = getattr(plugin, "widget", None)
            if widget is not None:
                self._dirty_tracker.attach_widget(widget)

    def _install_close_handler(self, main_window: object | None) -> None:
        if main_window is None:
            return
        class _CloseEventFilter(QObject):
            def __init__(self, handler: "ProjectsTab") -> None:
                super().__init__()
                self._handler = handler

            def eventFilter(self, _obj: object, event: object) -> bool:  # noqa: N802 - Qt API
                if event.type() == QEvent.Type.Close:
                    if not self._handler.confirm_unsaved_changes("Programm beenden"):
                        event.ignore()
                        return True
                return False

        self._close_filter = _CloseEventFilter(self)
        main_window.installEventFilter(self._close_filter)

    def _insert_tab(self) -> None:
        if hasattr(self._tab_widget, "insertTab"):
            self._tab_widget.insertTab(0, self.widget, "Projekte")
        else:
            self._tab_widget.addTab(self.widget, "Projekte")

    def _build_ui(self) -> None:
        layout = make_vbox()
        self.widget.setLayout(layout)

        layout.addWidget(create_section_header("Projektverwaltung"))

        splitter = QSplitter()
        layout.addWidget(splitter)

        list_container = QWidget()
        list_layout = make_vbox()
        list_container.setLayout(list_layout)
        list_layout.addWidget(QLabel("Projektliste"))
        self._project_list = QListWidget()
        self._project_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._project_list.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._project_list.currentItemChanged.connect(self._on_project_selected)
        list_layout.addWidget(self._project_list)

        details_container = QWidget()
        details_layout = make_vbox()
        details_container.setLayout(details_layout)

        details_layout.addWidget(QLabel("Projektdetails"))
        form = QWidget()
        form_layout = make_grid()
        form.setLayout(form_layout)

        self._name_input = QLineEdit()
        self._author_input = QLineEdit()
        self._author_input.setText(self._author)
        self._description_input = QTextEdit()
        self._metadata_input = QTextEdit()

        form_layout.addWidget(QLabel("Name:"), 0, 0)
        form_layout.addWidget(self._name_input, 0, 1)
        form_layout.addWidget(QLabel("Autor:"), 1, 0)
        form_layout.addWidget(self._author_input, 1, 1)
        form_layout.addWidget(QLabel("Beschreibung:"), 2, 0)
        form_layout.addWidget(self._description_input, 2, 1)
        form_layout.addWidget(QLabel("Metadaten (JSON):"), 3, 0)
        form_layout.addWidget(self._metadata_input, 3, 1)

        details_layout.addWidget(form)

        self._status_label = QLabel("Kein Projekt ausgewählt.")
        details_layout.addWidget(self._status_label)

        actions_container = QWidget()
        self._new_button = QPushButton("Neu")
        self._save_button = QPushButton("Speichern")
        self._load_button = QPushButton("Laden")
        self._delete_button = QPushButton("Löschen")
        actions_layout = create_button_row(
            [self._new_button, self._save_button, self._load_button, self._delete_button]
        )
        actions_container.setLayout(actions_layout)

        details_layout.addWidget(actions_container)

        self._new_button.clicked.connect(self._enter_new_mode)
        self._save_button.clicked.connect(self.save_project)
        self._load_button.clicked.connect(self.load_selected_project)
        self._delete_button.clicked.connect(self.delete_selected_project)

        splitter.addWidget(list_container)
        splitter.addWidget(details_container)

        for widget in (
            self._name_input,
            self._author_input,
            self._description_input,
            self._metadata_input,
        ):
            widget.textChanged.connect(self._on_project_fields_changed)

    def refresh_projects(self) -> None:
        previous_selection = self._selected_project_id
        records = self._store.list_projects()
        self._project_cache = {record.id: record for record in records}
        self._project_list.blockSignals(True)
        self._project_list.clear()
        for record in records:
            item = QListWidgetItem(self._format_project_label(record))
            item.setData(self._user_role(), record.id)
            self._project_list.addItem(item)
        self._project_list.blockSignals(False)
        if previous_selection and previous_selection in self._project_cache:
            self._select_project_by_id(previous_selection)
        elif self._project_cache:
            first_id = next(iter(self._project_cache))
            self._select_project_by_id(first_id)
        else:
            self._clear_form(reset_dirty=False)
        self._update_action_buttons()

    def _select_project_by_id(self, project_id: str) -> None:
        for row in range(self._project_list.count()):
            item = self._project_list.item(row)
            if item is None:
                continue
            if item.data(self._user_role()) == project_id:
                self._project_list.setCurrentRow(row)
                return

    def _on_project_selected(self, current: object, _previous: object) -> None:
        project_id = None
        if current is not None and hasattr(current, "data"):
            project_id = current.data(self._user_role())
        if not project_id:
            self._selected_project_id = None
            self._clear_form(reset_dirty=False)
            self._update_action_buttons()
            self._set_status("Kein Projekt ausgewählt.")
            return
        record = self._project_cache.get(project_id)
        if record is None:
            return
        self._selected_project_id = project_id
        self._is_new_mode = False
        self._load_record_into_form(record)
        self._update_action_buttons()
        self._set_status(f"Projekt '{record.name}' ausgewählt.")

    def _load_record_into_form(self, record: ProjectRecord) -> None:
        self._suppress_project_updates = True
        try:
            self._name_input.setText(record.name)
            self._author_input.setText(record.author)
            self._description_input.setPlainText(record.description)
            self._metadata_input.setPlainText(
                json.dumps(record.metadata, indent=2, ensure_ascii=False)
            )
        finally:
            self._suppress_project_updates = False

    def _clear_form(self, *, reset_dirty: bool = True) -> None:
        self._suppress_project_updates = True
        try:
            self._name_input.setText("")
            self._author_input.setText(self._author)
            self._description_input.setPlainText("")
            self._metadata_input.setPlainText("{}")
        finally:
            self._suppress_project_updates = False
        if reset_dirty:
            self._set_dirty(False)

    def _enter_new_mode(self) -> None:
        if not self.confirm_unsaved_changes("Neues Projekt"):
            return
        self._is_new_mode = True
        self._selected_project_id = None
        self._project_list.blockSignals(True)
        self._project_list.setCurrentRow(-1)
        self._project_list.blockSignals(False)
        self._clear_form(reset_dirty=False)
        self._set_status("Neues Projekt vorbereitet. Bitte Projektdaten eingeben.")
        self._update_action_buttons()

    def save_project(self) -> bool:
        name = self._text(self._name_input).strip()
        author = self._text(self._author_input).strip()
        description = self._plain_text(self._description_input).strip()
        metadata = self._parse_metadata()
        if metadata is None:
            return False
        if not name:
            self._show_error("Fehler", "Bitte einen Projektnamen angeben.")
            self._set_status("Speichern abgebrochen: Projektname fehlt.")
            return False
        with self._dirty_tracker.paused():
            plugin_states, errors = self._state_coordinator.collect_states()
        if errors:
            self._show_error(
                "Fehler",
                "Einige Plugins konnten nicht gespeichert werden:\n" + "\n".join(errors),
            )
            self._set_status("Speichern abgebrochen: Plugin-Zustände unvollständig.")
            return False
        project_id = None if self._is_new_mode else self._selected_project_id
        try:
            record = self._store.save_project(
                name=name,
                author=author,
                description=description,
                metadata=metadata,
                plugin_states=plugin_states,
                ui_state=self._capture_ui_state(),
                project_id=project_id,
            )
        except ValueError as exc:
            self._show_error("Fehler", str(exc))
            return False
        self._selected_project_id = record.id
        self._active_project_id = record.id
        self._is_new_mode = False
        self.refresh_projects()
        self._set_dirty(False)
        self._show_info("Gespeichert", f"Projekt '{record.name}' wurde gespeichert.")
        self._set_status(
            f"Projekt gespeichert. {len(plugin_states)} Plugin-Zustände wurden erfasst."
        )
        logger.info("Project %s saved with %s plugin states.", record.id, len(plugin_states))
        return True

    def load_selected_project(self) -> None:
        if not self._selected_project_id:
            self._show_info("Hinweis", "Bitte zuerst ein Projekt auswählen.")
            self._set_status("Kein Projekt ausgewählt zum Laden.")
            return
        if not self.confirm_unsaved_changes("Projekt laden"):
            return
        record = self._store.load_project(self._selected_project_id)
        if not record:
            self._show_error("Fehler", "Projekt konnte nicht geladen werden.")
            self._set_status("Projekt konnte nicht geladen werden.")
            return
        with self._dirty_tracker.paused():
            missing, unknown, errors = self._state_coordinator.apply_states(record.plugin_states)
            self._apply_ui_state(record.ui_state)
        self._active_project_id = record.id
        self._set_dirty(False)
        if errors:
            self._show_warning(
                "Unvollständig",
                "Einige Plugins konnten nicht geladen werden:\n" + "\n".join(errors),
            )
        if missing:
            missing_names = [self._spec_lookup.get(pid, pid) for pid in missing]
            self._show_warning(
                "Fehlende Zustände",
                "Für folgende Plugins fehlen gespeicherte Zustände:\n"
                + ", ".join(missing_names),
            )
        if unknown:
            unknown_names = [self._spec_lookup.get(pid, pid) for pid in unknown]
            self._show_warning(
                "Nicht installierte Plugins",
                "Diese Plugins sind nicht installiert und wurden übersprungen:\n"
                + ", ".join(unknown_names),
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
        if not self.confirm_unsaved_changes("Projekt löschen"):
            return
        result = QMessageBox.question(
            self.widget,
            "Löschen bestätigen",
            f"Soll das Projekt '{record.name}' wirklich gelöscht werden?",
            self._message_box_button("Yes") | self._message_box_button("No"),
            self._message_box_button("No"),
        )
        if result != self._message_box_button("Yes"):
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

    def confirm_unsaved_changes(self, action_label: str) -> bool:
        if not self._dirty:
            return True
        result = self._prompt_unsaved_changes(action_label)
        if result == "save":
            return self.save_project()
        if result == "discard":
            self._set_dirty(False)
            return True
        return False

    def _prompt_unsaved_changes(self, action_label: str) -> str:
        buttons = (
            self._message_box_button("Save")
            | self._message_box_button("Discard")
            | self._message_box_button("Cancel")
        )
        default_button = self._message_box_button("Cancel")
        result = QMessageBox.question(
            self.widget,
            "Ungespeicherte Änderungen",
            f"Es gibt ungespeicherte Änderungen. Aktion '{action_label}' fortsetzen?",
            buttons,
            default_button,
        )
        if result == self._message_box_button("Save"):
            return "save"
        if result == self._message_box_button("Discard"):
            return "discard"
        return "cancel"

    def _message_box_button(self, name: str) -> object:
        return getattr(QMessageBox.StandardButton, name, QMessageBox.StandardButton.NoButton)

    def _on_project_fields_changed(self, *_args: object) -> None:
        if self._suppress_project_updates:
            return
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if self._dirty:
            return
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        if dirty:
            self._set_status("Projekt geändert (ungespeichert).")
        else:
            if self._active_project_id:
                record = self._project_cache.get(self._active_project_id)
                name = record.name if record else "(unbekannt)"
                self._set_status(f"Projekt '{name}' gespeichert.")
            else:
                self._set_status("Kein ungespeichertes Projekt.")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        has_selection = bool(self._selected_project_id)
        self._save_button.setEnabled(True)
        self._load_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)

    def _format_project_label(self, record: ProjectRecord) -> str:
        updated = record.updated_at or "–"
        return f"{record.name}  ·  {updated}"

    def _capture_ui_state(self) -> dict[str, Any]:
        if not self._tab_widget:
            return {}
        current = self._tab_widget.currentIndex()
        return {"active_tab": int(current)}

    def _apply_ui_state(self, state: dict[str, Any]) -> None:
        if not self._tab_widget or not isinstance(state, dict):
            return
        active_tab = state.get("active_tab")
        if not isinstance(active_tab, int):
            return
        count = self._tab_widget.count()
        if count:
            active_tab = max(0, min(active_tab, count - 1))
        self._tab_widget.setCurrentIndex(active_tab)

    def _user_role(self) -> int:
        return int(Qt.ItemDataRole.UserRole)

    def _text(self, widget: object) -> str:
        return str(widget.text())

    def _plain_text(self, widget: object) -> str:
        return str(widget.toPlainText())

    def _parse_metadata(self) -> dict[str, Any] | None:
        raw = self._plain_text(self._metadata_input).strip() or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._show_error("Fehler", f"Metadaten sind ungültiges JSON: {exc}")
            return None
        if not isinstance(data, dict):
            self._show_error("Fehler", "Metadaten müssen ein JSON-Objekt sein.")
            return None
        return data

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self.widget, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self.widget, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self.widget, title, message)
