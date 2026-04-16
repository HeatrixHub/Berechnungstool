"""Unterstützende UI- und State-Helfer für das Isolierung-Plugin."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QComboBox, QGraphicsView, QLabel, QWidget


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    alignment: Qt.AlignmentFlag = Qt.AlignCenter
    formatter: Callable[[dict[str, Any], Any], str] | None = None


class DictTableModel(QAbstractTableModel):
    def __init__(
        self,
        columns: list[TableColumn],
        rows: list[dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows = rows or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802 - Qt API
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self._columns[index.column()]
        if role == Qt.DisplayRole:
            value = row.get(column.key)
            if column.formatter is not None:
                return column.formatter(row, value)
            if value is None:
                return "–"
            return str(value)
        if role == Qt.TextAlignmentRole:
            return column.alignment
        if role == Qt.BackgroundRole and bool(row.get("is_manual_cut")):
            return QBrush(QColor("#ffd7d7"))
        if role == Qt.ForegroundRole and bool(row.get("is_manual_cut")):
            return QBrush(QColor("#7f1d1d"))
        return None

    def headerData(  # noqa: N802 - Qt API
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self._columns):
            return self._columns[section].label
        return None

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> list[dict[str, Any]]:
        return self._rows


class CutPlanView(QGraphicsView):
    def __init__(self, on_resize: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_resize = on_resize
        self._zoom = 1.0
        self._auto_fit_enabled = True
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

    def fit_scene(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        bounds = scene.itemsBoundingRect()
        if bounds.width() <= 0 or bounds.height() <= 0:
            return
        self.fitInView(bounds.adjusted(-16, -16, 16, 16), Qt.KeepAspectRatio)
        self._zoom = 1.0
        self._auto_fit_enabled = True

    def zoom_in(self) -> None:
        self._apply_zoom(1.2)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / 1.2)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self._zoom = 1.0
        self._auto_fit_enabled = False

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.angleDelta().y() > 0:
            self._apply_zoom(1.15)
        else:
            self._apply_zoom(1 / 1.15)

    def _apply_zoom(self, factor: float) -> None:
        self.scale(factor, factor)
        self._zoom *= factor
        self._auto_fit_enabled = False

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._on_resize is not None and self._auto_fit_enabled:
            self._on_resize()


def format_mm_one(row: dict[str, Any], value: Any) -> str:
    del row
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "–"


def format_rotation(row: dict[str, Any], value: Any) -> str:
    del row
    if value is None:
        return "–"
    return "90°" if bool(value) else "0°"


def format_price(row: dict[str, Any], value: Any) -> str:
    del row
    if value is None:
        return "–"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "–"


def format_cost(row: dict[str, Any], value: Any) -> str:
    override = row.get("cost_display")
    if isinstance(override, str) and override:
        return override
    return format_price(row, value)


def parse_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def float_or_zero(value: str | float | int | None) -> float:
    parsed = parse_float(value)
    return parsed if parsed is not None else 0.0


def coerce_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def coerce_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def serialize_layers(layers: Any) -> list[dict[str, Any]]:
    if not isinstance(layers, list):
        return []
    serialized: list[dict[str, Any]] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        serialized.append(
            {
                "thickness": coerce_str(layer.get("thickness", "")),
                "family": coerce_str(layer.get("family", "")),
                "family_id": coerce_optional_int(layer.get("family_id")),
                "variant": coerce_str(layer.get("variant", "")),
                "variant_id": coerce_optional_int(layer.get("variant_id")),
            }
        )
    return serialized


def set_label_text(widget: QLabel | None, value: str) -> None:
    if widget is None:
        return
    widget.setText(value)


def select_combo_value(combo: QComboBox, value: str) -> None:
    if not value:
        combo.setCurrentIndex(0)
        return
    index = combo.findText(value)
    combo.setCurrentIndex(0 if index == -1 else index)


def select_combo_value_by_data(combo: QComboBox, value: object, role: int = Qt.UserRole) -> bool:
    if value in (None, ""):
        combo.setCurrentIndex(0)
        return False
    index = combo.findData(value, role)
    if index == -1:
        combo.setCurrentIndex(0)
        return False
    combo.setCurrentIndex(index)
    return True
