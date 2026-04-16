from __future__ import annotations

from pathlib import Path

from app.core.bundled_assets import BUNDLED_DATA_FILES
from app.core.plugin_registry import BUNDLED_REGISTRY_PATH, REGISTRY_PATH
from app.core.runtime_paths import app_data_dir, bundle_root, resolve_bundled_path
from app.ui_qt.style.assets import APP_HEADER_LOGO_PATH


def test_all_declared_bundled_assets_exist_in_repo() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    for source_rel_path, _target_rel_dir in BUNDLED_DATA_FILES:
        source = repo_root / source_rel_path
        assert source.exists(), f"Bundled asset fehlt: {source_rel_path}"


def test_header_logo_and_plugin_registry_use_bundle_resolver() -> None:
    assert APP_HEADER_LOGO_PATH == resolve_bundled_path("app", "ui_qt", "style", "assets", "3dots.svg")
    assert BUNDLED_REGISTRY_PATH == resolve_bundled_path("app", "core", "plugins.json")


def test_registry_path_is_writable_user_data_not_bundle() -> None:
    data_dir = app_data_dir()
    assert REGISTRY_PATH.parent == data_dir
    assert REGISTRY_PATH != BUNDLED_REGISTRY_PATH
    assert not str(REGISTRY_PATH).startswith(str(bundle_root()))
