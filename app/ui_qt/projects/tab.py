"""Qt tab for managing projects and plugin states."""
from __future__ import annotations

import getpass
import importlib.util
import json
import logging
from typing import Any, Sequence

from app.core.projects.store import ProjectRecord, ProjectStore
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.plugins.registry import QtPluginSpec, get_plugins
from app.ui_qt.projects.state import DirtyStateTracker, PluginStateCoordinator

logger = logging.getLogger(__name__)


class _StubWidget:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.clicked = _StubSignal()
        self.currentItemChanged = _StubSignal()
        self.textChanged = _StubSignal()
        self.itemSelectionChanged = _StubSignal()
        return None

    def __getattr__(self, _name: str) -> Any:
        if _name == "itemSelectionChanged" or _name.endswith("Changed"):
            return _StubSignal()

        def _noop(*_args: object, **_kwargs: object) -> Any:
            return None

        return _noop


class _StubListItem:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self._data: dict[int, object] = {}

    def text(self) -> str:
        return self._text

    def setData(self, role: int, value: object) -> None:
        self._data[role] = value

    def data(self, role: int) -> object:
        return self._data.get(role)


class _StubListWidget:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self._items: list[_StubListItem] = []
        self._current_row = -1
        self.currentItemChanged = _StubSignal()

    def addItem(self, item: _StubListItem) -> None:
        self._items.append(item)

    def clear(self) -> None:
        self._items.clear()
        self._current_row = -1

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> _StubListItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def setCurrentRow(self, index: int) -> None:
        self._current_row = index

    def currentItem(self) -> _StubListItem | None:
        return self.item(self._current_row)

    def blockSignals(self, _state: bool) -> None:
        return None


class _StubSignal:
    def connect(self, *_args: object, **_kwargs: object) -> None:
        return None


class _StubQt:
    AlignLeft = 0
    AlignVCenter = 0
    UserRole = 0


class _StubMessageBox:
    class StandardButton:
        Save = 0
        Discard = 1
        Cancel = 2
        Yes = 3
        No = 4

    Save = 0
    Discard = 1
    Cancel = 2
    Yes = 3
    No = 4

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
        return _StubMessageBox.Cancel


class _StubEvent:
    class Type:
        Close = 0


class _StubQObject:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        return None

    def eventFilter(self, *_args: object, **_kwargs: object) -> bool:
        return False


