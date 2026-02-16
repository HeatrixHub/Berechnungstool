"""Helper utilities for consistent Qt layout defaults."""
from __future__ import annotations

from collections.abc import Sequence

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui_qt.style.assets import APP_HEADER_LOGO_PATH

ROOT_MARGINS = (16, 16, 16, 16)
ROOT_SPACING = 12
SECTION_MARGINS = (12, 12, 12, 12)
SECTION_SPACING = 8
CONTENT_MARGINS = (0, 0, 0, 0)
DEFAULT_MARGINS = SECTION_MARGINS
DEFAULT_SPACING = SECTION_SPACING
HEADER_TITLE_SIZE = 18
HEADER_SUBTITLE_SIZE = 10
HEADER_TEXT_SPACING = 4
PAGE_HEADER_SPACING = 12
PAGE_HEADER_LOGO_HEIGHT = 28


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


def make_root_vbox(parent: QWidget | None = None) -> QVBoxLayout:
    layout = QVBoxLayout(parent)
    apply_layout_defaults(layout, margins=ROOT_MARGINS, spacing=ROOT_SPACING)
    return layout


def make_hbox(parent: QWidget | None = None) -> QHBoxLayout:
    layout = QHBoxLayout(parent)
    apply_layout_defaults(layout)
    return layout


def make_root_hbox(parent: QWidget | None = None) -> QHBoxLayout:
    layout = QHBoxLayout(parent)
    apply_layout_defaults(layout, margins=ROOT_MARGINS, spacing=ROOT_SPACING)
    return layout


def make_grid(parent: QWidget | None = None) -> QGridLayout:
    layout = QGridLayout(parent)
    apply_layout_defaults(layout)
    return layout


def apply_form_layout_defaults(
    layout: QGridLayout,
    *,
    label_columns: Sequence[int] = (0,),
    field_columns: Sequence[int] = (1,),
    label_alignment: Qt.Alignment = Qt.AlignRight | Qt.AlignVCenter,
    field_stretch: int = 1,
) -> QGridLayout:
    for column in label_columns:
        layout.setColumnStretch(column, 0)
    for column in field_columns:
        layout.setColumnStretch(column, field_stretch)
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QLabel):
            _row, column, _row_span, _column_span = layout.getItemPosition(index)
            if column in label_columns:
                layout.setAlignment(widget, label_alignment)
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


def apply_app_style(app: object) -> None:
    if hasattr(app, "setStyleSheet"):
        app.setStyleSheet(
            "QPushButton { min-height: 28px; }"
            "QLineEdit, QTextEdit, QComboBox { min-height: 24px; }"
            "QHeaderView::section { padding: 4px 6px; }"
        )


def _create_logo_widget(logo_path: Path, height: int) -> QWidget | None:
    if not logo_path.exists():
        return None

    if logo_path.suffix.lower() == ".svg":
        renderer = QSvgRenderer(str(logo_path))
        if not renderer.isValid():
            return None
        size = renderer.defaultSize()
        if not size.isValid() or size.height() <= 0:
            width = height
        else:
            width = max(1, round(size.width() * height / size.height()))

        logo_widget = QSvgWidget(str(logo_path))
        logo_widget.setFixedSize(width, height)
        logo_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return logo_widget

    pixmap = QPixmap(str(logo_path))
    if pixmap.isNull():
        return None

    logo_label = QLabel()
    logo_label.setPixmap(pixmap.scaledToHeight(height, Qt.SmoothTransformation))
    logo_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return logo_label


def create_page_header(
    title: str,
    *,
    subtitle: str | None = None,
    actions: QWidget | None = None,
    logo_path: str | Path | None = None,
    show_logo: bool = False,
    parent: QWidget | None = None,
) -> QWidget:
    header = QWidget(parent)
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(PAGE_HEADER_SPACING)

    title_layout = QVBoxLayout()
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(HEADER_TEXT_SPACING)

    title_label = QLabel(title)
    title_font = QFont()
    title_font.setPointSize(HEADER_TITLE_SIZE)
    title_font.setWeight(QFont.Weight.DemiBold)
    title_label.setFont(title_font)
    title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    title_layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_font = QFont()
        subtitle_font.setPointSize(HEADER_SUBTITLE_SIZE)
        subtitle_label.setFont(subtitle_font)
        title_layout.addWidget(subtitle_label)

    layout.addLayout(title_layout)

    if actions is not None:
        actions.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(actions)

    layout.addStretch()

    if show_logo:
        resolved_logo = Path(logo_path) if logo_path is not None else APP_HEADER_LOGO_PATH
        logo_widget = _create_logo_widget(resolved_logo, PAGE_HEADER_LOGO_HEIGHT)
        if logo_widget is not None:
            logo_widget.setProperty("is_app_header_logo", True)
            if hasattr(logo_widget, "setAlignment"):
                logo_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(logo_widget, alignment=Qt.AlignRight | Qt.AlignVCenter)

    header.setLayout(layout)
    header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return header


def create_page_layout(
    page: QWidget,
    title: str,
    *,
    subtitle: str | None = None,
    actions: QWidget | None = None,
    logo_path: str | Path | None = None,
    show_logo: bool = False,
) -> QVBoxLayout:
    root_layout = make_root_vbox()
    page.setLayout(root_layout)
    header = create_page_header(
        title,
        subtitle=subtitle,
        actions=actions,
        logo_path=logo_path,
        show_logo=show_logo,
        parent=page,
    )
    root_layout.addWidget(header)

    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)
    apply_layout_defaults(content_layout, margins=CONTENT_MARGINS, spacing=SECTION_SPACING)
    content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    root_layout.addWidget(content_widget, 1)
    return content_layout
