"""Entscheidungsmodell für den Isolierungs-Austauschimport (ohne Persistierung)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .matching_service import PreparedInsulationImportMatchingAnalysis

ACTION_USE_EXACT_MATCH = "use_exact_match"
ACTION_CREATE_NEW = "create_new"
ACTION_SELECT_CANDIDATE = "select_candidate"
ACTION_SKIP_IMPORT = "skip_import"

_ALLOWED_ACTIONS = {
    ACTION_USE_EXACT_MATCH,
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
}


@dataclass(frozen=True)
class FamilyDecisionInput:
    import_index: int
    action: str
    selected_candidate_id: int | None = None


@dataclass(frozen=True)
class InsulationFamilyDecision:
    import_index: int
    import_family_name: str
    matching_status: str
    action: str
    selected_candidate_id: int | None
    exact_family_id: int | None


@dataclass(frozen=True)
class PreparedInsulationImportDecisions:
    source_path: Path
    summary: dict[str, int]
    warnings: list[str]
    family_decisions: list[InsulationFamilyDecision]


class PreparedInsulationImportDecisionService:
    """Validiert explizite Benutzerentscheidungen gegen die Matching-Analyse."""

    def build_decisions(
        self,
        analysis: PreparedInsulationImportMatchingAnalysis,
        decision_inputs: list[FamilyDecisionInput],
    ) -> PreparedInsulationImportDecisions:
        by_index: dict[int, FamilyDecisionInput] = {}
        for item in decision_inputs:
            if item.import_index in by_index:
                raise ValueError(f"Doppelte Entscheidung für Importindex {item.import_index}.")
            by_index[item.import_index] = item

        decisions: list[InsulationFamilyDecision] = []
        for result in analysis.results:
            raw = by_index.get(result.import_index)
            if raw is None:
                raise ValueError(f"Fehlende Entscheidung für Familie '{result.import_family_name}' (#{result.import_index}).")
            decisions.append(self._validate_and_map(result, raw))

        return PreparedInsulationImportDecisions(
            source_path=analysis.source_path,
            summary=dict(analysis.summary),
            warnings=list(analysis.warnings),
            family_decisions=decisions,
        )

    def _validate_and_map(self, result, item: FamilyDecisionInput) -> InsulationFamilyDecision:
        action = str(item.action or "").strip()
        if action not in _ALLOWED_ACTIONS:
            raise ValueError(f"Unbekannte Aktion für '{result.import_family_name}': {action!r}.")

        candidate_ids = {candidate.family_id for candidate in result.candidates}

        if action == ACTION_USE_EXACT_MATCH and result.exact_family_id is None:
            raise ValueError(f"Aktion 'use_exact_match' ist für '{result.import_family_name}' nicht zulässig.")

        selected_candidate_id = item.selected_candidate_id
        if action == ACTION_SELECT_CANDIDATE:
            if selected_candidate_id is None:
                raise ValueError(f"Für '{result.import_family_name}' muss ein Kandidat ausgewählt werden.")
            if selected_candidate_id not in candidate_ids:
                raise ValueError(
                    f"Ausgewählter Kandidat #{selected_candidate_id} ist für '{result.import_family_name}' nicht gültig."
                )
        else:
            selected_candidate_id = None

        return InsulationFamilyDecision(
            import_index=result.import_index,
            import_family_name=result.import_family_name,
            matching_status=result.status,
            action=action,
            selected_candidate_id=selected_candidate_id,
            exact_family_id=result.exact_family_id,
        )
