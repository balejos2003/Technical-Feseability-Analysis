"""SQLite storage layer for analysis requests and completed assessments."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import application_paths


def ensure_database(database_path: str | Path) -> Path:
    """Ensure the parent directories and SQLite database file exist."""

    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def get_connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection configured for application history storage."""

    resolved_path = Path(database_path).expanduser().resolve() if database_path else application_paths().database_path
    ensure_database(resolved_path)
    conn = sqlite3.connect(resolved_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_schema(database_path: str | Path | None = None) -> Path:
    """Create the schema used for persisted analysis requests and assessments."""

    path = ensure_database(database_path or application_paths().database_path)
    with get_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS request (
                request_id TEXT PRIMARY KEY,
                principal_id TEXT NOT NULL,
                codebase_root TEXT NOT NULL,
                change_description TEXT NOT NULL,
                scope_rules TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assessment (
                assessment_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                conclusion TEXT NOT NULL,
                evaluated_scope TEXT NOT NULL,
                findings TEXT NOT NULL,
                limitations TEXT NOT NULL,
                report_markdown TEXT NOT NULL,
                analyzer_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                FOREIGN KEY (request_id) REFERENCES request(request_id)
            );

            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                path TEXT,
                start_line INTEGER,
                end_line INTEGER,
                excerpt TEXT,
                file_hash TEXT,
                description TEXT NOT NULL,
                FOREIGN KEY (assessment_id) REFERENCES assessment(assessment_id)
            );

            CREATE TABLE IF NOT EXISTS finding (
                finding_id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT,
                statement TEXT NOT NULL,
                basis TEXT NOT NULL,
                uncertainty TEXT,
                FOREIGN KEY (assessment_id) REFERENCES assessment(assessment_id)
            );

            CREATE TABLE IF NOT EXISTS finding_evidence (
                finding_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                PRIMARY KEY (finding_id, evidence_id),
                FOREIGN KEY (finding_id) REFERENCES finding(finding_id),
                FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
            );

            CREATE INDEX IF NOT EXISTS idx_request_principal ON request(principal_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_assessment_principal ON assessment(principal_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_assessment_conclusion ON assessment(conclusion);
            CREATE INDEX IF NOT EXISTS idx_assessment_request ON assessment(request_id);
            """
        )
    return path


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


__all__ = [
    "ensure_database",
    "get_connection",
    "initialize_schema",
]
