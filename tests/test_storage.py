import sqlite3
from pathlib import Path

from feasibility.storage import ensure_database, get_connection, initialize_schema


def test_initialize_schema_creates_tables(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

    names = {row[0] for row in tables}
    assert {"request", "assessment", "evidence", "finding", "finding_evidence"}.issubset(names)


def test_get_connection_uses_database_path(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    conn = get_connection(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] in {"delete", "wal", "memory"}
    finally:
        conn.close()


def test_ensure_database_creates_directory_and_db(tmp_path):
    db_path = tmp_path / "subdir" / "history.sqlite3"
    ensure_database(db_path)
    assert db_path.exists()
