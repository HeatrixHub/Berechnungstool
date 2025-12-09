"""
database.py
Verwaltet alle Projekt- und Material-Operationen in einer zentralen SQLite-Datenbank.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .models import (
    Material,
    MaterialMeasurement,
    MaterialVariant,
    Project,
    ProjectLayer,
    ProjectResult,
)

DB_PATH = "heatrix.db"
LEGACY_PROJECT_DB = "projects.db"
LEGACY_MATERIAL_DB = "heatrix_data.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema_meta(conn: sqlite3.Connection) -> int:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    row = conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_meta (id, version) VALUES (1, 0)")
        conn.commit()
        return 0
    return int(row["version"])


def _migration_1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            T_left REAL NOT NULL,
            T_inf REAL NOT NULL,
            h REAL NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            classification_temp REAL,
            density REAL,
            length REAL,
            width REAL,
            height REAL,
            price REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS material_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            temperature REAL NOT NULL,
            conductivity REAL NOT NULL,
            FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE,
            UNIQUE(material_id, temperature)
        );

        CREATE TABLE IF NOT EXISTS project_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            thickness REAL NOT NULL,
            custom_name TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE RESTRICT,
            UNIQUE(project_id, order_index)
        );

        CREATE TABLE IF NOT EXISTS project_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            version_label TEXT NOT NULL DEFAULT 'latest',
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, version_label)
        );

        CREATE INDEX IF NOT EXISTS idx_project_layers_project ON project_layers(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_layers_material ON project_layers(material_id);
        CREATE INDEX IF NOT EXISTS idx_project_results_project ON project_results(project_id);
        CREATE INDEX IF NOT EXISTS idx_measurements_material ON material_measurements(material_id);
        """
    )


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing_columns:
        # definition must include both column name and type, because SQLite's ALTER TABLE
        # syntax requires the full column definition. Passing only the type ("REAL") would
        # try to create a column literally named after the type and raise a duplicate
        # column error on subsequent runs.
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migration_2(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "materials", "length", "REAL")
    _add_column_if_missing(conn, "materials", "width", "REAL")
    _add_column_if_missing(conn, "materials", "height", "REAL")
    _add_column_if_missing(conn, "materials", "price", "REAL")


def _migration_3(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_layers_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            thickness REAL NOT NULL,
            custom_name TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE,
            UNIQUE(project_id, order_index)
        );

        INSERT INTO project_layers_new (project_id, material_id, order_index, thickness, custom_name)
        SELECT project_id, material_id, order_index, thickness, custom_name FROM project_layers;

        DROP TABLE project_layers;
        ALTER TABLE project_layers_new RENAME TO project_layers;

        CREATE INDEX IF NOT EXISTS idx_project_layers_project ON project_layers(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_layers_material ON project_layers(material_id);
        """
    )


def _migration_4(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS material_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            thickness REAL NOT NULL,
            length REAL,
            width REAL,
            height REAL,
            price REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE,
            UNIQUE(material_id, name)
        );

        CREATE INDEX IF NOT EXISTS idx_material_variants_material ON material_variants(material_id);
        """
    )

    rows = conn.execute(
        "SELECT id, name, length, width, height, price FROM materials"
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO material_variants (
                material_id, name, thickness, length, width, height, price
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                "Standard",
                row["height"] if row["height"] is not None else 0.0,
                row["length"],
                row["width"],
                row["height"],
                row["price"],
            ),
        )


MIGRATIONS: Sequence[Tuple[int, Any]] = [
    (1, _migration_1),
    (2, _migration_2),
    (3, _migration_3),
    (4, _migration_4),
]


def _run_migrations() -> None:
    with _get_connection() as conn:
        current_version = _ensure_schema_meta(conn)
        for version, migration in MIGRATIONS:
            if version > current_version:
                migration(conn)
                conn.execute("UPDATE schema_meta SET version = ? WHERE id = 1", (version,))
                conn.commit()
                current_version = version


def _migrate_legacy_data() -> None:
    with _get_connection() as conn:
        _migrate_legacy_projects(conn)
        _migrate_legacy_materials(conn)


