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


def _load_plugins() -> tuple[List[Plugin], List[str]]:
    specs = registry.load_registry()
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
            plugins.append(plugin_cls())
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


def _build_header(root: tk.Misc, plugins: Iterable[Plugin]) -> None:
    header = ttk.Frame(root, padding=(0, 8, 12, 0))
    header.place(relx=1.0, rely=0.0, x=-4, y=8, anchor="ne")
    controls_frame = ttk.Frame(header)
    controls_frame.pack(side="right")
    theme_toggle = _create_theme_button(controls_frame, plugins)
    plugin_manager_button = _create_plugin_manager_button(
        controls_frame, dialog_parent=root
    )
    for widget in (theme_toggle, plugin_manager_button):
        if widget is not None:
            widget.pack(side="right", padx=(8, 0))


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
    frame = ttk.Frame(root, padding=(12, 6))
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

    registry.ensure_default_registry()
    plugins, load_errors = _load_plugins()

    _build_header(root, plugins)
    _build_warning_panel(root, load_errors)

    content = ttk.Frame(root, padding=(16, 12, 16, 16))
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(content)
    notebook.grid(row=0, column=0, sticky="nsew")

    context = AppContext(root=root, notebook=notebook)
    for plugin in plugins:
        plugin.attach(context)

    if sv_ttk:
        current = sv_ttk.get_theme()
        for plugin in plugins:
            plugin.on_theme_changed(current)

    _build_footer(root)

    root.mainloop()


if __name__ == "__main__":
    main()
