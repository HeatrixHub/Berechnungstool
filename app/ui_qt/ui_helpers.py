"""Helper utilities for consistent Qt layout defaults."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLayout, QVBoxLayout, QWidget

DEFAULT_MARGINS = (12, 12, 12, 12)
DEFAULT_SPACING = 8


def apply_layout_defaults(
    layout: QLayout,
    *,
    margins: tuple[int, int, int, int] = DEFAULT_MARGINS,
    spacing: int = DEFAULT_SPACING,
) -> QLayout:
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def make_vbox(parent: QWidget | None = None) -> QVBoxLayout:
    layout = QVBoxLayout(parent)
    apply_layout_defaults(layout)
    return layout


def make_hbox(parent: QWidget | None = None) -> QHBoxLayout:
    layout = QHBoxLayout(parent)
    apply_layout_defaults(layout)
    return layout


def make_grid(parent: QWidget | None = None) -> QGridLayout:
    layout = QGridLayout(parent)
    apply_layout_defaults(layout)
    return layout
