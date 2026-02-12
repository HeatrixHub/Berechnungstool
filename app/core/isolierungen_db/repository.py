"""SQLite repository for insulation family management."""
from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from typing import Any, Iterator

from Isolierung.core.database import DB_PATH

SCHEMA_VERSION = 1


class IsolierungRepository:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        self._ensure_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS isolierung_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT value FROM isolierung_meta WHERE key = 'schema_version'"
            ).fetchone()
            current_version = int(row["value"]) if row else None
            if current_version != SCHEMA_VERSION:
                self._reset_schema(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO isolierung_meta (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            conn.commit()

    def _reset_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP TABLE IF EXISTS isolierung_measurements;
            DROP TABLE IF EXISTS isolierung_variants;
            DROP TABLE IF EXISTS isolierung_families;

            CREATE TABLE isolierung_families (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                classification_temp REAL NOT NULL,
                density REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE isolierung_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                thickness REAL NOT NULL CHECK(thickness > 0),
                length REAL,
                width REAL,
                price REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(family_id, name),
                FOREIGN KEY(family_id) REFERENCES isolierung_families(id) ON DELETE CASCADE
            );

            CREATE TABLE isolierung_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                temperature REAL NOT NULL,
                conductivity REAL NOT NULL CHECK(conductivity > 0),
                UNIQUE(family_id, position),
                FOREIGN KEY(family_id) REFERENCES isolierung_families(id) ON DELETE CASCADE
            );

            CREATE INDEX idx_isolierung_family_name ON isolierung_families(name);
            CREATE INDEX idx_isolierung_variants_family ON isolierung_variants(family_id);
            CREATE INDEX idx_isolierung_measurements_family ON isolierung_measurements(family_id);
            """
        )

    def list_families(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.name, f.classification_temp, f.density,
                       COUNT(v.id) AS variant_count
                FROM isolierung_families f
                LEFT JOIN isolierung_variants v ON v.family_id = f.id
                GROUP BY f.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_family(self, family_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            family = conn.execute(
                "SELECT * FROM isolierung_families WHERE id = ?", (family_id,)
            ).fetchone()
            if family is None:
                return None
            measurements = conn.execute(
                """
                SELECT temperature, conductivity
                FROM isolierung_measurements
                WHERE family_id = ?
                ORDER BY position ASC
                """,
                (family_id,),
            ).fetchall()
            variants = conn.execute(
                """
                SELECT id, name, thickness, length, width, price
                FROM isolierung_variants
                WHERE family_id = ?
                ORDER BY name COLLATE NOCASE ASC
                """,
                (family_id,),
            ).fetchall()
            return {
                "id": family["id"],
                "name": family["name"],
                "classification_temp": family["classification_temp"],
                "density": family["density"],
                "temps": [row["temperature"] for row in measurements],
                "ks": [row["conductivity"] for row in measurements],
                "variants": [dict(row) for row in variants],
            }

    def get_family_by_name(self, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM isolierung_families WHERE name = ?", (name,)
            ).fetchone()
        return self.get_family(int(row["id"])) if row else None

    def create_family(
        self, name: str, classification_temp: float, density: float, temps: list[float], ks: list[float]
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO isolierung_families (name, classification_temp, density)
                VALUES (?, ?, ?)
                """,
                (name, classification_temp, density),
            )
            family_id = int(cursor.lastrowid)
            self._replace_measurements(conn, family_id, temps, ks)
            conn.commit()
            return family_id

    def update_family(
        self, family_id: int, name: str, classification_temp: float, density: float, temps: list[float], ks: list[float]
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE isolierung_families
                SET name = ?, classification_temp = ?, density = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, classification_temp, density, family_id),
            )
            self._replace_measurements(conn, family_id, temps, ks)
            conn.commit()

    def _replace_measurements(
        self, conn: sqlite3.Connection, family_id: int, temps: list[float], ks: list[float]
    ) -> None:
        conn.execute("DELETE FROM isolierung_measurements WHERE family_id = ?", (family_id,))
        if not temps:
            return
        conn.executemany(
            """
            INSERT INTO isolierung_measurements (family_id, position, temperature, conductivity)
            VALUES (?, ?, ?, ?)
            """,
            [(family_id, idx, float(temp), float(k)) for idx, (temp, k) in enumerate(zip(temps, ks))],
        )

    def delete_family(self, family_id: int) -> bool:
        with self._connect() as conn:
            result = conn.execute("DELETE FROM isolierung_families WHERE id = ?", (family_id,))
            conn.commit()
            return result.rowcount > 0

    def create_variant(
        self,
        family_id: int,
        name: str,
        thickness: float,
        length: float | None,
        width: float | None,
        price: float | None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO isolierung_variants (family_id, name, thickness, length, width, price)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (family_id, name, thickness, length, width, price),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_variant(
        self,
        variant_id: int,
        name: str,
        thickness: float,
        length: float | None,
        width: float | None,
        price: float | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE isolierung_variants
                SET name = ?, thickness = ?, length = ?, width = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, thickness, length, width, price, variant_id),
            )
            conn.commit()

    def delete_variant(self, variant_id: int) -> bool:
        with self._connect() as conn:
            result = conn.execute("DELETE FROM isolierung_variants WHERE id = ?", (variant_id,))
            conn.commit()
            return result.rowcount > 0
