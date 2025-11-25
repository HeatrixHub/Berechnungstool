"""
models.py
Definiert die zentralen Datenstrukturen für Projekte und Materialien.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MaterialMeasurement:
    """Ein einzelner Messpunkt für eine Isolierung (Temperatur vs. k)."""

    temperature: float
    conductivity: float


@dataclass
class Material:
    """Beschreibt eine Isolierung inkl. optionaler Messdaten."""

    name: str
    classification_temp: Optional[float] = None
    density: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    price: Optional[float] = None
    measurements: List[MaterialMeasurement] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self, include_measurements: bool = True) -> Dict:
        data = {
            "name": self.name,
            "classification_temp": self.classification_temp,
            "density": self.density,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "price": self.price,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_measurements:
            data["temps"] = [m.temperature for m in self.measurements]
            data["ks"] = [m.conductivity for m in self.measurements]
        return data


@dataclass
class ProjectLayer:
    """Eine Schicht eines Projektes."""

    order_index: int
    thickness: float
    material_name: str


@dataclass
class ProjectResult:
    """Meta-Informationen zu einem gespeicherten Berechnungsergebnis."""

    version_label: str = "latest"
    data: Optional[Dict] = None
    created_at: Optional[str] = None


@dataclass
class Project:
    """Bündelt alle relevanten Projektdaten und Ergebnisse."""

    name: str
    thicknesses: List[float]
    isolierungen: List[str]
    T_left: float = 0.0
    T_inf: float = 0.0
    h: float = 0.0
    result: Optional[Dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    layers: List[ProjectLayer] = field(default_factory=list)
    result_meta: Optional[ProjectResult] = None

    def __post_init__(self):
        self.thicknesses = list(self.thicknesses or [])
        self.isolierungen = list(self.isolierungen or [])
        self.result = self.result or {}

        if not self.layers and self.thicknesses:
            self.layers = [
                ProjectLayer(i, thickness, self.isolierungen[i] if i < len(self.isolierungen) else "")
                for i, thickness in enumerate(self.thicknesses)
            ]

        if self.result_meta and self.result_meta.data and not self.result:
            self.result = dict(self.result_meta.data)

    def __repr__(self):
        return f"<Project {self.name} ({len(self.thicknesses)} Schichten)>"

    def to_dict(self) -> Dict:
        """Serialisiert das Projekt in ein Dictionary (z. B. für UI oder Tests)."""
        return {
            "name": self.name,
            "thicknesses": self.thicknesses,
            "isolierungen": self.isolierungen,
            "T_left": self.T_left,
            "T_inf": self.T_inf,
            "h": self.h,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }
