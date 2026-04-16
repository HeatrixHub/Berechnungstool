from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.core.isolierungen_exchange.import_service import prepare_insulation_exchange_import_from_file
from app.core.projects.import_service import ProjectImportService
from app.core.projects.store import ProjectStore
from app.core.time_utils import normalize_timestamp, utc_now_iso_z


class TimestampStrategyTests(unittest.TestCase):
    def test_utc_now_iso_z_uses_explicit_utc_suffix(self) -> None:
        value = utc_now_iso_z()
        self.assertTrue(value.endswith("Z"))
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_normalize_timestamp_accepts_legacy_and_offset_formats(self) -> None:
        self.assertEqual(normalize_timestamp("2026-04-16 10:00:00"), "2026-04-16T10:00:00Z")
        self.assertEqual(normalize_timestamp("2026-04-16T12:00:00+02:00"), "2026-04-16T10:00:00Z")
        self.assertEqual(normalize_timestamp("2026-04-16T10:00:00"), "2026-04-16T10:00:00Z")

    def test_project_store_normalizes_overrides_to_canonical_utc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(path=Path(tmp) / "projects.json")
            record = store.save_project(
                name="Demo",
                author="A",
                plugin_states={},
                created_at_override="2026-04-16 10:00:00",
                updated_at_override="2026-04-16T12:00:00+02:00",
            )
            self.assertEqual(record.created_at, "2026-04-16T10:00:00Z")
            self.assertEqual(record.updated_at, "2026-04-16T10:00:00Z")

    def test_project_import_normalizes_master_data_timestamps(self) -> None:
        service = ProjectImportService()
        payload = {
            "export_format": {"name": "heatrix_project_exchange", "version": 1},
            "project": {
                "master_data": {
                    "name": "Demo",
                    "author": "A",
                    "description": "",
                    "metadata": {},
                    "created_at": "2026-04-16 10:00:00",
                    "updated_at": "2026-04-16T12:00:00+02:00",
                },
                "plugin_states": {},
                "ui_state": {},
                "embedded_isolierungen": {"families": []},
                "insulation_resolution": {"entries": []},
            },
        }
        prepared = service.prepare_import_payload(payload)
        self.assertEqual(prepared.created_at, "2026-04-16T10:00:00Z")
        self.assertEqual(prepared.updated_at, "2026-04-16T10:00:00Z")

    def test_insulation_exchange_import_normalizes_exported_at(self) -> None:
        payload = {
            "export_format": {"name": "heatrix_insulation_exchange", "version": 1},
            "exported_at": "2026-04-09 10:00:00",
            "isolierungen": [
                {
                    "family": {
                        "name": "A",
                        "classification_temp": 100,
                        "max_temp": 120,
                        "density": 50,
                        "temps": [20],
                        "ks": [0.04],
                        "variants": [],
                    }
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.hpxins.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            prepared = prepare_insulation_exchange_import_from_file(path)
        self.assertEqual(prepared.exported_at, "2026-04-09T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
