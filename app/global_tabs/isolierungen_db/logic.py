"""
Gemeinsame Logik für die Verwaltung von Isolierungen.
Ermöglicht das Speichern, Laden, Bearbeiten und Löschen von Isolierungen
sowie die Interpolation der Wärmeleitfähigkeit.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import csv
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import numpy as np

from Isolierung.core.database import (
    delete_material,
    list_materials,
    load_material,
    save_material,
)


def get_all_insulations() -> List[Dict]:
    materials = list_materials()
    return [
        {
            "name": material.name,
            "classification_temp": material.classification_temp,
            "density": material.density,
            "length": material.length,
            "width": material.width,
            "height": material.height,
            "price": material.price,
        }
        for material in materials
    ]


def load_insulation(name: str) -> Dict:
    material = load_material(name)
    if not material:
        return {}
    return material.to_dict(include_measurements=True)


def save_insulation(
    name: str,
    classification_temp: float,
    density: float,
    length: float | None,
    width: float | None,
    height: float | None,
    price: float | None,
    temps: List[float],
    ks: List[float],
):
    return save_material(
        name,
        classification_temp,
        density,
        length,
        width,
        height,
        price,
        temps,
        ks,
    )


def delete_insulation(name: str):
    return delete_material(name)


def interpolate_k(temps: List[float], ks: List[float], x_range: np.ndarray):
    """
    Interpoliert/approximiert Wärmeleitfähigkeit k(T) über x_range.
    - >=3 Messpunkte: quadratische Anpassung (Polyfit deg=2)
    - 2 Messpunkte: lineare Anpassung
    - 1 Messpunkt: konstante k
    Rückgabe: np.ndarray mit k-Werten für x_range (gleiche Länge)
    """
    if len(temps) == 0 or len(ks) == 0:
        raise ValueError("Keine Temperatur- oder k-Werte übergeben.")

    temps_arr = np.array(temps, dtype=float)
    ks_arr = np.array(ks, dtype=float)
    order = np.argsort(temps_arr)
    temps_arr = temps_arr[order]
    ks_arr = ks_arr[order]

    unique_temps: List[float] = []
    unique_ks: List[float] = []
    i = 0
    n = len(temps_arr)
    while i < n:
        t = temps_arr[i]
        same_idx = np.where(np.isclose(temps_arr, t))[0]
        same_idx = same_idx[same_idx >= i]
        if same_idx.size > 1:
            mean_k = float(np.mean(ks_arr[same_idx]))
            unique_temps.append(float(t))
            unique_ks.append(mean_k)
            i = int(same_idx[-1] + 1)
        else:
            unique_temps.append(float(t))
            unique_ks.append(float(ks_arr[i]))
            i += 1

    temps_u = np.array(unique_temps)
    ks_u = np.array(unique_ks)

    if temps_u.size >= 3:
        coeffs = np.polyfit(temps_u, ks_u, 2)
        k_fit = np.polyval(coeffs, x_range)
    elif temps_u.size == 2:
        coeffs = np.polyfit(temps_u, ks_u, 1)
        k_fit = np.polyval(coeffs, x_range)
    else:
        k_fit = np.full_like(x_range, ks_u[0], dtype=float)

    return k_fit


CSV_HEADERS = [
    "name",
    "classification_temp",
    "density",
    "length",
    "width",
    "height",
    "price",
    "temps",
    "ks",
]

REQUIRED_HEADERS = {"name", "temps", "ks"}


@dataclass
class FileImportResult:
    file_path: str
    imported: int
    errors: List[str]
    skipped_reason: str | None = None


def export_insulations_to_csv(names: List[str], file_path: str) -> Tuple[int, List[str]]:
    """Exportiert ausgewählte Isolierungen in eine einzige CSV-Datei.

    Returns:
        Tuple[int, List[str]]: Anzahl erfolgreich exportierter Datensätze und Namen,
        die nicht geladen werden konnten.
    """

    failed: List[str] = []
    exported = 0
    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for name in names:
            row = _build_insulation_row(name)
            if row is None:
                failed.append(name)
                continue
            writer.writerow(row)
            exported += 1
    return exported, failed


def export_insulations_to_folder(
    names: List[str], target_directory: str
) -> Tuple[int, List[str], str]:
    """Exportiert mehrere Isolierungen als einzelne CSV-Dateien in einem neuen Ordner."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(target_directory)
    export_dir = base_dir / f"isolierungen_export_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=False)

    failed: List[str] = []
    exported = 0
    used_names: set[str] = set()

    for name in names:
        row = _build_insulation_row(name)
        if row is None:
            failed.append(name)
            continue

        safe_name = _sanitize_filename(name)
        candidate = safe_name
        counter = 1
        while candidate in used_names or (export_dir / f"{candidate}.csv").exists():
            candidate = f"{safe_name}_{counter}"
            counter += 1
        used_names.add(candidate)

        file_path = export_dir / f"{candidate}.csv"
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerow(row)
        exported += 1

    return exported, failed, str(export_dir)


