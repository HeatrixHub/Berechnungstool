"""Qt UI entrypoint."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from app.ui_qt.plugins.base import QtAppContext
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.projects.tab import ProjectsTab
from app.ui_qt.global_tabs.report import ReportTab
from app.ui_qt.ui_helpers import apply_app_style


def main() -> int:
    app = QApplication(sys.argv)
    apply_app_style(app)
    window = QMainWindow()
    tab_widget = QTabWidget()
    window.setCentralWidget(tab_widget)
    context = QtAppContext(main_window=window, tab_widget=tab_widget)
    plugin_manager = QtPluginManager(context)
    report_tab = ReportTab(tab_widget, plugin_manager=plugin_manager, title="Bericht")
    projects_tab = ProjectsTab(
        tab_widget,
        plugin_manager=plugin_manager,
        main_window=window,
        on_project_loaded=report_tab.refresh_preview,
    )

    from app.ui_qt.global_tabs.isolierungen_db import IsolierungenDbTab

    IsolierungenDbTab(tab_widget, title="Isolierungen DB")

    plugin_manager.load_plugins()
    report_tab.refresh_preview()
    projects_tab.on_plugins_loaded()

    def _refresh_report_on_tab_change(index: int) -> None:
        if tab_widget.widget(index) is report_tab.widget:
            report_tab.refresh_preview()

    tab_widget.currentChanged.connect(_refresh_report_on_tab_change)

    window.setWindowTitle("Heatrix Berechnungstools")
    window.resize(1280, 840)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
