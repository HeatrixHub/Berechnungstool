"""Host-Anwendung, die alle Tools als Plugins lädt."""
from __future__ import annotations

import importlib
from typing import Iterable, List, Sequence, Tuple

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as exc:  # pragma: no cover - tkinter ist optional bei Tests
    raise RuntimeError("tkinter wird für die Host-Anwendung benötigt") from exc

try:
    import sv_ttk
except Exception:  # pragma: no cover - sv_ttk ist optional
    sv_ttk = None  # type: ignore[assignment]

from tkinter import messagebox

from app.plugins.base import AppContext, Plugin
from app.plugins.manager import PluginManagerDialog
from app.plugins import registry
from app.projects import ProjectStore, ProjectsTab
from app.global_tabs.isolierungen_db import IsolierungenTab


def _load_plugins(specs: Sequence[registry.PluginSpec]) -> tuple[List[Plugin], List[str]]:
    plugins: List[Plugin] = []
    errors: List[str] = []
    for spec in specs:
        if not spec.enabled:
            continue
        try:
            module = importlib.import_module(spec.module)
            plugin_cls = getattr(module, spec.class_name)
            if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, Plugin):
                raise TypeError(
                    f"{spec.module}.{spec.class_name} ist kein Plugin-Typ"
                )
            plugin_instance = plugin_cls()
            plugin_instance.identifier = spec.identifier
            plugins.append(plugin_instance)
        except Exception as exc:  # pragma: no cover - Laufzeitdiagnose
            errors.append(f"{spec.name}: {exc}")
    return plugins, errors


def _configure_theme(root: tk.Misc) -> None:
    if not sv_ttk:
        return
    try:
        sv_ttk.use_dark_theme()
    except Exception:
        pass


def _configure_styles(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    style.configure("TFrame", padding=0)
    style.configure("TLabel", font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
    style.configure("Section.TLabelframe", padding=(12, 8, 12, 12))
    style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
    style.configure("TButton", padding=(10, 6))
    style.configure("Card.TFrame", relief="ridge", padding=(14, 12))
    style.map(
        "TButton",
        relief=[("pressed", "sunken"), ("active", "raised")],
    )
    return style


def _build_header(root: tk.Misc, plugins: Iterable[Plugin]) -> ttk.Frame:
    header = ttk.Frame(root, padding=(16, 12))
    header.pack(fill="x")

    header.columnconfigure(0, weight=1)

    ttk.Label(header, text="Heatrix Berechnungstools", style="Title.TLabel").grid(
        row=0, column=0, sticky="w"
    )

    controls_frame = ttk.Frame(header)
    controls_frame.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
    theme_toggle = _create_theme_button(controls_frame, plugins)
    plugin_manager_button = _create_plugin_manager_button(
        controls_frame, dialog_parent=root
    )
    for widget in (plugin_manager_button, theme_toggle):
        if widget is not None:
            widget.pack(side="right", padx=(8, 0))
    return header


def _build_footer(root: tk.Misc) -> None:
    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=8)
    footer = ttk.Frame(root, padding=(16, 6, 16, 12))
    footer.pack(fill="x", side="bottom")
    ttk.Label(
        footer,
        text="© 2025 Heatrix GmbH",
        font=("Segoe UI", 9),
    ).pack(side="left")


def _create_theme_button(parent: tk.Misc, plugins: Iterable[Plugin]) -> tk.Widget | None:
    if not sv_ttk:
        return None

    def toggle_theme() -> None:
        current = sv_ttk.get_theme()
        if current == "dark":
            sv_ttk.use_light_theme()
            button.config(text="🌙")
            new_theme = "light"
        else:
            sv_ttk.use_dark_theme()
            button.config(text="☀")
            new_theme = "dark"
        for plugin in plugins:
            plugin.on_theme_changed(new_theme)

    button = ttk.Button(
        parent, text="☀", width=3, style="Toolbutton", command=toggle_theme
    )
    try:
        current_theme = sv_ttk.get_theme()
    except Exception:
        current_theme = "dark"
    if current_theme == "light":
        button.config(text="🌙")
    return button


def _create_plugin_manager_button(
    parent: tk.Misc, dialog_parent: tk.Misc
) -> tk.Widget:
    def _show_dialog() -> None:
        def _on_save() -> None:
            messagebox.showinfo(
                "Pluginverwaltung",
                "Änderungen gespeichert. Bitte Anwendung neu starten, "
                "damit die Plugin-Auswahl übernommen wird.",
            )

        dialog = PluginManagerDialog(dialog_parent, on_save=_on_save)
        dialog.grab_set()

    return ttk.Button(
        parent, text="⚙", width=3, style="Toolbutton", command=_show_dialog
    )


def _build_warning_panel(root: tk.Misc, errors: Sequence[str]) -> None:
    if not errors:
        return
    frame = ttk.Frame(root, padding=(16, 10))
    frame.pack(fill="x")
    ttk.Label(
        frame,
        text="Einige Plugins konnten nicht geladen werden:",
        font=("Segoe UI", 10, "bold"),
        foreground="#b45309",
    ).pack(anchor="w")
    for error in errors:
        ttk.Label(frame, text=f"• {error}", foreground="#92400e").pack(anchor="w")


def main() -> None:
    root = tk.Tk()
    root.title("Heatrix Berechnungstools")
    root.geometry("1280x840")
    root.minsize(1100, 720)

    _configure_theme(root)
    _configure_styles(root)

    registry.ensure_default_registry()
    specs = registry.load_registry()
    plugins, load_errors = _load_plugins(specs)

    header = _build_header(root, plugins)
    _build_warning_panel(root, load_errors)

    content = ttk.Frame(root, padding=(16, 0, 16, 16))
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)

    notebook_container = ttk.Frame(content, padding=(0, 8, 0, 0), style="Card.TFrame")
    notebook_container.grid(row=0, column=0, sticky="nsew")
    notebook_container.columnconfigure(0, weight=1)
    notebook_container.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(notebook_container)
    notebook.grid(row=0, column=0, sticky="nsew")

    project_store = ProjectStore()
    projects_tab = ProjectsTab(notebook, project_store, plugins, specs)
    IsolierungenTab(notebook, tab_name="Isolierungen DB")

    context = AppContext(root=root, notebook=notebook, project_store=project_store)
    for plugin in plugins:
        plugin.attach(context)

    if sv_ttk:
        current = sv_ttk.get_theme()
        for plugin in plugins:
            plugin.on_theme_changed(current)

    _build_footer(root)

    def _on_close() -> None:
        answer = messagebox.askyesnocancel(
            "Programm schließen",
            "Möchten Sie den aktuellen Stand speichern, bevor das Programm beendet wird?",
        )
        if answer is None:
            return
        if answer:
            saved = projects_tab.save_project()
            if not saved:
                return
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    root.mainloop()


if __name__ == "__main__":
    main()
