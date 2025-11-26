from __future__ import annotations

from tkinter import ttk

BUTTON_STYLES = {
    "primary": "Primary.TButton",
    "apply": "Apply.TButton",
    "danger": "Danger.TButton",
    "info": "Info.TButton",
    "secondary": "Secondary.TButton",
    "ghost": "Ghost.TButton",
}


def _configure_stateful_style(
    style: ttk.Style,
    name: str,
    *,
    base: str,
    hover: str,
    active: str,
    border: str,
    foreground: str,
    disabled_background: str,
    disabled_foreground: str = "#cbd5e1",
    focus: str = "#0ea5e9",
) -> None:
    """Configure a colored ttk style with consistent states.

    The sv-ttk theme honors standard ttk option names for colors and borders.
    """

    style.configure(
        name,
        padding=(12, 8),
        font=("Segoe UI", 10, "bold"),
        background=base,
        foreground=foreground,
        bordercolor=border,
        darkcolor=border,
        lightcolor=border,
        focusthickness=2,
        focuscolor=focus,
        relief="flat",
    )
    style.map(
        name,
        background=[
            ("disabled", disabled_background),
            ("pressed", active),
            ("active", hover),
        ],
        foreground=[("disabled", disabled_foreground)],
        bordercolor=[
            ("disabled", disabled_background),
            ("pressed", active),
            ("active", hover),
            ("focus", focus),
        ],
        lightcolor=[("focus", focus)],
        darkcolor=[("focus", focus)],
    )


def configure_button_styles(style: ttk.Style) -> None:
    """Register consistent button styles used across the application."""

    palette = {
        "primary": {
            "base": "#16a34a",
            "hover": "#15803d",
            "active": "#166534",
            "border": "#15803d",
            "foreground": "#ffffff",
        },
        "apply": {
            "base": "#f59e0b",
            "hover": "#d97706",
            "active": "#b45309",
            "border": "#d97706",
            "foreground": "#111827",
        },
        "danger": {
            "base": "#dc2626",
            "hover": "#b91c1c",
            "active": "#991b1b",
            "border": "#b91c1c",
            "foreground": "#ffffff",
        },
        "info": {
            "base": "#2563eb",
            "hover": "#1d4ed8",
            "active": "#1e40af",
            "border": "#1d4ed8",
            "foreground": "#ffffff",
        },
        "secondary": {
            "base": "#6b7280",
            "hover": "#4b5563",
            "active": "#374151",
            "border": "#4b5563",
            "foreground": "#ffffff",
        },
        "ghost": {
            "base": "#e5e7eb",
            "hover": "#d1d5db",
            "active": "#9ca3af",
            "border": "#d1d5db",
            "foreground": "#111827",
        },
    }

    disabled_bg = "#e5e7eb"

    _configure_stateful_style(
        style,
        BUTTON_STYLES["primary"],
        base=palette["primary"]["base"],
        hover=palette["primary"]["hover"],
        active=palette["primary"]["active"],
        border=palette["primary"]["border"],
        foreground=palette["primary"]["foreground"],
        disabled_background=disabled_bg,
    )
    _configure_stateful_style(
        style,
        BUTTON_STYLES["apply"],
        base=palette["apply"]["base"],
        hover=palette["apply"]["hover"],
        active=palette["apply"]["active"],
        border=palette["apply"]["border"],
        foreground=palette["apply"]["foreground"],
        disabled_background=disabled_bg,
        disabled_foreground="#9ca3af",
    )
    _configure_stateful_style(
        style,
        BUTTON_STYLES["danger"],
        base=palette["danger"]["base"],
        hover=palette["danger"]["hover"],
        active=palette["danger"]["active"],
        border=palette["danger"]["border"],
        foreground=palette["danger"]["foreground"],
        disabled_background=disabled_bg,
    )
    _configure_stateful_style(
        style,
        BUTTON_STYLES["info"],
        base=palette["info"]["base"],
        hover=palette["info"]["hover"],
        active=palette["info"]["active"],
        border=palette["info"]["border"],
        foreground=palette["info"]["foreground"],
        disabled_background=disabled_bg,
    )
    _configure_stateful_style(
        style,
        BUTTON_STYLES["secondary"],
        base=palette["secondary"]["base"],
        hover=palette["secondary"]["hover"],
        active=palette["secondary"]["active"],
        border=palette["secondary"]["border"],
        foreground=palette["secondary"]["foreground"],
        disabled_background=disabled_bg,
    )
    _configure_stateful_style(
        style,
        BUTTON_STYLES["ghost"],
        base=palette["ghost"]["base"],
        hover=palette["ghost"]["hover"],
        active=palette["ghost"]["active"],
        border=palette["ghost"]["border"],
        foreground=palette["ghost"]["foreground"],
        disabled_background=disabled_bg,
        disabled_foreground="#9ca3af",
    )

    # Default ttk button falls back to a neutral, high-contrast appearance.
    style.configure(
        "TButton",
        padding=(10, 6),
        font=("Segoe UI", 10, "bold"),
        background=palette["secondary"]["base"],
        foreground=palette["secondary"]["foreground"],
        bordercolor=palette["secondary"]["border"],
        focusthickness=2,
        focuscolor="#0ea5e9",
        relief="flat",
    )
    style.map(
        "TButton",
        background=[
            ("disabled", disabled_bg),
            ("pressed", palette["secondary"]["active"]),
            ("active", palette["secondary"]["hover"]),
        ],
        foreground=[("disabled", "#cbd5e1")],
        bordercolor=[
            ("disabled", disabled_bg),
            ("pressed", palette["secondary"]["active"]),
            ("active", palette["secondary"]["hover"]),
            ("focus", "#0ea5e9"),
        ],
    )

    # Toolbuttons should remain compact but follow the neutral palette.
    style.configure(
        "Toolbutton",
        padding=(8, 4),
        background=palette["ghost"]["base"],
        foreground=palette["ghost"]["foreground"],
        bordercolor=palette["ghost"]["border"],
        focusthickness=2,
        focuscolor="#0ea5e9",
    )
    style.map(
        "Toolbutton",
        background=[
            ("disabled", disabled_bg),
            ("pressed", palette["ghost"]["active"]),
            ("active", palette["ghost"]["hover"]),
        ],
        foreground=[("disabled", "#9ca3af")],
    )
