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
    assert "Evidence type: code" in rendered
    assert "## Developer Review" in rendered
    assert "advisory" in rendered.lower()
    assert "no codebase change was applied" in rendered.lower()


def test_render_report_labels_non_code_evidence_and_relevance():
    evidence = EvidenceItem(
        evidence_id="ev-assumption",
        kind=EvidenceKind.ASSUMPTION,
        description="The public API contract remains stable.",
    )
    finding = Finding(
        finding_id="f-assumption",
        category=FindingCategory.RISK,
        statement="The assessment depends on the API contract remaining stable.",
        basis="The requested change references that contract.",
        evidence_ids=[evidence.evidence_id],
    )
    assessment = FeasibilityAssessment(
        assessment_id="assess-assumption",
        request_id="req-assumption",
        principal_id="alice",
        conclusion=FeasibilityConclusion.CONDITIONALLY_FEASIBLE,
        evaluated_scope=["src/service.py"],
        findings=[finding],
        limitations=["The external contract was not inspected."],
        report_markdown="placeholder",
        analyzer_version="1.0.0",
        evidence_items=[evidence],
        status=AssessmentStatus.COMPLETED,
    )

    rendered = render_report(assessment)

    assert "Evidence type: assumption" in rendered
    assert "no source span available" in rendered
    assert "Relevance: The public API contract remains stable." in rendered


def test_render_report_separates_risks_from_limitations():
    evidence = EvidenceItem(
        evidence_id="ev-risk",
        kind=EvidenceKind.CODE,
        description="The current evaluator processes operations sequentially.",
        path="src/calculator.py",
        start_line=4,
        end_line=6,
        excerpt="return operation(left, right)",
        file_hash="risk-hash",
    )
    risk = Finding(
        finding_id="f-risk",
        category=FindingCategory.RISK,
        statement="Parentheses may conflict with sequential evaluation.",
        basis="The current evaluator does not group expressions.",
        severity=Severity.HIGH,
        evidence_ids=[evidence.evidence_id],
    )
    assessment = FeasibilityAssessment(
        assessment_id="assess-risk",
        request_id="req-risk",
        principal_id="alice",
        conclusion=FeasibilityConclusion.CONDITIONALLY_FEASIBLE,
        evaluated_scope=["src/calculator.py"],
        findings=[risk],
        limitations=["Runtime behavior was not tested."],
        report_markdown="placeholder",
        analyzer_version="1.0.0",
        evidence_items=[evidence],
        status=AssessmentStatus.COMPLETED,
    )

    rendered = render_report(assessment)

    assert "## Risks and Limitations" in rendered
    assert "### Risks" in rendered
    assert "- f-risk: Parentheses may conflict with sequential evaluation. (high)" in rendered
    assert "### Limitations" in rendered
    assert "- Runtime behavior was not tested." in rendered
