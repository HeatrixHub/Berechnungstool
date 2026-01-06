"""Registry of Qt UI plugins."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Type

from app.ui_qt.plugins.base import QtPlugin
from app.ui_qt.plugins.demo import DemoOverviewPlugin, DemoSettingsPlugin


@dataclass(frozen=True)
class QtPluginSpec:
    identifier: str
    plugin_cls: Type[QtPlugin]


def get_plugins() -> Sequence[QtPluginSpec]:
    return (
        QtPluginSpec(identifier="demo.overview", plugin_cls=DemoOverviewPlugin),
        QtPluginSpec(identifier="demo.settings", plugin_cls=DemoSettingsPlugin),
    )
