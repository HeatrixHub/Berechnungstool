import unittest
from unittest.mock import patch

from app.core.projects.import_service import ProjectImportError, ProjectImportService
from app.core.projects.insulation_matching import InsulationImportMatchingService
from app.core.projects.insulation_runtime_resolution import InsulationRuntimeResolver
from app.core.projects.isolierung_embedding import build_embedded_isolierungen_from_plugin_states


class RuntimeResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = InsulationRuntimeResolver()
        self.plugin_states = {
            "isolierung": {
                "inputs": {
                    "berechnung": {
                        "layers": [
                            {"family_id": 1, "variant_id": None, "family": "Old", "variant": ""}
                        ]
                    }
                }
            }
        }
        self.embedded = {
            "families": [
                {
                    "project_family_key": "fam-1",
                    "name": "Embedded A",
                    "classification_temp": 100,
                    "max_temp": 150,
                    "density": 80,
                    "temps": [0, 100],
                    "ks": [0.04, 0.05],
                    "variants": [],
                }
            ]
        }

    @patch("app.core.projects.insulation_runtime_resolution.get_family_by_id")
    def test_embedded_without_local_reference(self, _mock_get_family):
        result = self.resolver.resolve_project_runtime(
            plugin_states=self.plugin_states,
            embedded_isolierungen=self.embedded,
            insulation_resolution={
                "entries": [
                    {
                        "project_insulation_key": "fam-1",
                        "family_key": "fam-1",
                        "variant_key": None,
                        "active_source": "embedded",
                        "local_db": {"family_id": None, "variant_id": None},
                    }
                ]
            },
        )
        item = result.resolved_items[0]
        self.assertEqual(item.effective_source, "embedded")
        self.assertEqual(item.local_status, "Keine Verknüpfung")
        self.assertEqual(result.plugin_states["isolierung"]["inputs"]["berechnung"]["layers"][0]["family"], "Embedded A")

    @patch("app.core.projects.insulation_runtime_resolution.get_family_by_id", side_effect=ValueError("missing"))
    def test_invalid_local_reference_falls_back_to_embedded(self, _mock_get_family):
        result = self.resolver.resolve_project_runtime(
            plugin_states=self.plugin_states,
            embedded_isolierungen=self.embedded,
            insulation_resolution={
                "entries": [
                    {
                        "project_insulation_key": "fam-1",
                        "family_key": "fam-1",
                        "variant_key": None,
                        "active_source": "local",
                        "local_db": {"family_id": 999, "variant_id": None},
                    }
                ]
            },
        )
        item = result.resolved_items[0]
        self.assertEqual(item.effective_source, "embedded")
        self.assertIn("Fallback", item.warning or "")

    @patch("app.core.projects.insulation_runtime_resolution.get_family_by_id")
    def test_active_source_local_uses_local_data(self, mock_get_family):
        mock_get_family.return_value = {
            "id": 2,
            "name": "Embedded A",
            "classification_temp": 100,
            "max_temp": 150,
            "density": 80,
            "temps": [0, 100],
            "ks": [0.04, 0.05],
            "variants": [],
        }
        result = self.resolver.resolve_project_runtime(
            plugin_states=self.plugin_states,
            embedded_isolierungen=self.embedded,
            insulation_resolution={
                "entries": [
                    {
                        "project_insulation_key": "fam-1",
                        "family_key": "fam-1",
                        "variant_key": None,
                        "active_source": "local",
                        "local_db": {"family_id": 2, "variant_id": None},
                    }
                ]
            },
        )
        item = result.resolved_items[0]
        self.assertEqual(item.effective_source, "local")
        self.assertEqual(item.family_name, "Embedded A")
        self.assertEqual(item.local_status, "Lokal synchron")

    @patch("app.core.projects.insulation_runtime_resolution.get_family_by_id")
    def test_switch_back_to_embedded(self, mock_get_family):
        mock_get_family.return_value = {
            "id": 2,
            "name": "Local B",
            "classification_temp": 100,
            "max_temp": 150,
            "density": 80,
            "temps": [0, 100],
            "ks": [0.04, 0.05],
            "variants": [],
        }
        updated, error = self.resolver.switch_active_source(
            insulation_resolution={
                "entries": [
                    {
                        "project_insulation_key": "fam-1",
                        "family_key": "fam-1",
                        "variant_key": None,
                        "active_source": "local",
                        "local_db": {"family_id": 2, "variant_id": None},
                    }
                ]
            },
            embedded_isolierungen=self.embedded,
            project_insulation_key="fam-1",
            target_source="embedded",
        )
        self.assertIsNone(error)
        self.assertEqual(updated["entries"][0]["active_source"], "embedded")


