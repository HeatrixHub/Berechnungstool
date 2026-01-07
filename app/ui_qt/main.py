"""Qt UI entrypoint."""
from __future__ import annotations

import importlib.util
import sys
from typing import Tuple, Type

from app.ui_qt.plugins.base import QtAppContext
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.project_manager import ProjectManagerUI


class _StubApplication:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv

    def exec(self) -> int:
        return 0


class _StubTabWidget:
    def __init__(self) -> None:
        self.tabs: list[tuple[object, str]] = []
        self._current_index = 0

    def addTab(self, widget: object, title: str) -> None:
        self.tabs.append((widget, title))

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:
        self._current_index = index

    def count(self) -> int:
        return len(self.tabs)


class _StubMainWindow:
    def __init__(self) -> None:
        self._title = ""
        self._size = (0, 0)
        self._central_widget: object | None = None

    def setWindowTitle(self, title: str) -> None:
        self._title = title

    def resize(self, width: int, height: int) -> None:
        self._size = (width, height)

    def setCentralWidget(self, widget: object) -> None:
        self._central_widget = widget

    def show(self) -> None:
        return None


def _resolve_qt_widgets() -> Tuple[Type[object], Type[object], Type[object]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

        return QApplication, QMainWindow, QTabWidget
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

        return QApplication, QMainWindow, QTabWidget
    return _StubApplication, _StubMainWindow, _StubTabWidget


def main() -> int:
    QApplication, QMainWindow, QTabWidget = _resolve_qt_widgets()

    app = QApplication(sys.argv)
    window = QMainWindow()
    tab_widget = QTabWidget()
    if hasattr(window, "setCentralWidget"):
        window.setCentralWidget(tab_widget)
    context = QtAppContext(main_window=window, tab_widget=tab_widget)

    plugin_manager = QtPluginManager(context)
    plugin_manager.load_plugins()
    project_manager = ProjectManagerUI(
        main_window=window,
        plugin_manager=plugin_manager,
        tab_widget=tab_widget,
    )
    project_manager.attach()

    if hasattr(window, "setWindowTitle"):
        window.setWindowTitle("Heatrix Berechnungstools")
    if hasattr(window, "resize"):
        window.resize(1280, 840)
    if hasattr(window, "show"):
        window.show()
    if hasattr(app, "exec"):
        return app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
