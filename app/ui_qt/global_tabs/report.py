"""Global Qt tab for PDF report generation."""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QWidget,
)

from app.core.reporting import ReportingService
from app.ui_qt.plugins.manager import QtPluginManager
from app.ui_qt.ui_helpers import (
    create_button_row,
    create_page_layout,
    make_hbox,
)


@dataclass(frozen=True)
class _ReportTemplateSpec:
    name: str
    path: Path


class ReportTab:
    """Global tab for building PDF reports from current plugin states."""

    def __init__(
        self,
        tab_widget: object,
        plugin_manager: QtPluginManager,
        *,
        title: str = "Bericht",
    ) -> None:
        self._tab_widget = tab_widget
        self._plugin_manager = plugin_manager
        self._report_logger = logging.getLogger(__name__)
        self._report_service = ReportingService(self._report_logger)

        self._report_templates: list[_ReportTemplateSpec] = []
        self._report_current_text: str = ""
        self._report_template_combo: object | None = None
        self._report_preview: object | None = None
        self._report_status_label: object | None = None

        self.widget = QWidget()
        self._build_ui()
        self._insert_tab(title)
        self._discover_report_templates()
        self._update_report_preview()

        if hasattr(self._tab_widget, "currentChanged"):
            self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def _insert_tab(self, title: str) -> None:
        if isinstance(self._tab_widget, QTabWidget):
            self._tab_widget.insertTab(1, self.widget, title)
        else:
            self._tab_widget.addTab(self.widget, title)

    def _build_ui(self) -> None:
        layout = create_page_layout(self.widget, "Bericht", show_logo=True)

        template_layout = make_hbox()
        template_layout.addWidget(QLabel("Template"))
        self._report_template_combo = QComboBox()
        self._report_template_combo.currentIndexChanged.connect(self._update_report_preview)
        template_layout.addWidget(self._report_template_combo)
        refresh_button = QPushButton("Templates aktualisieren")
        refresh_button.clicked.connect(self._discover_report_templates)
        template_layout.addWidget(refresh_button)
        template_layout.addStretch()
        layout.addLayout(template_layout)

        preview_button = QPushButton("Vorschau aktualisieren")
        preview_button.clicked.connect(self._update_report_preview)
        export_button = QPushButton("PDF exportieren")
        export_button.clicked.connect(self._on_report_export_pdf)
        action_layout = create_button_row([preview_button, export_button])
        layout.addLayout(action_layout)

        self._report_preview = QTextBrowser()
        self._report_preview.setOpenExternalLinks(False)
        preview_font = QFont("Courier New")
        preview_font.setStyleHint(QFont.Monospace)
        self._report_preview.setFont(preview_font)
        layout.addWidget(self._report_preview)

        self._report_status_label = QLabel()
        self._report_status_label.setWordWrap(True)
        layout.addWidget(self._report_status_label)

    def _discover_report_templates(self) -> None:
        self._report_templates = []
        report_dir = self._resolve_report_directory()
        if report_dir is not None and report_dir.exists():
            for template_path in sorted(report_dir.glob("*.j2")):
                self._report_templates.append(
                    _ReportTemplateSpec(name=template_path.stem, path=template_path)
                )
        if self._report_template_combo is not None:
            current_name = self._report_template_combo.currentText()
            with QSignalBlocker(self._report_template_combo):
                self._report_template_combo.clear()
                for spec in self._report_templates:
                    self._report_template_combo.addItem(spec.name)
            if current_name:
                index = self._report_template_combo.findText(current_name)
                if index >= 0:
                    self._report_template_combo.setCurrentIndex(index)
        if not self._report_templates:
            self._set_report_status(
                "Keine Templates gefunden. Lege .j2-Dateien in Isolierung/reports ab."
            )
        else:
            self._set_report_status("Templates geladen. Vorschau aktualisieren, um den Bericht zu sehen.")

    def _resolve_report_directory(self) -> Path | None:
        module = importlib.import_module("Isolierung")
        module_file = getattr(module, "__file__", None)
        if not module_file:
            return None
        return Path(module_file).resolve().parent / "reports"

    def _current_report_template(self) -> _ReportTemplateSpec | None:
        if not self._report_templates:
            return None
        if self._report_template_combo is None:
            return self._report_templates[0]
        name = self._report_template_combo.currentText()
        for spec in self._report_templates:
            if spec.name == name:
                return spec
        return self._report_templates[0]

    def _update_report_preview(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            self._set_report_preview_text("Keine Report-Templates gefunden.")
            self._set_report_status("Keine Templates verfügbar.")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="report-preview-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
        except Exception as exc:
            self._set_report_preview_text(f"Bericht konnte nicht erstellt werden:\n{exc}")
            self._set_report_status("Bericht konnte nicht aktualisiert werden.")
            return
        self._report_current_text = rendered
        self._set_report_preview_text(rendered)
        self._set_report_status("Bericht aktualisiert.")

    def _set_report_preview_text(self, text: str) -> None:
        if self._report_preview is None:
            return
        self._report_preview.setPlainText(text)

    def _set_report_status(self, message: str) -> None:
        if self._report_status_label is None:
            return
        self._report_status_label.setText(message)

    def _on_report_export_pdf(self) -> None:
        spec = self._current_report_template()
        if spec is None:
            QMessageBox.warning(self.widget, "Hinweis", "Keine Report-Templates gefunden.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "PDF speichern",
            "",
            "PDF (*.pdf);;Alle Dateien (*.*)",
        )
        if not path:
            return
        try:
            with tempfile.TemporaryDirectory(prefix="report-") as tmp_dir:
                resource_dir = Path(tmp_dir)
                rendered = self._render_report_template(spec, resource_dir)
                self._report_current_text = rendered
                self._set_report_preview_text(rendered)
                self._report_service.export_pdf([(f"Bericht – {spec.name}", rendered)], Path(path))
        except Exception as exc:
            QMessageBox.critical(
                self.widget,
                "Fehler",
                f"Der Bericht konnte nicht erstellt werden:\n{exc}",
            )
            return
        self._set_report_status(f"Bericht gespeichert unter {path}.")
        QMessageBox.information(self.widget, "Fertig", "Der Bericht wurde erstellt.")

    def _render_report_template(self, spec: _ReportTemplateSpec, resource_dir: Path) -> str:
        project, plugin_states = self._build_report_context()
        prepared_states = self._report_service.build_plugin_states(plugin_states, resource_dir)
        context = {"project": project, "plugin_states": prepared_states}
        return self._report_service.render_preview(context, spec.path)

    def _build_report_context(self) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        project = {
            "name": "Aktuelle Eingaben",
            "author": "",
            "created_at": "",
            "updated_at": "",
        }
        plugin_states = self._plugin_manager.export_all_states()
        return project, plugin_states

    def _on_tab_changed(self, index: int) -> None:
        if not hasattr(self._tab_widget, "indexOf"):
            return
        if self._tab_widget.indexOf(self.widget) == index:
            self._update_report_preview()