def _resolve_qt_widgets() -> tuple[bool, dict[str, Any]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtCore import Qt, QObject, QEvent
        from PyQt6.QtWidgets import (
            QAbstractItemView,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        return True, {
            "Qt": Qt,
            "QObject": QObject,
            "QEvent": QEvent,
            "QAbstractItemView": QAbstractItemView,
            "QGridLayout": QGridLayout,
            "QHBoxLayout": QHBoxLayout,
            "QLabel": QLabel,
            "QLineEdit": QLineEdit,
            "QListWidget": QListWidget,
            "QListWidgetItem": QListWidgetItem,
            "QMessageBox": QMessageBox,
            "QPushButton": QPushButton,
            "QSplitter": QSplitter,
            "QTextEdit": QTextEdit,
            "QVBoxLayout": QVBoxLayout,
            "QWidget": QWidget,
        }
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtCore import Qt, QObject, QEvent
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        return True, {
            "Qt": Qt,
            "QObject": QObject,
            "QEvent": QEvent,
            "QAbstractItemView": QAbstractItemView,
            "QGridLayout": QGridLayout,
            "QHBoxLayout": QHBoxLayout,
            "QLabel": QLabel,
            "QLineEdit": QLineEdit,
            "QListWidget": QListWidget,
            "QListWidgetItem": QListWidgetItem,
            "QMessageBox": QMessageBox,
            "QPushButton": QPushButton,
            "QSplitter": QSplitter,
            "QTextEdit": QTextEdit,
            "QVBoxLayout": QVBoxLayout,
            "QWidget": QWidget,
        }
    return False, {
        "Qt": _StubQt,
        "QObject": _StubQObject,
        "QEvent": _StubEvent,
        "QAbstractItemView": _StubWidget,
        "QGridLayout": _StubWidget,
        "QHBoxLayout": _StubWidget,
        "QLabel": _StubWidget,
        "QLineEdit": _StubWidget,
        "QListWidget": _StubListWidget,
        "QListWidgetItem": _StubListItem,
        "QMessageBox": _StubMessageBox,
        "QPushButton": _StubWidget,
        "QSplitter": _StubWidget,
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
        main_window: object | None = None,
    ) -> None:
        self._qt_available, widgets = _resolve_qt_widgets()
        self._Qt = widgets["Qt"]
        self._QObject = widgets["QObject"]
        self._QEvent = widgets["QEvent"]
        self._QAbstractItemView = widgets["QAbstractItemView"]
        self._QGridLayout = widgets["QGridLayout"]
        self._QHBoxLayout = widgets["QHBoxLayout"]
        self._QLabel = widgets["QLabel"]
        self._QLineEdit = widgets["QLineEdit"]
        self._QListWidget = widgets["QListWidget"]
        self._QListWidgetItem = widgets["QListWidgetItem"]
        self._QMessageBox = widgets["QMessageBox"]
        self._QPushButton = widgets["QPushButton"]
        self._QSplitter = widgets["QSplitter"]
        self._QTextEdit = widgets["QTextEdit"]
        self._QVBoxLayout = widgets["QVBoxLayout"]
        self._QWidget = widgets["QWidget"]

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

        self.widget = self._QWidget()
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
        if not self._qt_available or main_window is None:
            return
        if hasattr(main_window, "installEventFilter"):
            class _CloseEventFilter(self._QObject):  # type: ignore[misc]
                def __init__(self, handler: "ProjectsTab") -> None:
                    super().__init__()
                    self._handler = handler

                def eventFilter(self, _obj: object, event: object) -> bool:  # noqa: N802 - Qt API
                    if hasattr(event, "type"):
                        close_type = self._handler._QEvent.Type.Close
                        if event.type() == close_type:
                            if not self._handler.confirm_unsaved_changes("Programm beenden"):
                                if hasattr(event, "ignore"):
                                    event.ignore()
                                return True
                    return False

            self._close_filter = _CloseEventFilter(self)
            main_window.installEventFilter(self._close_filter)

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

        splitter = self._QSplitter()
        if hasattr(layout, "addWidget"):
            layout.addWidget(splitter)

        list_container = self._QWidget()
        list_layout = self._QVBoxLayout()
        if hasattr(list_container, "setLayout"):
            list_container.setLayout(list_layout)
        list_layout.addWidget(self._QLabel("Projektliste"))
        self._project_list = self._QListWidget()
        if self._qt_available and hasattr(self._project_list, "setSelectionMode"):
            self._project_list.setSelectionMode(
                self._QAbstractItemView.SelectionMode.SingleSelection
            )
        if self._qt_available and hasattr(self._project_list, "setEditTriggers"):
            self._project_list.setEditTriggers(
                self._QAbstractItemView.EditTrigger.NoEditTriggers
            )
        if hasattr(self._project_list, "currentItemChanged"):
            self._project_list.currentItemChanged.connect(self._on_project_selected)
        list_layout.addWidget(self._project_list)

        details_container = self._QWidget()
        details_layout = self._QVBoxLayout()
        if hasattr(details_container, "setLayout"):
            details_container.setLayout(details_layout)

        details_layout.addWidget(self._QLabel("Projektdetails"))
        form = self._QWidget()
        form_layout = self._QGridLayout()
        if hasattr(form, "setLayout"):
            form.setLayout(form_layout)

        self._name_input = self._QLineEdit()
        self._author_input = self._QLineEdit()
        if hasattr(self._author_input, "setText"):
            self._author_input.setText(self._author)
        self._description_input = self._QTextEdit()
        self._metadata_input = self._QTextEdit()

        form_layout.addWidget(self._QLabel("Name:"), 0, 0)
        form_layout.addWidget(self._name_input, 0, 1)
        form_layout.addWidget(self._QLabel("Autor:"), 1, 0)
        form_layout.addWidget(self._author_input, 1, 1)
        form_layout.addWidget(self._QLabel("Beschreibung:"), 2, 0)
        form_layout.addWidget(self._description_input, 2, 1)
        form_layout.addWidget(self._QLabel("Metadaten (JSON):"), 3, 0)
        form_layout.addWidget(self._metadata_input, 3, 1)

        details_layout.addWidget(form)

        self._status_label = self._QLabel("Kein Projekt ausgewählt.")
        details_layout.addWidget(self._status_label)

        actions_container = self._QWidget()
        actions_layout = self._QHBoxLayout()
        if hasattr(actions_container, "setLayout"):
            actions_container.setLayout(actions_layout)

        self._new_button = self._QPushButton("Neu")
        self._save_button = self._QPushButton("Speichern")
        self._load_button = self._QPushButton("Laden")
        self._delete_button = self._QPushButton("Löschen")

        actions_layout.addWidget(self._new_button)
        actions_layout.addWidget(self._save_button)
        actions_layout.addWidget(self._load_button)
        actions_layout.addWidget(self._delete_button)

        details_layout.addWidget(actions_container)

        if hasattr(self._new_button, "clicked"):
            self._new_button.clicked.connect(self._enter_new_mode)
        if hasattr(self._save_button, "clicked"):
            self._save_button.clicked.connect(self.save_project)
        if hasattr(self._load_button, "clicked"):
            self._load_button.clicked.connect(self.load_selected_project)
        if hasattr(self._delete_button, "clicked"):
            self._delete_button.clicked.connect(self.delete_selected_project)

        if hasattr(splitter, "addWidget"):
            splitter.addWidget(list_container)
            splitter.addWidget(details_container)

        for widget in (
            self._name_input,
            self._author_input,
            self._description_input,
            self._metadata_input,
        ):
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._on_project_fields_changed)

    def refresh_projects(self) -> None:
        previous_selection = self._selected_project_id
        records = self._store.list_projects()
        self._project_cache = {record.id: record for record in records}
        if hasattr(self._project_list, "blockSignals"):
            self._project_list.blockSignals(True)
        if hasattr(self._project_list, "clear"):
            self._project_list.clear()
        for record in records:
            item = self._QListWidgetItem(self._format_project_label(record))
            if hasattr(item, "setData"):
                item.setData(self._user_role(), record.id)
            if hasattr(self._project_list, "addItem"):
                self._project_list.addItem(item)
        if hasattr(self._project_list, "blockSignals"):
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
        if not self._qt_available:
            self._selected_project_id = project_id
            return
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
            if hasattr(self._name_input, "setText"):
                self._name_input.setText(record.name)
            if hasattr(self._author_input, "setText"):
                self._author_input.setText(record.author)
            if hasattr(self._description_input, "setPlainText"):
                self._description_input.setPlainText(record.description)
            if hasattr(self._metadata_input, "setPlainText"):
                self._metadata_input.setPlainText(
                    json.dumps(record.metadata, indent=2, ensure_ascii=False)
                )
        finally:
            self._suppress_project_updates = False

    def _clear_form(self, *, reset_dirty: bool = True) -> None:
        self._suppress_project_updates = True
        try:
            if hasattr(self._name_input, "setText"):
                self._name_input.setText("")
            if hasattr(self._author_input, "setText"):
                self._author_input.setText(self._author)
            if hasattr(self._description_input, "setPlainText"):
                self._description_input.setPlainText("")
            if hasattr(self._metadata_input, "setPlainText"):
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
        if hasattr(self._project_list, "blockSignals"):
            self._project_list.blockSignals(True)
        if hasattr(self._project_list, "setCurrentRow"):
            self._project_list.setCurrentRow(-1)
        if hasattr(self._project_list, "blockSignals"):
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
        result = self._QMessageBox.question(
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
        result = self._QMessageBox.question(
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
        if hasattr(self._QMessageBox, "StandardButton"):
            return getattr(self._QMessageBox.StandardButton, name, 0)
        return getattr(self._QMessageBox, name, 0)

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
        if hasattr(self._save_button, "setEnabled"):
            self._save_button.setEnabled(True)
        if hasattr(self._load_button, "setEnabled"):
            self._load_button.setEnabled(has_selection)
        if hasattr(self._delete_button, "setEnabled"):
            self._delete_button.setEnabled(has_selection)

    def _format_project_label(self, record: ProjectRecord) -> str:
        updated = record.updated_at or "–"
        return f"{record.name}  ·  {updated}"

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

    def _user_role(self) -> int:
        if hasattr(self._Qt, "ItemDataRole"):
            return self._Qt.ItemDataRole.UserRole
        return self._Qt.UserRole

    def _text(self, widget: object) -> str:
        if hasattr(widget, "text"):
            return str(widget.text())
        return ""

    def _plain_text(self, widget: object) -> str:
        if hasattr(widget, "toPlainText"):
            return str(widget.toPlainText())
        return ""

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
        if hasattr(self._status_label, "setText"):
            self._status_label.setText(message)

    def _show_info(self, title: str, message: str) -> None:
        self._QMessageBox.information(self.widget, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        self._QMessageBox.warning(self.widget, title, message)

    def _show_error(self, title: str, message: str) -> None:
        self._QMessageBox.critical(self.widget, title, message)
