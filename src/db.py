from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "ugel.sqlite3"


@contextmanager
def connect(db_path: Path = DB_PATH):
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_time TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'automatico'
                    CHECK (tipo IN ('automatico', 'manual')),
                filename TEXT,
                source_hash TEXT,
                row_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS docentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                dni TEXT NOT NULL,
                nombre TEXT,
                primer_apellido TEXT,
                segundo_apellido TEXT,
                email TEXT,
                celular TEXT,
                nivel_educativo TEXT,
                cargo TEXT,
                especialidad TEXT,
                colegio_nombre TEXT,
                colegio_codigo TEXT NOT NULL,
                estado TEXT,
                situacion_laboral TEXT,
                row_hash TEXT NOT NULL,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS school_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                colegio_codigo TEXT NOT NULL,
                colegio_nombre TEXT,
                added_count INTEGER NOT NULL DEFAULT 0,
                removed_count INTEGER NOT NULL DEFAULT 0,
                modified_count INTEGER NOT NULL DEFAULT 0,
                has_changes INTEGER NOT NULL DEFAULT 0,
                change_summary_json TEXT,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_docentes_version
                ON docentes(version_id);
            CREATE INDEX IF NOT EXISTS idx_docentes_version_colegio
                ON docentes(version_id, colegio_codigo);
            CREATE INDEX IF NOT EXISTS idx_docentes_version_dni
                ON docentes(version_id, dni);
            CREATE INDEX IF NOT EXISTS idx_school_changes_version
                ON school_changes(version_id, has_changes);
            """
        )


def create_version(
    conn: sqlite3.Connection,
    *,
    date_time: str,
    tipo: str,
    filename: str,
    source_hash: str,
    row_count: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO versions (date_time, tipo, filename, source_hash, row_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (date_time, tipo, filename, source_hash, row_count),
    )
    return int(cursor.lastrowid)


def insert_docentes(conn: sqlite3.Connection, rows: Iterable[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO docentes (
            version_id, dni, nombre, primer_apellido, segundo_apellido, email,
            celular, nivel_educativo, cargo, especialidad, colegio_nombre,
            colegio_codigo, estado, situacion_laboral, row_hash
        )
        VALUES (
            :version_id, :dni, :nombre, :primer_apellido, :segundo_apellido,
            :email, :celular, :nivel_educativo, :cargo, :especialidad,
            :colegio_nombre, :colegio_codigo, :estado, :situacion_laboral,
            :row_hash
        )
        """,
        list(rows),
    )


def replace_school_changes(
    conn: sqlite3.Connection, version_id: int, changes: Iterable[dict]
) -> None:
    conn.execute("DELETE FROM school_changes WHERE version_id = ?", (version_id,))
    conn.executemany(
        """
        INSERT INTO school_changes (
            version_id, colegio_codigo, colegio_nombre, added_count,
            removed_count, modified_count, has_changes, change_summary_json
        )
        VALUES (
            :version_id, :colegio_codigo, :colegio_nombre, :added_count,
            :removed_count, :modified_count, :has_changes, :change_summary_json
        )
        """,
        [
            {
                **change,
                "version_id": version_id,
                "change_summary_json": json.dumps(
                    change.get("change_summary", {}), ensure_ascii=False
                ),
            }
            for change in changes
        ],
    )


def get_versions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM versions ORDER BY id DESC"
    ).fetchall()


def get_version(conn: sqlite3.Connection, version_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM versions WHERE id = ?", (version_id,)
    ).fetchone()


def get_previous_version_id(conn: sqlite3.Connection, version_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM versions WHERE id < ? ORDER BY id DESC LIMIT 1",
        (version_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def get_latest_version_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM versions ORDER BY id DESC LIMIT 1").fetchone()
    return int(row["id"]) if row else None


def get_docentes(
    conn: sqlite3.Connection, version_id: int, colegio_codigo: str | None = None
) -> list[sqlite3.Row]:
    if colegio_codigo:
        return conn.execute(
            """
            SELECT * FROM docentes
            WHERE version_id = ? AND colegio_codigo = ?
            ORDER BY primer_apellido, segundo_apellido, nombre, dni
            """,
            (version_id, colegio_codigo),
        ).fetchall()
    return conn.execute(
        """
        SELECT * FROM docentes
        WHERE version_id = ?
        ORDER BY colegio_nombre, primer_apellido, segundo_apellido, nombre, dni
        """,
        (version_id,),
    ).fetchall()


def get_changed_schools(
    conn: sqlite3.Connection, version_id: int, only_changed: bool = True
) -> list[sqlite3.Row]:
    clause = "AND has_changes = 1" if only_changed else ""
    return conn.execute(
        f"""
        SELECT * FROM school_changes
        WHERE version_id = ? {clause}
        ORDER BY colegio_nombre, colegio_codigo
        """,
        (version_id,),
    ).fetchall()


def count_docentes(conn: sqlite3.Connection, version_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM docentes WHERE version_id = ?", (version_id,)
    ).fetchone()
    return int(row["total"])
