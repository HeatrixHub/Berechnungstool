"""Qt UI entrypoint."""
from __future__ import annotations

import importlib.util
import sys
from typing import Tuple, Type


class _StubApplication:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv

    def exec(self) -> int:
        return 0


class _StubMainWindow:
    def __init__(self) -> None:
        self._title = ""
        self._size = (0, 0)

    def setWindowTitle(self, title: str) -> None:
        self._title = title

    def resize(self, width: int, height: int) -> None:
        self._size = (width, height)

    def show(self) -> None:
        return None


def _resolve_qt_widgets() -> Tuple[Type[object], Type[object]]:
    if importlib.util.find_spec("PyQt6") is not None:
        from PyQt6.QtWidgets import QApplication, QMainWindow

        return QApplication, QMainWindow
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtWidgets import QApplication, QMainWindow

        return QApplication, QMainWindow
    return _StubApplication, _StubMainWindow


def main() -> int:
    QApplication, QMainWindow = _resolve_qt_widgets()

    app = QApplication(sys.argv)
    window = QMainWindow()
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
