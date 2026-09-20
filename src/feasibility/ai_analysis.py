"""AI analysis provider contracts and validation for feasibility assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Mapping
from typing import Any

from .context import SourceContext
from .errors import AIServiceUnavailableError
from .models import (
    AnalysisRequest,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
    Severity,
)


Provider = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class AnalysisEvidenceRef:
    """Evidence reference emitted by the analysis provider."""

    id: str
    kind: EvidenceKind | str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    excerpt: str | None = None
    hash: str | None = None
    description: str = ""

    def to_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=self.id,
            kind=self.kind,
            description=self.description or "Evidence from the analysis context.",
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            excerpt=self.excerpt,
            file_hash=self.hash,
        )


@dataclass(frozen=True)
class AnalysisEstimate:
    """A labeled estimate or forecast returned by the analysis provider."""

    label: str
    value: str
    basis: str
    uncertainty: str | None = None


@dataclass(frozen=True)
class AnalysisResponse:
    """Normalized AI output for a completed feasibility evaluation."""

    conclusion: FeasibilityConclusion
    findings: list[Finding]
    limits: list[str]
    assumptions: list[str]
    estimates: list[dict[str, str]]
    suggestions: list[str]
    unresolved_questions: list[str] = field(default_factory=list)


def build_analysis_prompt(
    *,
    repository_root: str,
    change_description: str,
    scope_summary: str,
    context: str,
) -> str:
    """Build a bounded prompt aimed at reasoning over supplied source context."""

    return (
        "You are assessing the technical feasibility of a proposed change in a read-only codebase.\n"
        f"Repository root: {repository_root}\n"
        f"Requested change: {change_description}\n"
        f"Scope summary: {scope_summary}\n\n"
        "Analyze only the supplied source context and evidence. Do not modify the repository.\n"
        "Explain your reasoning in plain language, distinguish fact from interpretation, and cite evidence\n"
        "for every material finding.\n\n"
        "Required output contract:\n"
        "- conclusion: feasible | infeasible | conditionally_feasible\n"
        "- findings: list of material findings with category, statement, basis, uncertainty, severity, and evidence\n"
        "- limitations: list of missing, stale, or ambiguous evidence\n"
        "- assumptions: list of explicit assumptions used during assessment\n"
        "- estimates: list of labeled estimates with value, basis, and uncertainty\n"
        "- suggestions: list of actionable suggestions\n"
        "- unresolved_questions: list of open questions\n\n"
        "Provided context:\n"
        f"{context}\n"
    )


def invoke_analysis_provider(
    request: AnalysisRequest,
    source_context: SourceContext,
    *,
    provider: Provider,
) -> dict[str, Any]:
    """Build the bounded analysis prompt and invoke the injected AI provider.

    The provider receives only the rendered source snapshot and request metadata.
    Response normalization is intentionally deferred to ``normalize_analysis_response``.
    """

    scope_summary = (
        f"{len(source_context.items)} files included, "
        f"{len(source_context.issues)} discovery issues, "
        f"{source_context.total_chars}/{source_context.max_context_chars} characters"
    )
    prompt = build_analysis_prompt(
        repository_root=request.codebase_root,
        change_description=request.change_description,
        scope_summary=scope_summary,
        context=source_context.as_text(),
    )

    try:
        response = provider(prompt)
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise AIServiceUnavailableError(
            "The AI analysis provider is unavailable",
            provider=type(provider).__name__,
        ) from exc

    if not isinstance(response, Mapping):
        raise TypeError("AI provider must return a mapping response")
    return dict(response)


def _coerce_conclusion(value: Any) -> FeasibilityConclusion:
    try:
        return FeasibilityConclusion(value)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported conclusion: {value}") from exc


def _to_finding(item: dict[str, Any]) -> Finding:
    evidence_values = item.get("evidence") or []
    if not isinstance(evidence_values, list) or not evidence_values:
        raise ValueError(f"Finding {item.get('id', '<unknown>')} requires at least one evidence item")

    evidence_ids = []
    for evidence in evidence_values:
        if not isinstance(evidence, dict):
            continue
        evidence_id = evidence.get("id")
        if evidence_id:
            evidence_ids.append(str(evidence_id))

    if not evidence_ids:
        raise ValueError(f"Finding {item.get('id', '<unknown>')} requires evidence ids")

    return Finding(
        finding_id=str(item.get("id") or "finding"),
        category=item.get("category", FindingCategory.INTERPRETATION.value),
        statement=str(item.get("statement") or ""),
        basis=str(item.get("basis") or ""),
        uncertainty=item.get("uncertainty"),
        severity=item.get("severity"),
        evidence_ids=evidence_ids,
    )


def normalize_analysis_response(payload: dict[str, Any]) -> AnalysisResponse:
    """Normalize and validate a provider response structure."""

    if not isinstance(payload, dict):
        raise ValueError("AI response must be a dictionary")

    conclusion = _coerce_conclusion(payload.get("conclusion"))
    findings = payload.get("findings") or []
    if not isinstance(findings, list) or not findings:
        raise ValueError("AI response requires at least one finding")

    normalized_findings = [_to_finding(item) for item in findings]

    limitations = payload.get("limitations") or []
    if not isinstance(limitations, list):
        raise ValueError("limitations must be a list")

    assumptions = payload.get("assumptions") or []
    if not isinstance(assumptions, list):
        raise ValueError("assumptions must be a list")

    estimates = payload.get("estimates") or []
    if not isinstance(estimates, list):
        raise ValueError("estimates must be a list")
    for estimate in estimates:
        if not isinstance(estimate, dict):
            raise ValueError("Each estimate must be a mapping")
        if not estimate.get("label") or not estimate.get("value") or not estimate.get("basis"):
            raise ValueError("Each estimate requires label, value, and basis")

    suggestions = payload.get("suggestions") or []
    if not isinstance(suggestions, list):
        raise ValueError("suggestions must be a list")

    unresolved_questions = payload.get("unresolved_questions") or []
    if not isinstance(unresolved_questions, list):
        raise ValueError("unresolved_questions must be a list")

    return AnalysisResponse(
        conclusion=conclusion,
        findings=normalized_findings,
        limits=list(limitations),
        assumptions=list(assumptions),
        estimates=[dict(estimate) for estimate in estimates],
        suggestions=list(suggestions),
        unresolved_questions=list(unresolved_questions),
    )


__all__ = [
    "AnalysisEstimate",
    "AnalysisEvidenceRef",
    "AnalysisResponse",
    "build_analysis_prompt",
    "invoke_analysis_provider",
    "normalize_analysis_response",
]
