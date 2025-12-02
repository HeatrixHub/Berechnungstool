"""Hilfsfunktionen für PDF-Berichte des Isolierungs-Plugins."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Dict, List

import matplotlib

# Für headless Rendering des Diagramms
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  - nach Backend-Wahl importieren


def _build_layer_summaries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    thicknesses = state.get("thicknesses", []) or []
    isolierungen = state.get("isolierungen", []) or []
    result = state.get("result", {}) or {}
    interfaces = result.get("interface_temperatures", []) or []
    averages = result.get("T_avg", []) or []
    k_final = result.get("k_final", []) or []

    layers: List[Dict[str, Any]] = []
    for index, thickness in enumerate(thicknesses):
        layers.append(
            {
                "index": index + 1,
                "name": isolierungen[index] if index < len(isolierungen) else "",
                "thickness_mm": thickness,
                "T_left": interfaces[index] if index < len(interfaces) else None,
                "T_right": interfaces[index + 1]
                if index + 1 < len(interfaces)
                else None,
                "T_mean": averages[index] if index < len(averages) else None,
                "k_mean": k_final[index] if index < len(k_final) else None,
            }
        )
    return layers


def _create_temperature_plot(
    thicknesses: List[float], temperatures: List[float]
) -> str | None:
    if not thicknesses or not temperatures or len(temperatures) < 2:
        return None

    cumulative_x = [0]
    for thickness in thicknesses:
        cumulative_x.append(cumulative_x[-1] + thickness)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    ax.plot(cumulative_x, temperatures, linewidth=2, marker="o", color="#0f172a")
    ax.fill_between(
        cumulative_x,
        temperatures,
        color="#cbd5e1",
        alpha=0.45,
        step="pre",
    )

    for x, temp in zip(cumulative_x, temperatures):
        ax.text(
            x,
            temp + 5,
            f"{temp:.1f} °C",
            ha="center",
            fontsize=9,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"),
        )

    ax.set_xlabel("Dicke [mm]")
    ax.set_ylabel("Temperatur [°C]")
    ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.55, color="#94a3b8")

    output_dir = Path(tempfile.mkdtemp(prefix="isolierung_report_"))
    output_path = output_dir / "temperature_profile.png"
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    return str(output_path)


def enrich_report_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Erweitert den Plugin-Zustand um Berichts-spezifische Daten."""

    enriched: Dict[str, Any] = dict(state)
    thicknesses = state.get("thicknesses", []) or []
    result = state.get("result", {}) or {}
    interface_temperatures = result.get("interface_temperatures", []) or []

    layer_summaries = _build_layer_summaries(state)
    temperature_plot = _create_temperature_plot(thicknesses, interface_temperatures)

    enriched["report"] = {
        "layers": layer_summaries,
        "temperature_plot": temperature_plot,
        "has_result": bool(result),
    }
    return enriched
