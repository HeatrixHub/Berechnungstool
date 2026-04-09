"""Qt tab for managing projects and plugin states."""
from __future__ import annotations

import getpass
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QSplitter,
    QTextEdit,
    QWidget,
)

from app.core.projects.export import (
    EXPORT_FILE_SUFFIX,
    build_project_export_payload,
    export_project_to_file,
)
from app.core.projects.import_service import ProjectImportError, ProjectImportService
from app.core.projects.store import ProjectRecord, ProjectStore
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.projects.insulation_import_dialog import InsulationImportDialog
from app.ui_qt.plugins.registry import QtPluginSpec, get_plugins
from app.ui_qt.projects.state import DirtyStateTracker, PluginStateCoordinator
from app.ui_qt.ui_helpers import (
    apply_form_layout_defaults,
    create_button_row,
    create_page_layout,
    make_grid,
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
        on_project_loaded: Callable[[], None] | None = None,
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
        self._workspace_plugin_states: dict[str, dict[str, Any]] = {}
        self._active_form_snapshot: dict[str, str] = self._default_form_snapshot()
        self._preview_mode = False
        self._dirty = False
        self._suppress_project_updates = False
        self._on_project_loaded = on_project_loaded

        self._state_coordinator = PluginStateCoordinator(
            plugin_manager=self._plugin_manager,
            plugin_specs=self._plugin_specs,
        )
        self._import_service = ProjectImportService()
        self._dirty_tracker = DirtyStateTracker(self._mark_dirty)

        self.widget = QWidget()
        self._build_ui()
        self._insert_tab()
        self.refresh_projects()
        self._activate_unsaved_workspace(reset_plugins=False)
        self._install_close_handler(main_window)

    def on_plugins_loaded(self) -> None:
        for plugin in self._plugin_manager.plugins.values():
            widget = getattr(plugin, "widget", None)
            if widget is not None:
                self._dirty_tracker.attach_widget(widget)
        with self._dirty_tracker.paused():
            states, _errors = self._state_coordinator.collect_states()
        self._workspace_plugin_states = states
        self._activate_unsaved_workspace(reset_plugins=False, reset_dirty=False)

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
        layout = create_page_layout(self.widget, "Projektverwaltung", show_logo=True)

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

        form_layout.addWidget(QLabel("Name:"), 0, 0)
        form_layout.addWidget(self._name_input, 0, 1)
        form_layout.addWidget(QLabel("Autor:"), 1, 0)
        form_layout.addWidget(self._author_input, 1, 1)
        form_layout.addWidget(QLabel("Beschreibung:"), 2, 0)
        form_layout.addWidget(self._description_input, 2, 1)

        apply_form_layout_defaults(form_layout)
        details_layout.addWidget(form)

        self._active_project_label = QLabel("Aktiv: Ungespeichertes Projekt")
        details_layout.addWidget(self._active_project_label)
        self._status_label = QLabel("Ungespeicherte Arbeitsfläche aktiv.")
        details_layout.addWidget(self._status_label)

        actions_container = QWidget()
        self._new_button = QPushButton("Neu")
        self._save_button = QPushButton("Speichern")
        self._import_button = QPushButton("Importieren")
        self._export_button = QPushButton("Exportieren")
        self._load_button = QPushButton("Laden")
        self._delete_button = QPushButton("Löschen")
        actions_layout = create_button_row(
            [
                self._new_button,
                self._save_button,
                self._import_button,
                self._export_button,
                self._load_button,
                self._delete_button,
            ]
        )
        actions_container.setLayout(actions_layout)

        details_layout.addWidget(actions_container)

        self._new_button.clicked.connect(self._enter_new_mode)
        self._save_button.clicked.connect(self.save_project)
        self._import_button.clicked.connect(self.import_project_file)
        self._export_button.clicked.connect(self.export_active_project)
        self._load_button.clicked.connect(self.load_selected_project)
        self._delete_button.clicked.connect(self.delete_selected_project)

        splitter.addWidget(list_container)
        splitter.addWidget(details_container)

        for widget in (
            self._name_input,
            self._author_input,
            self._description_input,
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
        else:
            self._selected_project_id = None
            self._project_list.setCurrentRow(-1)
        self._update_active_project_label()
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
            self._show_active_form_snapshot()
            self._update_action_buttons()
            self._set_status("Keine Auswahl in der Projektliste.")
            return
        record = self._project_cache.get(project_id)
        if record is None:
            return
        self._selected_project_id = project_id
        if self._selected_project_id == self._active_project_id:
            self._show_active_form_snapshot()
            self._set_status(f"Projekt '{record.name}' ausgewählt (aktiv geladen).")
        else:
            self._preview_selected_record(record)
            self._set_status(f"Projekt '{record.name}' ausgewählt (nur Vorschau).")
        self._update_action_buttons()

    def _preview_selected_record(self, record: ProjectRecord) -> None:
        """Aktualisiert nur die Formularfelder für die Listen-Vorschau."""
        self._capture_active_form_snapshot()
        with self._dirty_tracker.paused():
            self._load_record_into_form(record)
        self._set_preview_mode(True)

    def _show_active_form_snapshot(self) -> None:
        with self._dirty_tracker.paused():
            self._load_form_snapshot(self._active_form_snapshot)
        self._set_preview_mode(False)

    def _load_record_into_form(self, record: ProjectRecord) -> None:
        self._suppress_project_updates = True
        try:
            self._name_input.setText(record.name)
            self._author_input.setText(record.author)
            self._description_input.setPlainText(record.description)
        finally:
            self._suppress_project_updates = False

    def _clear_form(self, *, reset_dirty: bool = True) -> None:
        self._suppress_project_updates = True
        try:
            self._name_input.setText("")
            self._author_input.setText(self._author)
            self._description_input.setPlainText("")
        finally:
            self._suppress_project_updates = False
        self._active_form_snapshot = self._capture_form_snapshot()
        if reset_dirty:
            self._set_dirty(False)

    def _enter_new_mode(self) -> None:
        if not self.confirm_unsaved_changes("Neues Projekt"):
            return
        self._activate_unsaved_workspace(reset_plugins=True)
        self._set_status("Ungespeicherte Arbeitsfläche vorbereitet.")

    def save_project(self) -> bool:
        if self._is_previewing_foreign_project():
            self._show_warning(
                "Speichern gesperrt",
                "Die angezeigten Projektdaten sind nur Vorschau und können nicht gespeichert werden.",
            )
            self._set_status("Speichern gesperrt: Nur Vorschau eines anderen Projekts aktiv.")
            return False
        self._capture_active_form_snapshot()
        return self._save_project_from_form_snapshot()

    def _save_project_from_form_snapshot(self) -> bool:
        name = self._active_form_snapshot["name"].strip()
        author = self._active_form_snapshot["author"].strip()
        description = self._active_form_snapshot["description"].strip()
        metadata = self._metadata_for_save()
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
        project_id = self._active_project_id
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
        self.refresh_projects()
        self._update_active_project_label()
        self._set_dirty(False)
        self._show_active_form_snapshot()
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
            self._load_record_into_form(record)
            self._active_form_snapshot = self._capture_form_snapshot()
        self._active_project_id = record.id
        self._selected_project_id = record.id
        self._set_preview_mode(False)
        self._update_active_project_label()
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
        if self._on_project_loaded is not None:
            self._on_project_loaded()

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
            if self._active_project_id == record.id:
                self._activate_unsaved_workspace(reset_plugins=True)
            self.refresh_projects()
            self._set_status("Projekt gelöscht. Ungespeicherte Arbeitsfläche aktiv.")
        else:
            self._show_error("Fehler", "Projekt konnte nicht gelöscht werden.")
            self._set_status("Löschen fehlgeschlagen.")

    def export_active_project(self) -> None:
        if not self._active_project_id:
            self._show_info(
                "Hinweis",
                "Es ist kein aktives Projekt geladen, das exportiert werden kann.",
            )
            self._set_status("Export abgebrochen: Kein aktives Projekt vorhanden.")
            return
        record = self._project_cache.get(self._active_project_id)
        if record is None:
            record = self._store.load_project(self._active_project_id)
        if record is None:
            self._show_error("Fehler", "Das aktive Projekt wurde nicht gefunden.")
            self._set_status("Export abgebrochen: Aktives Projekt nicht gefunden.")
            return

        self._capture_active_form_snapshot()
        with self._dirty_tracker.paused():
            plugin_states, errors = self._state_coordinator.collect_states()
        if errors:
            self._show_error(
                "Fehler",
                "Export abgebrochen. Einige Plugin-Zustände konnten nicht gelesen werden:\n"
                + "\n".join(errors),
            )
            self._set_status("Export abgebrochen: Plugin-Zustände unvollständig.")
            return

        default_file_name = f"{record.name.strip() or 'projekt'}{EXPORT_FILE_SUFFIX}"
        selected_path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "Projekt exportieren",
            default_file_name,
            f"Heatrix Projekt-Export (*{EXPORT_FILE_SUFFIX});;JSON (*.json)",
        )
        if not selected_path:
            self._set_status("Export abgebrochen: Kein Zieldateiname gewählt.")
            return

        try:
            payload = build_project_export_payload(
                project=record,
                plugin_states=plugin_states,
                ui_state=self._capture_ui_state(),
                name=self._active_form_snapshot["name"],
                author=self._active_form_snapshot["author"],
                description=self._active_form_snapshot["description"],
                app_version=self._resolve_app_version(),
            )
            target_path = export_project_to_file(payload, Path(selected_path))
        except ValueError as exc:
            self._show_error("Fehler", str(exc))
            self._set_status(f"Export abgebrochen: {exc}")
            return
        except OSError as exc:
            self._show_error("Fehler", f"Datei konnte nicht geschrieben werden: {exc}")
            self._set_status("Export fehlgeschlagen: Datei konnte nicht geschrieben werden.")
            return

        self._show_info("Export erfolgreich", f"Projekt wurde exportiert:\n{target_path}")
        self._set_status(f"Projekt exportiert: {target_path.name}")

    def import_project_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self.widget,
            "Projekt importieren",
            "",
            f"Heatrix Projekt-Export (*{EXPORT_FILE_SUFFIX});;JSON (*.json);;Alle Dateien (*)",
        )
        if not selected_path:
            self._set_status("Import abgebrochen: Keine Datei ausgewählt.")
            return

        try:
            prepared = self._import_service.prepare_import_from_file(Path(selected_path))
            dialog = InsulationImportDialog(prepared, self.widget)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._set_status("Import abgebrochen: Isolierungsdialog abgebrochen.")
                return
            prepared_with_decisions = self._import_service.apply_insulation_import_decisions(
                prepared,
                decisions=dialog.decisions(),
            )
            imported = self._import_service.persist_prepared_import(
                prepared_with_decisions,
                store=self._store,
            )
        except ProjectImportError as exc:
            self._show_error("Import fehlgeschlagen", str(exc))
            self._set_status(f"Import abgebrochen: {exc}")
            return
        except OSError as exc:
            self._show_error("Import fehlgeschlagen", f"Datei konnte nicht verarbeitet werden: {exc}")
            self._set_status("Import fehlgeschlagen: Dateizugriff nicht möglich.")
            return
        except ValueError as exc:
            self._show_error("Import fehlgeschlagen", str(exc))
            self._set_status(f"Import abgebrochen: {exc}")
            return

        self.refresh_projects()
        self._selected_project_id = imported.id
        self._select_project_by_id(imported.id)
        self._show_info("Import erfolgreich", f"Projekt '{imported.name}' wurde als neues lokales Projekt importiert.")
        self._set_status(f"Projekt importiert: {imported.name}")

    def confirm_unsaved_changes(self, action_label: str) -> bool:
        if not self._dirty:
            return True
        result = self._prompt_unsaved_changes(action_label)
        if result == "save":
            if self._preview_mode:
                return self._save_project_from_form_snapshot()
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
        if self._preview_mode:
            return
        self._capture_active_form_snapshot()
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
                self._set_status("Ungespeicherte Arbeitsfläche ohne Änderungen.")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        has_selection = bool(self._selected_project_id)
        self._save_button.setEnabled(not self._is_previewing_foreign_project())
        self._export_button.setEnabled(bool(self._active_project_id))
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

    def _metadata_for_save(self) -> dict[str, Any]:
        if self._active_project_id:
            record = self._project_cache.get(self._active_project_id)
            if record is None:
                record = self._store.load_project(self._active_project_id)
            if record is not None:
                return dict(record.metadata)
        return {}

    def _resolve_app_version(self) -> str | None:
        try:
            from app import __version__ as app_version  # type: ignore[attr-defined]
        except Exception:
            return None
        app_version_text = str(app_version).strip()
        return app_version_text or None

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _activate_unsaved_workspace(
        self, *, reset_plugins: bool, reset_dirty: bool = True
    ) -> None:
        with self._dirty_tracker.paused():
            if reset_plugins and self._workspace_plugin_states:
                self._state_coordinator.apply_states(self._workspace_plugin_states)
            self._clear_form(reset_dirty=False)
        self._active_project_id = None
        self._selected_project_id = None
        self._set_preview_mode(False)
        self._project_list.blockSignals(True)
        self._project_list.setCurrentRow(-1)
        self._project_list.blockSignals(False)
        self._update_active_project_label()
        if reset_dirty:
            self._set_dirty(False)
        self._update_action_buttons()

    def _update_active_project_label(self) -> None:
        if self._active_project_id:
            record = self._project_cache.get(self._active_project_id)
            name = record.name if record else "(unbekannt)"
            self._active_project_label.setText(f"Aktiv: {name}")
            return
        self._active_project_label.setText("Aktiv: Ungespeichertes Projekt")

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self.widget, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self.widget, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self.widget, title, message)

    def _default_form_snapshot(self) -> dict[str, str]:
        return {
            "name": "",
            "author": self._author,
            "description": "",
        }

    def _capture_form_snapshot(self) -> dict[str, str]:
        return {
            "name": self._text(self._name_input),
            "author": self._text(self._author_input),
            "description": self._plain_text(self._description_input),
        }

    def _capture_active_form_snapshot(self) -> None:
        if self._preview_mode:
            return
        self._active_form_snapshot = self._capture_form_snapshot()

    def _load_form_snapshot(self, snapshot: dict[str, str]) -> None:
        self._suppress_project_updates = True
        try:
            self._name_input.setText(snapshot.get("name", ""))
            self._author_input.setText(snapshot.get("author", self._author))
            self._description_input.setPlainText(snapshot.get("description", ""))
        finally:
            self._suppress_project_updates = False

    def _is_previewing_foreign_project(self) -> bool:
        return (
            self._selected_project_id is not None
            and self._selected_project_id != self._active_project_id
        )

    def _set_preview_mode(self, enabled: bool) -> None:
        self._preview_mode = enabled
        for widget in (
            self._name_input,
            self._author_input,
            self._description_input,
        ):
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(enabled)
