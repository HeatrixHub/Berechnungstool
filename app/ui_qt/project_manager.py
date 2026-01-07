"""Project management UI layer for the Qt host."""
from __future__ import annotations

import getpass
import importlib.util
from typing import Any, Callable, Iterable, Optional

from app.core.projects.store import ProjectRecord, ProjectStore
from app.ui_qt.plugins.manager import QtPluginManager


class _StubAction:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self._callback: Optional[Callable[[], None]] = None

    def triggered(self) -> "_StubAction":
        return self

    def connect(self, callback: Callable[[], None]) -> None:
        self._callback = callback


class _StubMenu:
    def addAction(self, _action: object) -> None:
        return None

    def addSeparator(self) -> None:
        return None


class _StubMenuBar:
    def addMenu(self, _title: str) -> _StubMenu:
        return _StubMenu()


class _StubInputDialog:
    @staticmethod
    def getText(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        return "", False

    @staticmethod
    def getItem(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        return "", False


class _StubMessageBox:
    @staticmethod
    def information(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def warning(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def critical(*_args: object, **_kwargs: object) -> None:
        return None


def _resolve_qt_helpers() -> tuple[type[object], type[object], type[object], type[object]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QInputDialog, QMenuBar, QMessageBox

        return QAction, QInputDialog, QMenuBar, QMessageBox
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QInputDialog, QMenuBar, QMessageBox

        return QAction, QInputDialog, QMenuBar, QMessageBox
    return _StubAction, _StubInputDialog, _StubMenuBar, _StubMessageBox


class ProjectManagerUI:
    """Wires project persistence into the Qt host."""

    def __init__(
        self,
        *,
        main_window: object,
        plugin_manager: QtPluginManager,
        store: ProjectStore | None = None,
        author: str | None = None,
    ) -> None:
        self._main_window = main_window
        self._plugin_manager = plugin_manager
        self._store = store or ProjectStore()
        self._author = author or getpass.getuser()
        self._current_project_id: str | None = None
        self._current_project_name: str | None = None
        self._status_bar: object | None = None

    def attach(self) -> None:
        QAction, QInputDialog, QMenuBar, QMessageBox = _resolve_qt_helpers()

        menu_bar = None
        if hasattr(self._main_window, "menuBar"):
            menu_bar = self._main_window.menuBar()
        if menu_bar is None:
            menu_bar = QMenuBar()
        if hasattr(menu_bar, "addMenu"):
            project_menu = menu_bar.addMenu("Projekt")
            action_new = QAction("Neues Projekt", self._main_window)
            action_save = QAction("Projekt speichern", self._main_window)
            action_load = QAction("Projekt laden", self._main_window)
            project_menu.addAction(action_new)
            project_menu.addAction(action_save)
            project_menu.addSeparator()
            project_menu.addAction(action_load)
            self._connect_action(action_new, self.create_new_project)
            self._connect_action(action_save, self.save_project)
            self._connect_action(action_load, self.load_project)

        self._input_dialog = QInputDialog
        self._message_box = QMessageBox

        if hasattr(self._main_window, "statusBar"):
            self._status_bar = self._main_window.statusBar()
        self._update_status()

    def create_new_project(self) -> None:
        name = self._prompt_project_name(default="")
        if not name:
            return
        self._current_project_id = None
        self._current_project_name = name
        self._update_status()
        self._show_info("Projekt gestartet", f"Neues Projekt „{name}“ wurde erstellt.")

    def save_project(self) -> None:
        name = self._current_project_name or self._prompt_project_name(default="")
        if not name:
            return
        states = self._plugin_manager.export_all_states()
        try:
            record = self._store.save_project(
                name=name,
                author=self._author,
                plugin_states=states,
                project_id=self._current_project_id,
            )
        except ValueError as exc:
            self._show_error("Projekt speichern fehlgeschlagen", str(exc))
            return
        self._current_project_id = record.id
        self._current_project_name = record.name
        self._update_status()
        self._show_info(
            "Projekt gespeichert",
            f"Projekt „{record.name}“ wurde gespeichert (ID: {record.id}).",
        )

    def load_project(self) -> None:
        projects = self._store.list_projects()
        if not projects:
            self._show_warning("Keine Projekte", "Es sind keine gespeicherten Projekte vorhanden.")
            return
        selection = self._prompt_project_selection(projects)
        if selection is None:
            return
        record = self._store.load_project(selection)
        if record is None:
            self._show_error("Projekt laden fehlgeschlagen", "Das ausgewählte Projekt wurde nicht gefunden.")
            return
        self._plugin_manager.import_all_states(record.plugin_states)
        self._current_project_id = record.id
        self._current_project_name = record.name
        self._update_status()
        self._show_info(
            "Projekt geladen",
            f"Projekt „{record.name}“ wurde geladen (ID: {record.id}).",
        )

    def _connect_action(self, action: object, callback: Callable[[], None]) -> None:
        triggered = getattr(action, "triggered", None)
        if triggered is not None and hasattr(triggered, "connect"):
            triggered.connect(callback)
            return
        if hasattr(action, "connect"):
            action.connect(callback)

    def _prompt_project_name(self, default: str) -> str | None:
        if not hasattr(self, "_input_dialog"):
            return None
        label = "Projektname eingeben:"
        result = self._input_dialog.getText(self._main_window, "Projektname", label, text=default)
        name, ok = self._normalize_dialog_result(result)
        name = name.strip()
        if not ok or not name:
            return None
        return name

    def _prompt_project_selection(self, projects: Iterable[ProjectRecord]) -> str | None:
        items = []
        mapping: dict[str, str] = {}
        for record in projects:
            label = f"{record.name} ({record.id})"
            items.append(label)
            mapping[label] = record.id
        if not items:
            return None
        result = self._input_dialog.getItem(
            self._main_window,
            "Projekt laden",
            "Projekt auswählen:",
            items,
            0,
            False,
        )
        selection, ok = self._normalize_dialog_result(result)
        if not ok:
            return None
        return mapping.get(selection)

    def _normalize_dialog_result(self, result: Any) -> tuple[str, bool]:
        if isinstance(result, tuple) and len(result) >= 2:
            return str(result[0]), bool(result[1])
        return str(result), True

    def _update_status(self) -> None:
        if not self._status_bar or not hasattr(self._status_bar, "showMessage"):
            return
        if self._current_project_name and self._current_project_id:
            message = f"Projekt: {self._current_project_name} (ID: {self._current_project_id})"
        elif self._current_project_name:
            message = f"Projekt: {self._current_project_name} (ungespeichert)"
        else:
            message = "Kein Projekt ausgewählt"
        self._status_bar.showMessage(message)

    def _show_info(self, title: str, message: str) -> None:
        if hasattr(self, "_message_box"):
            self._message_box.information(self._main_window, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        if hasattr(self, "_message_box"):
            self._message_box.warning(self._main_window, title, message)

    def _show_error(self, title: str, message: str) -> None:
        if hasattr(self, "_message_box"):
            self._message_box.critical(self._main_window, title, message)
