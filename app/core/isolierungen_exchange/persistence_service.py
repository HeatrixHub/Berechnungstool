"""Transaktionale Persistierung bestätigter Austausch-Importentscheidungen."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.isolierungen_db.repository import IsolierungRepository

from .decision_service import (
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
    ACTION_USE_EXACT_MATCH,
    InsulationFamilyDecision,
    PreparedInsulationImportDecisions,
)
from .import_service import PreparedInsulationFamilyImport, PreparedInsulationImport
from .matching_service import PreparedInsulationImportMatchingAnalysis
from .normalization import normalize_family_portable_for_compare


@dataclass(frozen=True)
class FamilyPersistenceOutcome:
    import_index: int
    import_family_name: str
    action: str
    status: str
    message: str | None = None
    created_family_id: int | None = None
    selected_candidate_id: int | None = None
    expected_variant_count: int | None = None
    expected_measurement_count: int | None = None


@dataclass(frozen=True)
class PreparedInsulationImportPersistenceResult:
    success: bool
    source_path: str
    summary: dict[str, int]
    outcomes: list[FamilyPersistenceOutcome]
    errors: list[str]


class PreparedInsulationImportPersistenceService:
    """Persistiert Importentscheidungen atomar in die lokale Isolierungs-DB."""

    def __init__(self, *, repository: IsolierungRepository | None = None) -> None:
        self._repository = repository or IsolierungRepository()

    def persist(
        self,
        prepared: PreparedInsulationImport,
        analysis: PreparedInsulationImportMatchingAnalysis,
        decisions: PreparedInsulationImportDecisions,
    ) -> PreparedInsulationImportPersistenceResult:
        self._validate_model_consistency(prepared, analysis, decisions)

        prepared_by_index = {item.index: item for item in prepared.families}
        matching_by_index = {item.import_index: item for item in analysis.results}

        outcomes: list[FamilyPersistenceOutcome] = []
        errors: list[str] = []
        created_family_ids: list[int] = []

        try:
            with self._repository.transaction() as conn:
                for decision in decisions.family_decisions:
                    outcome = self._apply_single_decision(
                        conn=conn,
                        decision=decision,
                        prepared_family=prepared_by_index.get(decision.import_index),
                        matching_result=matching_by_index.get(decision.import_index),
                    )
                    outcomes.append(outcome)
                    if outcome.created_family_id is not None:
                        created_family_ids.append(outcome.created_family_id)

                self._validate_persisted_families(conn, created_family_ids, expected_outcomes=outcomes)
        except Exception as exc:
            errors.append(str(exc))
            outcomes = self._mark_outcomes_rolled_back(outcomes)
            summary = self._build_summary(outcomes)
            summary["errors"] = len(errors)
            return PreparedInsulationImportPersistenceResult(
                success=False,
                source_path=str(prepared.source_path),
                summary=summary,
                outcomes=outcomes,
                errors=errors,
            )

        summary = self._build_summary(outcomes)
        return PreparedInsulationImportPersistenceResult(
            success=True,
            source_path=str(prepared.source_path),
            summary=summary,
            outcomes=outcomes,
            errors=[],
        )

    def _validate_model_consistency(
        self,
        prepared: PreparedInsulationImport,
        analysis: PreparedInsulationImportMatchingAnalysis,
        decisions: PreparedInsulationImportDecisions,
    ) -> None:
        if analysis.source_path != prepared.source_path or decisions.source_path != prepared.source_path:
            raise ValueError("PreparedImport, Matching-Analyse und Entscheidungsmodell gehören nicht zur gleichen Quelle.")
        expected_indices = {item.index for item in prepared.families}
        if {item.import_index for item in analysis.results} != expected_indices:
            raise ValueError("Matching-Analyse passt nicht vollständig zu den vorbereiteten Importfamilien.")
        if {item.import_index for item in decisions.family_decisions} != expected_indices:
            raise ValueError("Entscheidungsmodell passt nicht vollständig zu den vorbereiteten Importfamilien.")

    def _apply_single_decision(
        self,
        *,
        conn,
        decision: InsulationFamilyDecision,
        prepared_family: PreparedInsulationFamilyImport | None,
        matching_result,
    ) -> FamilyPersistenceOutcome:
        if prepared_family is None or matching_result is None:
            raise ValueError(f"Interner Fehler: Importindex {decision.import_index} kann nicht aufgelöst werden.")

        imported = prepared_family.family

        if decision.action == ACTION_USE_EXACT_MATCH:
            if matching_result.status != "exact_match":
                raise ValueError(
                    f"use_exact_match für '{decision.import_family_name}' ist nur bei exact_match zulässig."
                )
            if decision.exact_family_id is None:
                raise ValueError(f"Exact-Match-Entscheidung für '{decision.import_family_name}' ohne Ziel-ID.")
            return FamilyPersistenceOutcome(
                import_index=decision.import_index,
                import_family_name=decision.import_family_name,
                action=decision.action,
                status="exact_match_confirmed",
                selected_candidate_id=decision.exact_family_id,
            )

        if decision.action == ACTION_SKIP_IMPORT:
            return FamilyPersistenceOutcome(
                import_index=decision.import_index,
                import_family_name=decision.import_family_name,
                action=decision.action,
                status="skipped",
            )

        if decision.action == ACTION_CREATE_NEW:
            family_name = str(imported.get("name", "")).strip()
            if self._repository.get_family_by_name_in_connection(conn, family_name) is not None:
                raise ValueError(
                    f"Import abgebrochen: create_new für '{family_name}' nicht möglich, Name existiert bereits lokal."
                )

            created_id = self._repository.create_family_in_connection(
                conn,
                name=family_name,
                classification_temp=float(imported["classification_temp"]),
                max_temp=imported.get("max_temp"),
                density=float(imported["density"]),
                temps=[float(v) for v in imported.get("temps", [])],
                ks=[float(v) for v in imported.get("ks", [])],
            )
            self._create_variants_for_family(conn, family_id=created_id, imported_family=imported)
            return FamilyPersistenceOutcome(
                import_index=decision.import_index,
                import_family_name=decision.import_family_name,
                action=decision.action,
                status="created",
                created_family_id=created_id,
                expected_variant_count=len(imported.get("variants", [])),
                expected_measurement_count=len(imported.get("temps", [])),
            )

        if decision.action == ACTION_SELECT_CANDIDATE:
            if matching_result.status != "candidate_conflict":
                raise ValueError(
                    f"select_candidate für '{decision.import_family_name}' ist nur bei candidate_conflict zulässig."
                )
            candidate_id = decision.selected_candidate_id
            if candidate_id is None:
                raise ValueError(f"select_candidate für '{decision.import_family_name}' ohne candidate_id.")
            valid_candidate_ids = {candidate.family_id for candidate in matching_result.candidates}
            if int(candidate_id) not in valid_candidate_ids:
                raise ValueError(
                    f"select_candidate für '{decision.import_family_name}' verweist auf nicht analysierten Kandidaten #{candidate_id}."
                )

            local_candidate = self._repository.get_family_in_connection(conn, int(candidate_id))
            if local_candidate is None:
                raise ValueError(
                    f"select_candidate für '{decision.import_family_name}' fehlgeschlagen: Kandidat #{candidate_id} existiert nicht."
                )

            imported_portable = normalize_family_portable_for_compare(imported)
            local_portable = normalize_family_portable_for_compare(local_candidate)
            if imported_portable != local_portable:
                raise ValueError(
                    "select_candidate ist in diesem Schritt nur als sicherer No-Op erlaubt, "
                    f"aber '{decision.import_family_name}' weicht vom gewählten Kandidaten #{candidate_id} ab."
                )

            return FamilyPersistenceOutcome(
                import_index=decision.import_index,
                import_family_name=decision.import_family_name,
                action=decision.action,
                status="candidate_confirmed_noop",
                selected_candidate_id=candidate_id,
            )

        raise ValueError(f"Unbekannte Persistierungsaktion: {decision.action!r}.")

    def _create_variants_for_family(self, conn, *, family_id: int, imported_family: dict) -> None:
        seen_names: set[str] = set()
        for variant in imported_family.get("variants", []):
            variant_name = str(variant.get("name", "")).strip()
            variant_key = variant_name.casefold()
            if variant_key in seen_names:
                raise ValueError(
                    f"Import abgebrochen: Doppelte Variantenbezeichnung '{variant_name}' innerhalb der neuen Familie."
                )
            seen_names.add(variant_key)
            self._repository.create_variant_in_connection(
                conn,
                family_id=family_id,
                name=variant_name,
                thickness=float(variant["thickness"]),
                length=variant.get("length"),
                width=variant.get("width"),
                price=variant.get("price"),
            )

    def _validate_persisted_families(
        self,
        conn,
        created_family_ids: list[int],
        *,
        expected_outcomes: list[FamilyPersistenceOutcome],
    ) -> None:
        expected_by_family = {
            item.created_family_id: item
            for item in expected_outcomes
            if item.created_family_id is not None
        }
        for family_id in created_family_ids:
            loaded = self._repository.get_family_in_connection(conn, family_id)
            if loaded is None:
                raise RuntimeError(f"Post-Persist-Validierung fehlgeschlagen: Familie #{family_id} nicht lesbar.")

            expected = expected_by_family.get(family_id)
            if expected is None:
                raise RuntimeError(
                    f"Post-Persist-Validierung fehlgeschlagen: keine Erwartung für Familie #{family_id} vorhanden."
                )

            expected_variant_count = expected.expected_variant_count
            actual_variant_count = len(loaded.get("variants", []))
            if expected_variant_count is not None and actual_variant_count != expected_variant_count:
                raise RuntimeError(
                    "Post-Persist-Validierung fehlgeschlagen: Variantenzahl für "
                    f"Familie #{family_id} erwartet={expected_variant_count} ist={actual_variant_count}."
                )

            expected_measurement_count = expected.expected_measurement_count
            actual_measurement_count = len(loaded.get("temps", []))
            if expected_measurement_count is not None and actual_measurement_count != expected_measurement_count:
                raise RuntimeError(
                    "Post-Persist-Validierung fehlgeschlagen: Messpunktanzahl für "
                    f"Familie #{family_id} erwartet={expected_measurement_count} ist={actual_measurement_count}."
                )

    def _build_summary(self, outcomes: list[FamilyPersistenceOutcome]) -> dict[str, int]:
        summary = {
            "created": 0,
            "skipped": 0,
            "exact_match_confirmed": 0,
            "candidate_confirmed_noop": 0,
            "candidate_rejected": 0,
            "rolled_back": 0,
            "errors": 0,
            "total": len(outcomes),
        }
        for item in outcomes:
            if item.status in summary:
                summary[item.status] += 1
        return summary

    def _mark_outcomes_rolled_back(
        self,
        outcomes: list[FamilyPersistenceOutcome],
    ) -> list[FamilyPersistenceOutcome]:
        rolled_back: list[FamilyPersistenceOutcome] = []
        for item in outcomes:
            if item.status != "created":
                rolled_back.append(item)
                continue
            rolled_back.append(
                FamilyPersistenceOutcome(
                    import_index=item.import_index,
                    import_family_name=item.import_family_name,
                    action=item.action,
                    status="rolled_back",
                    message="Transaktion wegen Folgefehler zurückgerollt.",
                    created_family_id=item.created_family_id,
                    selected_candidate_id=item.selected_candidate_id,
                    expected_variant_count=item.expected_variant_count,
                    expected_measurement_count=item.expected_measurement_count,
                )
            )
        return rolled_back
