import tempfile
import unittest
from pathlib import Path

from app.core.isolierungen_db.repository import IsolierungRepository
from app.core.isolierungen_exchange.decision_service import (
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
    ACTION_USE_EXACT_MATCH,
    InsulationFamilyDecision,
    PreparedInsulationImportDecisions,
)
from app.core.isolierungen_exchange.import_service import (
    PreparedInsulationFamilyImport,
    PreparedInsulationImport,
)
from app.core.isolierungen_exchange.matching_service import (
    FamilyMatchingResult,
    MatchingCandidate,
    PreparedInsulationImportMatchingAnalysis,
    VariantPerspective,
)
from app.core.isolierungen_exchange.persistence_service import PreparedInsulationImportPersistenceService


class PreparedInsulationImportPersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self._tmp.close()
        self.repo = IsolierungRepository(db_path=self._tmp.name)
        self.service = PreparedInsulationImportPersistenceService(repository=self.repo)
        self.source_path = Path("sample.hpxins.json")

    def tearDown(self) -> None:
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_create_new_creates_family_and_variants(self) -> None:
        prepared = self._prepared([self._import_family(0, "Neue Familie", variants=2)])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Neue Familie", status="no_match"),
        ])
        decisions = self._decisions([
            self._decision(import_index=0, family_name="Neue Familie", action=ACTION_CREATE_NEW, status="no_match"),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertTrue(result.success)
        self.assertEqual(result.summary["created"], 1)
        families = self.repo.list_families()
        self.assertEqual(len(families), 1)
        persisted = self.repo.get_family(int(families[0]["id"]))
        assert persisted is not None
        self.assertEqual(persisted["name"], "Neue Familie")
        self.assertEqual(len(persisted["variants"]), 2)

    def test_use_exact_match_is_noop(self) -> None:
        existing_id = self.repo.create_family("Bestehend", 100.0, 350.0, 60.0, [20.0, 40.0], [0.03, 0.04])
        self.repo.create_variant(existing_id, "V1", 20.0, 1000.0, 500.0, 10.0)

        prepared = self._prepared([self._import_family(0, "Irgendwas", variants=1)])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Irgendwas", status="exact_match", exact_family_id=existing_id),
        ])
        decisions = self._decisions([
            self._decision(
                import_index=0,
                family_name="Irgendwas",
                action=ACTION_USE_EXACT_MATCH,
                status="exact_match",
                exact_family_id=existing_id,
            ),
        ])

        before = len(self.repo.list_families())
        result = self.service.persist(prepared, analysis, decisions)
        after = len(self.repo.list_families())

        self.assertTrue(result.success)
        self.assertEqual(before, after)
        self.assertEqual(result.summary["exact_match_confirmed"], 1)

    def test_skip_import_is_noop(self) -> None:
        prepared = self._prepared([self._import_family(0, "Skip Me", variants=1)])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Skip Me", status="no_match"),
        ])
        decisions = self._decisions([
            self._decision(import_index=0, family_name="Skip Me", action=ACTION_SKIP_IMPORT, status="no_match"),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertTrue(result.success)
        self.assertEqual(len(self.repo.list_families()), 0)
        self.assertEqual(result.summary["skipped"], 1)

    def test_create_new_name_collision_fails_without_overwrite(self) -> None:
        self.repo.create_family("Collision", 90.0, 250.0, 50.0, [20.0, 50.0], [0.03, 0.035])

        prepared = self._prepared([self._import_family(0, "Collision", variants=1)])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Collision", status="no_match"),
        ])
        decisions = self._decisions([
            self._decision(import_index=0, family_name="Collision", action=ACTION_CREATE_NEW, status="no_match"),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertFalse(result.success)
        self.assertIn("existiert bereits", " ".join(result.errors))
        self.assertEqual(len(self.repo.list_families()), 1)

    def test_partial_failure_rolls_back_complete_import_run(self) -> None:
        self.repo.create_family("Kollision", 90.0, 250.0, 50.0, [20.0, 50.0], [0.03, 0.035])

        prepared = self._prepared([
            self._import_family(0, "Neu OK", variants=1),
            self._import_family(1, "Kollision", variants=1),
        ])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Neu OK", status="no_match"),
            self._matching_result(import_index=1, family_name="Kollision", status="no_match"),
        ])
        decisions = self._decisions([
            self._decision(import_index=0, family_name="Neu OK", action=ACTION_CREATE_NEW, status="no_match"),
            self._decision(import_index=1, family_name="Kollision", action=ACTION_CREATE_NEW, status="no_match"),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertFalse(result.success)
        family_names = {row["name"] for row in self.repo.list_families()}
        self.assertEqual(family_names, {"Kollision"})

    def test_select_candidate_rejects_non_identical_merge(self) -> None:
        candidate_id = self.repo.create_family("Local", 100.0, 350.0, 60.0, [20.0, 40.0], [0.03, 0.04])
        self.repo.create_variant(candidate_id, "V1", 20.0, 1000.0, 500.0, 10.0)

        prepared = self._prepared([self._import_family(0, "Import abweichend", variants=2)])
        analysis = self._analysis([
            self._matching_result(
                import_index=0,
                family_name="Import abweichend",
                status="candidate_conflict",
                candidates=[self._candidate(candidate_id, "Local")],
            ),
        ])
        decisions = self._decisions([
            self._decision(
                import_index=0,
                family_name="Import abweichend",
                action=ACTION_SELECT_CANDIDATE,
                status="candidate_conflict",
                selected_candidate_id=candidate_id,
            ),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertFalse(result.success)
        self.assertIn("nur als sicherer No-Op erlaubt", " ".join(result.errors))
        self.assertEqual(len(self.repo.list_families()), 1)

    def test_result_summary_reports_outcomes(self) -> None:
        existing_id = self.repo.create_family("Exakt", 100.0, 350.0, 60.0, [20.0, 40.0], [0.03, 0.04])
        self.repo.create_variant(existing_id, "V1", 20.0, 1000.0, 500.0, 10.0)

        prepared = self._prepared([
            self._import_family(0, "Create", variants=1),
            self._import_family(1, "Exact", variants=1),
            self._import_family(2, "Skip", variants=1),
        ])
        analysis = self._analysis([
            self._matching_result(import_index=0, family_name="Create", status="no_match"),
            self._matching_result(import_index=1, family_name="Exact", status="exact_match", exact_family_id=existing_id),
            self._matching_result(import_index=2, family_name="Skip", status="no_match"),
        ])
        decisions = self._decisions([
            self._decision(import_index=0, family_name="Create", action=ACTION_CREATE_NEW, status="no_match"),
            self._decision(
                import_index=1,
                family_name="Exact",
                action=ACTION_USE_EXACT_MATCH,
                status="exact_match",
                exact_family_id=existing_id,
            ),
            self._decision(import_index=2, family_name="Skip", action=ACTION_SKIP_IMPORT, status="no_match"),
        ])

        result = self.service.persist(prepared, analysis, decisions)

        self.assertTrue(result.success)
        self.assertEqual(result.summary["created"], 1)
        self.assertEqual(result.summary["exact_match_confirmed"], 1)
        self.assertEqual(result.summary["skipped"], 1)
        self.assertEqual(result.summary["total"], 3)

    def _prepared(self, families: list[PreparedInsulationFamilyImport]) -> PreparedInsulationImport:
        return PreparedInsulationImport(
            source_path=self.source_path,
            export_format_name="heatrix-isolierungen",
            export_format_version=1,
            exported_at=None,
            app_version=None,
            families=families,
            issues=[],
        )

    def _analysis(self, results: list[FamilyMatchingResult]) -> PreparedInsulationImportMatchingAnalysis:
        summary = {"exact_match": 0, "candidate_conflict": 0, "no_match": 0}
        for result in results:
            summary[result.status] += 1
        return PreparedInsulationImportMatchingAnalysis(
            source_path=self.source_path,
            results=results,
            summary=summary,
            warnings=[],
        )

    def _decisions(self, decisions: list[InsulationFamilyDecision]) -> PreparedInsulationImportDecisions:
        return PreparedInsulationImportDecisions(
            source_path=self.source_path,
            summary={"exact_match": 0, "candidate_conflict": 0, "no_match": 0},
            warnings=[],
            family_decisions=decisions,
        )

    def _import_family(self, index: int, name: str, *, variants: int) -> PreparedInsulationFamilyImport:
        family = {
            "name": name,
            "classification_temp": 110.0,
            "max_temp": 400.0,
            "density": 80.0,
            "temps": [20.0, 40.0, 80.0],
            "ks": [0.031, 0.033, 0.038],
            "variants": [
                {
                    "name": f"V{variant_index + 1}",
                    "thickness": float(20 + variant_index),
                    "length": 1000.0,
                    "width": 500.0,
                    "price": 12.0,
                }
                for variant_index in range(variants)
            ],
        }
        return PreparedInsulationFamilyImport(index=index, family=family, source_local=None)

    def _matching_result(
        self,
        *,
        import_index: int,
        family_name: str,
        status: str,
        exact_family_id: int | None = None,
        candidates: list[MatchingCandidate] | None = None,
    ) -> FamilyMatchingResult:
        return FamilyMatchingResult(
            import_index=import_index,
            import_family_name=family_name,
            status=status,
            exact_family_id=exact_family_id,
            candidates=candidates or [],
            variant_analysis=VariantPerspective([], [], [], []),
            notes=[],
        )

    def _decision(
        self,
        *,
        import_index: int,
        family_name: str,
        action: str,
        status: str,
        exact_family_id: int | None = None,
        selected_candidate_id: int | None = None,
    ) -> InsulationFamilyDecision:
        return InsulationFamilyDecision(
            import_index=import_index,
            import_family_name=family_name,
            matching_status=status,
            action=action,
            selected_candidate_id=selected_candidate_id,
            exact_family_id=exact_family_id,
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
