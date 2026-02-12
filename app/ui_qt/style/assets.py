"""Asset loading helpers for Qt UI.

Das App-Header-Logo ist bewusst auf Top-Level-Seiten beschränkt.
Setze ``show_logo=True`` beim Erzeugen eines Page-Headers, wenn das Logo im
obersten Tab-Header angezeigt werden soll; bei Unterseiten bleibt es standardmäßig aus.
"""
from __future__ import annotations

from pathlib import Path
import sys

ASSET_DIR = "assets"


def _asset_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "ui_qt" / ASSET_DIR
    return Path(__file__).resolve().parent / ASSET_DIR


def get_asset_path(filename: str) -> Path:
    return _asset_base_dir() / filename


APP_HEADER_LOGO_PATH = get_asset_path("heatrix_logo_3dots.png")
