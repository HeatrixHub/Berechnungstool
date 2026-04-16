"""Dialog für explizite Importentscheidungen bei verwendeten Isolierungen."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.isolierungen_db.logic import get_family_by_id
from app.core.projects.import_service import (
    DECISION_ADOPT_TO_LOCAL,
    DECISION_USE_EMBEDDED,
    DECISION_USE_LOCAL,
    InsulationImportDecision,
    PreparedProjectImport,
)


_DECISION_LABELS = {
    DECISION_USE_EMBEDDED: "Eingebettete Projektversion verwenden",
    DECISION_USE_LOCAL: "Lokalen Datenbankeintrag verwenden",
    DECISION_ADOPT_TO_LOCAL: "In lokale Datenbank übernehmen",
}


@dataclass(slots=True)
class _RowWidgets:
    project_insulation_key: str
    decision_combo: QComboBox
    local_combo: QComboBox
    use_local_after_adopt: QCheckBox
    status: str


class InsulationImportDialog(QDialog):
    """Zeigt nur tatsächlich verwendete Isolierungen aus insulation_resolution.entries."""

    def __init__(self, prepared: PreparedProjectImport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prepared = prepared
        self._embedded_index = self._build_embedded_index(prepared.embedded_isolierungen)
        self._rows: list[_RowWidgets] = []

        self.setWindowTitle("Import: Isolierungen prüfen")
        self.resize(900, 680)

        root = QVBoxLayout(self)
        root.addWidget(self._build_summary_box())
        root.addWidget(self._build_entries_area(), stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_before_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def decisions(self) -> list[InsulationImportDecision]:
        items: list[InsulationImportDecision] = []
        for row in self._rows:
            decision_type = str(row.decision_combo.currentData() or DECISION_USE_EMBEDDED)
            local_data = row.local_combo.currentData() if row.local_combo.currentIndex() >= 0 else None
            family_id = None
            variant_id = None
            if isinstance(local_data, tuple):
                family_id, variant_id = local_data
            items.append(
                InsulationImportDecision(
                    project_insulation_key=row.project_insulation_key,
                    decision=decision_type,
                    local_family_id=family_id,
                    local_variant_id=variant_id,
                    use_local_after_adopt=row.use_local_after_adopt.isChecked(),
                )
            )
        return items

    def _build_summary_box(self) -> QWidget:
        box = QGroupBox("Matching-Zusammenfassung")
        form = QFormLayout(box)
        analysis = self._prepared.insulation_matching_analysis if isinstance(self._prepared.insulation_matching_analysis, dict) else {}
        summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}
        warnings = analysis.get("warnings", []) if isinstance(analysis.get("warnings"), list) else []
        errors = analysis.get("errors", []) if isinstance(analysis.get("errors"), list) else []
        form.addRow("Exakte Treffer", QLabel(str(summary.get("exact_match", 0))))
        form.addRow("Konfliktkandidaten", QLabel(str(summary.get("candidate_conflict", 0))))
        form.addRow("Keine Treffer", QLabel(str(summary.get("no_match", 0))))
        form.addRow("Ungültige Referenzen", QLabel(str(summary.get("invalid_reference", 0))))
        form.addRow("Warnungen", QLabel(str(len(warnings))))
        form.addRow("Fehler", QLabel(str(len(errors))))
        if warnings:
            warning_label = QLabel(" • " + "\n • ".join(str(item) for item in warnings[:3]))
            warning_label.setWordWrap(True)
            form.addRow("Warn-Details", warning_label)
        if errors:
            error_label = QLabel(" • " + "\n • ".join(str(item) for item in errors[:3]))
            error_label.setWordWrap(True)
            form.addRow("Fehler-Details", error_label)
        return box

    def _build_entries_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        entries = self._prepared.insulation_resolution.get("entries", [])
        if not isinstance(entries, list):
            entries = []

        if not entries:
            layout.addWidget(QLabel("Keine verwendeten Isolierungen im Import enthalten."))
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            panel = self._build_entry_panel(raw_entry)
            if panel is not None:
                layout.addWidget(panel)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _build_entry_panel(self, entry: dict[str, Any]) -> QWidget | None:
        project_key = str(entry.get("project_insulation_key", "")).strip()
        if not project_key:
            return None

        local_db = entry.get("local_db", {}) if isinstance(entry.get("local_db"), dict) else {}
        status = str(local_db.get("match_status") or "no_match")

        box = QGroupBox(self._format_target_label(entry))
        form = QFormLayout(box)
        form.addRow("Status", QLabel(self._status_label(status)))
        form.addRow("Vorgeschlagen", QLabel(self._format_local_ref(local_db.get("family_id"), local_db.get("variant_id"))))

        decision_combo = QComboBox()
        local_combo = QComboBox()
        adopt_checkbox = QCheckBox("Nach Übernahme lokal verwenden")

        self._fill_local_candidates(local_combo, entry)
        self._fill_decisions(decision_combo, status)
        self._set_defaults(entry, status, decision_combo, local_combo)

        decision_combo.currentIndexChanged.connect(
            lambda _index, dc=decision_combo, lc=local_combo, cb=adopt_checkbox: self._on_decision_changed(dc, lc, cb)
        )
        self._on_decision_changed(decision_combo, local_combo, adopt_checkbox)

        form.addRow("Lokale Kandidaten", local_combo)
        form.addRow("Entscheidung", decision_combo)
        form.addRow("Option", adopt_checkbox)

        note = QLabel(self._status_hint(status))
        note.setWordWrap(True)
        form.addRow("Hinweis", note)

        self._rows.append(
            _RowWidgets(
                project_insulation_key=project_key,
                decision_combo=decision_combo,
                local_combo=local_combo,
                use_local_after_adopt=adopt_checkbox,
                status=status,
            )
        )

        wrapper = QWidget()
        outer = QHBoxLayout(wrapper)
        outer.addWidget(box)
        return wrapper

    def _fill_local_candidates(self, combo: QComboBox, entry: dict[str, Any]) -> None:
        local_db = entry.get("local_db", {}) if isinstance(entry.get("local_db"), dict) else {}
        candidates = local_db.get("candidates", []) if isinstance(local_db.get("candidates"), list) else []
        exact_family = local_db.get("family_id")
        exact_variant = local_db.get("variant_id")
        if exact_family is not None:
            combo.addItem(
                f"Vorgeschlagener exakter Treffer: {self._format_local_ref(exact_family, exact_variant)}",
                (exact_family, exact_variant),
            )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            family_id = candidate.get("family_id")
            variant_id = candidate.get("variant_id")
            reason = str(candidate.get("reason") or "-")
            score = candidate.get("score")
            label = self._format_local_ref(family_id, variant_id)
            if score is not None:
                label = f"{label} (Grund: {reason}, Score: {score})"
            else:
                label = f"{label} (Grund: {reason})"
            combo.addItem(label, (family_id, variant_id))

    def _fill_decisions(self, combo: QComboBox, status: str) -> None:
        combo.addItem(_DECISION_LABELS[DECISION_USE_EMBEDDED], DECISION_USE_EMBEDDED)
        if status != "invalid_reference":
            combo.addItem(_DECISION_LABELS[DECISION_USE_LOCAL], DECISION_USE_LOCAL)
            combo.addItem(_DECISION_LABELS[DECISION_ADOPT_TO_LOCAL], DECISION_ADOPT_TO_LOCAL)

    def _set_defaults(self, entry: dict[str, Any], status: str, decision_combo: QComboBox, local_combo: QComboBox) -> None:
        if status == "exact_match":
            self._select_decision(decision_combo, DECISION_USE_LOCAL)
            if local_combo.count() > 0:
                local_combo.setCurrentIndex(0)
            return
        if status == "candidate_conflict":
            self._select_decision(decision_combo, DECISION_USE_EMBEDDED)
            return
        if status == "no_match":
            self._select_decision(decision_combo, DECISION_USE_EMBEDDED)
            return
        self._select_decision(decision_combo, DECISION_USE_EMBEDDED)

    def _on_decision_changed(self, decision_combo: QComboBox, local_combo: QComboBox, adopt_checkbox: QCheckBox) -> None:
        decision = str(decision_combo.currentData() or DECISION_USE_EMBEDDED)
        local_combo.setEnabled(decision == DECISION_USE_LOCAL)
        adopt_checkbox.setVisible(decision == DECISION_ADOPT_TO_LOCAL)
        if decision != DECISION_ADOPT_TO_LOCAL:
            adopt_checkbox.setChecked(False)

    def _validate_before_accept(self) -> None:
        for row in self._rows:
            decision = str(row.decision_combo.currentData() or DECISION_USE_EMBEDDED)
            if row.status == "candidate_conflict" and decision == DECISION_USE_LOCAL and row.local_combo.currentIndex() < 0:
                QMessageBox.warning(self, "Entscheidung fehlt", "Bei Konfliktfällen muss ein lokaler Kandidat gewählt werden.")
                return
            if decision == DECISION_USE_LOCAL and row.local_combo.currentIndex() < 0:
                QMessageBox.warning(self, "Entscheidung fehlt", "Für 'lokalen Datenbankeintrag verwenden' muss ein Kandidat gewählt werden.")
                return
            if row.status == "invalid_reference" and decision != DECISION_USE_EMBEDDED:
                QMessageBox.warning(self, "Ungültige Referenz", "Ungültige Referenzen können nur eingebettet verwendet werden.")
                return
        self.accept()

    def _status_hint(self, status: str) -> str:
        if status == "exact_match":
            return "Exakter Treffer wurde vorausgewählt, kann aber geändert werden."
        if status == "candidate_conflict":
            return "Konfliktkandidat erkannt: nichts wird automatisch lokal aktiviert."
        if status == "no_match":
            return "Kein lokaler Treffer: standardmäßig bleibt die eingebettete Version aktiv."
        return "Ungültige Referenz: sichere eingebettete Nutzung bleibt aktiv."

    def _status_label(self, status: str) -> str:
        labels = {
            "exact_match": "Exakter Match",
            "candidate_conflict": "Konfliktkandidat",
            "no_match": "Kein Match",
            "invalid_reference": "Ungültige Referenz",
        }
        return labels.get(status, status)

    def _format_target_label(self, entry: dict[str, Any]) -> str:
        family_key = str(entry.get("family_key", "")).strip()
        variant_key = str(entry.get("variant_key", "")).strip()
        key = variant_key or family_key
        target = self._embedded_index.get(key)
        if not isinstance(target, dict):
            return f"{entry.get('project_insulation_key')} (nicht auflösbar)"
        family = target.get("family") if isinstance(target.get("family"), dict) else {}
        variant = target.get("variant") if isinstance(target.get("variant"), dict) else None
        family_name = str(family.get("name") or "?")
        if variant is None:
            return f"{family_name} [Familie]"
        return f"{family_name} / {variant.get('name') or '?'}"

    def _format_local_ref(self, family_id: Any, variant_id: Any) -> str:
        try:
            family_int = int(family_id)
        except (TypeError, ValueError):
            return "Kein lokaler Treffer"
        try:
            family = get_family_by_id(family_int)
        except Exception:
            return f"Familie #{family_int}"
        family_name = str(family.get("name") or family_int)
        if variant_id is None:
            return family_name
        for variant in family.get("variants", []):
            if str(variant.get("id")) == str(variant_id):
                return f"{family_name} / {variant.get('name') or variant_id}"
        return f"{family_name} / Variante #{variant_id}"

    def _build_embedded_index(self, embedded: dict[str, Any]) -> dict[str, dict[str, Any]]:
        families = embedded.get("families", []) if isinstance(embedded, dict) else []
        index: dict[str, dict[str, Any]] = {}
        if not isinstance(families, list):
            return index
        for family in families:
            if not isinstance(family, dict):
                continue
            family_key = str(family.get("project_family_key", "")).strip()
            if family_key:
                index[family_key] = {"family": family, "variant": None}
            variants = family.get("variants", [])
            if not isinstance(variants, list):
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_key = str(variant.get("project_variant_key", "")).strip()
                if variant_key:
                    index[variant_key] = {"family": family, "variant": variant}
        return index

    def _select_decision(self, combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return
