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
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QFileDialog,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QWidget,
)

from app.core.projects.export import (
    EXPORT_FILE_SUFFIX,
    build_project_export_payload,
    export_project_to_file,
)
from app.core.projects.import_service import ProjectImportError, ProjectImportService
from app.core.projects.store import ProjectRecord, ProjectStore, ProjectStoreLoadError
from app.core.projects.insulation_runtime_resolution import (
    InsulationRuntimeResolver,
    RuntimeResolvedInsulation,
)
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
        try:
            self._store = store or ProjectStore()
        except ProjectStoreLoadError as exc:
            logger.exception("Projekt-Store konnte nicht geladen werden.")
            QMessageBox.critical(
                None,
                "Projektdatei beschädigt",
                "Die Projektdatei konnte nicht geladen werden.\n\n"
                f"{exc}\n\n"
                "Bitte sichern oder reparieren Sie die Datei und starten Sie die Anwendung neu.",
            )
            raise
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
        self._insulation_runtime_resolver = InsulationRuntimeResolver()
        self._active_embedded_isolierungen: dict[str, Any] = {"families": []}
        self._active_insulation_resolution: dict[str, Any] = {"entries": []}
        self._active_runtime_insulation_items: list[RuntimeResolvedInsulation] = []
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
        self._insulation_resolution_hint = QLabel("Isolierungsquelle: keine aktiven Projektdaten.")
        self._insulation_resolution_hint.setWordWrap(True)
        details_layout.addWidget(self._insulation_resolution_hint)
        self._insulation_resolution_table = QTableWidget(0, 6)
        self._insulation_resolution_table.setHorizontalHeaderLabels(
            ["Projekt-Isolierung", "Aktiv", "Lokal verknüpft", "Lokalstatus", "Hinweis", "Aktion"]
        )
        self._insulation_resolution_table.verticalHeader().setVisible(False)
        self._insulation_resolution_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._insulation_resolution_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._insulation_resolution_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        details_layout.addWidget(self._insulation_resolution_table)

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
        embedded_override = None
        resolution_override = None
        if self._active_embedded_isolierungen.get("families") or self._active_insulation_resolution.get("entries"):
            embedded_override = self._active_embedded_isolierungen
            resolution_override = self._active_insulation_resolution
        try:
            record = self._store.save_project(
                name=name,
                author=author,
                description=description,
                metadata=metadata,
                plugin_states=plugin_states,
                ui_state=self._capture_ui_state(),
                embedded_isolierungen=embedded_override,
                insulation_resolution=resolution_override,
                project_id=project_id,
            )
        except ValueError as exc:
            self._show_error("Fehler", str(exc))
            return False
        self._selected_project_id = record.id
        self._active_project_id = record.id
        self._active_embedded_isolierungen = record.embedded_isolierungen
        self._active_insulation_resolution = record.insulation_resolution
        runtime_after_save = self._insulation_runtime_resolver.resolve_project_runtime(
            plugin_states=plugin_states,
            embedded_isolierungen=record.embedded_isolierungen,
            insulation_resolution=record.insulation_resolution,
        )
        self._active_runtime_insulation_items = runtime_after_save.resolved_items
        self.refresh_projects()
        self._update_active_project_label()
        self._refresh_insulation_resolution_ui()
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
        runtime_resolution = self._insulation_runtime_resolver.resolve_project_runtime(
            plugin_states=record.plugin_states,
            embedded_isolierungen=record.embedded_isolierungen,
            insulation_resolution=record.insulation_resolution,
        )
        with self._dirty_tracker.paused():
            missing, unknown, errors = self._state_coordinator.apply_states(runtime_resolution.plugin_states)
            self._apply_ui_state(record.ui_state)
            self._load_record_into_form(record)
            self._active_form_snapshot = self._capture_form_snapshot()
        self._active_project_id = record.id
        self._selected_project_id = record.id
        self._active_embedded_isolierungen = runtime_resolution.embedded_isolierungen
        self._active_insulation_resolution = runtime_resolution.insulation_resolution
        self._active_runtime_insulation_items = runtime_resolution.resolved_items
        self._set_preview_mode(False)
        self._update_active_project_label()
        self._refresh_insulation_resolution_ui()
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
            import_report = self._import_service.build_import_decision_report(prepared_with_decisions)
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
        report_text = (
            "Isolierungs-Ergebnis:\n"
            f"• Eingebettet aktiv: {import_report.embedded_active}\n"
            f"• Lokal aktiv: {import_report.local_active}\n"
            f"• Neu in lokale DB übernommen: {import_report.adopted_to_local}"
        )
        self._show_info(
            "Import erfolgreich",
            f"Projekt '{imported.name}' wurde als neues lokales Projekt importiert.\n\n{report_text}",
        )
        self._set_status(f"Projekt importiert: {imported.name}")

    def confirm_unsaved_changes(self, action_label: str) -> bool:
        if not self._dirty:
            return True
        result = self._prompt_unsaved_changes(action_label)
        if result == "save":
            if self._requires_name_prompt_before_save():
                return self._save_unnamed_draft_with_name_prompt()
            if self._preview_mode:
                return self._save_project_from_form_snapshot()
            return self.save_project()
        if result == "discard":
            self._set_dirty(False)
            return True
        return False

    def _requires_name_prompt_before_save(self) -> bool:
        if self._active_project_id:
            return False
        if not self._preview_mode:
            self._capture_active_form_snapshot()
        return not self._active_form_snapshot.get("name", "").strip()

    def _save_unnamed_draft_with_name_prompt(self) -> bool:
        project_name = self._prompt_project_name_for_new_save()
        if project_name is None:
            self._set_status("Projektwechsel abgebrochen: Kein Projektname vergeben.")
            return False
        self._active_form_snapshot["name"] = project_name
        if not self._preview_mode:
            self._suppress_project_updates = True
            try:
                self._name_input.setText(project_name)
            finally:
                self._suppress_project_updates = False
        return self._save_project_from_form_snapshot()

    def _prompt_project_name_for_new_save(self) -> str | None:
        while True:
            value, accepted = QInputDialog.getText(
                self.widget,
                "Projektname erforderlich",
                "Bitte Projektnamen eingeben, um den Entwurf zu speichern:",
                text=self._active_form_snapshot.get("name", "").strip(),
            )
            if not accepted:
                return None
            name = value.strip()
            if name:
                return name
            self._show_warning(
                "Projektname erforderlich",
                "Ohne Projektnamen kann der Entwurf nicht gespeichert werden.",
            )

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
        self._active_embedded_isolierungen = {"families": []}
        self._active_insulation_resolution = {"entries": []}
        self._active_runtime_insulation_items = []
        self._set_preview_mode(False)
        self._project_list.blockSignals(True)
        self._project_list.setCurrentRow(-1)
        self._project_list.blockSignals(False)
        self._update_active_project_label()
        self._refresh_insulation_resolution_ui()
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

    def _refresh_insulation_resolution_ui(self) -> None:
        items = self._active_runtime_insulation_items
        if not self._active_project_id:
            self._insulation_resolution_hint.setText("Isolierungsquelle: keine aktiven Projektdaten.")
            self._insulation_resolution_table.setRowCount(0)
            return
        if not items:
            self._insulation_resolution_hint.setText(
                "Isolierungsquelle: Legacy-Projekt ohne embedded_isolierungen/insulation_resolution "
                "(Verhalten wie bisher: lokale DB aus Plugin-State)."
            )
            self._insulation_resolution_table.setRowCount(0)
            return
        self._insulation_resolution_hint.setText(
            "Isolierungsquellen aktiv: 'Aktiv' zeigt die wirksame Quelle, "
            "'Lokalstatus' zeigt Synchronität/Abweichung zur eingebetteten Importversion."
        )
        self._insulation_resolution_table.setRowCount(len(items))
        for row, item in enumerate(items):
            label = item.family_name
            if item.variant_name:
                label += f" / {item.variant_name}"
            label += f" ({item.project_insulation_key})"
            self._insulation_resolution_table.setItem(row, 0, QTableWidgetItem(label))
            active = item.effective_source
            if item.requested_source != item.effective_source:
                active = f"{active} (statt {item.requested_source})"
            self._insulation_resolution_table.setItem(row, 1, QTableWidgetItem(active))
            linked_text = "ja" if item.linked_local else "nein"
            self._insulation_resolution_table.setItem(row, 2, QTableWidgetItem(linked_text))
            self._insulation_resolution_table.setItem(row, 3, QTableWidgetItem(item.local_status))
            hint_text = item.local_status_hint or item.warning or "–"
            self._insulation_resolution_table.setItem(row, 4, QTableWidgetItem(hint_text))
            action_cell = QWidget()
            action_layout = create_button_row(
                [
                    self._build_source_button("Embedded aktivieren", item.project_insulation_key, "embedded"),
                    self._build_source_button("Lokal aktivieren", item.project_insulation_key, "local"),
                ]
            )
            action_cell.setLayout(action_layout)
            self._insulation_resolution_table.setCellWidget(row, 5, action_cell)
        self._insulation_resolution_table.resizeRowsToContents()

    def _build_source_button(self, label: str, project_key: str, source: str) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(lambda _checked=False, key=project_key, target=source: self._switch_insulation_source(key, target))
        return button

    def _switch_insulation_source(self, project_key: str, target_source: str) -> None:
        if not self._active_project_id:
            self._show_warning("Keine Aktion möglich", "Es ist kein aktives Projekt geladen.")
            return
        updated_resolution, error = self._insulation_runtime_resolver.switch_active_source(
            insulation_resolution=self._active_insulation_resolution,
            embedded_isolierungen=self._active_embedded_isolierungen,
            project_insulation_key=project_key,
            target_source=target_source,
        )
        if error:
            self._show_warning("Umschalten nicht möglich", error)
            self._set_status(f"Umschalten abgelehnt: {error}")
            return
        record = self._store.load_project(self._active_project_id)
        if record is None:
            self._show_error("Fehler", "Aktives Projekt konnte nicht erneut geladen werden.")
            return
        resolved = self._insulation_runtime_resolver.resolve_project_runtime(
            plugin_states=record.plugin_states,
            embedded_isolierungen=record.embedded_isolierungen,
            insulation_resolution=updated_resolution,
        )
        with self._dirty_tracker.paused():
            _missing, _unknown, errors = self._state_coordinator.apply_states(resolved.plugin_states)
        if errors:
            self._show_warning("Umschalten unvollständig", "\n".join(errors))
        self._active_embedded_isolierungen = resolved.embedded_isolierungen
        self._active_insulation_resolution = resolved.insulation_resolution
        self._active_runtime_insulation_items = resolved.resolved_items
        self._refresh_insulation_resolution_ui()
        try:
            self._store.save_project(
                name=record.name,
                author=record.author,
                description=record.description,
                metadata=record.metadata,
                plugin_states=resolved.plugin_states,
                ui_state=record.ui_state,
                embedded_isolierungen=self._active_embedded_isolierungen,
                insulation_resolution=self._active_insulation_resolution,
                project_id=record.id,
                created_at_override=record.created_at,
            )
        except ValueError as exc:
            self._show_error("Fehler", f"Projekt konnte nach Umschaltung nicht gespeichert werden: {exc}")
            return
        self.refresh_projects()
        self._select_project_by_id(record.id)
        self._set_status(f"Isolierungsquelle für {project_key} explizit auf '{target_source}' umgeschaltet.")
        if self._on_project_loaded is not None:
            self._on_project_loaded()

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
