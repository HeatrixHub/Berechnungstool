"""
tab2_projekte_logic.py
Logische Steuerung des Projekte-Tabs.
Beinhaltet alle Operationen zum Laden, Löschen und Anzeigen von Projekten.
"""

from core.database import get_all_project_names, load_project, delete_project
from core.models import Project
from typing import List, Optional


def list_projects() -> List[str]:
    """Liefert alle gespeicherten Projektnamen alphabetisch sortiert."""
    return get_all_project_names()


def get_project_details(name: str) -> Optional[Project]:
    """Lädt ein Projektobjekt anhand des Namens."""
    return load_project(name)


def remove_project(name: str) -> bool:
    """Löscht ein Projekt aus der Datenbank."""
    return delete_project(name)