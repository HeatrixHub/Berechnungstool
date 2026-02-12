"""Fachlogik und Services für das Isolierung-Plugin."""

from .projects import get_project_details, list_projects, remove_project
from .schichtaufbau import BuildResult, LayerResult, Plate, compute_plate_dimensions
from .tab1_berechnung import get_k_values_for_layers, perform_calculation, validate_inputs
from .zuschnitt import Placement, color_for, format_material_label, pack_plates, resolve_variant_data

__all__ = [
    "BuildResult",
    "LayerResult",
    "Placement",
    "Plate",
    "color_for",
    "compute_plate_dimensions",
    "format_material_label",
    "get_k_values_for_layers",
    "get_project_details",
    "list_projects",
    "pack_plates",
    "perform_calculation",
    "remove_project",
    "resolve_variant_data",
    "validate_inputs",
]
