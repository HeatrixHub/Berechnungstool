"""Zentrales Berichtssystem zur Kombination aller Plugin-Beiträge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass
class ReportContribution:
    """Ein einzelner Abschnitt, der von einem Plugin bereitgestellt wird."""

    plugin_name: str
    section_id: str
    title: str
    content: str
    include_in_report: bool = True


class ReportManager:
    """Verwaltet optionale Berichtsinhalte aller Plugins."""

    def __init__(self) -> None:
        self._contributions: Dict[str, ReportContribution] = {}
        self._listeners: List[Callable[[], None]] = []

    def submit_contribution(
        self, *, plugin_name: str, section_id: str, title: str, content: str
    ) -> None:
        key = self._key(plugin_name, section_id)
        self._contributions[key] = ReportContribution(
            plugin_name=plugin_name,
            section_id=section_id,
            title=title,
            content=content,
        )
        self._notify()

    def toggle_inclusion(self, plugin_name: str, section_id: str, include: bool) -> None:
        key = self._key(plugin_name, section_id)
        if key in self._contributions:
            self._contributions[key].include_in_report = include
            self._notify()

    def remove_contribution(self, plugin_name: str, section_id: str) -> None:
        key = self._key(plugin_name, section_id)
        if key in self._contributions:
            del self._contributions[key]
            self._notify()

    def list_contributions(self) -> List[ReportContribution]:
        return list(self._contributions.values())

    def compile_report(self, only_included: bool = True) -> str:
        sections = [
            c
            for c in self._contributions.values()
            if (not only_included) or c.include_in_report
        ]
        sections.sort(key=lambda item: (item.plugin_name.lower(), item.title.lower()))
        lines: List[str] = []
        for contribution in sections:
            lines.append(f"## {contribution.title} ({contribution.plugin_name})")
            lines.append(contribution.content.strip())
            lines.append("")
        return "\n".join(lines).strip()

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _key(self, plugin_name: str, section_id: str) -> str:
        return f"{plugin_name}:{section_id}"

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                continue
