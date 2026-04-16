"""Importdialog für Isolierungs-Austauschdateien inkl. expliziter Benutzerentscheidungen."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
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

from app.core.isolierungen_exchange.decision_service import (
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
    ACTION_USE_EXACT_MATCH,
    FamilyDecisionInput,
    PreparedInsulationImportDecisionService,
    PreparedInsulationImportDecisions,
)
from app.core.isolierungen_exchange.matching_service import PreparedInsulationImportMatchingAnalysis


_DECISION_PLACEHOLDER = "__choose__"
_STATUS_LABELS = {
    "exact_match": "Exakter Treffer",
    "candidate_conflict": "Kandidaten-Konflikt",
    "no_match": "Kein lokaler Treffer",
}


@dataclass(slots=True)
class _DecisionRow:
    import_index: int
    status: str
    decision_combo: QComboBox
    candidate_combo: QComboBox
    has_candidates: bool


class InsulationExchangeImportDialog(QDialog):
    def __init__(self, analysis: PreparedInsulationImportMatchingAnalysis, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis = analysis
        self._decision_service = PreparedInsulationImportDecisionService()
        self._rows: list[_DecisionRow] = []
        self._decision_model: PreparedInsulationImportDecisions | None = None

        self.setWindowTitle("Isolierungs-Import: Matching & Entscheidungen")
        self.resize(980, 760)

        root = QVBoxLayout(self)
        root.addWidget(self._build_summary_box())
        root.addWidget(self._build_families_area(), stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def decisions(self) -> PreparedInsulationImportDecisions | None:
        return self._decision_model

    def _build_summary_box(self) -> QWidget:
        box = QGroupBox("Analyse-Summary")
        form = QFormLayout(box)
        summary = self._analysis.summary
        form.addRow("Familien gesamt", QLabel(str(len(self._analysis.results))))
        form.addRow("Exakte Treffer", QLabel(str(summary.get("exact_match", 0))))
        form.addRow("Kandidaten-Konflikte", QLabel(str(summary.get("candidate_conflict", 0))))
        form.addRow("Kein Match", QLabel(str(summary.get("no_match", 0))))

        warnings = self._analysis.warnings
        if warnings:
            warning_label = QLabel("• " + "\n• ".join(warnings))
            warning_label.setWordWrap(True)
            form.addRow("Warnungen", warning_label)
        else:
            form.addRow("Warnungen", QLabel("Keine"))
        return box

    def _build_families_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        for result in self._analysis.results:
            layout.addWidget(self._build_family_panel(result))

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _build_family_panel(self, result) -> QWidget:
        box = QGroupBox(f"Importfamilie #{result.import_index}: {result.import_family_name}")
        form = QFormLayout(box)

        form.addRow("Matching-Status", QLabel(_STATUS_LABELS.get(result.status, result.status)))
        form.addRow("Exakter lokaler Treffer", QLabel(self._format_exact(result.exact_family_id)))
        form.addRow("Varianten (gesamt)", QLabel(self._format_variant_hints(result.variant_analysis)))

        if result.candidates:
            candidates_text = QLabel("\n".join(self._format_candidate_line(candidate) for candidate in result.candidates))
            candidates_text.setWordWrap(True)
            form.addRow("Kandidaten", candidates_text)
        else:
            form.addRow("Kandidaten", QLabel("Keine Kandidaten."))

        if result.notes:
            note_label = QLabel("\n".join(f"• {note}" for note in result.notes))
            note_label.setWordWrap(True)
            form.addRow("Hinweise", note_label)

        decision_combo = QComboBox()
        candidate_combo = QComboBox()
        has_candidates = bool(result.candidates)

        self._fill_decisions(decision_combo, result.status, has_candidates)
        self._fill_candidates(candidate_combo, result)
        self._set_default_for_status(result.status, decision_combo)

        decision_combo.currentIndexChanged.connect(
            lambda _idx, d=decision_combo, c=candidate_combo: self._on_decision_changed(d, c)
        )
        self._on_decision_changed(decision_combo, candidate_combo)

        form.addRow("Entscheidung", decision_combo)
        form.addRow("Kandidat auswählen", candidate_combo)
        form.addRow("Hinweis", QLabel(self._status_hint(result.status)))

        self._rows.append(
            _DecisionRow(
                import_index=result.import_index,
                status=result.status,
                decision_combo=decision_combo,
                candidate_combo=candidate_combo,
                has_candidates=has_candidates,
            )
        )

        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.addWidget(box)
        return wrap

    def _fill_decisions(self, combo: QComboBox, status: str, has_candidates: bool) -> None:
        if status == "candidate_conflict":
            combo.addItem("Bitte explizit auswählen …", _DECISION_PLACEHOLDER)
        combo.addItem("Exakten Treffer übernehmen", ACTION_USE_EXACT_MATCH)
        combo.addItem("Neuen Eintrag anlegen", ACTION_CREATE_NEW)
        if has_candidates:
            combo.addItem("Kandidat manuell auswählen", ACTION_SELECT_CANDIDATE)
        combo.addItem("Import überspringen", ACTION_SKIP_IMPORT)

    def _fill_candidates(self, combo: QComboBox, result) -> None:
        if not result.candidates:
            combo.addItem("Keine Kandidaten verfügbar", None)
            return
        combo.addItem("Bitte Kandidat wählen …", None)
        for candidate in result.candidates:
            combo.addItem(
                f"#{candidate.family_id} · {candidate.family_name} ({', '.join(candidate.reasons)})",
                int(candidate.family_id),
            )

    def _set_default_for_status(self, status: str, combo: QComboBox) -> None:
        if status == "exact_match":
            self._select_decision(combo, ACTION_USE_EXACT_MATCH)
        elif status == "no_match":
            self._select_decision(combo, ACTION_CREATE_NEW)
        else:
            self._select_decision(combo, _DECISION_PLACEHOLDER)

    def _select_decision(self, combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return

    def _on_decision_changed(self, decision_combo: QComboBox, candidate_combo: QComboBox) -> None:
        action = decision_combo.currentData()
        candidate_combo.setEnabled(action == ACTION_SELECT_CANDIDATE)

    def _confirm(self) -> None:
        inputs: list[FamilyDecisionInput] = []
        for row in self._rows:
            action = row.decision_combo.currentData()
            if action == _DECISION_PLACEHOLDER:
                QMessageBox.warning(
                    self,
                    "Entscheidung fehlt",
                    "Bei Kandidaten-Konflikten bitte explizit 'Kandidat auswählen', 'Neuen Eintrag' oder 'Überspringen' wählen.",
                )
                return

            selected_candidate_id = None
            if action == ACTION_SELECT_CANDIDATE:
                selected_candidate_id = row.candidate_combo.currentData()
                if selected_candidate_id is None:
                    QMessageBox.warning(self, "Kandidat fehlt", "Bitte einen konkreten lokalen Kandidaten auswählen.")
                    return

            if action == ACTION_USE_EXACT_MATCH and row.status != "exact_match":
                QMessageBox.warning(
                    self,
                    "Ungültige Auswahl",
                    "'Exakten Treffer übernehmen' ist nur bei Status 'exact_match' zulässig.",
                )
                return

            inputs.append(
                FamilyDecisionInput(
                    import_index=row.import_index,
                    action=str(action),
                    selected_candidate_id=int(selected_candidate_id) if selected_candidate_id is not None else None,
                )
            )

        try:
            self._decision_model = self._decision_service.build_decisions(self._analysis, inputs)
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültige Entscheidungen", str(exc))
            return
        self.accept()

    def _format_exact(self, exact_family_id: int | None) -> str:
        if exact_family_id is None:
            return "Kein exakter Treffer"
        return f"Lokale Familie #{exact_family_id}"

    def _format_candidate_line(self, candidate) -> str:
        hints = self._format_variant_hints(candidate.variant_hints)
        return (
            f"#{candidate.family_id} · {candidate.family_name} "
            f"(Priorität: {candidate.priority}, Gründe: {', '.join(candidate.reasons)}; Varianten: {hints})"
        )

    def _format_variant_hints(self, hints) -> str:
        def _join(items: list[str]) -> str:
            return ", ".join(items) if items else "—"

        return (
            f"exakt: {_join(hints.exact_variant_names)} | "
            f"fehlend: {_join(hints.missing_local_variant_names)} | "
            f"Konflikte: {_join(hints.conflicting_variant_names)}"
        )

    def _status_hint(self, status: str) -> str:
        if status == "exact_match":
            return "Exakter Treffer ist vorausgewählt, kann aber geändert werden."
        if status == "candidate_conflict":
            return "Kein Auto-Merge: Entscheidung muss explizit getroffen werden."
        return "Kein lokaler Treffer: Standard ist 'Neuen Eintrag anlegen'."
