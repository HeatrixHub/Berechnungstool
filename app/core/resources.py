"""Gemeinsam genutzte Datenstrukturen (Isolierungen, Materialien, ...)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class IsolationRecord:
    """Ein Eintrag in der globalen Isolierungsdatenbank."""

    name: str
    material: str
    thickness_mm: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class IsolationLibrary:
    """Zentrales Repository für alle Isolierungsdaten."""

    def __init__(self) -> None:
        self._records: Dict[str, IsolationRecord] = {}
        self._listeners: List[Callable[[], None]] = []

    def upsert(self, record: IsolationRecord) -> None:
        self._records[record.name] = record
        self._notify()

    def delete(self, name: str) -> None:
        if name in self._records:
            del self._records[name]
            self._notify()

    def list_records(self) -> List[IsolationRecord]:
        return sorted(self._records.values(), key=lambda rec: rec.name.lower())

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                continue