def import_insulations_from_csv_files(
    file_paths: List[str],
) -> Tuple[int, List[FileImportResult]]:
    """Importiert Isolierungen aus mehreren CSV-Dateien.

    Jeder Dateipfad wird einzeln validiert (Encoding, Kopfzeilen, Pflichtfelder).
    Bei Dateifehlern wird die Datei übersprungen, gültige Dateien werden Zeile für
    Zeile verarbeitet. Pro Zeile wird entweder ein vollständiger Datensatz
    gespeichert oder verworfen.

    Returns:
        Gesamtzahl importierter Datensätze und eine Liste mit Dateiergebnissen.
    """

    existing_names = {material.name for material in list_materials()}
    results: List[FileImportResult] = []
    total_imported = 0

    for file_path in file_paths:
        imported = 0
        errors: List[str] = []

        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                validation_error = _validate_csv_headers(reader.fieldnames)
                if validation_error:
                    results.append(
                        FileImportResult(
                            file_path=file_path,
                            imported=0,
                            errors=[],
                            skipped_reason=validation_error,
                        )
                    )
                    continue

                for idx, row in enumerate(reader, start=2):
                    base_name = (row.get("name") or "").strip()
                    try:
                        _ensure_required_fields(base_name)
                        class_temp = _parse_optional_float(
                            row.get("classification_temp")
                        )
                        density = _parse_optional_float(row.get("density"))
                        length = _parse_optional_float(row.get("length"))
                        width = _parse_optional_float(row.get("width"))
                        height = _parse_optional_float(row.get("height"))
                        price = _parse_optional_float(row.get("price"))
                        temps = _parse_numeric_list(row.get("temps", ""))
                        ks = _parse_numeric_list(row.get("ks", ""))
                        if len(temps) != len(ks):
                            raise ValueError(
                                "Temperatur- und k-Liste müssen gleich lang sein."
                            )

                        name = _generate_unique_name(base_name, existing_names)
                        saved = save_insulation(
                            name,
                            class_temp if class_temp is not None else 0.0,
                            density if density is not None else 0.0,
                            length,
                            width,
                            height,
                            price,
                            temps,
                            ks,
                        )
                        if not saved:
                            raise ValueError("Speichern fehlgeschlagen.")
                        imported += 1
                    except Exception as exc:  # pragma: no cover - Laufzeitvalidierung
                        display_name = base_name or "<unbenannt>"
                        errors.append(f"Zeile {idx} ({display_name}): {exc}")

        except UnicodeDecodeError as exc:
            results.append(
                FileImportResult(
                    file_path=file_path,
                    imported=0,
                    errors=[],
                    skipped_reason=f"Ungültiges Encoding: {exc}",
                )
            )
            continue
        except Exception as exc:
            results.append(
                FileImportResult(
                    file_path=file_path,
                    imported=0,
                    errors=[],
                    skipped_reason=f"Datei konnte nicht gelesen werden: {exc}",
                )
            )
            continue

        total_imported += imported
        results.append(
            FileImportResult(
                file_path=file_path, imported=imported, errors=errors, skipped_reason=None
            )
        )

    return total_imported, results


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return float(cleaned)


def _parse_numeric_list(value: str) -> List[float]:
    cleaned = (value or "").strip()
    if not cleaned:
        return []
    return [float(item.strip()) for item in cleaned.split(";") if item.strip()]


def _ensure_required_fields(name: str) -> None:
    if not name:
        raise ValueError("Pflichtfeld 'name' fehlt.")


def _validate_csv_headers(headers: List[str] | None) -> str | None:
    if not headers:
        return "Datei enthält keine Kopfzeile."
    missing = REQUIRED_HEADERS.difference({header.strip() for header in headers})
    if missing:
        return f"Pflichtspalten fehlen: {', '.join(sorted(missing))}"
    unexpected = [h for h in headers if h not in CSV_HEADERS]
    if unexpected:
        return "Unbekannte Spalten gefunden. Bitte Schema prüfen."
    return None


def _generate_unique_name(base_name: str, used_names: set[str]) -> str:
    name = base_name
    counter = 1
    while name in used_names:
        name = f"{base_name} ({counter})"
        counter += 1
    used_names.add(name)
    return name


def _build_insulation_row(name: str) -> Dict[str, str | float] | None:
    data = load_insulation(name)
    if not data:
        return None
    return {
        "name": data.get("name", ""),
        "classification_temp": data.get("classification_temp"),
        "density": data.get("density"),
        "length": data.get("length"),
        "width": data.get("width"),
        "height": data.get("height"),
        "price": data.get("price"),
        "temps": ";".join(map(str, data.get("temps", []))),
        "ks": ";".join(map(str, data.get("ks", []))),
    }


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/]+", "_", name).strip()
    cleaned = re.sub(r"[^A-Za-z0-9 _.-]", "_", cleaned)
    cleaned = cleaned or "isolierung"
    return cleaned
