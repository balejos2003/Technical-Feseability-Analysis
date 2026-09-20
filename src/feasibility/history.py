"""Principal-scoped history queries for completed assessments."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .models import (
    AssessmentStatus,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    HistoryDetail,
    HistoryListEntry,
)
from .storage import get_connection


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        raise ValueError("Assessment timestamp is required")
    return datetime.fromisoformat(value)


def _parse_findings(value: str | list[dict[str, Any]] | None) -> list[Finding]:
    payload = value if isinstance(value, list) else json.loads(value or "[]")
    findings: list[Finding] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        findings.append(
            Finding(
                finding_id=str(item.get("finding_id") or "finding"),
                category=item.get("category", "interpretation"),
                statement=str(item.get("statement") or ""),
                basis=str(item.get("basis") or ""),
                uncertainty=item.get("uncertainty"),
                severity=item.get("severity"),
                evidence_ids=list(item.get("evidence_ids") or []),
            )
        )
    return findings


def _row_to_history_entry(row: Any) -> HistoryListEntry:
    return HistoryListEntry(
        assessment_id=row["assessment_id"],
        principal_id=row["principal_id"],
        created_at=_parse_datetime(row["created_at"]),
        summary=(row["summary"] or "Completed assessment").strip(),
        conclusion=row["conclusion"],
    )


def list_history(
    principal_id: str,
    *,
    limit: int = 50,
    database_path: str | None = None,
) -> list[HistoryListEntry]:
    """List completed assessments owned by the current principal."""

    with get_connection(database_path) as conn:
        rows = conn.execute(
            """
            SELECT a.assessment_id, a.principal_id, a.created_at, a.conclusion,
                   COALESCE(SUBSTR(r.change_description, 1, 120), 'Completed assessment') AS summary
            FROM assessment AS a
            JOIN request AS r ON r.request_id = a.request_id
            WHERE a.principal_id = ? AND a.status = 'completed'
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (principal_id, limit),
        ).fetchall()

    return [_row_to_history_entry(row) for row in rows]


def search_history(
    principal_id: str,
    query: str,
    *,
    limit: int = 50,
    database_path: str | None = None,
) -> list[HistoryListEntry]:
    """Search completed assessments for the current principal."""

    normalized_query = (query or "").strip()
    if not normalized_query:
        return list_history(principal_id, limit=limit, database_path=database_path)

    search_term = f"%{normalized_query.lower()}%"
    with get_connection(database_path) as conn:
        rows = conn.execute(
            """
            SELECT a.assessment_id, a.principal_id, a.created_at, a.conclusion,
                   COALESCE(SUBSTR(r.change_description, 1, 120), 'Completed assessment') AS summary
            FROM assessment AS a
            JOIN request AS r ON r.request_id = a.request_id
            WHERE a.principal_id = ?
              AND a.status = 'completed'
              AND (
                    LOWER(r.change_description) LIKE ?
                 OR LOWER(a.conclusion) LIKE ?
                 OR LOWER(COALESCE(a.evaluated_scope, '')) LIKE ?
              )
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (principal_id, search_term, search_term, search_term, limit),
        ).fetchall()

    return [_row_to_history_entry(row) for row in rows]


def get_history_detail(
    assessment_id: str,
    principal_id: str,
    *,
    database_path: str | None = None,
) -> HistoryDetail | None:
    """Return a full immutable assessment for an authorized principal."""

    with get_connection(database_path) as conn:
        row = conn.execute(
            """
            SELECT a.*
            FROM assessment AS a
            WHERE a.assessment_id = ? AND a.principal_id = ? AND a.status = 'completed'
            LIMIT 1
            """,
            (assessment_id, principal_id),
        ).fetchone()

        if row is None:
            return None

        refined_assessment = FeasibilityAssessment(
            assessment_id=row["assessment_id"],
            request_id=row["request_id"],
            principal_id=row["principal_id"],
            conclusion=FeasibilityConclusion(row["conclusion"]),
            evaluated_scope=json.loads(row["evaluated_scope"] or "[]"),
            findings=_parse_findings(row["findings"]),
            limitations=json.loads(row["limitations"] or "[]"),
            report_markdown=row["report_markdown"],
            analyzer_version=row["analyzer_version"],
            created_at=_parse_datetime(row["created_at"]),
            status=AssessmentStatus.COMPLETED,
        )

        return HistoryDetail(
            assessment=refined_assessment,
            markdown_report=row["report_markdown"],
        )


__all__ = [
    "get_history_detail",
    "list_history",
    "search_history",
]
