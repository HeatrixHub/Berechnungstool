"""Gemeinsame Pfad-Helfer für Quellcode- und PyInstaller-Laufzeit."""
from __future__ import annotations

import os
from pathlib import Path
import sys

APP_NAME = "Berechnungstool"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Basisverzeichnis für gebündelte Ressourcen."""

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def resolve_bundled_path(*parts: str) -> Path:
    """Löst einen Pfad relativ zum Bundle-/Projekt-Root auf."""

    return bundle_root().joinpath(*parts)


def app_data_dir(app_name: str = APP_NAME) -> Path:
    """Beschreibbares Verzeichnis für nutzerspezifische Laufzeitdaten."""

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    target = base / app_name
    target.mkdir(parents=True, exist_ok=True)
    return target
