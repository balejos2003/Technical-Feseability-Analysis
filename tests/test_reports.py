from feasibility.models import (
    AssessmentStatus,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
    Severity,
)
from feasibility.reports import render_report


def test_render_report_contains_contract_headings_and_evidence():
    evidence = EvidenceItem(
        evidence_id="ev-1",
        kind=EvidenceKind.CODE,
        description="The adapter entry point is clearly defined.",
        path="src/service.py",
        start_line=10,
        end_line=12,
        excerpt="def connect():\n    return Client()",
        file_hash="abc123",
    )

    finding = Finding(
        finding_id="f-1",
        category=FindingCategory.INTERPRETATION,
        statement="The change is feasible with a small adapter layer.",
        basis="The service already exposes a clear integration seam.",
        uncertainty="Low uncertainty.",
        severity=Severity.MEDIUM,
        evidence_ids=[evidence.evidence_id],
    )

    assessment = FeasibilityAssessment(
        assessment_id="assess-1",
        request_id="req-1",
        principal_id="alice",
        conclusion=FeasibilityConclusion.CONDITIONALLY_FEASIBLE,
        evaluated_scope=["src/service.py"],
        findings=[finding],
        limitations=["Runtime verification is still pending."],
        report_markdown="placeholder",
        analyzer_version="1.0.0",
        evidence_items=[evidence],
        status=AssessmentStatus.COMPLETED,
    )

    rendered = render_report(assessment)

    assert "# Technical Feasibility Assessment" in rendered
    assert "## Request" in rendered
    assert "## Conclusion" in rendered
    assert "## Findings" in rendered
    assert "### Finding f-1" in rendered
    assert "src/service.py lines 10-12" in rendered
    assert "sha256:abc123" in rendered
    assert "## Developer Review" in rendered
    assert "advisory" in rendered.lower()
    assert "no codebase change was applied" in rendered.lower()
