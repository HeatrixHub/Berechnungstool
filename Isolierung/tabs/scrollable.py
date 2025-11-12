import tkinter as tk
from tkinter import ttk

class ScrollableFrame(ttk.Frame):
    """
    A scrollable frame with smooth scrolling support for all platforms (Windows, macOS, Linux).
    Place widgets inside `self.inner`.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Canvas & vertical scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Inner frame for actual content
        self.inner = ttk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # Keep scrollregion updated
        self.inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Scroll only when mouse is over this widget
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    # ----------------------------------------------------------------------
    # Internal methods
    # ----------------------------------------------------------------------
    def _on_frame_configure(self, event):
        """Update scrollregion after inserting widgets."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Make inner frame width match canvas width."""
        self.canvas.itemconfig(self.inner_id, width=event.width)

    def _on_mousewheel(self, event):
        """Cross-platform mouse wheel handler."""
        if event.num == 4:       # Linux scroll up
            delta = -1
        elif event.num == 5:     # Linux scroll down
            delta = 1
        else:                    # Windows / macOS
            delta = -1 * int(event.delta / 120)
        self.canvas.yview_scroll(delta, "units")

    def _bind_mousewheel(self, event):
        """Activate scrolling when the mouse enters the canvas."""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        """Deactivate scrolling when the mouse leaves the canvas."""
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")