def _migrate_legacy_projects(conn: sqlite3.Connection) -> None:
    legacy_path = Path(LEGACY_PROJECT_DB)
    if not legacy_path.exists():
        return
    existing = conn.execute("SELECT COUNT(1) FROM projects").fetchone()[0]
    if existing:
        return
    legacy_conn = sqlite3.connect(str(legacy_path))
    legacy_conn.row_factory = sqlite3.Row
    try:
        rows = legacy_conn.execute(
            "SELECT name, thicknesses, isolierungen, T_left, T_inf, h, result FROM projects"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = legacy_conn.execute(
            "SELECT name, thicknesses, '' AS isolierungen, T_left, T_inf, h, result FROM projects"
        ).fetchall()
    for row in rows:
        try:
            thicknesses = json.loads(row["thicknesses"]) if row["thicknesses"] else []
        except json.JSONDecodeError:
            thicknesses = []
        isolierungen_raw = row["isolierungen"]
        isolierungen: List[str]
        if isolierungen_raw:
            try:
                isolierungen = json.loads(isolierungen_raw)
            except json.JSONDecodeError:
                isolierungen = []
        else:
            isolierungen = [f"Schicht {i+1}" for i in range(len(thicknesses))]
        result_raw = row["result"]
        try:
            result = json.loads(result_raw) if result_raw else {}
        except json.JSONDecodeError:
            result = {}
        _persist_project(
            conn,
            name=row["name"],
            thicknesses=thicknesses,
            isolierungen=isolierungen,
            T_left=row["T_left"],
            T_inf=row["T_inf"],
            h=row["h"],
            result=result,
            version_label="legacy",
        )
    legacy_conn.close()


def _migrate_legacy_materials(conn: sqlite3.Connection) -> None:
    legacy_path = Path(LEGACY_MATERIAL_DB)
    if not legacy_path.exists():
        return
    existing = conn.execute("SELECT COUNT(1) FROM materials").fetchone()[0]
    if existing:
        return
    legacy_conn = sqlite3.connect(str(legacy_path))
    legacy_conn.row_factory = sqlite3.Row
    try:
        rows = legacy_conn.execute(
            "SELECT name, classification_temp, density, temps, ks FROM insulations"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        temps = _safe_load_json(row["temps"]) if row["temps"] else []
        ks = _safe_load_json(row["ks"]) if row["ks"] else []
        _persist_material(
            conn,
            name=row["name"],
            classification_temp=row["classification_temp"],
            density=row["density"],
            length=None,
            width=None,
            height=None,
            price=None,
            temps=temps,
            ks=ks,
        )
    legacy_conn.close()


def _safe_load_json(payload: str) -> List[float]:
    try:
        data = json.loads(payload)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _normalize_material_name(name: str, fallback_index: int | None = None) -> str:
    normalized = (name or "").strip()
    if normalized:
        return normalized
    if fallback_index is not None:
        return f"Schicht {fallback_index + 1}"
    return "Unbenannte Isolierung"


def _ensure_material(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM materials WHERE name = ?", (name,)).fetchone()
    if row:
        return int(row["id"])
    conn.execute("INSERT INTO materials (name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM materials WHERE name = ?", (name,)).fetchone()
    if not row:
        raise RuntimeError(f"Material '{name}' konnte nicht erstellt werden.")
    return int(row["id"])


def _persist_project(
    conn: sqlite3.Connection,
    *,
    name: str,
    thicknesses: Sequence[float],
    isolierungen: Sequence[str],
    T_left: float,
    T_inf: float,
    h: float,
    result: Optional[Dict] = None,
    created_by: Optional[str] = None,
    version_label: str = "latest",
) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO projects (name, T_left, T_inf, h, created_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            T_left = excluded.T_left,
            T_inf = excluded.T_inf,
            h = excluded.h,
            created_by = COALESCE(excluded.created_by, projects.created_by),
            updated_at = CURRENT_TIMESTAMP
        """,
        (name, float(T_left), float(T_inf), float(h), created_by),
    )
    project_id = cursor.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()["id"]
    cursor.execute("DELETE FROM project_layers WHERE project_id = ?", (project_id,))
    for idx, thickness in enumerate(thicknesses):
        material_name = _normalize_material_name(
            isolierungen[idx] if idx < len(isolierungen) else "",
            fallback_index=idx,
        )
        material_id = _ensure_material(conn, material_name)
        cursor.execute(
            """
            INSERT INTO project_layers (project_id, material_id, order_index, thickness, custom_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                material_id,
                idx,
                float(thickness),
                material_name,
            ),
        )
    cursor.execute(
        "DELETE FROM project_results WHERE project_id = ? AND version_label = ?",
        (project_id, version_label),
    )
    if result is not None:
        cursor.execute(
            """
            INSERT INTO project_results (project_id, version_label, data)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id, version_label) DO UPDATE SET
                data = excluded.data,
                created_at = CURRENT_TIMESTAMP
            """,
            (project_id, version_label, json.dumps(result)),
        )
    conn.commit()
    return True


def _persist_material(
    conn: sqlite3.Connection,
    *,
    name: str,
    classification_temp: Optional[float],
    density: Optional[float],
    temps: Sequence[float],
    ks: Sequence[float],
) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO materials (name, classification_temp, density)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            classification_temp = excluded.classification_temp,
            density = excluded.density,
            updated_at = CURRENT_TIMESTAMP
        """,
        (name, classification_temp, density),
    )
    material_id = cursor.execute("SELECT id FROM materials WHERE name = ?", (name,)).fetchone()["id"]
    cursor.execute("DELETE FROM material_measurements WHERE material_id = ?", (material_id,))
    ordered_pairs = sorted(zip(temps, ks), key=lambda pair: pair[0])
    for temp, k_val in ordered_pairs:
        cursor.execute(
            "INSERT INTO material_measurements (material_id, temperature, conductivity) VALUES (?, ?, ?)",
            (material_id, float(temp), float(k_val)),
        )
    conn.commit()
    return True


def save_project(
    name: str,
    thicknesses: Sequence[float],
    isolierungen: Sequence[str],
    T_left: float,
    T_inf: float,
    h: float,
    result: Optional[Dict],
    *,
    created_by: Optional[str] = None,
    version_label: str = "latest",
) -> bool:
    """Speichert oder aktualisiert ein Projekt inkl. Schichten und Ergebnis."""

    try:
        with _get_connection() as conn:
            return _persist_project(
                conn,
                name=name,
                thicknesses=thicknesses,
                isolierungen=isolierungen,
                T_left=T_left,
                T_inf=T_inf,
                h=h,
                result=result,
                created_by=created_by,
                version_label=version_label,
            )
    except Exception as exc:
        print(f"[DB] Fehler beim Speichern von '{name}': {exc}")
        return False


def load_project(name: str) -> Optional[Project]:
    """Lädt ein Projekt mit allen Schichten und dem aktuellsten Ergebnis."""

    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            if not row:
                return None
            layers_rows = conn.execute(
                """
                SELECT l.order_index, l.thickness, COALESCE(m.name, l.custom_name) AS material_name
                FROM project_layers l
                LEFT JOIN materials m ON m.id = l.material_id
                WHERE l.project_id = ?
                ORDER BY l.order_index ASC
                """,
                (row["id"],),
            ).fetchall()
            thicknesses = [float(layer["thickness"]) for layer in layers_rows]
            isolierungen = [layer["material_name"] for layer in layers_rows]
            result_row = conn.execute(
                """
                SELECT version_label, data, created_at
                FROM project_results
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            project_result = None
            if result_row:
                try:
                    result_data = json.loads(result_row["data"])
                except json.JSONDecodeError:
                    result_data = {}
                project_result = ProjectResult(
                    version_label=result_row["version_label"],
                    data=result_data,
                    created_at=result_row["created_at"],
                )
            project = Project(
                name=row["name"],
                thicknesses=thicknesses,
                isolierungen=isolierungen,
                T_left=row["T_left"],
                T_inf=row["T_inf"],
                h=row["h"],
                result=project_result.data if project_result else {},
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
                layers=[
                    ProjectLayer(layer["order_index"], float(layer["thickness"]), layer["material_name"])
                    for layer in layers_rows
                ],
                result_meta=project_result,
            )
            return project
    except Exception as exc:
        print(f"[DB] Fehler beim Laden von '{name}': {exc}")
        return None


def delete_project(name: str) -> bool:
    try:
        with _get_connection() as conn:
            cur = conn.execute("DELETE FROM projects WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
    except Exception as exc:
        print(f"[DB] Fehler beim Löschen von '{name}': {exc}")
        return False


def get_all_project_names() -> List[str]:
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM projects ORDER BY name COLLATE NOCASE ASC"
            ).fetchall()
            return [row["name"] for row in rows]
    except Exception as exc:
        print(f"[DB] Fehler beim Abrufen der Projektnamen: {exc}")
        return []


def list_projects_overview() -> List[Dict[str, Any]]:
    """Liefert eine Übersichtsliste aller Projekte inkl. Metadaten."""

    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.name,
                    p.T_left,
                    p.T_inf,
                    p.h,
                    p.created_at,
                    p.updated_at,
                    COUNT(l.id) AS layer_count
                FROM projects p
                LEFT JOIN project_layers l ON l.project_id = p.id
                GROUP BY p.id
                ORDER BY p.name COLLATE NOCASE
                """
            ).fetchall()
            return [
                {
                    "name": row["name"],
                    "T_left": row["T_left"],
                    "T_inf": row["T_inf"],
                    "h": row["h"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "layer_count": row["layer_count"],
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"[DB] Fehler beim Abrufen der Projektübersicht: {exc}")
        return []


def _load_variants_for_materials(
    conn: sqlite3.Connection, material_ids: Sequence[int]
) -> Dict[int, List[MaterialVariant]]:
    if not material_ids:
        return {}
    placeholders = ",".join(["?"] * len(material_ids))
    rows = conn.execute(
        f"""
        SELECT material_id, name, thickness, length, width, height, price
        FROM material_variants
        WHERE material_id IN ({placeholders})
        ORDER BY thickness ASC
        """,
        list(material_ids),
    ).fetchall()
    variants: Dict[int, List[MaterialVariant]] = {}
    for row in rows:
        variants.setdefault(row["material_id"], []).append(
            MaterialVariant(
                name=row["name"],
                thickness=row["thickness"],
                length=row["length"],
                width=row["width"],
                height=row["height"],
                price=row["price"],
            )
        )
    return variants


def list_materials() -> List[Material]:
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.id,
                    m.name,
                    m.classification_temp,
                    m.density,
                    m.created_at,
                    m.updated_at
                FROM materials m
                ORDER BY m.name COLLATE NOCASE
                """
            ).fetchall()
            variants = _load_variants_for_materials(conn, [row["id"] for row in rows])
            return [
                Material(
                    name=row["name"],
                    classification_temp=row["classification_temp"],
                    density=row["density"],
                    variants=variants.get(row["id"], []),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
    except Exception as exc:
        print(f"[DB] Fehler beim Abrufen der Materialien: {exc}")
        return []


def load_material(name: str) -> Optional[Material]:
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM materials WHERE name = ?",
                (name,),
            ).fetchone()
            if not row:
                return None
            variants = _load_variants_for_materials(conn, [row["id"]]).get(
                row["id"], []
            )
            measurement_rows = conn.execute(
                "SELECT temperature, conductivity FROM material_measurements WHERE material_id = ? ORDER BY temperature ASC",
                (row["id"],),
            ).fetchall()
            measurements = [
                MaterialMeasurement(temperature=m["temperature"], conductivity=m["conductivity"])
                for m in measurement_rows
            ]
            return Material(
                name=row["name"],
                classification_temp=row["classification_temp"],
                density=row["density"],
                variants=variants,
                measurements=measurements,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
    except Exception as exc:
        print(f"[DB] Fehler beim Laden des Materials '{name}': {exc}")
        return None


def save_material_family(
    name: str,
    classification_temp: Optional[float],
    density: Optional[float],
    temps: Sequence[float],
    ks: Sequence[float],
) -> bool:
    try:
        with _get_connection() as conn:
            return _persist_material(
                conn,
                name=name,
                classification_temp=classification_temp,
                density=density,
                temps=temps,
                ks=ks,
            )
    except Exception as exc:
        print(f"[DB] Fehler beim Speichern der Materialfamilie '{name}': {exc}")
        return False


def save_material_variant(
    material_name: str,
    variant_name: str,
    thickness: float,
    length: Optional[float],
    width: Optional[float],
    height: Optional[float],
    price: Optional[float],
) -> bool:
    try:
        with _get_connection() as conn:
            cursor = conn.execute("SELECT id FROM materials WHERE name = ?", (material_name,))
            row = cursor.fetchone()
            if not row:
                return False
            conn.execute(
                """
                INSERT INTO material_variants (
                    material_id, name, thickness, length, width, height, price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(material_id, name) DO UPDATE SET
                    thickness=excluded.thickness,
                    length=excluded.length,
                    width=excluded.width,
                    height=excluded.height,
                    price=excluded.price,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    row["id"],
                    variant_name,
                    thickness,
                    length,
                    width,
                    height,
                    price,
                ),
            )
            conn.commit()
            return True
    except Exception as exc:
        print(f"[DB] Fehler beim Speichern der Variante '{variant_name}': {exc}")
        return False


def delete_material(name: str) -> bool:
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id FROM materials WHERE name = ?", (name,),
            ).fetchone()
            if not row:
                return False

            cursor.execute("DELETE FROM materials WHERE id = ?", (row["id"],))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as exc:
        print(f"[DB] Fehler beim Löschen der Isolierung '{name}': {exc}")
        return False


def delete_material_variant(material_name: str, variant_name: str) -> bool:
    try:
        with _get_connection() as conn:
            material_row = conn.execute(
                "SELECT id FROM materials WHERE name = ?", (material_name,)
            ).fetchone()
            if not material_row:
                return False
            cursor = conn.execute(
                "DELETE FROM material_variants WHERE material_id = ? AND name = ?",
                (material_row["id"], variant_name),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as exc:
        print(f"[DB] Fehler beim Löschen der Variante '{variant_name}': {exc}")
        return False


_run_migrations()
_migrate_legacy_data()
