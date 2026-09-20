import sqlite3
import json
from pathlib import Path

from feasibility.models import (
    AnalysisRequest,
    AssessmentStatus,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
    Severity,
)
from feasibility.storage import ensure_database, get_connection, initialize_schema, save_analysis_record


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


def test_save_analysis_record_persists_request_assessment_and_evidence(tmp_path):
    db_path = tmp_path / "history.sqlite3"

    request = AnalysisRequest(
        request_id="req-100",
        principal_id="alice",
        codebase_root=str(tmp_path),
        change_description="Add validation around the API boundary.",
    )

    evidence = EvidenceItem(
        evidence_id="ev-100",
        kind=EvidenceKind.CODE,
        description="The API boundary is the integration point.",
        path="src/service.py",
        start_line=10,
        end_line=12,
        excerpt="def connect():\n    return Client()",
        file_hash="abc123",
    )

    finding = Finding(
        finding_id="f-100",
        category=FindingCategory.INTERPRETATION,
        statement="This is a clean integration seam.",
        basis="The service exposes a narrow boundary.",
        uncertainty="Low uncertainty.",
        severity=Severity.MEDIUM,
        evidence_ids=[evidence.evidence_id],
    )

    assessment = FeasibilityAssessment(
        assessment_id="assess-100",
        request_id=request.request_id,
        principal_id=request.principal_id,
        conclusion=FeasibilityConclusion.CONDITIONALLY_FEASIBLE,
        evaluated_scope=["src/service.py"],
        findings=[finding],
        limitations=["Runtime validation is still pending."],
        report_markdown="# Technical Feasibility Assessment\n\nThe seam is narrow.",
        analyzer_version="1.0.0",
        evidence_items=[evidence],
        assumptions=["The API contract is stable."],
        estimates=[{"label": "Implementation effort", "value": "2-4 days", "basis": "Single seam", "uncertainty": "Medium."}],
        suggestions=["Add a thin adapter and validate the contract."],
        unresolved_questions=["What is the production contract version?"],
        status=AssessmentStatus.COMPLETED,
    )

    save_analysis_record(request, assessment, database_path=db_path)

    with sqlite3.connect(db_path) as conn:
        request_row = conn.execute(
            "SELECT request_id, principal_id, change_description FROM request WHERE request_id = ?",
            (request.request_id,),
        ).fetchone()
        assessment_row = conn.execute(
            "SELECT conclusion, findings, limitations FROM assessment WHERE assessment_id = ?",
            (assessment.assessment_id,),
        ).fetchone()
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE assessment_id = ?",
            (assessment.assessment_id,),
        ).fetchone()[0]

    assert request_row is not None
    assert request_row[1] == "alice"
    assert assessment_row is not None
    assert json.loads(assessment_row[1])[0]["statement"] == "This is a clean integration seam."
    assert evidence_count == 1
