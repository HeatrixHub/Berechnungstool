"""Helper utilities for consistent Qt layout defaults."""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

DEFAULT_MARGINS = (12, 12, 12, 12)
DEFAULT_SPACING = 8
HEADER_TITLE_SIZE = 16
HEADER_SUBTITLE_SIZE = 10
HEADER_TEXT_SPACING = 4


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


def create_button_row(
    buttons: Sequence[QPushButton],
    align: Qt.Alignment = Qt.AlignRight,
) -> QHBoxLayout:
    layout = make_hbox()
    if align & Qt.AlignHCenter:
        layout.addStretch()
    elif align & Qt.AlignRight:
        layout.addStretch()

    for button in buttons:
        layout.addWidget(button)

    if align & Qt.AlignHCenter:
        layout.addStretch()
    elif align & Qt.AlignLeft:
        layout.addStretch()

    layout.setAlignment(align)
    return layout


def create_section_header(
    title: str,
    subtitle: str | None = None,
    right_widget: QWidget | None = None,
) -> QWidget:
    header = QWidget()
    layout = make_hbox()

    text_layout = QVBoxLayout()
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(HEADER_TEXT_SPACING)

    title_label = QLabel(title)
    title_font = QFont()
    title_font.setPointSize(HEADER_TITLE_SIZE)
    title_font.setBold(True)
    title_label.setFont(title_font)
    text_layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_font = QFont()
        subtitle_font.setPointSize(HEADER_SUBTITLE_SIZE)
        subtitle_label.setFont(subtitle_font)
        text_layout.addWidget(subtitle_label)

    layout.addLayout(text_layout)
    layout.addStretch()

    if right_widget is not None:
        layout.addWidget(right_widget)

    header.setLayout(layout)
    return header
