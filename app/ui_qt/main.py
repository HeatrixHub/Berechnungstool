"""Qt UI entry point."""

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget


def main() -> int:
    app = QApplication([])

    window = QMainWindow()
    window.setWindowTitle("Heatrix Berechnungstools")

    tabs = QTabWidget()
    window.setCentralWidget(tabs)

    window.resize(1280, 840)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
