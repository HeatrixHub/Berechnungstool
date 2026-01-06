"""Fachlogik für die Zuschnittoptimierung."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, List, Tuple

from rectpack import MaxRectsBssf, PackingBin, newPacker

from app.global_tabs.isolierungen_db.logic import load_insulation


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


def pack_plates(plates: List[dict], kerf: float) -> Tuple[List[Placement], List[dict], float | None, int]:
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
    material_summary: List[dict] = []
    total_cost: float | None = None
    total_bin_count: int | None = None
    total_bins = 0
    for (material, required_thickness), items in grouped.items():
        variant_data = resolve_variant_data(material, required_thickness)
        material_label = format_material_label(material, variant_data)
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
        material_summary.append(
            {
                "material": material_label,
                "count": len(packer),
                "price": price,
                "cost": cost,
            }
        )

    if not placements:
        raise ValueError("Keine Platzierungen erstellt.")

    known_costs = [entry["cost"] for entry in material_summary if entry["cost"] is not None]
    total_cost = sum(known_costs) if known_costs else None
    total_bin_count = total_bins
    return placements, material_summary, total_cost, total_bin_count


def format_material_label(material: str, variant: Dict[str, object]) -> str:
    variant_name = variant.get("name") or f"{variant.get('thickness')} mm"
    return f"{material} ({variant_name})"


def resolve_variant_data(
    material: str, required_thickness: float
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


def color_for(material: str) -> str:
    random.seed(hash(material))
    r = 120 + random.randint(0, 100)
    g = 120 + random.randint(0, 100)
    b = 180 + random.randint(0, 60)
    return f"#{r:02x}{g:02x}{b:02x}"
