"""
models.py
Definiert die zentralen Datenstrukturen für Projekte.
"""

from typing import List, Optional, Dict


class Project:
    def __init__(
        self,
        name: str,
        thicknesses: List[float],
        ks: Optional[List[float]] = None,
        isolierungen: Optional[List[str]] = None,
        T_left: float = 0.0,
        T_inf: float = 0.0,
        h: float = 0.0,
        result: Optional[Dict] = None,
    ):
        self.name = name
        self.thicknesses = thicknesses
        self.ks = ks or []
        self.isolierungen = isolierungen or []  # ✅ neu: speichert Materialnamen
        self.T_left = T_left
        self.T_inf = T_inf
        self.h = h
        self.result = result or {}

    def __repr__(self):
        return f"<Project {self.name} ({len(self.thicknesses)} Schichten)>"

    def to_dict(self) -> Dict:
        """Ermöglicht einfaches Serialisieren in Dictionaries."""
        return {
            "name": self.name,
            "thicknesses": self.thicknesses,
            "ks": self.ks,
            "isolierungen": self.isolierungen,
            "T_left": self.T_left,
            "T_inf": self.T_inf,
            "h": self.h,
            "result": self.result,
        }