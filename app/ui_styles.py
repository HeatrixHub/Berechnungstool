"""Gemeinsame Button-Farbpaletten für die Tkinter-Oberfläche."""
from __future__ import annotations

from tkinter import ttk


def apply_button_styles(style: ttk.Style) -> None:
    """Ergänzt farbcodierte Button-Styles für wiederkehrende Aktionen."""

    palettes = {
        "Success": {"bg": "#16a34a", "active": "#15803d", "fg": "#ffffff"},
        "Warning": {"bg": "#f59e0b", "active": "#d97706", "fg": "#1f2937"},
        "Danger": {"bg": "#dc2626", "active": "#b91c1c", "fg": "#ffffff"},
        "Neutral": {"bg": "#e5e7eb", "active": "#d1d5db", "fg": "#111827"},
    }

    for name, colors in palettes.items():
        style_name = f"{name}.TButton"
        style.configure(style_name, background=colors["bg"], foreground=colors["fg"])
        style.map(
            style_name,
            background=[("active", colors["active"]), ("pressed", colors["active"])],
            foreground=[("disabled", "#9ca3af")],
        )
