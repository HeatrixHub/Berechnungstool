"""SQLite repository for insulation family management."""
from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from Isolierung.core.database import DB_PATH

SCHEMA_VERSION = 2

LOGGER = logging.getLogger(__name__)


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
            current_version = self._read_schema_version(conn)
            reset_executed = False
            reset_reason: str | None = None

            try:
                if current_version is None:
                    if self._has_any_core_table(conn):
                        reset_executed = True
                        reset_reason = "Inkonsistente Meta-Information (schema_version fehlt bei vorhandenen Kern-Tabellen)."
                        LOGGER.warning("Isolierungen-DB Reset erforderlich: %s", reset_reason)
                        self._reset_schema(conn)
                    else:
                        self._reset_schema(conn)
                    self._write_schema_version(conn, SCHEMA_VERSION)
                elif current_version < SCHEMA_VERSION:
                    self.migrate_schema(conn, current_version, SCHEMA_VERSION)
                    self._write_schema_version(conn, SCHEMA_VERSION)
                elif current_version > SCHEMA_VERSION:
                    reset_executed = True
                    reset_reason = (
                        f"Nicht unterstützte schema_version={current_version} (Code unterstützt bis {SCHEMA_VERSION})."
                    )
                    LOGGER.warning("Isolierungen-DB Reset erforderlich: %s", reset_reason)
                    self._reset_schema(conn)
                    self._write_schema_version(conn, SCHEMA_VERSION)
                elif not self._is_schema_consistent(conn, current_version):
                    reset_executed = True
                    reset_reason = "Schema inkonsistent oder Kern-Tabellen fehlen."
                    LOGGER.warning("Isolierungen-DB Reset erforderlich: %s", reset_reason)
                    self._reset_schema(conn)
                    self._write_schema_version(conn, SCHEMA_VERSION)
            except sqlite3.DatabaseError as exc:
                reset_executed = True
                reset_reason = f"DB-Fehler während Schema-Check/Migration: {exc}"
                LOGGER.warning("Isolierungen-DB Reset erforderlich: %s", reset_reason)
                self._reset_schema(conn)
                self._write_schema_version(conn, SCHEMA_VERSION)

            conn.commit()
            row_counts = self._collect_row_counts(conn)
            LOGGER.info(
                "Isolierungen-DB bereit. path=%s schema_version=%s reset=%s reason=%s counts=%s",
                Path(self._db_path).resolve(),
                self._read_schema_version(conn),
                reset_executed,
                reset_reason or "-",
                row_counts,
            )

    def migrate_schema(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        current = from_version
        while current < to_version:
            next_version = current + 1
            migration = getattr(self, f"_migrate_{current}_to_{next_version}", None)
            if migration is None:
                raise sqlite3.DatabaseError(
                    f"Keine Migration von schema_version {current} nach {next_version} vorhanden."
                )
            LOGGER.info("Isolierungen-DB Migration gestartet: %s -> %s", current, next_version)
            conn.execute("BEGIN")
            try:
                migration(conn)
                self._write_schema_version(conn, next_version)
                conn.commit()
                LOGGER.info("Isolierungen-DB Migration abgeschlossen: %s -> %s", current, next_version)
            except Exception:
                conn.rollback()
                raise
            current = next_version

    def _migrate_1_to_2(self, conn: sqlite3.Connection) -> None:
        for table in ("isolierung_families", "isolierung_variants", "isolierung_measurements"):
            if not self._table_exists(conn, table):
                raise sqlite3.DatabaseError(f"Migration 1->2 nicht möglich: Tabelle '{table}' fehlt.")
        self._add_column_if_missing(conn, "isolierung_families", "max_temp", "REAL")

    def _read_schema_version(self, conn: sqlite3.Connection) -> int | None:
        row = conn.execute(
            "SELECT value FROM isolierung_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return None
        try:
            return int(row["value"])
        except (TypeError, ValueError) as exc:
            raise sqlite3.DatabaseError("Ungültige schema_version in isolierung_meta.") from exc

    def _write_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO isolierung_meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _has_any_core_table(self, conn: sqlite3.Connection) -> bool:
        return any(
            self._table_exists(conn, table)
            for table in ("isolierung_families", "isolierung_variants", "isolierung_measurements")
        )

    def _is_schema_consistent(self, conn: sqlite3.Connection, schema_version: int) -> bool:
        required_tables = ("isolierung_families", "isolierung_variants", "isolierung_measurements")
        if any(not self._table_exists(conn, table) for table in required_tables):
            return False
        if schema_version >= 2 and not self._column_exists(conn, "isolierung_families", "max_temp"):
            return False
        return True

    def _column_exists(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(row["name"] == column_name for row in rows)

    def _add_column_if_missing(
        self, conn: sqlite3.Connection, table_name: str, column_name: str, definition: str
    ) -> None:
        if not self._column_exists(conn, table_name, column_name):
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _collect_row_counts(self, conn: sqlite3.Connection) -> dict[str, int | str]:
        counts: dict[str, int | str] = {}
        for table in ("isolierung_families", "isolierung_variants", "isolierung_measurements"):
            if not self._table_exists(conn, table):
                counts[table] = "missing"
                continue
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts

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
                max_temp REAL,
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
                SELECT f.id, f.name, f.classification_temp, f.max_temp, f.density,
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
                "max_temp": family["max_temp"],
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
        self,
        name: str,
        classification_temp: float,
        max_temp: float | None,
        density: float,
        temps: list[float],
        ks: list[float],
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO isolierung_families (name, classification_temp, max_temp, density)
                VALUES (?, ?, ?, ?)
                """,
                (name, classification_temp, max_temp, density),
            )
            family_id = int(cursor.lastrowid)
            self._replace_measurements(conn, family_id, temps, ks)
            conn.commit()
            return family_id

    def update_family(
        self,
        family_id: int,
        name: str,
        classification_temp: float,
        max_temp: float | None,
        density: float,
        temps: list[float],
        ks: list[float],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE isolierung_families
                SET name = ?, classification_temp = ?, max_temp = ?, density = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, classification_temp, max_temp, density, family_id),
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
