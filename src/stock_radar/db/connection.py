"""SQLite connection and schema initialization for Stock Radar."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enforced and Row access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Create a fresh Stock Radar database at db_path using schema.sql.

    db_path may be ':memory:' for an in-process database (used by tests).
    """
    conn = get_connection(db_path)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()
    return conn


def get_or_init_connection(db_path: str) -> sqlite3.Connection:
    """Open db_path, creating the schema first if it isn't there yet.

    For callers (the Phase 7 pipeline, in particular) that may point at a
    brand-new path with no prior data — e.g. a GitHub Actions runner's
    first-ever run, before any cache of the DB exists. Safe to call
    repeatedly: if the schema is already present, this is equivalent to
    get_connection() (schema.sql's CREATE TABLE statements have no
    IF NOT EXISTS, so re-running init_db() against an already-initialized
    DB would raise "table already exists").
    """
    conn = get_connection(db_path)
    has_schema = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'companies'"
        ).fetchone()
        is not None
    )
    if not has_schema:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
    return conn
