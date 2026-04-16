import json
import tempfile
import unittest
from pathlib import Path

from app.core.isolierungen_exchange.import_service import (
    PreparedInsulationImport,
    prepare_insulation_exchange_import_from_file,
)


class InsulationExchangeImportTests(unittest.TestCase):
    def test_valid_file_creates_prepared_import(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
            "exported_at": "2026-04-09T10:00:00Z",
            "app_version": "3.4.5",
            "isolierungen": [
                {
                    "source_local": {"family_id": 12},
                    "family": {
                        "name": "Mineralwolle A",
                        "classification_temp": 650,
                        "max_temp": 700,
                        "density": 95,
                        "temps": [20, 100],
                        "ks": [0.04, 0.06],
                        "variants": [
                            {"name": "30 mm", "thickness": 30, "length": 1000, "width": 500, "price": 12.5}
                        ],
                    },
                }
            ],
        }

        prepared = self._prepare_payload(payload)

        self.assertIsInstance(prepared, PreparedInsulationImport)
        self.assertEqual(prepared.export_format_name, "heatrix_insulation_exchange")
        self.assertEqual(prepared.export_format_version, 1)
        self.assertEqual(prepared.exported_at, "2026-04-09T10:00:00Z")
        self.assertEqual(prepared.app_version, "3.4.5")
        self.assertEqual(len(prepared.families), 1)
        family = prepared.families[0].family
        self.assertEqual(family["name"], "Mineralwolle A")
        self.assertEqual(family["temps"], [20.0, 100.0])
        self.assertEqual(family["ks"], [0.04, 0.06])
        self.assertEqual(family["variants"][0]["name"], "30 mm")
        self.assertEqual(len(prepared.issues), 0)

    def test_rejects_invalid_export_format_name(self):
        payload = {
            "export_format": {"name": "other_format", "version": 1},
            "isolierungen": [],
        }

        with self.assertRaisesRegex(ValueError, "Nicht unterstütztes Austauschformat"):
            self._prepare_payload(payload)

    def test_rejects_invalid_export_format_version(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 2},
            "isolierungen": [],
        }

        with self.assertRaisesRegex(ValueError, "Nicht unterstützte Formatversion"):
            self._prepare_payload(payload)

    def test_rejects_missing_required_blocks(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
        }

        with self.assertRaisesRegex(ValueError, "'isolierungen'"):
            self._prepare_payload(payload)

    def test_rejects_inconsistent_temps_ks(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
            "isolierungen": [
                {
                    "family": {
                        "name": "A",
                        "classification_temp": 100,
                        "max_temp": 120,
                        "density": 50,
                        "temps": [20, 100],
                        "ks": [0.04],
                        "variants": [{"name": "V1", "thickness": 20}],
                    }
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "gleich lang"):
            self._prepare_payload(payload)

    def test_duplicate_variant_names_are_reported_as_warning(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
            "isolierungen": [
                {
                    "family": {
                        "name": "A",
                        "classification_temp": 100,
                        "max_temp": 120,
                        "density": 50,
                        "temps": [20],
                        "ks": [0.04],
                        "variants": [
                            {"name": "V1", "thickness": 20},
                            {"name": "v1", "thickness": 25},
                        ],
                    }
                }
            ],
        }

        prepared = self._prepare_payload(payload)

        self.assertEqual(len(prepared.issues), 1)
        self.assertEqual(prepared.issues[0].code, "duplicate_variant_name")
        self.assertEqual(prepared.issues[0].level, "warning")

    def test_prepared_model_contains_normalized_families(self):
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
            "isolierungen": [
                {
                    "source_local": {"family_id": "99", "legacy": True},
                    "family": {
                        "name": "  A  ",
                        "classification_temp": "100",
                        "max_temp": "120",
                        "density": "50",
                        "temps": ["20", "100"],
                        "ks": ["0.04", "0.06"],
                        "variants": [
                            {
                                "name": "  V2  ",
                                "thickness": "30",
                                "length": "1000",
                                "width": "500",
                                "price": "12.5",
                            }
                        ],
                    },
                }
            ],
        }

        prepared = self._prepare_payload(payload)
        family_import = prepared.families[0]

        self.assertEqual(family_import.family["name"], "A")
        self.assertEqual(family_import.family["classification_temp"], 100.0)
        self.assertEqual(family_import.family["variants"][0]["name"], "V2")
        self.assertEqual(family_import.source_local, {"family_id": "99", "legacy": True})

    def _prepare_payload(self, payload: dict) -> PreparedInsulationImport:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.hpxins.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return prepare_insulation_exchange_import_from_file(path)


if __name__ == "__main__":
    unittest.main()
