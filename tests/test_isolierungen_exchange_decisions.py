import unittest
from pathlib import Path

from app.core.isolierungen_exchange.decision_service import (
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
    ACTION_USE_EXACT_MATCH,
    FamilyDecisionInput,
    PreparedInsulationImportDecisionService,
)
from app.core.isolierungen_exchange.matching_service import (
    FamilyMatchingResult,
    MatchingCandidate,
    PreparedInsulationImportMatchingAnalysis,
    VariantPerspective,
)


class PreparedInsulationImportDecisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PreparedInsulationImportDecisionService()

    def test_exact_match_can_be_selected_and_changed(self) -> None:
        analysis = self._analysis([
            self._result(status="exact_match", import_index=0, exact_family_id=21),
        ])
        exact = self.service.build_decisions(
            analysis,
            [FamilyDecisionInput(import_index=0, action=ACTION_USE_EXACT_MATCH)],
        )
        self.assertEqual(exact.family_decisions[0].action, ACTION_USE_EXACT_MATCH)

        changed = self.service.build_decisions(
            analysis,
            [FamilyDecisionInput(import_index=0, action=ACTION_SKIP_IMPORT)],
        )
        self.assertEqual(changed.family_decisions[0].action, ACTION_SKIP_IMPORT)

    def test_candidate_conflict_without_selection_fails(self) -> None:
        analysis = self._analysis([
            self._result(
                status="candidate_conflict",
                import_index=0,
                candidates=[self._candidate(7, "Local A")],
            ),
        ])

        with self.assertRaisesRegex(ValueError, "Kandidat"):
            self.service.build_decisions(
                analysis,
                [FamilyDecisionInput(import_index=0, action=ACTION_SELECT_CANDIDATE)],
            )

    def test_no_match_can_default_to_create_new(self) -> None:
        analysis = self._analysis([
            self._result(status="no_match", import_index=0),
        ])

        model = self.service.build_decisions(
            analysis,
            [FamilyDecisionInput(import_index=0, action=ACTION_CREATE_NEW)],
        )
        self.assertEqual(model.family_decisions[0].action, ACTION_CREATE_NEW)

    def test_missing_decision_behaves_like_cancel_no_model(self) -> None:
        analysis = self._analysis([
            self._result(status="no_match", import_index=0),
        ])

        with self.assertRaisesRegex(ValueError, "Fehlende Entscheidung"):
            self.service.build_decisions(analysis, [])

    def test_confirmed_decisions_produce_structured_model(self) -> None:
        analysis = self._analysis([
            self._result(status="exact_match", import_index=0, exact_family_id=5),
            self._result(
                status="candidate_conflict",
                import_index=1,
                candidates=[self._candidate(9, "Candidate 9"), self._candidate(12, "Candidate 12")],
            ),
            self._result(status="no_match", import_index=2),
        ])

        model = self.service.build_decisions(
            analysis,
            [
                FamilyDecisionInput(import_index=0, action=ACTION_USE_EXACT_MATCH),
                FamilyDecisionInput(import_index=1, action=ACTION_SELECT_CANDIDATE, selected_candidate_id=12),
                FamilyDecisionInput(import_index=2, action=ACTION_CREATE_NEW),
            ],
        )

        self.assertEqual(len(model.family_decisions), 3)
        self.assertEqual([item.import_index for item in model.family_decisions], [0, 1, 2])
        self.assertEqual(model.family_decisions[1].selected_candidate_id, 12)
        self.assertEqual(model.summary["candidate_conflict"], 1)
        self.assertEqual(model.source_path, Path("sample.hpxins.json"))

    def _analysis(self, results: list[FamilyMatchingResult]) -> PreparedInsulationImportMatchingAnalysis:
        summary = {"exact_match": 0, "candidate_conflict": 0, "no_match": 0}
        for item in results:
            summary[item.status] += 1
        return PreparedInsulationImportMatchingAnalysis(
            source_path=Path("sample.hpxins.json"),
            results=results,
            summary=summary,
            warnings=[],
        )

    def _result(
        self,
        *,
        status: str,
        import_index: int,
        exact_family_id: int | None = None,
        candidates: list[MatchingCandidate] | None = None,
    ) -> FamilyMatchingResult:
        return FamilyMatchingResult(
            import_index=import_index,
            import_family_name=f"Family {import_index}",
            status=status,
            exact_family_id=exact_family_id,
            candidates=candidates or [],
            variant_analysis=VariantPerspective([], [], [], []),
            notes=[],
        )

    def _candidate(self, family_id: int, family_name: str) -> MatchingCandidate:
        return MatchingCandidate(
            family_id=family_id,
            family_name=family_name,
            priority=90,
            reasons=["same_family_name"],
            variant_hints=VariantPerspective([], [], [], []),
        )


if __name__ == "__main__":
    unittest.main()
