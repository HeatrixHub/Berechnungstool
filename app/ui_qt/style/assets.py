"""Asset loading helpers for Qt UI."""
from __future__ import annotations

from pathlib import Path
import sys

ASSET_DIR = "assets"
LOGO_FILENAME = "heatrix_logo_v1.svg"


def _asset_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "ui_qt" / ASSET_DIR
    return Path(__file__).resolve().parent / ASSET_DIR


def get_asset_path(filename: str) -> Path:
    return _asset_base_dir() / filename


def get_logo_path() -> Path:
    return get_asset_path(LOGO_FILENAME)
