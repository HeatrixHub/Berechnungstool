"""Zuschnittoptimierung für die im Schichtaufbau erzeugten Plattenlisten."""

from __future__ import annotations

import csv
import math
import random
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Tuple

from rectpack import MaxRectsBssf, PackingBin, newPacker

from app.global_tabs.isolierungen_db.logic import load_insulation
from .scrollable import ScrollableFrame


@dataclass
class Placement:
    """Ein platzierter Zuschnitt auf einer Rohlingplatte."""

    material: str
    bin_index: int
    part_label: str
    x: float
    y: float
    width: float
    height: float
    rotated: bool
    bin_width: float
    bin_height: float
    original_width: float
    original_height: float


class ZuschnittTab:
    """UI und Logik für die automatische Zuschnittsoptimierung."""

    def __init__(self, notebook):
        container = ttk.Frame(notebook)
        notebook.add(container, text="Zuschnitt")

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)
        self.frame = self.scrollable.inner

        self.plate_importer: Callable[[], List[dict]] | None = None
        self.placements: List[Placement] = []
        self.material_summary: List[dict] = []
        self.total_cost: float | None = None
        self.total_bin_count: int | None = None

        self._build_ui()

    # ---------------------------------------------------------------
    # UI
    # ---------------------------------------------------------------
    def _build_ui(self) -> None:
        self.frame.columnconfigure(1, weight=1)

        ttk.Label(
            self.frame, text="Zuschnittoptimierung", font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))

        settings = ttk.LabelFrame(self.frame, text="Einstellungen")
        settings.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Schnittfuge [mm]:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.kerf_var = tk.StringVar(value="0")
        ttk.Entry(settings, textvariable=self.kerf_var, width=10).grid(
            row=0, column=1, sticky="w", padx=6, pady=4
        )

        btn_frame = ttk.Frame(settings)
        btn_frame.grid(row=0, column=2, padx=6, pady=4, sticky="e")
        ttk.Button(btn_frame, text="Platten übernehmen", command=self.import_plates).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_frame, text="Berechnen", command=self.run_optimization).pack(
            side=tk.LEFT, padx=3
        )

        overview_frame = ttk.LabelFrame(self.frame, text="Rohlingübersicht")
        overview_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
        overview_frame.columnconfigure(0, weight=1)

        overview_columns = ("material", "count", "price", "cost")
        self.overview_tree = ttk.Treeview(
            overview_frame, columns=overview_columns, show="headings", height=6
        )
        headings = {
            "material": "Material",
            "count": "Rohlinge (min)",
            "price": "Preis/Stk [€]",
            "cost": "Kosten [€]",
        }
        for key, label in headings.items():
            self.overview_tree.heading(key, text=label)
        self.overview_tree.column("material", width=160, anchor="w")
        self.overview_tree.column("count", width=110, anchor="center")
        self.overview_tree.column("price", width=110, anchor="center")
        self.overview_tree.column("cost", width=110, anchor="center")
        self.overview_tree.grid(row=0, column=0, sticky="ew")


        columns = (
            "material",
            "bin",
            "teil",
            "breite",
            "hoehe",
            "x",
            "y",
            "rotation",
        )
        table_frame = ttk.LabelFrame(self.frame, text="Platzierungen")
        table_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=6)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        headings = {
            "material": "Material",
            "bin": "Rohling",
            "teil": "Teil",
            "breite": "Eff. Breite [mm]",
            "hoehe": "Eff. Höhe [mm]",
            "x": "X [mm]",
            "y": "Y [mm]",
            "rotation": "Drehung",
        }
        for key, label in headings.items():
            self.tree.heading(key, text=label)
        widths = {
            "material": 140,
            "bin": 90,
            "teil": 170,
            "breite": 110,
            "hoehe": 110,
            "x": 90,
            "y": 90,
            "rotation": 80,
        }
        for key, width in widths.items():
            self.tree.column(key, width=width, anchor="center")

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")

        export_frame = ttk.Frame(table_frame)
        export_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=4)
        ttk.Button(export_frame, text="CSV exportieren", command=self.export_csv).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(export_frame, text="Excel exportieren", command=self.export_excel).pack(
            side=tk.LEFT, padx=4
        )

        preview_frame = ttk.LabelFrame(self.frame, text="Graphische Übersicht")
        preview_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_frame, height=360, background="white")
        scroll_x = ttk.Scrollbar(
            preview_frame, orient="horizontal", command=self.preview_canvas.xview
        )
        self.preview_canvas.configure(xscrollcommand=scroll_x.set)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        scroll_x.grid(row=1, column=0, sticky="ew")

        # Bei Größenänderungen die grafische Übersicht neu zeichnen, damit alle
        # Rohlinge sichtbar bleiben.
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

    # ---------------------------------------------------------------
    # Datenbeschaffung
    # ---------------------------------------------------------------
    def register_plate_importer(self, importer: Callable[[], List[dict]]):
        self.plate_importer = importer

    def import_plates(self) -> None:
        if self.plate_importer is None:
            messagebox.showwarning("Keine Quelle", "Kein Tab zum Übernehmen verbunden.")
            return
        try:
            plates = self.plate_importer()
            if not plates:
                messagebox.showinfo("Leere Liste", "Keine Platten gefunden.")
                return
            self._cached_plates = plates
            messagebox.showinfo(
                "Platten übernommen",
                f"{len(plates)} Platten aus dem Schichtaufbau geladen.",
            )
        except Exception as exc:  # pragma: no cover - GUI Fehlerdialog
            messagebox.showerror("Übernahme fehlgeschlagen", str(exc))

    # ---------------------------------------------------------------
    # Optimierung
    # ---------------------------------------------------------------
    def run_optimization(self) -> None:
        try:
            kerf = float(self.kerf_var.get() or 0)
            if kerf < 0:
                raise ValueError("Schnittfuge muss >= 0 sein.")
            plates = getattr(self, "_cached_plates", None)
            if not plates:
                self.import_plates()
                plates = getattr(self, "_cached_plates", None)
            if not plates:
                return
            placements = self._pack_plates(plates, kerf)
            self.placements = placements
            self._display_results()
        except ValueError as exc:
            messagebox.showerror("Eingabefehler", str(exc))
        except Exception as exc:  # pragma: no cover - GUI Fehlerdialog
            import traceback

            traceback.print_exc()
            messagebox.showerror("Optimierung fehlgeschlagen", str(exc))

    def _pack_plates(self, plates: List[dict], kerf: float) -> List[Placement]:
        grouped: Dict[Tuple[str, float], List[dict]] = {}
        for plate in plates:
            material = plate.get("material", "")
            if not material:
                raise ValueError(
                    "Material in der Plattenliste fehlt. Bitte Material im Schichtaufbau setzen."
                )

            try:
                thickness = float(plate.get("thickness", 0))
            except (TypeError, ValueError):
                raise ValueError(
                    f"Ungültige Dicke für {plate.get('name', 'Teil')} von {material}."
                )

            grouped.setdefault((material, thickness), []).append(plate)

        placements: List[Placement] = []
        self.material_summary = []
        self.total_cost = None
        self.total_bin_count = None
        total_bins = 0
        for (material, required_thickness), items in grouped.items():
            variant_data = self._resolve_variant_data(material, required_thickness)
            material_label = self._format_material_label(material, variant_data)
            bin_width, bin_height = variant_data["length"], variant_data["width"]
            if bin_width <= 0 or bin_height <= 0:
                raise ValueError(
                    f"Ungültige Rohlingmaße für {material}. Bitte Länge/Breite in der Variante pflegen."
                )

            packer = newPacker(
                rotation=True,
                bin_algo=PackingBin.Global,
                pack_algo=MaxRectsBssf,
            )
            rect_map: List[dict] = []
            for idx, plate in enumerate(items):
                width = float(plate.get("length", 0)) + kerf
                height = float(plate.get("width", 0)) + kerf
                if min(width, height) <= 0:
                    raise ValueError(
                        f"Ungültige Abmessung für {plate.get('name','Teil')} von {material}."
                    )
                rect_map.append(
                    {
                        "index": idx,
                        "width": width,
                        "height": height,
                        "original_width": width - kerf,
                        "original_height": height - kerf,
                        "part_label": f"Schicht {plate.get('layer')}: {plate.get('name')}",
                    }
                )
                packer.add_rect(width, height, idx)

            packer.add_bin(bin_width, bin_height, float("inf"))
            packer.pack()

            for bin_index, abin in enumerate(packer, start=1):
                for rect in abin:
                    rect_data = rect_map[rect.rid]
                    rotated = not (
                        math.isclose(rect.width, rect_data["width"], rel_tol=1e-6)
                        and math.isclose(rect.height, rect_data["height"], rel_tol=1e-6)
                    )
                    placements.append(
                        Placement(
                            material=material_label,
                            bin_index=bin_index,
                            part_label=rect_data["part_label"],
                            x=float(rect.x),
                            y=float(rect.y),
                            width=float(rect.width),
                            height=float(rect.height),
                            rotated=rotated,
                            bin_width=bin_width,
                            bin_height=bin_height,
                            original_width=rect_data["original_width"],
                            original_height=rect_data["original_height"],
                        )
                    )
            total_bins += len(packer)
            price = variant_data["price"]
            cost = None if price is None else price * len(packer)
            self.material_summary.append(
                {
                    "material": material_label,
                    "count": len(packer),
                    "price": price,
                    "cost": cost,
                }
            )

        if not placements:
            raise ValueError("Keine Platzierungen erstellt.")

        known_costs = [entry["cost"] for entry in self.material_summary if entry["cost"] is not None]
        self.total_cost = sum(known_costs) if known_costs else None
        self.total_bin_count = total_bins
        return placements

    def _format_material_label(self, material: str, variant: Dict[str, object]) -> str:
        variant_name = variant.get("name") or f"{variant.get('thickness')} mm"
        return f"{material} ({variant_name})"

    def _resolve_variant_data(
        self, material: str, required_thickness: float
    ) -> Dict[str, float | str | None]:
        data = load_insulation(material)
        variants = data.get("variants") or []
        if not variants:
            raise ValueError(
                f"Für {material} sind keine Varianten in der Isolierung DB hinterlegt."
            )

        selectable = [
            variant
            for variant in variants
            if variant.get("thickness") is not None
        ]
        if not selectable:
            raise ValueError(
                f"Für {material} sind keine Variantendicken hinterlegt. Bitte Varianten prüfen."
            )

        best_variant = min(
            selectable,
            key=lambda variant: abs(float(variant.get("thickness", 0)) - required_thickness),
        )

        try:
            length = float(best_variant["length"])
            width = float(best_variant["width"])
        except (TypeError, ValueError, KeyError):
            raise ValueError(
                f"Für {material} konnte keine Variante mit Rohlingmaßen gefunden werden."
            )

        price_raw = best_variant.get("price")
        price = None if price_raw in (None, "") else float(price_raw)

        return {
            "name": best_variant.get("name"),
            "thickness": float(best_variant.get("thickness", required_thickness)),
            "length": length,
            "width": width,
            "price": price,
        }

    # ---------------------------------------------------------------
    # Projektzustand
    # ---------------------------------------------------------------
    def _safe_float(self, value: str | float | int | None) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def export_state(self) -> Dict[str, object]:
        return {
            "kerf": self._safe_float(self.kerf_var.get()),
            "cached_plates": getattr(self, "_cached_plates", []),
            "placements": [asdict(item) for item in self.placements],
            "material_summary": self.material_summary,
            "total_cost": self.total_cost,
            "total_bin_count": self.total_bin_count,
        }

    def import_state(self, state: Dict[str, object]) -> None:
        self.kerf_var.set(str(state.get("kerf", 0) or 0))
        cached = state.get("cached_plates")
        self._cached_plates = cached if isinstance(cached, list) else []

        placements_raw = state.get("placements") or []
        placements: List[Placement] = []
        for placement in placements_raw:
            try:
                placements.append(Placement(**placement))
            except Exception:
                continue
        self.placements = placements

        summary = state.get("material_summary")
        self.material_summary = summary if isinstance(summary, list) else []
        self.total_cost = state.get("total_cost")
        self.total_bin_count = state.get("total_bin_count")

        self._display_results()

    # ---------------------------------------------------------------
    # Darstellung
    # ---------------------------------------------------------------
    def _display_results(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for placement in self.placements:
            self.tree.insert(
                "",
                "end",
                values=(
                    placement.material,
                    f"{placement.bin_index}",
                    placement.part_label,
                    f"{placement.width:.1f}",
                    f"{placement.height:.1f}",
                    f"{placement.x:.1f}",
                    f"{placement.y:.1f}",
                    "90°" if placement.rotated else "0°",
                ),
            )

        self._update_summary_table()
        self._draw_preview()

    def _update_summary_table(self) -> None:
        for item in self.overview_tree.get_children():
            self.overview_tree.delete(item)

        for entry in self.material_summary:
            price = entry.get("price")
            cost = entry.get("cost")
            self.overview_tree.insert(
                "",
                "end",
                values=(
                    entry.get("material", "-"),
                    entry.get("count", "-"),
                    "-" if price is None else f"{price:.2f}",
                    "-" if cost is None else f"{cost:.2f}",
                ),
            )

        if not self.material_summary:
            return

        total_count = self.total_bin_count
        missing_prices = any(entry.get("price") is None for entry in self.material_summary)

        if missing_prices and self.total_cost is not None:
            cost_text = f"{self.total_cost:.2f} (ohne fehlende Preise)"
        elif missing_prices:
            cost_text = "- (fehlende Preise)"
        elif self.total_cost is None:
            cost_text = "-"
        else:
            cost_text = f"{self.total_cost:.2f}"

        self.overview_tree.insert(
            "",
            "end",
            values=(
                "Summe",
                "-" if total_count is None else total_count,
                "-",
                cost_text,
            ),
        )

    def _draw_preview(self) -> None:
        self.preview_canvas.delete("all")
        if not self.placements:
            self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        grouped: Dict[Tuple[str, int], List[Placement]] = {}
        for placement in self.placements:
            key = (placement.material, placement.bin_index)
            grouped.setdefault(key, []).append(placement)

        bins = list(grouped.items())
        columns = max(1, math.ceil(math.sqrt(len(bins))))
        rows = math.ceil(len(bins) / columns)

        col_widths: List[float] = [0.0 for _ in range(columns)]
        row_heights: List[float] = [0.0 for _ in range(rows)]
        for idx, (_, entries) in enumerate(bins):
            col = idx % columns
            row = idx // columns
            col_widths[col] = max(col_widths[col], entries[0].bin_width)
            row_heights[row] = max(row_heights[row], entries[0].bin_height)

        gap = 30.0
        padding = 16.0
        total_width = sum(col_widths) + gap * (columns - 1)
        total_height = sum(row_heights) + gap * (rows - 1)

        self.preview_canvas.update_idletasks()
        canvas_width = max(self.preview_canvas.winfo_width(), 200)
        canvas_height = max(self.preview_canvas.winfo_height(), 200)
        scale = min(
            (canvas_width - 2 * padding) / total_width,
            (canvas_height - 2 * padding) / total_height,
        )
        scale = min(scale, 2.0)

        col_offsets: List[float] = [padding]
        for width in col_widths[:-1]:
            col_offsets.append(col_offsets[-1] + width * scale + gap * scale)
        row_offsets: List[float] = [padding]
        for height in row_heights[:-1]:
            row_offsets.append(row_offsets[-1] + height * scale + gap * scale)

        label_offset = 6
        for idx, ((material, bin_idx), entries) in enumerate(bins):
            col = idx % columns
            row = idx // columns
            x_cursor = col_offsets[col]
            y_cursor = row_offsets[row]
            bin_w = entries[0].bin_width
            bin_h = entries[0].bin_height

            self.preview_canvas.create_rectangle(
                x_cursor,
                y_cursor + label_offset,
                x_cursor + bin_w * scale,
                y_cursor + bin_h * scale + label_offset,
                outline="#444",
                width=2,
            )
            self.preview_canvas.create_text(
                x_cursor + 6,
                y_cursor + 6,
                anchor="nw",
                text=f"{material} – Rohling {bin_idx}",
                font=("Segoe UI", 9, "bold"),
                width=max(bin_w * scale - 12, 50),
            )

            for placement in entries:
                color = self._color_for(material)
                px = x_cursor + placement.x * scale
                py = y_cursor + label_offset + placement.y * scale
                pw = placement.width * scale
                ph = placement.height * scale
                self.preview_canvas.create_rectangle(
                    px,
                    py,
                    px + pw,
                    py + ph,
                    fill=color,
                    outline="#222",
                )
                self.preview_canvas.create_text(
                    px + pw / 2,
                    py + ph / 2,
                    text=placement.part_label,
                    font=("Segoe UI", 8),
                    width=max(pw - 12, 20),
                )

        layout_width = padding * 2 + total_width * scale + max(gap * scale, 0)
        layout_height = padding * 2 + total_height * scale + label_offset + max(gap * scale, 0)
        self.preview_canvas.configure(scrollregion=(0, 0, layout_width, layout_height))

    def _on_canvas_resize(self, _event) -> None:
        if self.placements:
            self._draw_preview()

    @staticmethod
    def _color_for(material: str) -> str:
        random.seed(hash(material))
        r = 120 + random.randint(0, 100)
        g = 120 + random.randint(0, 100)
        b = 180 + random.randint(0, 60)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ---------------------------------------------------------------
    # Export
    # ---------------------------------------------------------------
    def _ensure_results(self) -> None:
        if not self.placements:
            raise ValueError("Keine Ergebnisse zum Export vorhanden.")

    def export_csv(self) -> None:
        try:
            self._ensure_results()
            path = filedialog.asksaveasfilename(
                title="CSV speichern",
                defaultextension=".csv",
                filetypes=(("CSV", "*.csv"), ("Alle Dateien", "*.*")),
            )
            if not path:
                return
            with Path(path).open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(
                    [
                        "Material",
                        "Rohling",
                        "Teil",
                        "Breite_eff_mm",
                        "Hoehe_eff_mm",
                        "X_mm",
                        "Y_mm",
                        "Rotation",
                        "Breite_original_mm",
                        "Hoehe_original_mm",
                    ]
                )
                for p in self.placements:
                    writer.writerow(
                        [
                            p.material,
                            p.bin_index,
                            p.part_label,
                            f"{p.width:.2f}",
                            f"{p.height:.2f}",
                            f"{p.x:.2f}",
                            f"{p.y:.2f}",
                            "90" if p.rotated else "0",
                            f"{p.original_width:.2f}",
                            f"{p.original_height:.2f}",
                        ]
                    )
            messagebox.showinfo("Export abgeschlossen", f"CSV exportiert nach: {path}")
        except Exception as exc:  # pragma: no cover - GUI Fehlerdialog
            messagebox.showerror("Export fehlgeschlagen", str(exc))

    def export_excel(self) -> None:
        try:
            self._ensure_results()
            path = filedialog.asksaveasfilename(
                title="Excel speichern",
                defaultextension=".xlsx",
                filetypes=(("Excel", "*.xlsx"), ("Alle Dateien", "*.*")),
            )
            if not path:
                return
            try:
                from openpyxl import Workbook
            except Exception as exc:  # pragma: no cover - optionale Abhängigkeit
                raise RuntimeError(
                    "openpyxl wird für den Excel-Export benötigt. Bitte installieren."
                ) from exc

            wb = Workbook()
            ws = wb.active
            ws.title = "Zuschnitt"
            ws.append(
                [
                    "Material",
                    "Rohling",
                    "Teil",
                    "Breite_eff_mm",
                    "Hoehe_eff_mm",
                    "X_mm",
                    "Y_mm",
                    "Rotation",
                    "Breite_original_mm",
                    "Hoehe_original_mm",
                ]
            )
            for p in self.placements:
                ws.append(
                    [
                        p.material,
                        p.bin_index,
                        p.part_label,
                        p.width,
                        p.height,
                        p.x,
                        p.y,
                        90 if p.rotated else 0,
                        p.original_width,
                        p.original_height,
                    ]
                )
            wb.save(path)
            messagebox.showinfo("Export abgeschlossen", f"Excel exportiert nach: {path}")
        except Exception as exc:  # pragma: no cover - GUI Fehlerdialog
            messagebox.showerror("Export fehlgeschlagen", str(exc))

    # ---------------------------------------------------------------
    # Theme (nur Canvas-Hintergrund)
    # ---------------------------------------------------------------
    def update_theme_colors(self):  # pragma: no cover - UI Callback
        # Einfacher Farbwechsel für helle/dunkle Themes
        self.preview_canvas.configure(background="white")
