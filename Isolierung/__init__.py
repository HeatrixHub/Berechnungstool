"""Isolierungstool als Plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ui.plugin import IsolierungPlugin

__all__ = ["IsolierungPlugin"]


def __getattr__(name: str):
    if name == "IsolierungPlugin":
        from .ui.plugin import IsolierungPlugin

        return IsolierungPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
