import unittest
from pathlib import Path

from app.core.isolierungen_exchange.import_service import (
    ImportIssue,
    PreparedInsulationFamilyImport,
    PreparedInsulationImport,
)
from app.core.isolierungen_exchange.matching_service import (
    PreparedInsulationImportMatchingService,
)


class InsulationExchangeMatchingTests(unittest.TestCase):
    def test_exact_match_when_family_and_variants_are_portably_identical(self):
        prepared = self._prepared([self._family_import(0, self._family_a())])
        service = PreparedInsulationImportMatchingService(
            local_family_provider=lambda: [self._local_family(10, self._family_a())]
        )

        analysis = service.analyze(prepared)

        self.assertEqual(analysis.summary["exact_match"], 1)
        result = analysis.results[0]
        self.assertEqual(result.status, "exact_match")
        self.assertEqual(result.exact_family_id, 10)
        self.assertEqual(result.candidates, [])

    def test_no_match_when_no_plausible_candidate_exists(self):
        prepared = self._prepared([self._family_import(0, self._family_a(name="Alpha"))])
        service = PreparedInsulationImportMatchingService(
            local_family_provider=lambda: [self._local_family(11, self._family_b(name="Zulu"))]
        )

        analysis = service.analyze(prepared)

        self.assertEqual(analysis.summary["no_match"], 1)
        self.assertEqual(analysis.results[0].status, "no_match")
        self.assertEqual(analysis.results[0].candidates, [])

    def test_candidate_conflict_for_same_name_but_different_family_core(self):
        imported = self._family_a(name="Mineralwolle A", density=95)
        local = self._family_a(name="Mineralwolle A", density=120)
        prepared = self._prepared([self._family_import(0, imported)])
        service = PreparedInsulationImportMatchingService(
            local_family_provider=lambda: [self._local_family(12, local)]
        )

        analysis = service.analyze(prepared)

        result = analysis.results[0]
        self.assertEqual(result.status, "candidate_conflict")
        self.assertIsNone(result.exact_family_id)
        self.assertEqual(len(result.candidates), 1)
        self.assertIn("same_family_name", result.candidates[0].reasons)

    def test_candidate_conflict_for_same_family_core_with_variant_differences(self):
        imported = self._family_a(
            variants=[
                {"name": "30 mm", "thickness": 30.0, "length": 1000.0, "width": 500.0, "price": 12.5},
                {"name": "40 mm", "thickness": 40.0, "length": 1000.0, "width": 500.0, "price": 15.0},
            ]
        )
        local = self._family_a(
            variants=[
                {"name": "30 mm", "thickness": 31.0, "length": 1000.0, "width": 500.0, "price": 12.5},
            ]
        )
        prepared = self._prepared([self._family_import(0, imported)])
        service = PreparedInsulationImportMatchingService(
            local_family_provider=lambda: [self._local_family(13, local)]
        )

        analysis = service.analyze(prepared)

        result = analysis.results[0]
        self.assertEqual(result.status, "candidate_conflict")
        self.assertIn("same_family_core_values", result.candidates[0].reasons)
        self.assertEqual(result.variant_analysis.missing_local_variant_names, ["40 mm"])
        self.assertEqual(result.variant_analysis.conflicting_variant_names, ["30 mm"])

    def test_exact_is_kept_separate_from_candidate_conflict(self):
        imported = self._family_a(name="Glass Wool")
        prepared = self._prepared([self._family_import(0, imported)])
        service = PreparedInsulationImportMatchingService(
            local_family_provider=lambda: [
                self._local_family(14, imported),
                self._local_family(15, self._family_a(name="Glass Wool", density=101)),
            ]
        )

        analysis = service.analyze(prepared)

        result = analysis.results[0]
        self.assertEqual(result.status, "exact_match")
        self.assertEqual(result.exact_family_id, 14)
        self.assertEqual(result.candidates, [])

    def test_prepared_warnings_are_carried_defensively(self):
        prepared = self._prepared(
            [self._family_import(0, self._family_a())],
            issues=[ImportIssue(level="warning", code="duplicate_variant_name", message="dup", path="isolierungen[0]")],
        )
        service = PreparedInsulationImportMatchingService(local_family_provider=lambda: [])

        analysis = service.analyze(prepared)

        self.assertTrue(analysis.warnings)
        self.assertIn("Hinweis", analysis.warnings[0])
        self.assertIn("dup", analysis.results[0].notes)

    def _prepared(
        self,
        families: list[PreparedInsulationFamilyImport],
        issues: list[ImportIssue] | None = None,
    ) -> PreparedInsulationImport:
        return PreparedInsulationImport(
            source_path=Path("sample.hpxins.json"),
            export_format_name="heatrix_insulation_exchange",
            export_format_version=1,
            exported_at=None,
            app_version=None,
            families=families,
            issues=issues or [],
        )

    def _family_import(self, index: int, family: dict, source_local: dict | None = None) -> PreparedInsulationFamilyImport:
        return PreparedInsulationFamilyImport(index=index, family=family, source_local=source_local)

    @staticmethod
    def _local_family(family_id: int, portable_family: dict) -> dict:
        return {"id": family_id, "portable": portable_family}

    @staticmethod
    def _family_a(
        name: str = "Mineralwolle A",
        density: float = 95.0,
        variants: list[dict] | None = None,
    ) -> dict:
        return {
            "name": name,
            "classification_temp": 650.0,
            "max_temp": 700.0,
            "density": density,
            "temps": [20.0, 100.0],
            "ks": [0.04, 0.06],
            "variants": variants
            if variants is not None
            else [
                {"name": "30 mm", "thickness": 30.0, "length": 1000.0, "width": 500.0, "price": 12.5}
            ],
        }

    @staticmethod
    def _family_b(name: str = "Alternative") -> dict:
        return {
            "name": name,
            "classification_temp": 400.0,
            "max_temp": 450.0,
            "density": 60.0,
            "temps": [20.0, 80.0],
            "ks": [0.07, 0.09],
            "variants": [
                {"name": "10 mm", "thickness": 10.0, "length": 1200.0, "width": 600.0, "price": 5.0}
            ],
        }


if __name__ == "__main__":
    unittest.main()
