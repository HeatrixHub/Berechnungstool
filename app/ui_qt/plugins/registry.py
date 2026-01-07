"""Registry of Qt UI plugins."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.core.plugin_registry import load_registry


@dataclass(frozen=True)
class QtPluginSpec:
    identifier: str
    name: str
    module: str
    class_name: str | None
    factory_name: str | None


def get_plugins() -> Sequence[QtPluginSpec]:
    specs: list[QtPluginSpec] = []
    for spec in load_registry():
        if not spec.enabled:
            continue
        specs.append(
            QtPluginSpec(
                identifier=spec.identifier,
                name=spec.name,
                module=spec.module,
                class_name=spec.class_name,
                factory_name=spec.factory_name,
            )
        )
    return tuple(specs)
