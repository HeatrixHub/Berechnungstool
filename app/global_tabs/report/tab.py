from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from Isolierung.tabs.scrollable import ScrollableFrame
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.plugins.base import AppContext, Plugin, ReportSection


class ReportTab:
    """Aggregiert freiwillige Berichtsinhalte aus allen Plugins."""

    def __init__(self, notebook: ttk.Notebook, context: AppContext, tab_name: str = "Bericht"):
        self.context = context
        self.plugins: Sequence[Plugin] = context.plugins
        self.selected_plugin = tk.StringVar(value="Alle Plugins")
        self.output_path = tk.StringVar(
            value=str(Path.home() / "berichte" / "bericht.pdf")
        )

        container = ttk.Frame(notebook, padding=(14, 12, 14, 12))
        notebook.add(container, text=tab_name)

        ttk.Label(container, text="Berichtsexport", style="Title.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 8))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text="Plugin-Auswahl:").grid(row=0, column=0, sticky="w")
        self.plugin_combo = ttk.Combobox(
            controls,
            state="readonly",
            textvariable=self.selected_plugin,
            values=self._get_plugin_options(),
        )
        self.plugin_combo.grid(row=0, column=1, sticky="ew", padx=(6, 12))
        self.plugin_combo.bind("<<ComboboxSelected>>", self._refresh_sections)

        ttk.Label(controls, text="Zielpfad:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        path_entry = ttk.Entry(controls, textvariable=self.output_path)
        path_entry.grid(row=1, column=1, sticky="ew", padx=(6, 12), pady=(6, 0))
        ttk.Button(controls, text="…", width=3, command=self._choose_target).grid(
            row=1, column=2, sticky="w", pady=(6, 0)
        )
        ttk.Button(controls, text="PDF erzeugen", command=self._export_pdf).grid(
            row=0, column=3, rowspan=2, sticky="e", padx=(12, 0)
        )

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)

        self._render_sections(self._collect_sections())

    def _get_plugin_options(self) -> List[str]:
        names = [plugin.name for plugin in self.plugins]
        return ["Alle Plugins", *names]

    def _choose_target(self) -> None:
        initial = Path(self.output_path.get())
        initial_dir = initial.parent if initial.parent.exists() else Path.home()
        selected = filedialog.asksaveasfilename(
            parent=self.context.root,
            title="PDF speichern",
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf"), ("Alle Dateien", "*.*")],
            initialdir=initial_dir,
            initialfile=initial.name,
        )
        if selected:
            self.output_path.set(str(Path(selected)))

    def _collect_sections(self) -> List[tuple[Plugin, ReportSection]]:
        sections: List[tuple[Plugin, ReportSection]] = []
        selected = self.selected_plugin.get()
        for plugin in self.plugins:
            if selected != "Alle Plugins" and plugin.name != selected:
                continue
            hook = getattr(plugin, "export_report", None)
            if hook is None:
                continue
            try:
                section = hook()
            except Exception as exc:  # pragma: no cover - Laufzeitdiagnose
                messagebox.showwarning(
                    "Bericht", f"{plugin.name}: Bericht konnte nicht erzeugt werden\n{exc}"
                )
                continue
            if section is None:
                continue
            if not isinstance(section, ReportSection):
                messagebox.showwarning(
                    "Bericht",
                    f"{plugin.name}: export_report muss einen ReportSection zurückgeben",
                )
                continue
            sections.append((plugin, section))
        return sections

    def _refresh_sections(self, *_: object) -> None:
        self._render_sections(self._collect_sections())

    def _render_sections(self, sections: Iterable[tuple[Plugin, ReportSection]]) -> None:
        for child in self.scrollable.inner.winfo_children():
            child.destroy()

        for plugin, section in sections:
            card = ttk.LabelFrame(
                self.scrollable.inner,
                text=f"{plugin.name} – {section.title}",
                padding=10,
                style="Section.TLabelframe",
            )
            card.pack(fill="x", expand=True, padx=4, pady=4)

            if section.widget is not None:
                try:
                    section.widget.pack(in_=card, fill="x", expand=True)
                except Exception:
                    ttk.Label(
                        card,
                        text="Widget kann nicht eingebettet werden. Bitte HTML/Daten nutzen.",
                        foreground="#92400e",
                    ).pack(anchor="w")
            elif section.html:
                ttk.Label(card, text=section.html, wraplength=1000, justify="left").pack(
                    anchor="w"
                )
            elif section.data is not None:
                ttk.Label(card, text=str(section.data), justify="left").pack(anchor="w")
            else:
                ttk.Label(card, text="Keine Inhalte verfügbar.").pack(anchor="w")

    def _export_pdf(self) -> None:
        sections = self._collect_sections()
        if not sections:
            messagebox.showinfo("Bericht", "Keine Berichtsinhalte vorhanden.")
            return

        target = Path(self.output_path.get()).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(target), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        for idx, (plugin, section) in enumerate(sections):
            story.append(Paragraph(f"<b>{plugin.name} – {section.title}</b>", styles["Heading3"]))
            body_text = self._section_to_text(section)
            story.append(Paragraph(body_text, styles["BodyText"]))
            if idx < len(sections) - 1:
                story.append(Spacer(1, 12))
                story.append(PageBreak())

        try:
            doc.build(story)
        except Exception as exc:  # pragma: no cover - Laufzeitdiagnose
            messagebox.showerror("Bericht", f"PDF konnte nicht erstellt werden: {exc}")
            return

        messagebox.showinfo("Bericht", f"PDF gespeichert: {target}")

    def _section_to_text(self, section: ReportSection) -> str:
        if section.html:
            return section.html
        if section.data is not None:
            return str(section.data)
        widget = section.widget
        if widget is None:
            return ""
        extracted = self._extract_text_from_widget(widget)
        if extracted:
            return extracted
        return "(Widget-Inhalte können nicht als Text exportiert werden)"

    @staticmethod
    def _extract_text_from_widget(widget: tk.Widget) -> str:
        if isinstance(widget, (tk.Label, ttk.Label)):
            return str(widget.cget("text"))
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        if isinstance(widget, tk.Entry):
            return widget.get()
        return ""
