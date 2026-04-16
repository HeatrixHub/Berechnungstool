import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.isolierungen_exchange.export_service import (
    EXPORT_FILE_SUFFIX,
    EXPORT_FORMAT_NAME,
    EXPORT_FORMAT_VERSION,
    build_insulation_exchange_payload,
    export_insulations_to_file,
)
from app.core.isolierungen_exchange.normalization import (
    normalize_family_portable_for_compare,
    normalize_variant_portable_for_compare,
)


class InsulationExchangeExportTests(unittest.TestCase):
    @patch("app.core.isolierungen_exchange.export_service.get_family_by_id")
    def test_payload_contains_expected_exchange_structure(self, mock_get_family_by_id):
        mock_get_family_by_id.return_value = {
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

        payload = build_insulation_exchange_payload(family_ids=[10], app_version="2.0.1")

        self.assertEqual(payload["export_format"]["name"], EXPORT_FORMAT_NAME)
        self.assertEqual(payload["export_format"]["version"], EXPORT_FORMAT_VERSION)
        self.assertEqual(payload["app_version"], "2.0.1")
        self.assertIn("exported_at", payload)
        self.assertEqual(len(payload["isolierungen"]), 1)
        exported_family = payload["isolierungen"][0]
        self.assertEqual(exported_family["source_local"]["family_id"], 10)
        self.assertEqual(exported_family["family"]["name"], "Mineralwolle A")
        self.assertEqual(exported_family["family"]["temps"], [100.0, 200.0])
        self.assertEqual(exported_family["family"]["ks"], [0.1, 0.12])
        self.assertEqual(exported_family["family"]["variants"][0]["name"], "30 mm")
        self.assertEqual(exported_family["family"]["variants"][0]["source_local"]["variant_id"], 100)

    @patch("app.core.isolierungen_exchange.export_service.get_family_by_id")
    def test_payload_rejects_missing_selection(self, _mock_get_family_by_id):
        with self.assertRaises(ValueError):
            build_insulation_exchange_payload(family_ids=[])

    @patch("app.core.isolierungen_exchange.export_service.get_family_by_id")
    def test_export_writes_hpxins_suffix(self, mock_get_family_by_id):
        mock_get_family_by_id.return_value = {
            "id": 1,
            "name": "A",
            "classification_temp": 100,
            "max_temp": 120,
            "density": 50,
            "temps": [20],
            "ks": [0.04],
            "variants": [],
        }
        payload = build_insulation_exchange_payload(family_ids=[1])

        with tempfile.TemporaryDirectory() as tmp:
            out = export_insulations_to_file(payload, Path(tmp) / "demo.json")
            self.assertTrue(str(out).endswith(EXPORT_FILE_SUFFIX))
            loaded = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(loaded["export_format"]["name"], EXPORT_FORMAT_NAME)

    def test_portable_normalization_ignores_local_ids(self):
        family = {
            "id": 123,
            "name": "Portable",
            "classification_temp": 400,
            "max_temp": 450,
            "density": 88,
            "temps": [20, 100],
            "ks": [0.05, 0.07],
            "variants": [
                {"id": 999, "name": "V1", "thickness": 20, "length": 100, "width": 50, "price": 1.5}
            ],
        }
        portable = normalize_family_portable_for_compare(family)
        variant = normalize_variant_portable_for_compare(family["variants"][0])

        self.assertNotIn("source_local", portable)
        self.assertEqual(portable["name"], "Portable")
        self.assertEqual(variant["name"], "V1")
        self.assertNotIn("id", variant)


if __name__ == "__main__":
    unittest.main()
