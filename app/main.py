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

from app.plugins.base import AppContext, Plugin

# Statische Plugin-Liste; kann später durch dynamische Entdeckung ersetzt werden.
PLUGIN_SPECS: Sequence[Tuple[str, str]] = (
    ("Isolierung.plugin", "IsolierungPlugin"),
    ("SoffeigenschaftenLuft.plugin", "StoffeigenschaftenLuftPlugin"),
)


def _load_plugins() -> List[Plugin]:
    plugins: List[Plugin] = []
    for module_name, attr_name in PLUGIN_SPECS:
        module = importlib.import_module(module_name)
        plugin_cls = getattr(module, attr_name)
        if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, Plugin):
            raise TypeError(
                f"{module_name}.{attr_name} ist kein Plugin-Typ"
            )
        plugins.append(plugin_cls())
    return plugins


def _configure_theme(root: tk.Misc) -> None:
    if not sv_ttk:
        return
    try:
        sv_ttk.use_dark_theme()
    except Exception:
        pass


def _build_header(root: tk.Misc, theme_toggle: tk.Widget | None) -> None:
    header = ttk.Frame(root, padding=(12, 10))
    header.pack(fill="x")
    ttk.Label(
        header,
        text="Heatrix Berechnungstools",
        font=("Segoe UI", 18, "bold"),
    ).pack(side="left")
    if theme_toggle is not None:
        theme_toggle.pack(side="right")


def _build_footer(root: tk.Misc) -> None:
    footer = ttk.Frame(root, padding=(12, 6))
    footer.pack(fill="x", side="bottom")
    ttk.Label(
        footer,
        text="© 2025 Heatrix GmbH",
        font=("Segoe UI", 9),
    ).pack(side="left")


def _create_theme_button(root: tk.Misc, plugins: Iterable[Plugin]) -> tk.Widget | None:
    if not sv_ttk:
        return None

    def toggle_theme() -> None:
        current = sv_ttk.get_theme()
        if current == "dark":
            sv_ttk.use_light_theme()
            button.config(text="🌙 Dunkelmodus")
            new_theme = "light"
        else:
            sv_ttk.use_dark_theme()
            button.config(text="☀ Hellmodus")
            new_theme = "dark"
        for plugin in plugins:
            plugin.on_theme_changed(new_theme)

    button = ttk.Button(root, text="☀ Hellmodus", command=toggle_theme)
    return button


def main() -> None:
    root = tk.Tk()
    root.title("Heatrix Berechnungstools")
    root.geometry("1280x840")
    root.minsize(1100, 720)

    _configure_theme(root)

    plugins = _load_plugins()

    theme_button = _create_theme_button(root, plugins)
    _build_header(root, theme_button)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

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
