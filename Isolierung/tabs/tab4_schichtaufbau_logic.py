"""Berechnung des Schichtaufbaus für die Isolierungstafeln.

Dieses Modul kapselt die Berechnung der Plattenabmessungen für
mehrlagige Isolierungen. Es basiert auf dem bisher genutzten Python-Code
zur Schichtberechnung, wurde aber in ein wiederverwendbares Modul
überführt, damit es direkt aus dem neuen Tab aufgerufen werden kann.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple


# ----------------------------
# Datenmodelle
# ----------------------------
@dataclass
class Plate:
    name: str  # z.B. "Oben", "Unten", "Vorne", "Hinten", "Rechts", "Links"
    L: float  # Länge der Platte (in m, mm – konsistent bleiben)
    B: float  # Breite der Platte
    H: float  # Dicke der Platte (= Schichtdicke t_i)


@dataclass
class LayerResult:
    layer_index: int
    thickness: float
    plates: List[Plate]  # 6 Platten pro Schicht


@dataclass
class BuildResult:
    la_l: float
    la_b: float
    la_h: float  # verwendete Außenmaße
    li_l: float
    li_b: float
    li_h: float  # resultierende Innenmaße
    layers: List[LayerResult]


def compute_plate_dimensions(
    t_list: List[float],
    dims_type: Literal["outer", "inner"],
    L: float,
    B: float,
    H: float,
) -> BuildResult:
    """
    Berechnet die Plattenmaße (L,B,H) für jede Schicht i = 1..n um einen Quader.

    Vorgaben:
      - Oben/Unten (Top/Bottom):  L = la_l - 2*sum_{k < i}(t_k), B = la_b - 2*sum_{k < i}(t_k), H = t_i
      - Vorne/Hinten (Front/Back):L = la_h - 2*sum_{k <= i}(t_k), B = la_b - 2*sum_{k < i}(t_k), H = t_i
      - Rechts/Links (Right/Left):L = la_l - 2*sum_{k <= i}(t_k), B = la_h - 2*sum_{k <= i}(t_k), H = t_i

    Parameter:
      t_list   : Liste der Schichtdicken [t1, t2, ..., tn]
      dims_type: "outer" => L,B,H sind Außenmaße (la_l, la_b, la_h)
                 "inner" => L,B,H sind Innenmaße (li_l, li_b, li_h)
      L,B,H    : Länge, Breite, Höhe (je nach dims_type als Außen- bzw. Innenmaß)

    Rückgabe:
      BuildResult mit verwendeten Außen-/Innenmaßen und Plattenlisten je Schicht.

    Annahmen:
      - Alle Dicken >= 0
      - Wenn Innenmaße übergeben wurden, gilt: Innenmaß + 2*sum(t) = Außenmaß.
    """

    if any(t < 0 for t in t_list):
        raise ValueError("Alle Schichtdicken müssen ≥ 0 sein.")

    T = sum(t_list)

    if dims_type == "outer":
        la_l, la_b, la_h = float(L), float(B), float(H)
        li_l, li_b, li_h = la_l - 2 * T, la_b - 2 * T, la_h - 2 * T
        if min(li_l, li_b, li_h) <= 0:
            raise ValueError(
                "Innenmaß würde ≤ 0 werden. Außenmaße zu klein für die Summe der Dicken."
            )
    elif dims_type == "inner":
        li_l, li_b, li_h = float(L), float(B), float(H)
        la_l, la_b, la_h = li_l + 2 * T, li_b + 2 * T, li_h + 2 * T
    else:
        raise ValueError("dims_type muss 'outer' oder 'inner' sein.")

    layers_out: List[LayerResult] = []
    t_cum_prev = 0.0  # sum_{k < i} t_k

    for i, t_i in enumerate(t_list, start=1):
        t_cum_curr = t_cum_prev + t_i  # sum_{k <= i} t_k

        # Oben / Unten:
        top_bottom_L = la_l - 2 * t_cum_prev
        top_bottom_B = la_b - 2 * t_cum_prev
        # Vorne / Hinten:
        front_back_L = la_h - 2 * t_cum_curr
        front_back_B = la_b - 2 * t_cum_prev
        # Rechts / Links:
        right_left_L = la_l - 2 * t_cum_curr
        right_left_B = la_h - 2 * t_cum_curr

        # Validierungen (keine negativen/Null-Abmessungen für Platten)
        dims_to_check: List[Tuple[str, float]] = [
            ("Top/Bottom L", top_bottom_L),
            ("Top/Bottom B", top_bottom_B),
            ("Front/Back L", front_back_L),
            ("Front/Back B", front_back_B),
            ("Right/Left L", right_left_L),
            ("Right/Left B", right_left_B),
        ]
        for label, val in dims_to_check:
            if val <= 0:
                raise ValueError(
                    f"Nichtpositive Plattengröße in Schicht {i} ({label} = {val}). "
                    "Prüfe Außen-/Innenmaße und Schichtdicken."
                )

        plates = [
            Plate("Oben", top_bottom_L, top_bottom_B, t_i),
            Plate("Unten", top_bottom_L, top_bottom_B, t_i),
            Plate("Vorne", front_back_L, front_back_B, t_i),
            Plate("Hinten", front_back_L, front_back_B, t_i),
            Plate("Rechts", right_left_L, right_left_B, t_i),
            Plate("Links", right_left_L, right_left_B, t_i),
        ]
        layers_out.append(LayerResult(i, t_i, plates))
        t_cum_prev = t_cum_curr

    return BuildResult(la_l, la_b, la_h, li_l, li_b, li_h, layers_out)

