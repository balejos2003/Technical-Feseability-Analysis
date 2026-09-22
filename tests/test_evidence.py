from pathlib import Path

import pytest

from feasibility.evidence import EvidenceCapture, capture_evidence, validate_assessment_traceability
from feasibility.models import (
    AssessmentStatus,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
)


def test_capture_evidence_uses_inclusive_ranges_and_hash(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    code_path = repo / "src" / "app.py"
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    evidence = capture_evidence(
        repository_root=repo,
        path="src/app.py",
        start_line=2,
        end_line=3,
    )

    assert evidence.path == "src/app.py"
    assert evidence.start_line == 2
    assert evidence.end_line == 3
    assert evidence.excerpt.strip().splitlines() == ["beta", "gamma"]
    assert evidence.file_hash


def test_evidence_capture_rejects_invalid_ranges(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    code_path = repo / "file.py"
    code_path.write_text("a\nb\n", encoding="utf-8")

    try:
        capture_evidence(repo, "file.py", start_line=3, end_line=2)
        assert False, "Expected ValueError for reversed range"
    except ValueError:
        pass


def test_evidence_capture_rejects_missing_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    try:
        capture_evidence(repo, "missing.py", start_line=1, end_line=1)
        assert False, "Expected FileNotFoundError for missing file"
    except FileNotFoundError:
        pass


def _assessment_with_finding(evidence_items, evidence_ids):
    finding = Finding(
        finding_id="finding-1",
        category=FindingCategory.INTERPRETATION,
        statement="The change has a defined integration point.",
        basis="The supplied evidence identifies the integration point.",
        evidence_ids=evidence_ids,
    )
    return FeasibilityAssessment(
        assessment_id="assessment-1",
        request_id="request-1",
        principal_id="alice",
        conclusion=FeasibilityConclusion.CONDITIONALLY_FEASIBLE,
        evaluated_scope=["src/service.py"],
        findings=[finding],
        limitations=["Runtime behavior was not tested."],
        report_markdown="placeholder",
        analyzer_version="1.0.0",
        evidence_items=evidence_items,
        status=AssessmentStatus.COMPLETED,
    )


def test_traceability_rejects_missing_evidence_reference():
    assessment = _assessment_with_finding([], ["missing-evidence"])

    with pytest.raises(ValueError, match="references missing evidence"):
        validate_assessment_traceability(assessment)


def test_traceability_accepts_non_code_qualification_evidence():
    evidence = EvidenceItem(
        evidence_id="assumption-1",
        kind=EvidenceKind.ASSUMPTION,
        description="The existing API contract remains stable.",
    )
    assessment = _assessment_with_finding([evidence], [evidence.evidence_id])

    validate_assessment_traceability(assessment)