class MatchingAndImportValidationTests(unittest.TestCase):
    def test_matching_separates_exact_and_candidate_conflict(self):
        service = InsulationImportMatchingService()
        embedded = {
            "families": [
                {
                    "project_family_key": "fam-10",
                    "name": "Calcium",
                    "classification_temp": 650,
                    "max_temp": 700,
                    "density": 95,
                    "temps": [100, 200],
                    "ks": [0.1, 0.12],
                    "variants": [],
                },
                {
                    "project_family_key": "fam-11",
                    "name": "Aerogel",
                    "classification_temp": 700,
                    "max_temp": 750,
                    "density": 42,
                    "temps": [100, 200],
                    "ks": [0.09, 0.11],
                    "variants": [],
                },
            ]
        }
        local_rows = [
            {
                "id": 1,
                "name": "Calcium",
                "classification_temp": 650,
                "max_temp": 700,
                "density": 95,
                "temps": [100, 200],
                "ks": [0.1, 0.12],
                "variants": [],
            },
            {
                "id": 2,
                "name": "Aerogel",
                "classification_temp": 650,
                "max_temp": 700,
                "density": 44,
                "temps": [100, 200],
                "ks": [0.2, 0.22],
                "variants": [],
            },
        ]
        with patch("app.core.projects.insulation_matching.list_families", return_value=local_rows):
            analysis = service.analyze(
                embedded_isolierungen=embedded,
                insulation_resolution={
                    "entries": [
                        {"project_insulation_key": "fam-10", "family_key": "fam-10", "variant_key": None},
                        {"project_insulation_key": "fam-11", "family_key": "fam-11", "variant_key": None},
                    ]
                },
            )
        self.assertEqual(analysis.summary["exact_match"], 1)
        self.assertEqual(analysis.summary["candidate_conflict"], 1)

    def test_import_validation_rejects_wrong_format_and_version(self):
        service = ProjectImportService()
        base_project = {
            "project": {
                "master_data": {"name": "Demo", "author": "A", "description": "", "metadata": {}},
                "plugin_states": {},
                "ui_state": {},
                "embedded_isolierungen": {"families": []},
                "insulation_resolution": {"entries": []},
            }
        }
        wrong_name_payload = {"export_format": {"name": "wrong", "version": 1}, **base_project}
        with self.assertRaises(ProjectImportError):
            service.prepare_import_payload(wrong_name_payload)

        wrong_version_payload = {
            "export_format": {"name": "heatrix_project_exchange", "version": 999},
            **base_project,
        }
        with self.assertRaises(ProjectImportError):
            service.prepare_import_payload(wrong_version_payload)

    @patch("app.core.projects.isolierung_embedding.get_family_by_id")
    @patch("app.core.projects.insulation_matching.list_families")
    def test_canonical_entries_and_variant_exact_match_without_id_compare(
        self,
        mock_list_families,
        mock_get_family,
    ):
        def _family_from_db(family_id: int):
            if family_id == 10:
                return {
                    "id": 10,
                    "name": "Mineralwolle A",
                    "classification_temp": 650,
                    "max_temp": 700,
                    "density": 95,
                    "temps": [100, 200],
                    "ks": [0.1, 0.12],
                    "variants": [
                        {"id": 100, "name": "30 mm", "thickness": 30, "length": 1000, "width": 500, "price": 12.5}
                    ],
                }
            if family_id == 30:
                return {
                    "id": 30,
                    "name": "Schaum B",
                    "classification_temp": 400,
                    "max_temp": 450,
                    "density": 40,
                    "temps": [50, 100],
                    "ks": [0.2, 0.24],
                    "variants": [
                        {"id": 300, "name": "XPS-77", "thickness": 20, "length": 800, "width": 400, "price": 8.0}
                    ],
                }
            raise ValueError("missing")

        mock_get_family.side_effect = _family_from_db
        mock_list_families.return_value = [
            {
                "id": 501,
                "name": "Mineralwolle A",
                "classification_temp": 650,
                "max_temp": 700,
                "density": 95,
                "temps": [100, 200],
                "ks": [0.1, 0.12],
                "variants": [
                    # Gleiche Fachdaten wie importiert, aber andere lokale IDs.
                    {"id": 999, "name": "30 mm", "thickness": 30, "length": 1000, "width": 500, "price": 12.5}
                ],
            }
        ]

        plugin_states = {
            "isolierung": {
                "inputs": {
                    "berechnung": {
                        "layers": [
                            {"family_id": 10, "variant_id": None},
                            {"family_id": 30, "variant_id": 300},
                        ]
                    },
                    "schichtaufbau": {
                        "layers": [
                            {"family_id": 10, "variant_id": 100},
                        ]
                    },
                }
            }
        }
        embedded, resolution = build_embedded_isolierungen_from_plugin_states(plugin_states)

        entries = resolution["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual([entry["project_insulation_key"] for entry in entries], ["var-10-100", "var-30-300"])

        analysis = InsulationImportMatchingService().analyze(
            embedded_isolierungen=embedded,
            insulation_resolution=resolution,
        )
        self.assertEqual(len(analysis.annotated_insulation_resolution["entries"]), 2)
        self.assertEqual(analysis.summary["exact_match"], 1)
        self.assertEqual(analysis.summary["no_match"], 1)
        self.assertEqual(analysis.summary["candidate_conflict"], 0)
        self.assertEqual(analysis.summary["invalid_reference"], 0)


if __name__ == "__main__":
    unittest.main()
