import hashlib

import pytest

from feasibility.history import get_history_detail, list_history, search_history
from feasibility.models import EvidenceItem, EvidenceKind, FeasibilityAssessment, Finding, FindingCategory
from feasibility.reports import render_report
from feasibility.storage import save_analysis_record
from feasibility.models import AnalysisRequest


def _assessment(assessment_id: str, principal_id: str, report: str) -> tuple[AnalysisRequest, FeasibilityAssessment]:
    source = "def connect():\n    return Client()\n"
    evidence = EvidenceItem(
        evidence_id=f"ev-{assessment_id}",
        kind=EvidenceKind.CODE,
        description="The adapter entry point is visible in the source.",
        path="src/service.py",
        start_line=1,
        end_line=2,
        excerpt="def connect():\n    return Client()",
        file_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )
    finding = Finding(
        finding_id=f"finding-{assessment_id}",
        category=FindingCategory.INTERPRETATION,
        statement="The service exposes an adapter entry point.",
        basis="The cited source contains the connection function.",
        evidence_ids=[evidence.evidence_id],
    )
    request = AnalysisRequest(
        request_id=f"request-{assessment_id}",
        principal_id=principal_id,
        codebase_root="/tmp/repository",
        change_description="Add an adapter to the service",
    )
    assessment = FeasibilityAssessment(
        assessment_id=assessment_id,
        request_id=request.request_id,
        principal_id=principal_id,
        conclusion="conditionally_feasible",
        evaluated_scope=["src/service.py"],
        findings=[finding],
        limitations=["Runtime behavior was not tested."],
        report_markdown=report,
        analyzer_version="test",
        evidence_items=[evidence],
    )
    return request, assessment


def test_report_and_history_contract_preserve_hash_snapshot_and_principal_isolation(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    request, assessment = _assessment("assessment-contract", "alice", "original report")
    report = render_report(assessment)
    object.__setattr__(assessment, "report_markdown", report)
    save_analysis_record(request, assessment, database_path=db_path)

    detail = get_history_detail("assessment-contract", "alice", database_path=db_path)
    assert detail is not None
    assert "sha256:" + assessment.evidence_items[0].file_hash in detail.markdown_report
    assert detail.markdown_report == report
    assert get_history_detail("assessment-contract", "bob", database_path=db_path) is None
    assert list_history("bob", database_path=db_path) == []
    assert search_history("bob", "adapter", database_path=db_path) == []
    assert get_history_detail("missing-assessment", "alice", database_path=db_path) is None


def test_completed_assessment_snapshot_cannot_be_overwritten(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    request, assessment = _assessment("assessment-immutable", "alice", "original report")
    save_analysis_record(request, assessment, database_path=db_path)

    replacement_request, replacement = _assessment("assessment-immutable", "alice", "replacement report")
    replacement_request = AnalysisRequest(
        request_id=replacement_request.request_id,
        principal_id="alice",
        codebase_root="/tmp/repository",
        change_description="A different change",
    )

    with pytest.raises(ValueError, match="immutable"):
        save_analysis_record(replacement_request, replacement, database_path=db_path)

    detail = get_history_detail("assessment-immutable", "alice", database_path=db_path)
    assert detail is not None
    assert detail.markdown_report == "original report"