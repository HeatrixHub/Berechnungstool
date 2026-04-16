"""Zentrale Definition aller read-only Bundle-Ressourcen."""
from __future__ import annotations

from collections.abc import Sequence

# (source_rel_path, target_rel_dir_in_bundle)
BUNDLED_DATA_FILES: Sequence[tuple[str, str]] = (
    ("app/core/plugins.json", "app/core"),
    ("app/ui_qt/style/assets", "app/ui_qt/style/assets"),
    ("heatrix_logo_v3.png", "."),
)


__all__ = ["BUNDLED_DATA_FILES"]
