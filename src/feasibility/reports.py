"""Markdown report rendering for developer-facing feasibility assessments."""

from __future__ import annotations

from .models import FeasibilityAssessment, FeasibilityConclusion, Finding


def _conclusion_label(value: FeasibilityConclusion) -> str:
    mapping = {
        FeasibilityConclusion.FEASIBLE: "Feasible",
        FeasibilityConclusion.INFEASIBLE: "Infeasible",
        FeasibilityConclusion.CONDITIONALLY_FEASIBLE: "Conditionally feasible",
    }
    return mapping.get(value, str(value))


def _render_evidence_lines(assessment: FeasibilityAssessment, finding: Finding) -> list[str]:
    evidence_by_id = {item.evidence_id: item for item in assessment.evidence_items}
    lines: list[str] = []

    for evidence_id in finding.evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            lines.append(f"- Evidence: {evidence_id}")
            lines.append("  Relevance: Evidence reference is present but no source-backed payload was attached.")
            continue

        if evidence.path and evidence.start_line is not None and evidence.end_line is not None:
            path_text = f"{evidence.path} lines {evidence.start_line}-{evidence.end_line}"
            lines.append(f"- Evidence: {path_text} (sha256:{evidence.file_hash})")
            if evidence.excerpt:
                lines.append(f"  {evidence.excerpt}")
        else:
            lines.append(f"- Evidence: {evidence.kind.value} (no source span available)")
        lines.append(f"  Relevance: {evidence.description}")

    return lines


def render_report(assessment: FeasibilityAssessment) -> str:
    """Render a traceable Markdown report for a completed assessment."""

    lines = [
        "# Technical Feasibility Assessment",
        "## Request",
        f"- Assessment ID: {assessment.assessment_id}",
        f"- Request ID: {assessment.request_id}",
        f"- Principal: {assessment.principal_id}",
        "## Conclusion",
        f"{_conclusion_label(assessment.conclusion)}",
        "## Evaluated Scope",
    ]

    for item in assessment.evaluated_scope:
        lines.append(f"- {item}")

    lines.extend(["## Findings"])
    if not assessment.findings:
        lines.append("No material findings were recorded.")
    else:
        for finding in assessment.findings:
            lines.append(f"### Finding {finding.finding_id}: {finding.category.value}")
            lines.append(f"**Statement:** {finding.statement}")
            lines.append(f"**Basis:** {finding.basis}")
            if finding.uncertainty:
                lines.append(f"**Uncertainty:** {finding.uncertainty}")
            if finding.severity:
                lines.append(f"**Severity:** {finding.severity.value}")
            lines.append("#### Evidence")
            lines.extend(_render_evidence_lines(assessment, finding) or ["- Evidence: not available"])

    lines.extend([
        "## Estimates",
        "No estimates were supplied.",
        "## Suggestions",
        "No suggestions were supplied.",
        "## Risks and Limitations",
    ])
    if assessment.limitations:
        for limitation in assessment.limitations:
            lines.append(f"- {limitation}")
    else:
        lines.append("No limitations were identified.")

    lines.extend([
        "## Assumptions",
        "No explicit assumptions were recorded.",
        "## Unresolved Questions",
        "No unresolved questions were recorded.",
        "## Developer Review",
        "This result is advisory and no codebase change was applied by the analysis.",
    ])

    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
