"""
database.py
Verwaltet alle Projekt-Operationen (Speichern, Laden, Löschen)
in einer SQLite-Datenbank.
"""

import json
import sqlite3
from typing import List, Optional
from .models import Project

DB_PATH = "projects.db"


def _init_db():
    """Erstellt die Datenbank und Tabelle, falls sie nicht existiert oder alte Struktur hat."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            thicknesses TEXT,
            ks TEXT,
            isolierungen TEXT,
            T_left REAL,
            T_inf REAL,
            h REAL,
            result TEXT
        )
    """)
    conn.commit()

    # --- Prüfen, ob Spalte 'isolierungen' existiert; falls nicht, hinzufügen ---
    c.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in c.fetchall()]
    if "isolierungen" not in columns:
        c.execute("ALTER TABLE projects ADD COLUMN isolierungen TEXT DEFAULT '[]'")
        conn.commit()

    conn.close()


_init_db()  # Initialisiere beim Import


def save_project(name: str, thicknesses, isolierungen, T_left, T_inf, h, result) -> bool:
    """Speichert ein Projekt inkl. Isolierungen in der SQLite-Datenbank."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO projects
            (name, thicknesses, ks, isolierungen, T_left, T_inf, h, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            json.dumps(thicknesses),
            json.dumps([None] * len(thicknesses)),  # Placeholder für alte ks
            json.dumps(isolierungen),
            T_left,
            T_inf,
            h,
            json.dumps(result)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Fehler beim Speichern: {e}")
        return False


def load_project(name: str) -> Optional[Project]:
    """Lädt ein Projekt anhand seines Namens."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()

        if row:
            # Prüfen, ob 'isolierungen' enthalten ist (alte Projekte haben evtl. None)
            isolierungen = []
            if len(row) >= 8 and row[3]:
                try:
                    isolierungen = json.loads(row[3])
                except json.JSONDecodeError:
                    isolierungen = []

            # Fallback für alte Struktur (ohne isolierungen-Spalte)
            if not isolierungen:
                isolierungen = [f"Schicht {i+1}" for i in range(len(json.loads(row[1]) or []))]

            return Project(
                name=row[0],
                thicknesses=json.loads(row[1]),
                ks=json.loads(row[2]),
                isolierungen=isolierungen,
                T_left=row[4],
                T_inf=row[5],
                h=row[6],
                result=json.loads(row[7]) if row[7] else None
            )
        return None
    except Exception as e:
        print(f"[DB] Fehler beim Laden: {e}")
        return None


def delete_project(name: str) -> bool:
    """Löscht ein Projekt aus der Datenbank."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM projects WHERE name = ?", (name,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Fehler beim Löschen: {e}")
        return False


def get_all_project_names() -> List[str]:
    """Gibt alle gespeicherten Projektnamen zurück."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM projects ORDER BY name COLLATE NOCASE ASC")
        names = [row[0] for row in c.fetchall()]
        conn.close()
        return names
    except Exception as e:
        print(f"[DB] Fehler beim Abrufen: {e}")
        return []