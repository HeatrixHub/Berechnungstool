"""
tab2_projekte_logic.py
Logische Steuerung des Projekte-Tabs.
Beinhaltet alle Operationen zum Laden, Löschen und Anzeigen von Projekten.
"""

from core.database import delete_project, list_projects_overview, load_project
from core.models import Project
from typing import Any, Dict, List, Optional


def list_projects() -> List[Dict[str, Any]]:
    """Liefert eine Übersicht aller Projekte inkl. Metadaten."""
    return list_projects_overview()


def get_project_details(name: str) -> Optional[Project]:
    """Lädt ein Projektobjekt anhand des Namens."""
    return load_project(name)


def remove_project(name: str) -> bool:
    """Löscht ein Projekt aus der Datenbank."""
    return delete_project(name)