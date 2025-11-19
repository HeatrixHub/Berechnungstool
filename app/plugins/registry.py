"""Verwaltung der Plugin-Registry."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(slots=True)
class PluginSpec:
    """Beschreibt ein Plugin-Modul innerhalb der Host-Anwendung."""

    identifier: str
    name: str
    module: str
    class_name: str
    enabled: bool = True


REGISTRY_PATH = Path(__file__).with_name("plugins.json")

DEFAULT_SPECS: Sequence[PluginSpec] = (
    PluginSpec(
        identifier="isolierung",
        name="Isolierung",
        module="Isolierung.plugin",
        class_name="IsolierungPlugin",
    ),
    PluginSpec(
        identifier="stoffeigenschaften-luft",
        name="Stoffeigenschaften Luft",
        module="SoffeigenschaftenLuft.plugin",
        class_name="StoffeigenschaftenLuftPlugin",
    ),
)


class RegistryError(RuntimeError):
    """Fehler beim Lesen oder Schreiben der Plugin-Registry."""


def ensure_default_registry(path: Path | None = None) -> None:
    """Lege eine Registry-Datei mit Defaults an, falls sie fehlt."""

    target = path or REGISTRY_PATH
    if target.exists():
        return
    save_registry(list(DEFAULT_SPECS), path=target)


def load_registry(path: Path | None = None) -> List[PluginSpec]:
    """Lade alle bekannten Plugin-Spezifikationen."""

    target = path or REGISTRY_PATH
    if not target.exists():
        ensure_default_registry(target)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - Dateisystemfehler
        raise RegistryError(f"Registry {target} kann nicht gelesen werden") from exc

    plugins_data = raw.get("plugins") if isinstance(raw, dict) else raw
    if not isinstance(plugins_data, list):
        raise RegistryError("Registry-Datei ist beschädigt")

    specs: List[PluginSpec] = []
    for entry in plugins_data:
        if not isinstance(entry, dict):
            continue
        try:
            specs.append(
                PluginSpec(
                    identifier=str(entry["identifier"]),
                    name=str(entry["name"]),
                    module=str(entry["module"]),
                    class_name=str(entry["class_name"]),
                    enabled=bool(entry.get("enabled", True)),
                )
            )
        except KeyError as exc:
            raise RegistryError(
                f"Pflichtfeld fehlt in Registry-Eintrag: {exc}"
            ) from exc
    return specs


def save_registry(specs: Iterable[PluginSpec], path: Path | None = None) -> None:
    """Speichere alle Spezifikationen in der Registry-Datei."""

    target = path or REGISTRY_PATH
    data = {"plugins": [asdict(spec) for spec in specs]}
    try:
        target.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:  # pragma: no cover - Dateisystemfehler
        raise RegistryError(f"Registry {target} kann nicht geschrieben werden") from exc
