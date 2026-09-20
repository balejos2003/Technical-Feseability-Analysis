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

    lines.append("## Estimates")
    if assessment.estimates:
        for estimate in assessment.estimates:
            lines.append(f"- {estimate.get('label', 'Estimate')}: {estimate.get('value', '')}")
            lines.append(f"  Basis: {estimate.get('basis', 'No basis provided.')}")
            uncertainty = estimate.get("uncertainty")
            if uncertainty:
                lines.append(f"  Uncertainty: {uncertainty}")
    else:
        lines.append("No estimates were supplied.")

    lines.append("## Suggestions")
    if assessment.suggestions:
        for suggestion in assessment.suggestions:
            lines.append(f"- {suggestion}")
    else:
        lines.append("No suggestions were supplied.")

    lines.extend(["## Risks and Limitations"])
    if assessment.limitations:
        for limitation in assessment.limitations:
            lines.append(f"- {limitation}")
    else:
        lines.append("No limitations were identified.")

    lines.append("## Assumptions")
    if assessment.assumptions:
        for assumption in assessment.assumptions:
            lines.append(f"- {assumption}")
    else:
        lines.append("No explicit assumptions were recorded.")

    lines.append("## Unresolved Questions")
    if assessment.unresolved_questions:
        for question in assessment.unresolved_questions:
            lines.append(f"- {question}")
    else:
        lines.append("No unresolved questions were recorded.")

    lines.extend([
        "## Developer Review",
        "This result is advisory and no codebase change was applied by the analysis.",
    ])

    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
