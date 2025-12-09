from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import Dict, Iterable, List, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from app.plugins.base import Plugin
from app.projects.store import ProjectRecord, ProjectStore


@dataclass(slots=True)
class TemplateSpec:
    plugin: Plugin
    identifier: str
    name: str
    path: Path


class ReportBuildError(Exception):
    """Signalisiert Fehler beim Erstellen des PDF-Berichts."""


class ReportTab:
    """Erzeugt PDF-Berichte aus Plugin-Zuständen mittels Jinja2-Templates."""

    def __init__(
        self,
        notebook: ttk.Notebook,
        project_store: ProjectStore,
        plugins: Iterable[Plugin],
        tab_name: str = "Bericht",
    ) -> None:
        self.project_store = project_store
        self.plugins: List[Plugin] = list(plugins)
        self.templates: List[TemplateSpec] = []
        self.logger = logging.getLogger(__name__)

        self.frame = ttk.Frame(notebook, padding=(18, 16, 18, 16))
        notebook.add(self.frame, text=tab_name)

        self.status_var = tk.StringVar(value="Wähle Templates und erstelle einen Bericht.")
        self.project_var = tk.StringVar(value="Aktueller Stand")

        self._build_ui()
        self._discover_templates()
        self._refresh_project_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)

        ttk.Label(self.frame, text="PDF-Bericht", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        meta = ttk.LabelFrame(
            self.frame, text="Datenbasis", padding=10, style="Section.TLabelframe"
        )
        meta.grid(row=1, column=0, sticky="ew", pady=(8, 10))
        meta.columnconfigure(1, weight=1)

        ttk.Label(meta, text="Projekt:").grid(row=0, column=0, sticky="w", padx=4)
        self.project_combo = ttk.Combobox(
            meta,
            textvariable=self.project_var,
            state="readonly",
        )
        self.project_combo.grid(row=0, column=1, sticky="ew", padx=4)
        self.project_combo.bind("<<ComboboxSelected>>", lambda _: self._set_status("Projekt gewählt."))

        actions = ttk.Frame(self.frame, padding=(0, 4, 0, 10))
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        ttk.Button(actions, text="Templates aktualisieren", command=self._discover_templates).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Button(
            actions, text="PDF erstellen", style="Accent.TButton", command=self.create_report
        ).grid(row=0, column=1, sticky="e")

        panes = ttk.Panedwindow(self.frame, orient="horizontal")
        panes.grid(row=3, column=0, sticky="nsew")
        self.frame.rowconfigure(3, weight=1)

        template_frame = ttk.LabelFrame(
            panes, text="Verfügbare Templates", padding=10, style="Section.TLabelframe"
        )
        template_frame.columnconfigure(0, weight=1)
        template_frame.rowconfigure(0, weight=1)

        columns = ("plugin", "template")
        self.template_tree = ttk.Treeview(
            template_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            height=14,
        )
        self.template_tree.heading("plugin", text="Plugin")
        self.template_tree.heading("template", text="Template")
        self.template_tree.column("plugin", width=220, anchor="w")
        self.template_tree.column("template", width=260, anchor="w")
        self.template_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(template_frame, orient="vertical", command=self.template_tree.yview)
        self.template_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.preview = tk.Text(panes, wrap="word", state="disabled")

        panes.add(template_frame, weight=2)
        panes.add(self.preview, weight=3)

        ttk.Label(
            self.frame,
            textvariable=self.status_var,
            foreground="#6b7280",
            wraplength=1080,
            justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Template-Ermittlung & Projekte
    # ------------------------------------------------------------------
    def _discover_templates(self) -> None:
        self.templates.clear()
        for plugin in self.plugins:
            identifier = getattr(plugin, "identifier", None)
            if not identifier:
                continue
            module = importlib.import_module(plugin.__module__)
            module_file = getattr(module, "__file__", None)
            if not module_file:
                continue
            base = Path(module_file).resolve().parent
            report_dir = base / "reports"
            if not report_dir.exists():
                continue
            for template_path in report_dir.glob("*.j2"):
                self.templates.append(
                    TemplateSpec(
                        plugin=plugin,
                        identifier=identifier,
                        name=template_path.stem,
                        path=template_path,
                    )
                )
        self._refresh_template_tree()
        if self.templates:
            self._set_status("Templates gefunden. Wähle ein oder mehrere für den Bericht.")
        else:
            self._set_status("Keine Templates gefunden. Lege .j2-Dateien in <plugin>/reports an.")

    def _refresh_template_tree(self) -> None:
        self.template_tree.delete(*self.template_tree.get_children())
        for spec in self.templates:
            self.template_tree.insert(
                "",
                "end",
                iid=self._tree_id(spec),
                values=(spec.plugin.name, spec.name),
            )

    def _refresh_project_list(self) -> None:
        items = ["Aktueller Stand"]
        for record in self.project_store.list_projects():
            items.append(f"{record.name} ({record.updated_at})|{record.id}")
        self.project_combo.configure(values=items)
        if self.project_var.get() not in items:
            self.project_var.set(items[0])

    # ------------------------------------------------------------------
    # Berichtserstellung
    # ------------------------------------------------------------------
    def create_report(self) -> None:
        selected = self.template_tree.selection()
        if not selected:
            messagebox.showinfo("Hinweis", "Bitte mindestens ein Template auswählen.")
            return

        save_path = filedialog.asksaveasfilename(
            title="PDF speichern",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not save_path:
            return

        project_info, plugin_states = self._resolve_context()
        if project_info is None:
            return

        with tempfile.TemporaryDirectory(prefix="report-assets-") as tmp_dir:
            resource_dir = Path(tmp_dir)
            sections: List[Tuple[str, str]] = []
            for item in selected:
                spec = self._spec_from_tree_id(item)
                if not spec:
                    continue
                rendered = self._render_template(
                    spec, project_info, plugin_states, resource_dir
                )
                sections.append((f"{spec.plugin.name} – {spec.name}", rendered))

            if not sections:
                messagebox.showerror("Fehler", "Keine Inhalte zum Rendern gefunden.")
                return

            try:
                self._write_pdf(Path(save_path), sections)
            except ReportBuildError:
                return
            except Exception as exc:  # pragma: no cover - GUI Feedback
                messagebox.showerror(
                    "Fehler",
                    f"Der Bericht konnte nicht erstellt werden:\n{exc}",
                )
                return

        self._set_status(f"Bericht gespeichert unter {save_path}.")
        messagebox.showinfo("Fertig", "Der Bericht wurde erstellt.")

    def _resolve_context(self) -> Tuple[Dict[str, str] | None, Dict[str, Dict]]:
        selection = self.project_var.get()
        if selection == "Aktueller Stand":
            plugin_states: Dict[str, Dict] = {}
            errors: List[str] = []
            for plugin in self.plugins:
                identifier = getattr(plugin, "identifier", None)
                if not identifier:
                    continue
                try:
                    plugin_states[identifier] = plugin.export_state()
                except Exception as exc:  # pragma: no cover - GUI Feedback
                    errors.append(f"{plugin.name}: {exc}")
            if errors:
                messagebox.showerror(
                    "Export fehlgeschlagen",
                    "\n".join(["Folgende Plugins konnten nicht exportiert werden:"] + errors),
                )
                return None, {}
            project_info = {
                "name": "Aktuelle Eingaben",
                "author": "",
                "created_at": "",
                "updated_at": "",
            }
            return project_info, plugin_states

        if "|" not in selection:
            messagebox.showerror("Fehler", "Ungültige Projektauswahl.")
            return None, {}
        _, project_id = selection.split("|", 1)
        record = self.project_store.load_project(project_id)
        if not record:
            messagebox.showerror("Fehler", "Projekt konnte nicht geladen werden.")
            return None, {}
        return self._project_to_context(record)

    def _project_to_context(self, record: ProjectRecord) -> Tuple[Dict[str, str], Dict[str, Dict]]:
        meta = {
            "name": record.name,
            "author": record.author,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        return meta, record.plugin_states

    def _render_template(
        self,
        spec: TemplateSpec,
        project: Dict[str, str],
        plugin_states: Dict[str, Dict],
        resource_dir: Path,
    ) -> str:
        env = Environment(
            loader=FileSystemLoader(spec.path.parent),
            autoescape=False,
            undefined=StrictUndefined,
        )
        template = env.get_template(spec.path.name)
        context = {
            "project": project,
            "plugin_states": plugin_states,
        }
        context |= self._augment_context(spec, plugin_states, resource_dir)
        try:
            rendered = template.render(context)
        except Exception as exc:  # pragma: no cover - GUI Feedback
            messagebox.showerror(
                "Template-Fehler",
                f"{spec.name} ({spec.plugin.name}) konnte nicht gerendert werden:\n{exc}",
            )
            return ""
        self._show_preview(rendered)
        return rendered

    def _write_pdf(self, target: Path, sections: Sequence[Tuple[str, str]]) -> None:
        doc = SimpleDocTemplate(str(target), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for title, content in sections:
            story.append(Paragraph(title, styles["Heading1"]))
            story.append(Spacer(1, 12))
            for block in self._to_flowables(content, styles):
                story.append(block)
        try:
            doc.build(story)
        except Exception as exc:
            messagebox.showerror(
                "PDF-Fehler",
                f"Beim Erstellen des PDFs ist ein Fehler aufgetreten:\n{exc}",
            )
            raise ReportBuildError(exc) from exc

    def _to_flowables(self, content: str, styles) -> List:
        sanitized = content.strip()
        if not sanitized:
            return [Paragraph("(keine Daten)", styles["Normal"])]

        elements: List = []
        blocks = sanitized.split("\n\n")
        for index, raw_block in enumerate(blocks):
            block = raw_block.strip()
            image = self._parse_image_block(block)
            if image:
                elements.append(image)
            else:
                try:
                    elements.append(Paragraph(block.replace("\n", "<br/>"), styles["Normal"]))
                except Exception as exc:
                    self.logger.warning("Ungültiger Absatz im Bericht: %s", block, exc_info=exc)
                    elements.append(Paragraph("(keine Daten)", styles["Normal"]))

            if index < len(blocks) - 1:
                elements.append(Spacer(1, 8))
        return elements

    def _parse_image_block(self, block: str) -> Image | None:
        align = None
        para_match = re.fullmatch(r"<para([^>]*)>(.*)</para>", block, flags=re.IGNORECASE | re.DOTALL)
        if para_match:
            attr_text = para_match.group(1)
            align_match = re.search(r"align=\"?([a-zA-Z]+)\"?", attr_text or "")
            if align_match:
                align = align_match.group(1).upper()
            block = para_match.group(2).strip()

        img_match = re.fullmatch(r"<img\s+[^>]*src=\"([^\"]+)\"[^>]*>", block, flags=re.IGNORECASE)
        if not img_match:
            return None

        src = img_match.group(1)
        width = self._extract_dimension(block, "width")
        height = self._extract_dimension(block, "height")

        try:
            image = Image(src, width=width, height=height)
        except Exception as exc:
            self.logger.warning("Bild konnte nicht geladen werden: %s", src, exc_info=exc)
            return None

        if align in {"LEFT", "CENTER", "RIGHT"}:
            image.hAlign = align
        return image

    def _extract_dimension(self, block: str, name: str) -> float | None:
        match = re.search(rf"{name}=\"?([0-9.]+)\"?", block, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _augment_context(
        self, spec: TemplateSpec, plugin_states: Dict[str, Dict], resource_dir: Path
    ) -> Dict[str, Dict[str, str]]:
        if spec.identifier != "isolierung":
            return {}

        iso_state = plugin_states.get("isolierung", {})
        berechnung = iso_state.get("berechnung", {})
        result = berechnung.get("result")
        if not berechnung or not result:
            return {}

        thicknesses = berechnung.get("thicknesses") or []
        temperatures = result.get("interface_temperatures") or []
        if not thicknesses or len(temperatures) != len(thicknesses) + 1:
            return {}

        plot_path = resource_dir / "isolierung_temperature_plot.png"
        try:
            self._make_temperature_plot(thicknesses, temperatures, plot_path)
        except Exception:
            return {}

        enriched_berechnung = dict(berechnung)
        enriched_berechnung["temperature_plot"] = str(plot_path)

        updated_plugin_states = dict(plugin_states)
        updated_iso_state = dict(iso_state)
        updated_iso_state["berechnung"] = enriched_berechnung
        updated_plugin_states["isolierung"] = updated_iso_state
        return {"plugin_states": updated_plugin_states}

    def _make_temperature_plot(
        self, thicknesses: Sequence[float], temperatures: Sequence[float], target: Path
    ) -> None:
        plt.switch_backend("Agg")
        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        total_x = [0]
        for t in thicknesses:
            total_x.append(total_x[-1] + t)

        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("report_cmap", colors, N=256)
        ax.plot(total_x, temperatures, linewidth=2, marker="o", color="#111827")

        x_pos = 0
        for i, t in enumerate(thicknesses):
            color_value = i / max(len(thicknesses) - 1, 1)
            ax.axvspan(x_pos, x_pos + t, color=cmap(color_value), alpha=0.35)
            x_pos += t

        for x, temp in zip(total_x, temperatures):
            ax.text(
                x,
                temp + 5,
                f"{temp:.0f}°C",
                ha="center",
                fontsize=8,
                bbox=dict(facecolor="#ffffff", alpha=0.8, edgecolor="none"),
                color="#111827",
            )

        ax.set_xlabel("Dicke [mm]", color="#111827")
        ax.set_ylabel("Temperatur [°C]", color="#111827")
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=11, color="#111827")
        ax.grid(True, linestyle="--", alpha=0.5, color="#9ca3af")
        ax.tick_params(axis="x", colors="#111827", labelsize=8)
        ax.tick_params(axis="y", colors="#111827", labelsize=8)
        fig.tight_layout()
        fig.savefig(target, bbox_inches="tight")
        plt.close(fig)

    # ------------------------------------------------------------------
    # Hilfen
    # ------------------------------------------------------------------
    def _tree_id(self, spec: TemplateSpec) -> str:
        return f"{spec.identifier}::{spec.path}"

    def _spec_from_tree_id(self, tree_id: str) -> TemplateSpec | None:
        for spec in self.templates:
            if self._tree_id(spec) == tree_id:
                return spec
        return None

    def _show_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, text)
        self.preview.configure(state="disabled")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
