"""Standalone-Launcher für das Isolierungstool."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

try:
    import sv_ttk
except Exception:  # pragma: no cover - Theme-Bibliothek optional
    sv_ttk = None  # type: ignore[assignment]

from app.core.projects import ProjectStore
from app.ui.plugins.base import AppContext
from .plugin import IsolierungPlugin


def _configure_icon(root: tk.Tk) -> None:
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_ico_path = os.path.join(base_path, "logo-min.ico")
    if os.path.exists(icon_ico_path):
        try:
            root.iconbitmap(icon_ico_path)
        except Exception as exc:  # pragma: no cover - GUI Konfiguration
            print(f"Fehler beim Laden des .ico-Icons: {exc}")

    icon_png_path = os.path.join(base_path, "logo_min.png")
    if os.path.exists(icon_png_path):
        try:
            icon = tk.PhotoImage(file=icon_png_path)
            root.iconphoto(True, icon)
        except Exception as exc:  # pragma: no cover - GUI Konfiguration
            print(f"Fehler beim Laden des .png-Icons: {exc}")


def main() -> None:
    root = tk.Tk()
    root.title("Heatrix IsoSim v1.0")
    root.geometry("1200x800")
    root.minsize(1000, 700)

    if sv_ttk:
        try:
            sv_ttk.use_dark_theme()
        except Exception:
            pass

    _configure_icon(root)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    plugin = IsolierungPlugin()
    context = AppContext(root=root, notebook=notebook, project_store=ProjectStore())
    plugin.attach(context)

    if sv_ttk:
        plugin.on_theme_changed(sv_ttk.get_theme())

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        print("FEHLER beim Programmstart:")
        traceback.print_exc()
        input("\nDrücke Enter zum Schließen...")
