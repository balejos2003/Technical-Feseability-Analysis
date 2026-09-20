"""SQLite storage layer for analysis requests and completed assessments."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import AnalysisRequest, FeasibilityAssessment
from .config import application_paths


def ensure_database(database_path: str | Path) -> Path:
    """Ensure the parent directories and SQLite database file exist."""

    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _initialize_schema(conn: sqlite3.Connection) -> None:
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


def get_connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection configured for application history storage."""

    resolved_path = Path(database_path).expanduser().resolve() if database_path else application_paths().database_path
    ensure_database(resolved_path)
    conn = sqlite3.connect(resolved_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    _initialize_schema(conn)
    return conn


def initialize_schema(database_path: str | Path | None = None) -> Path:
    """Create the schema used for persisted analysis requests and assessments."""

    path = ensure_database(database_path or application_paths().database_path)
    with sqlite3.connect(path) as conn:
        _initialize_schema(conn)
    return path


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def save_request_record(request: AnalysisRequest, *, database_path: str | Path | None = None) -> str:
    """Persist one request as an immutable record for later historical lookup."""

    path = ensure_database(database_path or application_paths().database_path)
    initialize_schema(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO request (
                request_id,
                principal_id,
                codebase_root,
                change_description,
                scope_rules,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                principal_id = excluded.principal_id,
                codebase_root = excluded.codebase_root,
                change_description = excluded.change_description,
                scope_rules = excluded.scope_rules,
                created_at = excluded.created_at
            """,
            (
                request.request_id,
                request.principal_id,
                request.codebase_root,
                request.change_description,
                _dump_json(asdict(request.scope_rules)),
                request.created_at.isoformat(),
            ),
        )
    return request.request_id


def save_assessment_record(assessment: FeasibilityAssessment, *, database_path: str | Path | None = None) -> str:
    """Persist one completed assessment with its evidence and material findings."""

    path = ensure_database(database_path or application_paths().database_path)
    initialize_schema(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO assessment (
                assessment_id,
                request_id,
                principal_id,
                conclusion,
                evaluated_scope,
                findings,
                limitations,
                report_markdown,
                analyzer_version,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assessment_id) DO UPDATE SET
                request_id = excluded.request_id,
                principal_id = excluded.principal_id,
                conclusion = excluded.conclusion,
                evaluated_scope = excluded.evaluated_scope,
                findings = excluded.findings,
                limitations = excluded.limitations,
                report_markdown = excluded.report_markdown,
                analyzer_version = excluded.analyzer_version,
                created_at = excluded.created_at,
                status = excluded.status
            """,
            (
                assessment.assessment_id,
                assessment.request_id,
                assessment.principal_id,
                assessment.conclusion.value,
                _dump_json(assessment.evaluated_scope),
                _dump_json([
                    {
                        "finding_id": finding.finding_id,
                        "category": finding.category.value,
                        "statement": finding.statement,
                        "basis": finding.basis,
                        "uncertainty": finding.uncertainty,
                        "severity": finding.severity.value if finding.severity is not None else None,
                        "evidence_ids": finding.evidence_ids,
                    }
                    for finding in assessment.findings
                ]),
                _dump_json(assessment.limitations),
                assessment.report_markdown,
                assessment.analyzer_version,
                assessment.created_at.isoformat(),
                assessment.status.value,
            ),
        )

        for evidence in assessment.evidence_items:
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id,
                    assessment_id,
                    kind,
                    path,
                    start_line,
                    end_line,
                    excerpt,
                    file_hash,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    assessment_id = excluded.assessment_id,
                    kind = excluded.kind,
                    path = excluded.path,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    excerpt = excluded.excerpt,
                    file_hash = excluded.file_hash,
                    description = excluded.description
                """,
                (
                    evidence.evidence_id,
                    assessment.assessment_id,
                    evidence.kind.value,
                    evidence.path,
                    evidence.start_line,
                    evidence.end_line,
                    evidence.excerpt,
                    evidence.file_hash,
                    evidence.description,
                ),
            )

        for finding in assessment.findings:
            conn.execute(
                """
                INSERT INTO finding (
                    finding_id,
                    assessment_id,
                    category,
                    severity,
                    statement,
                    basis,
                    uncertainty
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(finding_id) DO UPDATE SET
                    assessment_id = excluded.assessment_id,
                    category = excluded.category,
                    severity = excluded.severity,
                    statement = excluded.statement,
                    basis = excluded.basis,
                    uncertainty = excluded.uncertainty
                """,
                (
                    finding.finding_id,
                    assessment.assessment_id,
                    finding.category.value,
                    finding.severity.value if finding.severity is not None else None,
                    finding.statement,
                    finding.basis,
                    finding.uncertainty,
                ),
            )
            for evidence_id in finding.evidence_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO finding_evidence (finding_id, evidence_id)
                    VALUES (?, ?)
                    """,
                    (finding.finding_id, evidence_id),
                )

    return assessment.assessment_id


def save_analysis_record(
    request: AnalysisRequest,
    assessment: FeasibilityAssessment,
    *,
    database_path: str | Path | None = None,
) -> str:
    """Persist both a request and its completed assessment in one transaction."""

    path = ensure_database(database_path or application_paths().database_path)
    initialize_schema(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO request (
                request_id,
                principal_id,
                codebase_root,
                change_description,
                scope_rules,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                principal_id = excluded.principal_id,
                codebase_root = excluded.codebase_root,
                change_description = excluded.change_description,
                scope_rules = excluded.scope_rules,
                created_at = excluded.created_at
            """,
            (
                request.request_id,
                request.principal_id,
                request.codebase_root,
                request.change_description,
                _dump_json(asdict(request.scope_rules)),
                request.created_at.isoformat(),
            ),
        )
        conn.execute(
            """
            INSERT INTO assessment (
                assessment_id,
                request_id,
                principal_id,
                conclusion,
                evaluated_scope,
                findings,
                limitations,
                report_markdown,
                analyzer_version,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assessment_id) DO UPDATE SET
                request_id = excluded.request_id,
                principal_id = excluded.principal_id,
                conclusion = excluded.conclusion,
                evaluated_scope = excluded.evaluated_scope,
                findings = excluded.findings,
                limitations = excluded.limitations,
                report_markdown = excluded.report_markdown,
                analyzer_version = excluded.analyzer_version,
                created_at = excluded.created_at,
                status = excluded.status
            """,
            (
                assessment.assessment_id,
                assessment.request_id,
                assessment.principal_id,
                assessment.conclusion.value,
                _dump_json(assessment.evaluated_scope),
                _dump_json([
                    {
                        "finding_id": finding.finding_id,
                        "category": finding.category.value,
                        "statement": finding.statement,
                        "basis": finding.basis,
                        "uncertainty": finding.uncertainty,
                        "severity": finding.severity.value if finding.severity is not None else None,
                        "evidence_ids": finding.evidence_ids,
                    }
                    for finding in assessment.findings
                ]),
                _dump_json(assessment.limitations),
                assessment.report_markdown,
                assessment.analyzer_version,
                assessment.created_at.isoformat(),
                assessment.status.value,
            ),
        )

        for evidence in assessment.evidence_items:
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id,
                    assessment_id,
                    kind,
                    path,
                    start_line,
                    end_line,
                    excerpt,
                    file_hash,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    assessment_id = excluded.assessment_id,
                    kind = excluded.kind,
                    path = excluded.path,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    excerpt = excluded.excerpt,
                    file_hash = excluded.file_hash,
                    description = excluded.description
                """,
                (
                    evidence.evidence_id,
                    assessment.assessment_id,
                    evidence.kind.value,
                    evidence.path,
                    evidence.start_line,
                    evidence.end_line,
                    evidence.excerpt,
                    evidence.file_hash,
                    evidence.description,
                ),
            )

        for finding in assessment.findings:
            conn.execute(
                """
                INSERT INTO finding (
                    finding_id,
                    assessment_id,
                    category,
                    severity,
                    statement,
                    basis,
                    uncertainty
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(finding_id) DO UPDATE SET
                    assessment_id = excluded.assessment_id,
                    category = excluded.category,
                    severity = excluded.severity,
                    statement = excluded.statement,
                    basis = excluded.basis,
                    uncertainty = excluded.uncertainty
                """,
                (
                    finding.finding_id,
                    assessment.assessment_id,
                    finding.category.value,
                    finding.severity.value if finding.severity is not None else None,
                    finding.statement,
                    finding.basis,
                    finding.uncertainty,
                ),
            )
            for evidence_id in finding.evidence_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO finding_evidence (finding_id, evidence_id)
                    VALUES (?, ?)
                    """,
                    (finding.finding_id, evidence_id),
                )

    return assessment.assessment_id


__all__ = [
    "ensure_database",
    "get_connection",
    "initialize_schema",
    "save_analysis_record",
    "save_assessment_record",
    "save_request_record",
]
