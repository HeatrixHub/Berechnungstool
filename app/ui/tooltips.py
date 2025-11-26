from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def add_tooltip(widget: ttk.Widget, text: str, *, delay_ms: int = 400) -> None:
    """Attach a lightweight tooltip to a widget."""

    tooltip = tk.Toplevel(widget)
    tooltip.wm_overrideredirect(True)
    tooltip.withdraw()
    tooltip.attributes("-topmost", True)

    label = tk.Label(
        tooltip,
        text=text,
        padding=(8, 6),
        justify="left",
        background="#111827",
        foreground="#f9fafb",
        relief="solid",
        borderwidth=1,
        wraplength=360,
    )
    label.pack()

    after_id: str | None = None

    def _show(_event: tk.Event | None = None) -> None:
        x = widget.winfo_rootx() + 12
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        tooltip.wm_geometry(f"+{x}+{y}")
        tooltip.deiconify()

    def _hide(_event: tk.Event | None = None) -> None:
        nonlocal after_id
        if after_id:
            widget.after_cancel(after_id)
            after_id = None
        tooltip.withdraw()

    def _schedule(_event: tk.Event) -> None:
        nonlocal after_id
        _hide()
        after_id = widget.after(delay_ms, _show)

    widget.bind("<Enter>", _schedule)
    widget.bind("<Leave>", _hide)
    widget.bind("<FocusIn>", _show)
    widget.bind("<FocusOut>", _hide)
