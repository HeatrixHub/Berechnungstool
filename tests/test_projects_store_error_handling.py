from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.projects.store import ProjectStore, ProjectStoreLoadError


class ProjectStoreErrorHandlingTests(unittest.TestCase):
    def test_raises_for_invalid_json_in_project_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projects.json"
            path.write_text("{ invalid json", encoding="utf-8")
            with self.assertRaises(ProjectStoreLoadError):
                ProjectStore(path=path)

    def test_raises_for_invalid_root_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projects.json"
            path.write_text('{"format_version": 1, "projects": {}}', encoding="utf-8")
            with self.assertRaises(ProjectStoreLoadError):
                ProjectStore(path=path)
