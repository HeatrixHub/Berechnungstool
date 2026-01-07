"""Projektverwaltung für die Host-Anwendung."""

from app.core.projects import ProjectStore
from .tab import ProjectsTab

__all__ = ["ProjectStore", "ProjectsTab"]
