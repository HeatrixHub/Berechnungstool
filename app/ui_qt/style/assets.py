"""Asset loading helpers for Qt UI.

Das App-Header-Logo ist bewusst auf Top-Level-Seiten beschränkt.
Setze ``show_logo=True`` beim Erzeugen eines Page-Headers, wenn das Logo im
obersten Tab-Header angezeigt werden soll; bei Unterseiten bleibt es standardmäßig aus.
"""
from __future__ import annotations

from pathlib import Path

from app.core.runtime_paths import resolve_bundled_path

ASSET_DIR = "style/assets"


def _asset_base_dir() -> Path:
    return resolve_bundled_path("app", "ui_qt", ASSET_DIR)


def get_asset_path(filename: str) -> Path:
    return _asset_base_dir() / filename


APP_HEADER_LOGO_PATH = get_asset_path("3dots.svg")
